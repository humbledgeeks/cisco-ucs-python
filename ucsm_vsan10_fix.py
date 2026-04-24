#!/usr/bin/env python3
"""
ucsm_vsan10_fix.py
The stale LAN Cloud VLAN 'hg-fcoe-a' (ID 1010) is blocking VSAN 10 creation.
Steps:
  1. Find and delete hg-fcoe-a from eth-uplink / LAN Cloud
  2. Retry VSAN 10 (hg-vsan-a) in fc-storage/fabric a with FCoE VLAN 1010
  3. Probe set fc-if options and retry vHBA template bindings
"""

import paramiko, time

HOST = '10.103.12.20'
USER = 'admin'
PASS = 'HybridAdm1n&&'
SLOW = 2.5; FAST = 0.8; COMMIT = 4.0

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
    while sh.recv_ready(): sh.recv(65535)
    return c, sh

def sr(sh, cmd, delay=SLOW, label=None):
    sh.send(cmd + '\n'); time.sleep(delay)
    resp = drain(sh).strip()
    bad = any(x in resp for x in ['Error','error','Invalid','invalid','Failed','failed'])
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
    if not ok: sr(sh, 'discard-buffer', FAST, 'discard-buffer [recovery]')
    return ok

def discard(sh): sr(sh, 'discard-buffer', FAST, 'discard-buffer')

def hg_org(sh):
    sr(sh, 'top', FAST); sr(sh, 'scope org /', FAST)
    sr(sh, 'scope org HumbledGeeks', FAST)

def main():
    print(f"Connecting to UCSM at {HOST} ...")
    client, sh = connect()
    print("Connected.\n")
    try:
        # ── 1. Show all LAN Cloud VLANs around ID 1010 ───────────────────────
        print("=== STEP 1: Inspect LAN Cloud VLANs ===")
        sr(sh, 'top', FAST); sr(sh, 'scope eth-uplink', FAST)
        sh.send('show vlan detail\n'); time.sleep(5)
        vlan_resp = drain(sh, rounds=6)
        # Only print lines mentioning 1010, hg-fcoe, or FCoE
        print("  VLANs containing 1010 / fcoe / hg-fcoe:")
        for line in vlan_resp.splitlines():
            if any(x in line.lower() for x in ['1010','fcoe','hg-fcoe']):
                print(f"    {line.strip()}")
        discard(sh)

        # ── 2. Delete hg-fcoe-a VLAN from LAN Cloud ──────────────────────────
        print("\n=== STEP 2: Delete hg-fcoe-a from LAN Cloud ===")
        sr(sh, 'top', FAST); sr(sh, 'scope eth-uplink', FAST)
        _, ok = sr(sh, 'delete vlan hg-fcoe-a', SLOW)
        if ok:
            if safe_commit(sh):
                print("  [SUCCESS] hg-fcoe-a VLAN deleted from LAN Cloud")
            else:
                print("  [WARN] Delete committed but verify in GUI")
        else:
            discard(sh)
            # Try by VLAN ID
            sr(sh, 'top', FAST); sr(sh, 'scope eth-uplink', FAST)
            _, ok2 = sr(sh, 'delete vlan 1010', SLOW)
            if ok2:
                if safe_commit(sh):
                    print("  [SUCCESS] VLAN 1010 deleted from LAN Cloud by ID")
            else:
                discard(sh)
                print("  [INFO] Could not delete via CLI — check GUI: LAN → LAN Cloud → VLANs → delete VLAN 1010")

        # ── 3. Retry VSAN 10 creation ─────────────────────────────────────────
        print("\n=== STEP 3: Retry VSAN 10 in fc-storage/fabric a ===")
        sr(sh, 'top', FAST); sr(sh, 'scope fc-storage', FAST)
        sr(sh, 'scope fabric a', FAST)
        _, ok = sr(sh, 'create vsan hg-vsan-a 10 1010', SLOW)
        if ok:
            if safe_commit(sh):
                print("  [SUCCESS] hg-vsan-a (VSAN 10, FCoE 1010) created in storage cloud!")
            else:
                print("  [WARN] Commit failed — FCoE VLAN 1010 conflict may still exist")
        else:
            discard(sh)
            print("  [WARN] VSAN 10 create failed")

        # ── 4. Verify both VSANs ──────────────────────────────────────────────
        print("\n=== STEP 4: VSAN verification ===")
        for fab in ['a', 'b']:
            sr(sh, 'top', FAST); sr(sh, 'scope fc-storage', FAST)
            sr(sh, f'scope fabric {fab}', FAST)
            sh.send('show vsan detail\n'); time.sleep(4)
            resp = drain(sh, rounds=5)
            print(f"\n  Storage Fabric {fab.upper()}:\n{resp}")
            discard(sh)

        # ── 5. Probe fc-if syntax and retry vHBA bindings ────────────────────
        print("\n=== STEP 5: vHBA template VSAN binding ===")
        for tmpl, vsan in [('hg-vmhba0','hg-vsan-a'), ('hg-vmhba1','hg-vsan-b')]:
            print(f"\n  -- {tmpl} → {vsan} --")
            hg_org(sh)
            sr(sh, f'scope vhba-templ {tmpl}', FAST)
            # Probe fc-if options
            sh.send('set fc-if ?\n'); time.sleep(SLOW)
            fc_probe = drain(sh)
            print(f"  fc-if options: {fc_probe[:200]}")
            _, ok = sr(sh, f'set fc-if {vsan}', FAST)
            if ok:
                safe_commit(sh)
                print(f"  [SUCCESS] {tmpl} → {vsan}")
            else:
                discard(sh)
                print(f"  [GUI] In UCSM GUI: SAN → Policies → HumbledGeeks → vHBA Templates")
                print(f"        → {tmpl} → VSAN: select {vsan}")

    finally:
        client.close()
        ok_c = sum(1 for r in results if r['ok'])
        warn_c = sum(1 for r in results if not r['ok'])
        print(f"\n=== DONE  Commands: {len(results)}  OK: {ok_c}  WARN: {warn_c} ===")
        if warn_c:
            print("Warnings:")
            for r in results:
                if not r['ok']: print(f"  {r['cmd']!r}")

if __name__ == '__main__':
    main()
