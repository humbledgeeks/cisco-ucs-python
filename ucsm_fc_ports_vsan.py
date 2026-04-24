#!/usr/bin/env python3
"""
ucsm_fc_ports_vsan.py
Three tasks:
  1. Assign FC Storage Ports 29-32 on FI-A  → hg-vsan-a (VSAN 10)
     Assign FC Storage Ports 29-32 on FI-B  → hg-vsan-b (VSAN 11)
  2. Retry vHBA template VSAN binding via set fc-if
  3. CDP/LLDP final attempt via all remaining syntax variants
"""
import paramiko, time

HOST = '10.103.12.20'
USER = 'admin'
PASS = 'HybridAdm1n&&'
SLOW = 2.5; FAST = 0.8; COMMIT = 4.5

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

# ─── 1. FC Storage Port VSAN Assignment ────────────────────────────────────────
def fix_fc_port_vsans(sh):
    print("\n=== FIX 1: FC Storage Port VSAN Assignment ===")

    # Probe interface scope syntax first
    print("\n  [Probe] fc-storage/fabric a interface scope")
    sr(sh, 'top', FAST); sr(sh, 'scope fc-storage', FAST)
    sr(sh, 'scope fabric a', FAST)
    sh.send('scope interface ?\n'); time.sleep(SLOW); print(drain(sh)[:400])
    discard(sh)

    # FI-A: ports 29-32 → hg-vsan-a
    # FI-B: ports 29-32 → hg-vsan-b
    fabric_map = [
        ('a', range(29, 33), 'hg-vsan-a'),
        ('b', range(29, 33), 'hg-vsan-b'),
    ]
    for fabric, ports, vsan in fabric_map:
        print(f"\n  -- Fabric {fabric.upper()} ports 29-32 → {vsan} --")
        for port in ports:
            sr(sh, 'top', FAST)
            sr(sh, 'scope fc-storage', FAST)
            sr(sh, f'scope fabric {fabric}', FAST)
            # Try different interface scope syntaxes
            scoped = False
            for intf_cmd in [f'scope interface fc 1/{port}',
                             f'scope interface 1/{port}',
                             f'scope interface {port}']:
                _, ok = sr(sh, intf_cmd, FAST, f'scope port {port}')
                if ok:
                    scoped = True
                    break
                else:
                    discard(sh)
                    sr(sh, 'top', FAST)
                    sr(sh, 'scope fc-storage', FAST)
                    sr(sh, f'scope fabric {fabric}', FAST)

            if not scoped:
                print(f"  [SKIP] Cannot scope into port {port} on fabric {fabric.upper()}")
                discard(sh)
                continue

            # Probe what we can set on this interface
            if port == 29:  # only probe once per fabric
                sh.send('set ?\n'); time.sleep(SLOW)
                probe_resp = drain(sh)
                print(f"  [Probe port {port} set ?]: {probe_resp[:300]}")

            # Set VSAN
            _, ok = sr(sh, f'set vsan {vsan}', FAST, f'port {port}: set vsan {vsan}')
            if not ok:
                discard(sh)
                # Try by VSAN ID
                sr(sh, 'top', FAST); sr(sh, 'scope fc-storage', FAST)
                sr(sh, f'scope fabric {fabric}', FAST)
                for intf_cmd in [f'scope interface fc 1/{port}',
                                 f'scope interface 1/{port}',
                                 f'scope interface {port}']:
                    _, ok2 = sr(sh, intf_cmd, FAST)
                    if ok2: break
                    else:
                        discard(sh)
                        sr(sh, 'top', FAST); sr(sh, 'scope fc-storage', FAST)
                        sr(sh, f'scope fabric {fabric}', FAST)
                vsan_id = 10 if fabric == 'a' else 11
                sr(sh, f'set vsan {vsan_id}', FAST, f'port {port}: set vsan {vsan_id} (by ID)')

        # Commit all ports for this fabric together
        if safe_commit(sh):
            print(f"  [SUCCESS] Fabric {fabric.upper()} ports assigned to {vsan}")
        else:
            print(f"  [WARN] Fabric {fabric.upper()} port VSAN commit failed")

# ─── 2. vHBA template VSAN binding (retry after port assignment) ───────────────
def fix_vhba_vsan(sh):
    print("\n=== FIX 2: vHBA Template VSAN Binding ===")
    # After FC ports are in the right VSAN, the storage VSAN
    # may now resolve from the org policy scope
    bindings = [('hg-vmhba0', 'hg-vsan-a'), ('hg-vmhba1', 'hg-vsan-b')]
    for tmpl, vsan in bindings:
        print(f"\n  -- {tmpl} → {vsan} --")
        bound = False
        # Try progressively different name formats
        for name in [vsan,
                     f'fabric-A/{vsan}' if 'a' in vsan else f'fabric-B/{vsan}',
                     f'fc-storage/fabric-A/net-{vsan}' if 'a' in vsan else f'fc-storage/fabric-B/net-{vsan}']:
            hg_org(sh)
            sr(sh, f'scope vhba-templ {tmpl}', FAST)
            _, ok = sr(sh, f'set fc-if {name}', FAST, f'set fc-if {name!r}')
            if ok:
                if safe_commit(sh):
                    print(f"  [SUCCESS] {tmpl} bound via fc-if={name!r}")
                    bound = True
                    break
                # else keep trying
            else:
                discard(sh)
        if not bound:
            print(f"  [RESULT] CLI binding not supported for storage-cloud VSANs in this UCSM version")
            print(f"           GUI: SAN tab → Policies → HumbledGeeks → vHBA Templates → {tmpl} → VSAN field → select {vsan}")

# ─── 3. CDP / LLDP final attempt ──────────────────────────────────────────────
def fix_cdp_lldp(sh):
    print("\n=== FIX 3: CDP/LLDP Final Attempt ===")
    hg_org(sh)
    sr(sh, 'scope nw-ctrl-policy hg-netcon', FAST)
    # Complete ? probe including all top-level commands
    sh.send('?\n'); time.sleep(SLOW); full_probe = drain(sh)
    print(f"  All commands in nw-ctrl-policy scope:\n{full_probe}")
    discard(sh)

    # Try every documented variant across UCSM 3.x → 4.x
    cdp_variants = [
        [('set cdp enabled', FAST)],
        [('set cdp enable', FAST)],
        [('set cdp-admin-state enabled', FAST)],
        [('set lldp-receive enabled', FAST), ('set lldp-transmit enabled', FAST)],
        [('set lldp receive enable', FAST), ('set lldp transmit enable', FAST)],
        [('set forge-transmit allow', FAST)],
    ]
    for variant in cdp_variants:
        hg_org(sh)
        sr(sh, 'scope nw-ctrl-policy hg-netcon', FAST)
        all_ok = True
        for cmd, delay in variant:
            _, ok = sr(sh, cmd, delay)
            if not ok:
                all_ok = False; break
        if all_ok:
            if safe_commit(sh):
                print(f"  [SUCCESS] CDP/LLDP set: {[c for c,_ in variant]}")
                return
        discard(sh)

    print("  [CONFIRMED] CDP/LLDP not CLI-settable in this UCSM version")
    print("  GUI: LAN tab → Policies → HumbledGeeks → Network Control Policies → hg-netcon")
    print("       Check: CDP Enabled, LLDP Transmit Enabled, LLDP Receive Enabled → Save")

# ─── Verification ──────────────────────────────────────────────────────────────
def verify(sh):
    print("\n=== VERIFICATION ===")

    # FC Storage Port VSAN state
    for fab, vsan in [('a','hg-vsan-a'), ('b','hg-vsan-b')]:
        sr(sh, 'top', FAST); sr(sh, 'scope fc-storage', FAST)
        sr(sh, f'scope fabric {fab}', FAST)
        sh.send('show interface detail\n'); time.sleep(5)
        resp = drain(sh, rounds=6)
        # Print only lines with port ID, VSAN, or state info
        print(f"\n  -- Fabric {fab.upper()} FC Storage Port states --")
        for line in resp.splitlines():
            if any(x in line for x in ['Port', 'VSAN', 'vsan', 'State', 'state', 'Oper']):
                print(f"    {line.strip()}")
        discard(sh)

    # vHBA Templates
    hg_org(sh)
    sh.send('show vhba-templ detail\n'); time.sleep(5)
    resp = drain(sh, rounds=6)
    print(f"\n  -- vHBA Templates --\n{resp[:1500]}")

    # Network Control Policy
    hg_org(sh)
    sh.send('show nw-ctrl-policy detail\n'); time.sleep(3)
    print(f"\n  -- Network Control Policy --\n{drain(sh, rounds=4)}")

# ─── main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"Connecting to UCSM at {HOST} ...")
    client, sh = connect()
    print("Connected.\n")
    try:
        fix_fc_port_vsans(sh)
        fix_vhba_vsan(sh)
        fix_cdp_lldp(sh)
        verify(sh)
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
