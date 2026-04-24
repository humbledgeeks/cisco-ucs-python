#!/usr/bin/env python3
"""
ucsm_last_two.py
1. vHBA VSAN binding — try multiple name resolution paths for Storage Cloud VSANs
2. CDP/LLDP — deep probe + try every known syntax variant
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

# ─── 1. vHBA VSAN binding ──────────────────────────────────────────────────────
def fix_vhba_vsan(sh):
    print("\n=== FIX 1: vHBA VSAN binding — exhaustive name resolution ===")

    # First: discover VSAN object names from within fc-storage scope
    print("\n  [Discovery] fc-storage/fabric a — show vsan")
    sr(sh, 'top', FAST); sr(sh, 'scope fc-storage', FAST)
    sr(sh, 'scope fabric a', FAST)
    sh.send('show vsan\n'); time.sleep(3); vsan_a_info = drain(sh)
    print(vsan_a_info)
    # Try scoping INTO the vsan to see its object name
    sr(sh, 'scope vsan hg-vsan-a', FAST)
    sh.send('pwd\n'); time.sleep(FAST); print(drain(sh))
    discard(sh)

    # Candidate fc-if name formats to try
    vhba_vsans = [
        ('hg-vmhba0', [
            'hg-vsan-a',
            'fc-storage/fabric-A/net-hg-vsan-a',
            'fabric-A/hg-vsan-a',
            'vsan-10',
            '10',
        ]),
        ('hg-vmhba1', [
            'hg-vsan-b',
            'fc-storage/fabric-B/net-hg-vsan-b',
            'fabric-B/hg-vsan-b',
            'vsan-11',
            '11',
        ]),
    ]
    for tmpl, candidates in vhba_vsans:
        print(f"\n  -- {tmpl} --")
        bound = False
        for name in candidates:
            hg_org(sh)
            sr(sh, f'scope vhba-templ {tmpl}', FAST)
            _, ok = sr(sh, f'set fc-if {name}', FAST, f'set fc-if {name!r}')
            if ok:
                if safe_commit(sh):
                    print(f"  [SUCCESS] {tmpl} bound via fc-if={name!r}")
                    bound = True
                    break
                else:
                    continue
            else:
                discard(sh)
        if not bound:
            print(f"  [RESULT] {tmpl}: VSAN binding needs GUI")
            print(f"           SAN → Policies → HumbledGeeks → vHBA Templates → {tmpl} → VSAN field")

# ─── 2. CDP / LLDP — deep probe ────────────────────────────────────────────────
def fix_cdp_lldp(sh):
    print("\n=== FIX 2: CDP/LLDP — deep probe and all syntax variants ===")
    hg_org(sh)
    sr(sh, 'scope nw-ctrl-policy hg-netcon', FAST)

    # Full scope probe — show all available commands including hidden ones
    print("\n  Full scope probe:")
    for probe_cmd in ['?', 'set ?', 'scope ?', 'create ?']:
        sh.send(probe_cmd + '\n'); time.sleep(SLOW)
        resp = drain(sh)
        print(f"  [{probe_cmd}]: {resp[:300]}")
    discard(sh)

    # Try every possible CDP/LLDP syntax documented across UCSM versions
    cdp_lldp_attempts = [
        # Format: (list-of-commands-to-try-in-sequence)
        ['scope nw-ctrl-policy hg-netcon', 'set cdp enabled'],
        ['scope nw-ctrl-policy hg-netcon', 'set cdp enable'],
        ['scope nw-ctrl-policy hg-netcon', 'set cdp-policy enabled'],
        ['scope nw-ctrl-policy hg-netcon', 'set lldp-receive enabled', 'set lldp-transmit enabled'],
        ['scope nw-ctrl-policy hg-netcon', 'set lldp receive enabled', 'set lldp transmit enabled'],
        ['scope nw-ctrl-policy hg-netcon', 'set lldp enabled'],
        ['scope nw-ctrl-policy hg-netcon', 'set forge-transmit enabled'],
    ]
    any_ok = False
    for attempt in cdp_lldp_attempts:
        hg_org(sh)
        cmds_ok = True
        for cmd in attempt:
            _, ok = sr(sh, cmd, FAST)
            if not ok:
                cmds_ok = False
                break
        if cmds_ok:
            if safe_commit(sh):
                print(f"  [SUCCESS] CDP/LLDP set via: {attempt}")
                any_ok = True
                break
            else:
                continue
        else:
            discard(sh)

    if not any_ok:
        # Final fallback: try via eth-uplink scope CDP policy
        print("\n  [Fallback] Checking eth-uplink CDP configuration...")
        sr(sh, 'top', FAST); sr(sh, 'scope eth-uplink', FAST)
        sh.send('show cdp ?\n'); time.sleep(SLOW); print(drain(sh))
        sh.send('set ?\n'); time.sleep(SLOW); resp = drain(sh)
        print(resp[:400])
        discard(sh)
        print("\n  [RESULT] CDP/LLDP on hg-netcon — not configurable via CLI in this UCSM version")
        print("           GUI path: LAN → Policies → HumbledGeeks → Network Control Policies")
        print("                     → hg-netcon → check CDP Enabled + LLDP Transmit/Receive")

# ─── Verification ──────────────────────────────────────────────────────────────
def verify(sh):
    print("\n=== VERIFICATION ===")
    hg_org(sh)
    sh.send('show vhba-templ detail\n'); time.sleep(5)
    print(drain(sh, rounds=6))
    hg_org(sh)
    sh.send('show nw-ctrl-policy detail\n'); time.sleep(3)
    print(drain(sh, rounds=4))

# ─── main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"Connecting to UCSM at {HOST} ...")
    client, sh = connect()
    print("Connected.\n")
    try:
        fix_vhba_vsan(sh)
        fix_cdp_lldp(sh)
        verify(sh)
    finally:
        client.close()
        ok_c = sum(1 for r in results if r['ok'])
        warn_c = sum(1 for r in results if not r['ok'])
        print(f"\n=== DONE  Commands: {len(results)}  OK: {ok_c}  WARN: {warn_c} ===")
        if warn_c:
            print("Remaining warnings:")
            for r in results:
                if not r['ok']: print(f"  {r['cmd']!r}")

if __name__ == '__main__':
    main()
