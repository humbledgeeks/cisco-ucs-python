#!/usr/bin/env python3
"""
ucsm_vsan_storage.py
FC ports are in Storage Cloud (FC Storage Ports, direct-attach).
VSANs must be created under scope fc-storage, not fc-uplink.

Steps:
  1. Probe fc-storage scope to confirm VSAN creation syntax
  2. Delete any stale VSANs from wrong scope (fc-uplink)
  3. Create VSAN 10 (hg-vsan-a) under fc-storage / fabric a
  4. Create VSAN 11 (hg-vsan-b) under fc-storage / fabric b
  5. Bind VSANs to vHBA templates via set fc-if
  6. Verify
"""

import paramiko, time

HOST = '10.103.12.20'
USER = 'admin'
PASS = 'HybridAdm1n&&'

SLOW   = 2.5
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

def storage_fabric(sh, fab):
    sr(sh, 'top', FAST)
    sr(sh, 'scope fc-storage', FAST)
    sr(sh, f'scope fabric {fab}', FAST)

def main():
    print(f"Connecting to UCSM at {HOST} ...")
    client, sh = connect()
    print("Connected.\n")

    try:
        # ── 1. Probe fc-storage scope ─────────────────────────────────────────
        print("=== PROBE: fc-storage scope ===")
        sr(sh, 'top', FAST)
        _, ok = sr(sh, 'scope fc-storage', FAST)
        if not ok:
            print("  [CRITICAL] scope fc-storage not available — check UCSM version")
            return
        sh.send('show ?\n'); time.sleep(SLOW); print(drain(sh))
        _, ok = sr(sh, 'scope fabric a', FAST)
        if ok:
            sh.send('show ?\n'); time.sleep(SLOW); print(drain(sh))
            sh.send('create vsan ?\n'); time.sleep(SLOW); print(drain(sh))
        discard(sh)

        # ── 2. Clean up stale VSANs from wrong scope (fc-uplink) ─────────────
        print("\n=== Clean up stale VSANs from fc-uplink scope ===")
        for fab, name in [('a','hg-vsan-a'), ('b','hg-vsan-b')]:
            sr(sh, 'top', FAST)
            sr(sh, 'scope fc-uplink', FAST)
            sr(sh, f'scope fabric {fab}', FAST)
            _, ok = sr(sh, f'delete vsan {name}', FAST)
            if ok:
                safe_commit(sh)
                print(f"  Cleaned {name} from fc-uplink fabric {fab}")
            else:
                discard(sh)

        # ── 3. Create VSANs in fc-storage scope ───────────────────────────────
        print("\n=== Create VSANs in fc-storage scope ===")
        vsans = [
            ('a', 'hg-vsan-a', 10, 1010),
            ('b', 'hg-vsan-b', 11, 1011),
        ]
        for fab, name, vid, fcoe in vsans:
            print(f"\n  -- Storage Fabric {fab.upper()}: {name} ID={vid} FCoE-VLAN={fcoe} --")
            storage_fabric(sh, fab)
            # Try 3-param (name, id, fcoe-vlan)
            _, ok = sr(sh, f'create vsan {name} {vid} {fcoe}', SLOW)
            if not ok:
                discard(sh)
                storage_fabric(sh, fab)
                # Try 2-param
                _, ok = sr(sh, f'create vsan {name} {vid}', SLOW)
                if not ok:
                    discard(sh)
                    print(f"  [SKIP] Cannot create {name} in fc-storage scope")
                    continue
            if safe_commit(sh):
                print(f"  [SUCCESS] {name} created in storage cloud")
            else:
                print(f"  [WARN] {name} commit failed")

        # ── 4. Verify VSANs in storage scope ──────────────────────────────────
        print("\n=== VSAN state (fc-storage) ===")
        for fab in ['a', 'b']:
            storage_fabric(sh, fab)
            sh.send('show vsan detail\n'); time.sleep(4)
            resp = drain(sh, rounds=5)
            print(f"\n  Storage Fabric {fab.upper()}:\n{resp}")
            discard(sh)

        # Also check fc-uplink for comparison
        print("\n  fc-uplink VSANs (for reference):")
        sr(sh, 'top', FAST); sr(sh, 'scope fc-uplink', FAST)
        sh.send('show vsan\n'); time.sleep(3)
        print(drain(sh))
        discard(sh)

        # ── 5. Bind VSANs to vHBA templates ──────────────────────────────────
        print("\n=== Bind VSANs to vHBA templates (set fc-if) ===")
        for tmpl, vsan in [('hg-vmhba0','hg-vsan-a'), ('hg-vmhba1','hg-vsan-b')]:
            print(f"\n  -- {tmpl} → {vsan} --")
            hg_org(sh)
            sr(sh, f'scope vhba-templ {tmpl}', FAST)
            _, ok = sr(sh, f'set fc-if {vsan}', FAST)
            if ok:
                safe_commit(sh)
                print(f"  [SUCCESS] {tmpl} bound to {vsan}")
            else:
                discard(sh)
                print(f"  [GUI needed] Assign {vsan} to {tmpl} in UCSM GUI:")
                print(f"    SAN → Storage Cloud → HumbledGeeks org → vHBA Templates → {tmpl}")

        # ── 6. Final vHBA verification ─────────────────────────────────────
        print("\n=== Final vHBA Template State ===")
        hg_org(sh)
        sh.send('show vhba-templ detail\n'); time.sleep(5)
        print(drain(sh, rounds=6))

    finally:
        client.close()
        ok_c   = sum(1 for r in results if r['ok'])
        warn_c = sum(1 for r in results if not r['ok'])
        print(f"\n=== DONE  Commands: {len(results)}  OK: {ok_c}  WARN: {warn_c} ===")
        if warn_c:
            print("Warnings:")
            for r in results:
                if not r['ok']:
                    print(f"  {r['cmd']!r}")

if __name__ == '__main__':
    main()
