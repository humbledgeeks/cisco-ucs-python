#!/usr/bin/env python3
"""
============================================================
UCSM HumbledGeeks Sub-Org Creator  v2
============================================================
Improvements over v1:
  - discard_buffer() after every failed commit
  - Each phase commits independently
  - Longer delays to prevent shell timing races
  - VSAN creation deferred (no active FC infrastructure)
  - Scope resets before every phase
============================================================
"""
import paramiko, time, sys

HOST = '10.103.12.20'
USER = 'admin'
PASS = 'HybridAdm1n&&'
LOG  = '/Users/ajohnson/ucsm_create_v2_log.txt'

results  = []
warnings = []
SLOW     = 2.0   # standard delay between commands
COMMIT_D = 3.0   # delay after commit-buffer

def drain(shell):
    """Fully drain the receive buffer."""
    buf = b''
    for _ in range(8):
        time.sleep(0.4)
        while shell.recv_ready():
            buf += shell.recv(65535)
            time.sleep(0.1)
    return buf.decode('utf-8', 'replace')

def sr(shell, cmd, delay=SLOW):
    shell.send(cmd + '\n')
    time.sleep(delay)
    resp = drain(shell).strip()
    tag = '[WARN]' if any(x in resp for x in
          ['Error','error','Invalid','Failed','failed']) else '[OK]  '
    results.append({'cmd': cmd, 'resp': resp})
    if tag == '[WARN]':
        warnings.append({'cmd': cmd, 'resp': resp})
        print(f"  {tag} {cmd!r}")
        print(f"         {resp[:120]}")
    else:
        print(f"  {tag} {cmd!r}")
    return resp


def discard(shell):
    """Discard any pending uncommitted changes."""
    shell.send('discard-buffer\n')
    time.sleep(2)
    drain(shell)
    print("  [DISC] discard-buffer (clean slate)")

def safe_commit(shell):
    """Commit, and discard on failure. Returns True if committed OK."""
    resp = sr(shell, 'commit-buffer', COMMIT_D)
    if 'Error' in resp or 'error' in resp or 'Failed' in resp:
        discard(shell)
        return False
    return True

def reset(shell):
    """Return to root org scope."""
    sr(shell, 'top', 1)
    sr(shell, 'scope org /', 1)
    sr(shell, 'scope org HumbledGeeks', 1)

def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30)
    sh = c.invoke_shell(width=220)
    time.sleep(3)
    drain(sh)
    return c, sh


# ──────────────────────────────────────────────────────────────────
# PHASE 1 ─ Create org HumbledGeeks
# ──────────────────────────────────────────────────────────────────
def phase1_org(sh):
    print("\n=== PHASE 1: Create org HumbledGeeks ===")
    sr(sh, 'top', 1)
    discard(sh)  # clear anything left from prior session
    sr(sh, 'scope org /', 1)
    sr(sh, 'create org HumbledGeeks', 1)
    sr(sh, 'set descr "HumbledGeeks VCF Lab per workbook design"', 1)
    ok = safe_commit(sh)
    if not ok:
        print("  [INFO] org may already exist - trying scope anyway")
    sr(sh, 'top', 1)
    sr(sh, 'scope org /', 1)
    sr(sh, 'scope org HumbledGeeks', 1)
    print("  [INFO] Scoped into HumbledGeeks")


# ──────────────────────────────────────────────────────────────────
# PHASE 2 ─ Identity Pools
# ──────────────────────────────────────────────────────────────────
def phase2_pools(sh):
    print("\n=== PHASE 2: Identity Pools ===")

    def pool(create_cmd, sets, block_cmd, label):
        print(f"  {label}...")
        reset(sh)
        sr(sh, create_cmd, 1)
        for s in sets:
            sr(sh, s, 1)
        sr(sh, block_cmd, 1)
        safe_commit(sh)

    # UUID pool (160 entries)
    pool('create uuid-suffix-pool hg-uuid-pool',
         ['set assignment-order sequential',
          'set descr "HumbledGeeks UUID 160 entries"'],
         'create block 0000-000000000001 0000-0000000000A0',
         'UUID pool (160)')

    # MAC Pool A - Fabric A (512)
    pool('create mac-pool hg-mac-a',
         ['set assignment-order sequential',
          'set descr "HumbledGeeks MAC Fabric A"'],
         'create block 00:25:B5:11:1A:01 00:25:B5:11:1C:00',
         'MAC pool A (512)')

    # MAC Pool B - Fabric B (512)
    pool('create mac-pool hg-mac-b',
         ['set assignment-order sequential',
          'set descr "HumbledGeeks MAC Fabric B"'],
         'create block 00:25:B5:11:1D:01 00:25:B5:11:1F:00',
         'MAC pool B (512)')

    # WWNN pool (160 entries)
    pool('create wwnn-pool hg-wwnn-pool',
         ['set assignment-order sequential',
          'set descr "HumbledGeeks WWNN"'],
         'create block 20:00:00:25:B5:11:1F:01 20:00:00:25:B5:11:1F:A0',
         'WWNN pool (160)')

    # WWPN pool A (160)
    pool('create wwpn-pool hg-wwpn-a',
         ['set assignment-order sequential',
          'set descr "HumbledGeeks WWPN Fabric A"'],
         'create block 20:00:00:25:B5:11:1A:01 20:00:00:25:B5:11:1A:A0',
         'WWPN pool A (160)')

    # WWPN pool B (160)
    pool('create wwpn-pool hg-wwpn-b',
         ['set assignment-order sequential',
          'set descr "HumbledGeeks WWPN Fabric B"'],
         'create block 20:00:00:25:B5:11:1B:01 20:00:00:25:B5:11:1B:A0',
         'WWPN pool B (160)')


# ──────────────────────────────────────────────────────────────────
# PHASE 3 ─ Policies
# ──────────────────────────────────────────────────────────────────
def phase3_policies(sh):
    print("\n=== PHASE 3: Policies ===")

    # Network Control Policy (CDP + LLDP)
    print("  Network Control Policy...")
    reset(sh)
    sr(sh, 'create network-control-policy hg-netcon', 1)
    sr(sh, 'set cdp enabled', 1)
    sr(sh, 'set lldp-receive enabled', 1)
    sr(sh, 'set lldp-transmit enabled', 1)
    sr(sh, 'set descr "HumbledGeeks CDP+LLDP enabled"', 1)
    safe_commit(sh)

    # QoS Policy (best-effort)
    print("  QoS Policy...")
    reset(sh)
    sr(sh, 'create qos-policy hg-qos-be', 1)
    sr(sh, 'set prio best-effort', 1)
    sr(sh, 'set host-control none', 1)
    sr(sh, 'set descr "HumbledGeeks QoS best-effort"', 1)
    safe_commit(sh)

    # BIOS Policy (quiet boot disabled)
    print("  BIOS Policy...")
    reset(sh)
    sr(sh, 'create bios-policy hg-bios', 1)
    sr(sh, 'set reboot-on-bios-settings-change no', 1)
    sr(sh, 'set descr "HumbledGeeks BIOS quiet-boot disabled"', 1)
    safe_commit(sh)

    # Maintenance Policy (user-ack)
    print("  Maintenance Policy...")
    reset(sh)
    sr(sh, 'create maint-policy hg-maint', 1)
    sr(sh, 'set reboot-policy user-ack', 1)
    sr(sh, 'set descr "HumbledGeeks Maintenance user-ack"', 1)
    safe_commit(sh)

    # Local Disk Config Policy (local-storage-only)
    print("  Local Disk Config Policy...")
    reset(sh)
    sr(sh, 'create local-disk-config-policy hg-local-disk', 1)
    sr(sh, 'set mode local-storage-only', 1)
    sr(sh, 'set protect yes', 1)
    sr(sh, 'set descr "HumbledGeeks LocalDisk local-storage-only"', 1)
    safe_commit(sh)

    # Power Control Policy (no-cap)
    print("  Power Control Policy...")
    reset(sh)
    sr(sh, 'create power-policy hg-power', 1)
    sr(sh, 'set prio no-cap', 1)
    sr(sh, 'set descr "HumbledGeeks Power no-cap"', 1)
    safe_commit(sh)

    # vCon Placement Policy (round-robin)
    print("  vCon Placement Policy...")
    reset(sh)
    sr(sh, 'create vcon-policy hg-vcon', 1)
    sr(sh, 'set type round-robin', 1)
    sr(sh, 'set descr "HumbledGeeks vCon round-robin"', 1)
    safe_commit(sh)


    # Boot Policy (Legacy, CD/DVD then Local HD)
    print("  Boot Policy...")
    reset(sh)
    sr(sh, 'create boot-policy hg-boot', 1)
    sr(sh, 'set boot-mode legacy', 1)
    sr(sh, 'set reboot-on-update no', 1)
    sr(sh, 'set enforce-vnic-name yes', 1)
    sr(sh, 'set descr "HumbledGeeks Boot legacy CD then local HD"', 1)
    sr(sh, 'create local-cd-dvd', 1)
    sr(sh, 'exit', 1)
    sr(sh, 'create local-hdd', 1)
    sr(sh, 'exit', 1)
    safe_commit(sh)


# ──────────────────────────────────────────────────────────────────
# PHASE 4 ─ vNIC Templates (6: vmnic0-5, 3 A/B pairs)
# ──────────────────────────────────────────────────────────────────
def phase4_vnic_templates(sh):
    print("\n=== PHASE 4: vNIC Templates ===")

    def make_vnic(name, fabric, mac_pool, mtu, label, vlans, native):
        print(f"  {name} ({label})...")
        reset(sh)
        sr(sh, f'create vnic-templ {name}', 1)
        sr(sh, f'set fabric {fabric}', 1)
        sr(sh, 'set target adapter', 1)
        sr(sh, 'set templtype updating-templ', 1)
        sr(sh, f'set mtu {mtu}', 1)
        sr(sh, f'set mac-pool {mac_pool}', 1)
        sr(sh, 'set nw-ctrl-policy hg-netcon', 1)
        sr(sh, 'set qos-policy hg-qos-be', 1)
        sr(sh, f'set descr "HumbledGeeks {name} {label}"', 1)
        for v in vlans:
            sr(sh, f'create eth-if {v}', 1)
            if v == native:
                sr(sh, 'set default-net yes', 1)
            sr(sh, 'exit', 1)
        safe_commit(sh)

    # vmnic0/1 - Management trunk (A/B) MTU 1500
    make_vnic('hg-vmnic0','a','hg-mac-a',1500,'Fabric-A Management',
              ['default','dc3-mgmt','dc3-vmotion','dc3-apps','dc3-nfs'],'default')
    make_vnic('hg-vmnic1','b','hg-mac-b',1500,'Fabric-B Management',
              ['default','dc3-mgmt','dc3-vmotion','dc3-apps','dc3-nfs'],'default')

    # vmnic2/3 - vMotion dedicated (A/B) jumbo MTU
    make_vnic('hg-vmnic2','a','hg-mac-a',9000,'Fabric-A vMotion',
              ['dc3-vmotion'],'dc3-vmotion')
    make_vnic('hg-vmnic3','b','hg-mac-b',9000,'Fabric-B vMotion',
              ['dc3-vmotion'],'dc3-vmotion')

    # vmnic4/5 - iSCSI dedicated (A/B) jumbo MTU
    make_vnic('hg-vmnic4','a','hg-mac-a',9000,'Fabric-A iSCSI-A',
              ['dc3-iscsi-a'],'dc3-iscsi-a')
    make_vnic('hg-vmnic5','b','hg-mac-b',9000,'Fabric-B iSCSI-B',
              ['dc3-iscsi-b'],'dc3-iscsi-b')


# ──────────────────────────────────────────────────────────────────
# PHASE 5 ─ vHBA Templates (2: vmhba0/1, Initial type)
# NOTE: Requires VSANs hg-vsan-a (10) and hg-vsan-b (11).
#       If VSANs don't exist, commit will warn - create via UCSM GUI first.
# ──────────────────────────────────────────────────────────────────
def phase5_vhba_templates(sh):
    print("\n=== PHASE 5: vHBA Templates ===")
    print("  NOTE: Requires VSANs hg-vsan-a/hg-vsan-b - will warn if missing")

    def make_vhba(name, fabric, wwpn_pool, vsan_name, label):
        print(f"  {name} ({label})...")
        reset(sh)
        sr(sh, f'create vhba-templ {name}', 1)
        sr(sh, f'set fabric {fabric}', 1)
        sr(sh, 'set target adapter', 1)
        sr(sh, 'set templtype initial-templ', 1)
        sr(sh, 'set max-data-field-size 2048', 1)
        sr(sh, f'set wwpn-pool {wwpn_pool}', 1)
        sr(sh, f'set descr "HumbledGeeks {name} {label}"', 1)
        sr(sh, f'create fc-if {vsan_name}', 1)
        sr(sh, 'exit', 1)
        safe_commit(sh)

    make_vhba('hg-vmhba0','a','hg-wwpn-a','hg-vsan-a','Fabric-A VSAN-10')
    make_vhba('hg-vmhba1','b','hg-wwpn-b','hg-vsan-b','Fabric-B VSAN-11')


# ──────────────────────────────────────────────────────────────────
# PHASE 6 ─ Service Profile Template
# ──────────────────────────────────────────────────────────────────
def phase6_spt(sh):
    print("\n=== PHASE 6: Service Profile Template ===")
    reset(sh)
    sr(sh, 'create service-profile hg-esx-template', 1)
    sr(sh, 'set type updating-template', 1)
    sr(sh, 'set descr "HumbledGeeks ESXi SPT workbook design"', 1)
    sr(sh, 'set bios-policy-name hg-bios', 1)
    sr(sh, 'set boot-policy-name hg-boot', 1)
    sr(sh, 'set maint-policy-name hg-maint', 1)
    sr(sh, 'set local-disk-policy-name hg-local-disk', 1)
    sr(sh, 'set power-policy-name hg-power', 1)
    sr(sh, 'set vcon-policy-name hg-vcon', 1)
    sr(sh, 'set uuid-pool hg-uuid-pool', 1)
    sr(sh, 'set wwnn-pool hg-wwnn-pool', 1)
    # vNICs bound to updating templates
    for vnic, tmpl, order in [
        ('vmnic0','hg-vmnic0',1), ('vmnic1','hg-vmnic1',2),
        ('vmnic2','hg-vmnic2',3), ('vmnic3','hg-vmnic3',4),
        ('vmnic4','hg-vmnic4',5), ('vmnic5','hg-vmnic5',6),
    ]:
        sr(sh, f'create vnic {vnic}', 1)
        sr(sh, f'set nw-templ-name {tmpl}', 1)
        sr(sh, 'set adapter-policy VMWare', 1)
        sr(sh, f'set order {order}', 1)
        sr(sh, 'exit', 1)
    # vHBAs bound to initial templates
    for vhba, tmpl, order in [
        ('vmhba0','hg-vmhba0',7), ('vmhba1','hg-vmhba1',8)
    ]:
        sr(sh, f'create vhba {vhba}', 1)
        sr(sh, f'set san-templ-name {tmpl}', 1)
        sr(sh, f'set order {order}', 1)
        sr(sh, 'exit', 1)
    safe_commit(sh)


# ──────────────────────────────────────────────────────────────────
# Log + Main
# ──────────────────────────────────────────────────────────────────
def write_log():
    with open(LOG, 'w') as f:
        f.write("UCSM HumbledGeeks Creation Log v2\n")
        f.write("=" * 70 + "\n\n")
        for r in results:
            f.write(f"CMD: {r['cmd']}\n")
            f.write(f"OUT: {r['resp']}\n")
            f.write("-" * 70 + "\n")
    print(f"\nDetailed log: {LOG}")


def main():
    print(f"Connecting to UCSM at {HOST}...")
    client, sh = connect()
    print("Connected.\n")
    try:
        phase1_org(sh)
        phase2_pools(sh)
        phase3_policies(sh)
        phase4_vnic_templates(sh)
        phase5_vhba_templates(sh)
        phase6_spt(sh)
    except Exception as e:
        print(f"\n[FATAL] {e}")
    finally:
        try:
            client.close()
        except Exception:
            pass
        write_log()

    print("\n" + "=" * 70)
    print("  CREATION COMPLETE")
    print("=" * 70)
    print(f"  Commands run  : {len(results)}")
    print(f"  Warnings/Errs : {len(warnings)}")
    if warnings:
        print("\n  Items needing manual review:")
        for w in warnings:
            print(f"    CMD: {w['cmd']}")
            print(f"    OUT: {w['resp'][:150]}")
            print()


if __name__ == '__main__':
    main()
