#!/usr/bin/env python3
"""
ucsm_final4.py — Final targeted fixes
  1. vHBA VSAN binding via correct 'set fc-if' attribute
  2. Check committed VSAN state and fabric scope
  3. Complete verification of entire HumbledGeeks org
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

def probe(sh, cmd):
    sh.send(cmd + '\n'); time.sleep(SLOW)
    resp = drain(sh)
    print(f"\n  [PROBE] {cmd!r}\n{resp}")
    return resp

def hg_org(sh):
    sr(sh, 'top', FAST)
    sr(sh, 'scope org /', FAST)
    sr(sh, 'scope org HumbledGeeks', FAST)

# ─── 1. Check VSANs across both fabric scopes ───────────────────────────────────
def check_vsans(sh):
    print("\n=== VSAN STATE CHECK ===")
    # Check fc-uplink scope (global)
    sh.send('top\n'); time.sleep(FAST)
    sh.send('scope fc-uplink\n'); time.sleep(FAST)
    drain(sh)
    probe(sh, 'show vsan detail')
    discard(sh)

    # Check per-fabric scopes — VSANs set to specific fabric appear here
    for fab in ['a', 'b']:
        sh.send('top\n'); time.sleep(FAST)
        sh.send('scope fc-uplink\n'); time.sleep(FAST)
        drain(sh)
        _, ok = sr(sh, f'scope fabric {fab}', FAST)
        if ok:
            probe(sh, 'show vsan detail')
        else:
            print(f"  [INFO] No per-fabric scope for {fab} in this UCSM version")
        discard(sh)

# ─── 2. vHBA template VSAN binding via set fc-if ───────────────────────────────
def fix_vhba_vsan(sh):
    print("\n=== FIX: vHBA Templates — set fc-if (VSAN binding) ===")
    templates = [
        ('hg-vmhba0', 'hg-vsan-a'),
        ('hg-vmhba1', 'hg-vsan-b'),
    ]
    for tmpl, vsan in templates:
        print(f"\n  -- {tmpl} → {vsan} --")
        hg_org(sh)
        sr(sh, f'scope vhba-templ {tmpl}', FAST)
        # Probe fc-if options
        probe(sh, 'set fc-if ?')
        # Try binding — fc-if takes the VSAN name
        _, ok = sr(sh, f'set fc-if {vsan}', FAST)
        if ok:
            safe_commit(sh)
        else:
            discard(sh)
            # Try with just the VSAN name as it appears in UCSM
            hg_org(sh)
            sr(sh, f'scope vhba-templ {tmpl}', FAST)
            # Try alternative VSAN names
            for vsan_name in [vsan, f'org-root/{vsan}', str(10 if tmpl=='hg-vmhba0' else 11)]:
                _, ok2 = sr(sh, f'set fc-if {vsan_name}', FAST)
                if ok2:
                    safe_commit(sh)
                    break
                else:
                    discard(sh)
                    hg_org(sh)
                    sr(sh, f'scope vhba-templ {tmpl}', FAST)
            else:
                print(f"  [INFO] {tmpl}: VSAN must be assigned via UCSM GUI")
                discard(sh)

# ─── Full org verification ──────────────────────────────────────────────────────
def verify_all(sh):
    print("\n=== COMPLETE HumbledGeeks ORG VERIFICATION ===")

    # VSANs at fc-uplink level
    sh.send('top\n'); time.sleep(FAST)
    sh.send('scope fc-uplink\n'); time.sleep(FAST)
    drain(sh)
    sh.send('show vsan detail\n'); time.sleep(4)
    resp = drain(sh, rounds=5); print(f"\n-- VSANs --\n{resp}")
    discard(sh)

    hg_cmds = [
        ('show vhba-templ detail',            'vHBA Templates'),
        ('show vnic-templ detail',            'vNIC Templates'),
        ('show service-profile detail',       'Service Profile Template'),
        ('show lan-connectivity-policy detail','LAN Connectivity'),
        ('show san-connectivity-policy detail','SAN Connectivity'),
        ('show wwn-pool detail',              'WWN Pools'),
        ('show uuid-suffix-pool detail',      'UUID Pool'),
        ('show mac-pool detail',              'MAC Pools'),
        ('show nw-ctrl-policy detail',        'Network Control Policy'),
        ('show boot-policy detail',           'Boot Policy'),
        ('show local-disk-config-policy detail','Local Disk Policy'),
    ]
    for cmd, label in hg_cmds:
        sh.send('top\n'); time.sleep(FAST)
        sh.send('scope org /\n'); time.sleep(FAST)
        sh.send('scope org HumbledGeeks\n'); time.sleep(FAST)
        drain(sh)
        sh.send(cmd + '\n'); time.sleep(4)
        resp = drain(sh, rounds=5, pause=0.5)
        print(f"\n{'─'*60}\n  {label}\n{'─'*60}\n{resp[:2000]}")

# ─── main ────────────────────────────────────────────────────────────────────────
def main():
    print(f"Connecting to UCSM at {HOST} ...")
    client, sh = connect()
    print("Connected.\n")
    try:
        check_vsans(sh)
        fix_vhba_vsan(sh)
        verify_all(sh)
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
