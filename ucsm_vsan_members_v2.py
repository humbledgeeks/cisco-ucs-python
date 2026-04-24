#!/usr/bin/env python3
"""
ucsm_vsan_members_v2.py
Correct syntax confirmed: create member-port fc <slot> <port>
  1. hg-vsan-a (Fabric A) ← ports 29-32
  2. hg-vsan-b (Fabric B) ← ports 29-32
  3. vHBA template fc-if binding (retry now ports are in VSAN)
  4. CDP/LLDP final attempt
  5. Full verification
"""
import paramiko, time

HOST='10.103.12.20'; USER='admin'; PASS='HybridAdm1n&&'
SLOW=2.5; FAST=0.8; COMMIT=4.5

results=[]

def drain(sh, rounds=4, pause=0.4):
    buf=b''
    for _ in range(rounds):
        time.sleep(pause)
        while sh.recv_ready(): buf+=sh.recv(65535)
    return buf.decode('utf-8','replace')

def connect():
    c=paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST,username=USER,password=PASS,timeout=20)
    sh=c.invoke_shell(width=300,height=9000)
    time.sleep(2); drain(sh)
    return c,sh

def sr(sh,cmd,delay=SLOW,label=None):
    sh.send(cmd+'\n'); time.sleep(delay)
    resp=drain(sh).strip()
    bad=any(x in resp for x in ['Error','error','Invalid','invalid','Failed','failed'])
    tag='[WARN]' if bad else '[OK]  '
    results.append({'cmd':cmd,'resp':resp,'ok':not bad})
    print(f"  {tag} {label or cmd!r}")
    if bad:
        for line in resp.splitlines():
            if any(x in line for x in ['Error','error','Invalid','invalid','Failed']):
                print(f"         >> {line.strip()}")
    return resp, not bad

def safe_commit(sh):
    _,ok=sr(sh,'commit-buffer',COMMIT,'commit-buffer')
    if not ok: sr(sh,'discard-buffer',FAST,'discard-buffer [recovery]')
    return ok

def discard(sh): sr(sh,'discard-buffer',FAST,'discard-buffer')

def hg_org(sh):
    sr(sh,'top',FAST); sr(sh,'scope org /',FAST)
    sr(sh,'scope org HumbledGeeks',FAST)

def scope_storage_vsan(sh, fab, vsan):
    sr(sh,'top',FAST); sr(sh,'scope fc-storage',FAST)
    sr(sh,f'scope fabric {fab}',FAST)
    return sr(sh,f'scope vsan {vsan}',FAST)

def main():
    print(f"Connecting to {HOST} ...")
    client,sh=connect(); print("Connected.\n")
    try:
        # ── FIX 1: VSAN member ports ──────────────────────────────────────────
        print("=== FIX 1: Add FC Storage Ports as VSAN Members ===")
        # Syntax confirmed: create member-port fc <slot> <port>
        vsan_ports = [
            ('a', 'hg-vsan-a', [29,30,31,32]),
            ('b', 'hg-vsan-b', [29,30,31,32]),
        ]
        for fab, vsan, ports in vsan_ports:
            print(f"\n  -- {vsan} Fabric {fab.upper()} ← ports {ports} --")
            _,ok = scope_storage_vsan(sh, fab, vsan)
            if not ok:
                discard(sh); continue
            for port in ports:
                sr(sh, f'create member-port fc 1 {port}', FAST, f'member-port fc 1/{port}')
            if safe_commit(sh):
                print(f"  [SUCCESS] {vsan} member ports committed")
            else:
                print(f"  [WARN] {vsan} member-port commit failed — ports may not exist on this FI")

        # ── Show VSAN membership after commit ─────────────────────────────────
        print("\n  VSAN membership state:")
        for fab, vsan in [('a','hg-vsan-a'),('b','hg-vsan-b')]:
            _,ok = scope_storage_vsan(sh, fab, vsan)
            if ok:
                sh.send('show member-port\n'); time.sleep(3)
                print(f"\n  {vsan}:\n{drain(sh,rounds=4)}")
            discard(sh)

        # ── FIX 2: vHBA template fc-if binding ───────────────────────────────
        print("\n=== FIX 2: vHBA Template VSAN Binding ===")
        for tmpl,vsan in [('hg-vmhba0','hg-vsan-a'),('hg-vmhba1','hg-vsan-b')]:
            print(f"\n  -- {tmpl} → {vsan} --")
            hg_org(sh)
            sr(sh,f'scope vhba-templ {tmpl}',FAST)
            _,ok=sr(sh,f'set fc-if {vsan}',FAST)
            if ok and safe_commit(sh):
                print(f"  [SUCCESS] {tmpl} → {vsan}")
            else:
                discard(sh)
                print(f"  [GUI] SAN → Policies → HumbledGeeks → vHBA Templates → {tmpl} → VSAN → {vsan}")

        # ── FIX 3: CDP/LLDP ──────────────────────────────────────────────────
        print("\n=== FIX 3: CDP/LLDP ===")
        cdp_fixed = False
        for cmds in [['set cdp enabled'],['set cdp enable'],
                     ['set lldp-receive enabled','set lldp-transmit enabled']]:
            hg_org(sh)
            sr(sh,'scope nw-ctrl-policy hg-netcon',FAST)
            if all(sr(sh,c,FAST)[1] for c in cmds) and safe_commit(sh):
                print(f"  [SUCCESS] {cmds}"); cdp_fixed=True; break
            discard(sh)
        if not cdp_fixed:
            print("  [GUI] LAN → Policies → HumbledGeeks → Network Control Policies → hg-netcon")
            print("        Enable: CDP Enabled, LLDP Transmit, LLDP Receive → Save")

        # ── VERIFY ────────────────────────────────────────────────────────────
        print("\n=== FINAL VERIFICATION ===")
        for fab in ['a','b']:
            sr(sh,'top',FAST); sr(sh,'scope fc-storage',FAST)
            sr(sh,f'scope fabric {fab}',FAST)
            sh.send('show vsan detail\n'); time.sleep(4)
            vsan_out=drain(sh,rounds=5)
            print(f"\n  Storage Fabric {fab.upper()} VSANs:\n{vsan_out}")
            discard(sh)

        hg_org(sh)
        sh.send('show vhba-templ detail\n'); time.sleep(4)
        print(f"\n  vHBA Templates:\n{drain(sh,rounds=5)[:1500]}")

        hg_org(sh)
        sh.send('show nw-ctrl-policy detail\n'); time.sleep(3)
        print(f"\n  NW Ctrl Policy:\n{drain(sh,rounds=4)}")

    finally:
        client.close()
        ok_c=sum(1 for r in results if r['ok'])
        warn_c=sum(1 for r in results if not r['ok'])
        print(f"\n=== DONE  Commands:{len(results)}  OK:{ok_c}  WARN:{warn_c} ===")
        if warn_c:
            print("Warnings:")
            for r in results:
                if not r['ok']: print(f"  {r['cmd']!r}")

if __name__=='__main__':
    main()
