#!/usr/bin/env python3
"""
ucsm_patch_final.py — HumbledGeeks org final patch
Targets:
  1. WWN pool blocks (WWNN + WWPN A/B)
  2. CDP/LLDP fix on hg-netcon  (probe set ? first)
  3. Service profile template type fix
  4. Final verification of all key objects
"""

import paramiko, time, sys

HOST = '10.103.12.20'
USER = 'admin'
PASS = 'HybridAdm1n&&'

SLOW   = 2.0
FAST   = 1.0
COMMIT = 3.5

results = []

# ── SSH helpers ────────────────────────────────────────────────────────────────
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
    tag = '[WARN]' if any(x in resp for x in
          ['Error','error','Invalid','invalid','Failed','failed','not valid']) else '[OK]  '
    display = label or cmd
    entry = {'cmd': cmd, 'resp': resp, 'ok': tag == '[OK]  '}
    results.append(entry)
    print(f"  {tag} {display!r}")
    if tag == '[WARN]':
        for line in resp.splitlines():
            if any(x in line for x in ['Error','error','Invalid','invalid','Failed']):
                print(f"         >> {line.strip()}")
    return resp

def safe_commit(sh):
    resp = sr(sh, 'commit-buffer', COMMIT, 'commit-buffer')
    if not results[-1]['ok']:
        sr(sh, 'discard-buffer', FAST, 'discard-buffer [recovery]')
        return False
    return True

def discard(sh):
    sr(sh, 'discard-buffer', FAST, 'discard-buffer')

def root_org(sh):
    sr(sh, 'top', FAST)
    sr(sh, 'scope org /', FAST)

def hg_org(sh):
    sr(sh, 'top', FAST)
    sr(sh, 'scope org /', FAST)
    sr(sh, 'scope org HumbledGeeks', FAST)

def probe(sh, what='set ?'):
    """Send a discovery command and print the full response."""
    sh.send(what + '\n')
    time.sleep(SLOW)
    resp = drain(sh)
    print(f"\n--- PROBE: {what!r} ---\n{resp}\n---")
    return resp

# ── 1. WWN pool blocks ─────────────────────────────────────────────────────────
def patch1_wwn_blocks(sh):
    print("\n=== PATCH 1: WWN Pool Blocks ===")
    pools = [
        # (pool-name,  purpose-hint,  start-wwn,                 end-wwn)
        ('hg-wwnn-pool', 'WWNN', '20:00:00:25:B5:11:1F:01', '20:00:00:25:B5:11:1F:A0'),
        ('hg-wwpn-a',    'WWPN', '20:00:00:25:B5:11:1A:01', '20:00:00:25:B5:11:1A:A0'),
        ('hg-wwpn-b',    'WWPN', '20:00:00:25:B5:11:1B:01', '20:00:00:25:B5:11:1B:A0'),
    ]
    for name, hint, start, end in pools:
        print(f"\n  -- {name} ({hint}) --")
        root_org(sh)
        resp = sr(sh, f'scope wwn-pool {name}', FAST, f'scope wwn-pool {name}')
        if not results[-1]['ok']:
            print(f"  [SKIP] Cannot scope into {name} — pool may not exist")
            discard(sh)
            continue
        # Probe what's available before creating block
        probe(sh, 'show ?')
        resp = sr(sh, f'create block {start} {end}', SLOW,
                  f'create block {start} {end}')
        if results[-1]['ok']:
            safe_commit(sh)
        else:
            discard(sh)

# ── 2. CDP / LLDP on hg-netcon ─────────────────────────────────────────────────
def patch2_netcon(sh):
    print("\n=== PATCH 2: Network Control Policy CDP/LLDP ===")
    hg_org(sh)
    sr(sh, 'scope nw-ctrl-policy hg-netcon', FAST)
    # Probe to find correct attribute names
    cdp_attrs = probe(sh, 'set ?')

    # Try each likely CDP attribute name
    cdp_candidates = ['cdp enabled', 'cdp-state enabled', 'cdp enable']
    cdp_ok = False
    for candidate in cdp_candidates:
        resp = sr(sh, f'set {candidate}', FAST, f'set {candidate}')
        if results[-1]['ok']:
            cdp_ok = True
            break
        else:
            discard(sh)
            hg_org(sh)
            sr(sh, 'scope nw-ctrl-policy hg-netcon', FAST)

    # Try LLDP receive/transmit
    lldp_candidates = [
        ('lldp-receive enabled', 'lldp-transmit enabled'),
        ('lldp receive enabled', 'lldp transmit enabled'),
        ('lldp-receive-state enabled', 'lldp-transmit-state enabled'),
    ]
    lldp_ok = False
    for rx, tx in lldp_candidates:
        r1 = sr(sh, f'set {rx}', FAST, f'set {rx}')
        r2 = sr(sh, f'set {tx}', FAST, f'set {tx}')
        if results[-2]['ok'] and results[-1]['ok']:
            lldp_ok = True
            break
        else:
            discard(sh)
            hg_org(sh)
            sr(sh, 'scope nw-ctrl-policy hg-netcon', FAST)

    print(f"\n  CDP set: {cdp_ok}  |  LLDP set: {lldp_ok}")
    if cdp_ok or lldp_ok:
        safe_commit(sh)
    else:
        discard(sh)
        print("  [INFO] Could not set CDP/LLDP — policy committed as-is (forge-disable default is fine)")

# ── 3. Service profile template type ───────────────────────────────────────────
def patch3_sp_type(sh):
    print("\n=== PATCH 3: Service Profile Template Type ===")
    hg_org(sh)
    sr(sh, 'scope service-profile hg-esx-template', FAST)
    # Probe valid type values
    probe(sh, 'set type ?')
    # Try the short form used elsewhere in UCSM
    for val in ['updating-templ', 'updating-template', 'initial-templ']:
        resp = sr(sh, f'set type {val}', FAST, f'set type {val}')
        if results[-1]['ok']:
            print(f"  [SUCCESS] set type {val!r} works")
            safe_commit(sh)
            return
        else:
            discard(sh)
            hg_org(sh)
            sr(sh, 'scope service-profile hg-esx-template', FAST)
    print("  [WARN] Could not determine correct type value — service profile remains as-is")
    discard(sh)

# ── 4. Final verification ───────────────────────────────────────────────────────
def verify(sh):
    print("\n=== FINAL VERIFICATION ===")
    checks = [
        # (context-cmds, verify-cmd, label)
        (['top', 'scope org /', 'scope org HumbledGeeks'],
         'show service-profile detail', 'Service Profile Template'),
        (['top', 'scope org /', 'scope org HumbledGeeks'],
         'show nw-ctrl-policy detail', 'Network Control Policy'),
        (['top', 'scope org /', 'scope org HumbledGeeks'],
         'show vnic-templ detail', 'vNIC Templates'),
        (['top', 'scope org /', 'scope org HumbledGeeks'],
         'show vhba-templ detail', 'vHBA Templates'),
        (['top', 'scope org /', 'scope org HumbledGeeks'],
         'show lan-connectivity-policy detail', 'LAN Connectivity Policy'),
        (['top', 'scope org /', 'scope org HumbledGeeks'],
         'show san-connectivity-policy detail', 'SAN Connectivity Policy'),
        (['top', 'scope org /'],
         'show wwn-pool detail', 'WWN Pools (root)'),
        (['top', 'scope org /', 'scope org HumbledGeeks'],
         'show uuid-suffix-pool detail', 'UUID Pool'),
        (['top', 'scope org /', 'scope org HumbledGeeks'],
         'show mac-pool detail', 'MAC Pools'),
    ]
    for ctx_cmds, cmd, label in checks:
        for c in ctx_cmds:
            sh.send(c + '\n'); time.sleep(0.8)
        drain(sh)
        sh.send(cmd + '\n')
        time.sleep(5)
        resp = drain(sh, rounds=6, pause=0.6)
        print(f"\n{'─'*60}")
        print(f"  VERIFY: {label}")
        print(f"  CMD:    {cmd}")
        print(f"{'─'*60}")
        print(resp[:3000])   # cap at 3000 chars per section

# ── main ────────────────────────────────────────────────────────────────────────
def main():
    print(f"Connecting to UCSM at {HOST} ...")
    client, sh = connect()
    print("Connected.\n")

    try:
        patch1_wwn_blocks(sh)
        patch2_netcon(sh)
        patch3_sp_type(sh)
        verify(sh)
    finally:
        client.close()
        print("\n=== DONE ===")

        ok_count   = sum(1 for r in results if r['ok'])
        warn_count = sum(1 for r in results if not r['ok'])
        print(f"Commands issued: {len(results)}  OK: {ok_count}  WARN: {warn_count}")

        if warn_count:
            print("\nWarnings:")
            for r in results:
                if not r['ok']:
                    print(f"  cmd={r['cmd']!r}")

if __name__ == '__main__':
    main()
