#!/usr/bin/env python3
"""
ucsm_vsan_v2.py
Create VSANs with FCoE VLAN as creation parameter (3-arg form):
  create vsan <name> <vsan-id> <fcoe-vlan-id>
Then bind to vHBA templates via set fc-if.
"""

import paramiko, time

HOST = '10.103.12.20'
USER = 'admin'
PASS = 'HybridAdm1n&&'

SLOW   = 2.0
FAST   = 0.8
COMMIT = 4.0

results = []

def drain(sh, rounds=4, pause=0.4):
    buf = b''
    for _ in range(rounds):
        time.sleep(pause)
        while sh.recv_ready():
            buf += sh.recv(65535)
    return buf.decode('utf-8', errors='replace')

def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)
    sh = c.invoke_shell(width=300, height=9000)
    time.sleep(2)
    while sh.recv_ready():
        sh.recv(65535)
    return c, sh

def sr(sh, cmd, delay=SLOW, label=None):
    sh.send(cmd + '\n')
    time.sleep(delay)
    resp = drain(sh).strip()
    bad = any(x in resp for x in
              ['Error','error','Invalid','invalid','Failed','failed'])
    tag = '[WARN]' if bad else '[OK]  '
    results.append({'cmd': cmd, 'resp': resp, 'ok': not bad})
    print(f"  {tag} {label or cmd!r}")
    if bad:
        for line in resp.splitlines():
            if any(x in line for x in ['Error','error','Invalid','invalid','Failed']):
                print(f"         >> {line.strip()}")
    return resp, not bad

def safe_commit(sh):
    _, ok = sr(sh, 'commit-buffer', COMMIT, 'commit-buffer')
    if not ok:
        sr(sh, 'discard-buffer', FAST, 'discard-buffer [recovery]')
    return ok

def discard(sh):
    sr(sh, 'discard-buffer', FAST, 'discard-buffer')

def hg_org(sh):
    sr(sh, 'top', FAST)
    sr(sh, 'scope org /', FAST)
    sr(sh, 'scope org HumbledGeeks', FAST)

def fc_fabric(sh, fab):
    sr(sh, 'top', FAST)
    sr(sh, 'scope fc-uplink', FAST)
    sr(sh, f'scope fabric {fab}', FAST)

def main():
    print(f"Connecting to UCSM at {HOST} ...")
    client, sh = connect()
    print("Connected.\n")

    try:
        # ── Probe create vsan syntax in fabric scope ──────────────────────────
        print("=== PROBE: create vsan syntax in fabric scope ===")
        fc_fabric(sh, 'a')
        sh.send('create vsan ?\n'); time.sleep(SLOW)
        probe_resp = drain(sh)
        print(probe_resp)
        discard(sh)

        # ── Delete existing incomplete VSANs ──────────────────────────────────
        print("=== Clean up incomplete VSANs ===")
        for fab, name in [('a','hg-vsan-a'), ('b','hg-vsan-b')]:
            fc_fabric(sh, fab)
            _, ok = sr(sh, f'delete vsan {name}', FAST)
            if ok:
                safe_commit(sh)
                print(f"  Cleaned up {name} on fabric {fab}")
            else:
                discard(sh)

        # ── Create VSANs with FCoE VLAN as creation parameter ─────────────────
        print("\n=== Create VSANs (3-param: name id fcoe-vlan) ===")
        vsans = [
            ('a', 'hg-vsan-a', 10, 1010),
            ('b', 'hg-vsan-b', 11, 1011),
        ]
        created = {}
        for fab, name, vid, fcoe in vsans:
            print(f"\n  -- Fabric {fab.upper()}: {name} ID={vid} FCoE-VLAN={fcoe} --")
            fc_fabric(sh, fab)
            # Try 3-parameter form first (name, vsan-id, fcoe-vlan)
            _, ok = sr(sh, f'create vsan {name} {vid} {fcoe}', SLOW)
            if not ok:
                discard(sh)
                # Try 2-parameter form (name, vsan-id) — FCoE auto-assigned
                fc_fabric(sh, fab)
                _, ok = sr(sh, f'create vsan {name} {vid}', SLOW)
                if not ok:
                    discard(sh)
                    print(f"  [SKIP] Cannot create {name}")
                    created[name] = False
                    continue
            if safe_commit(sh):
                created[name] = True
                print(f"  [SUCCESS] {name} created")
            else:
                created[name] = False

        # ── Verify VSANs visible after creation ───────────────────────────────
        print("\n=== VSAN state post-creation ===")
        for fab in ['a', 'b']:
            fc_fabric(sh, fab)
            sh.send('show vsan detail\n'); time.sleep(4)
            resp = drain(sh, rounds=6)
            print(f"\n  Fabric {fab.upper()}:\n{resp}")
            discard(sh)

        # Also check from top-level fc-uplink
        sr(sh, 'top', FAST)
        sr(sh, 'scope fc-uplink', FAST)
        sh.send('show vsan\n'); time.sleep(3)
        resp = drain(sh, rounds=4)
        print(f"\n  All VSANs (fc-uplink level):\n{resp}")
        discard(sh)

        # ── Bind VSANs to vHBA templates ──────────────────────────────────────
        print("\n=== Bind VSANs to vHBA templates (set fc-if) ===")
        for tmpl, vsan in [('hg-vmhba0','hg-vsan-a'), ('hg-vmhba1','hg-vsan-b')]:
            print(f"\n  -- {tmpl} → {vsan} --")
            hg_org(sh)
            sr(sh, f'scope vhba-templ {tmpl}', FAST)
            _, ok = sr(sh, f'set fc-if {vsan}', FAST)
            if ok:
                safe_commit(sh)
            else:
                discard(sh)
                print(f"  [GUI needed] Assign {vsan} to {tmpl} in UCSM GUI")

        # ── Final vHBA template verification ─────────────────────────────────
        print("\n=== Final vHBA Template State ===")
        hg_org(sh)
        sh.send('show vhba-templ detail\n'); time.sleep(5)
        resp = drain(sh, rounds=6)
        print(resp)

    finally:
        client.close()
        ok_c   = sum(1 for r in results if r['ok'])
        warn_c = sum(1 for r in results if not r['ok'])
        print(f"\n=== DONE  Commands: {len(results)}  OK: {ok_c}  WARN: {warn_c} ===")
        if warn_c:
            print("Remaining warnings:")
            for r in results:
                if not r['ok']:
                    print(f"  {r['cmd']!r}")

if __name__ == '__main__':
    main()
