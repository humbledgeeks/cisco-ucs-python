#!/usr/bin/env python3
"""
Fix vHBA template VSAN binding.
- hg-vmhba0: delete vnic-fc-if default, create vnic-fc-if hg-vsan-a
- hg-vmhba1: delete vnic-fc-if default, create vnic-fc-if hg-vsan-b
"""
import paramiko, time, sys

HOST = '10.103.12.20'
USER = 'admin'
PASS = 'HybridAdm1n&&'
FAST = 1.0
SLOW = 2.5

results = []

def drain(sh, pause=0.5):
    time.sleep(pause)
    buf = ''
    while sh.recv_ready():
        buf += sh.recv(65535).decode('utf-8', errors='replace')
        time.sleep(0.15)
    return buf

def sr(sh, cmd, delay=SLOW, label=None):
    sh.send(cmd + '\n')
    time.sleep(delay)
    resp = drain(sh).strip()
    bad = any(x in resp for x in ['Error','error','Invalid','invalid','Failed','failed','Ambiguous','ambiguous'])
    lbl = label or repr(cmd[:60])
    results.append({'cmd': cmd, 'resp': resp, 'ok': not bad})
    if bad:
        print(f'  [WARN] {lbl}')
        for ln in resp.split('\n'):
            ln = ln.strip()
            if ln and not ln.startswith('dc3-fi'):
                print(f'         >> {ln}')
    else:
        print(f'  [OK]   {lbl}')
    sys.stdout.flush()
    return resp

def safe_commit(sh):
    sh.send('commit-buffer\n')
    time.sleep(SLOW * 2)
    resp = drain(sh).strip()
    bad = any(x in resp for x in ['Error','error','Invalid','invalid','Failed','failed'])
    if bad:
        print(f'  [WARN] commit-buffer')
        for ln in resp.split('\n'):
            ln = ln.strip()
            if ln and not ln.startswith('dc3-fi'):
                print(f'         >> {ln}')
        sh.send('discard-buffer\n'); time.sleep(SLOW); drain(sh)
        print(f'  [OK]   discard-buffer [recovery]')
        results.append({'cmd': 'commit-buffer', 'resp': resp, 'ok': False})
        return False
    print(f'  [OK]   commit-buffer')
    results.append({'cmd': 'commit-buffer', 'resp': resp, 'ok': True})
    return True

def top(sh):
    sh.send('top\n'); time.sleep(FAST); drain(sh)

def hg_org(sh):
    top(sh)
    sr(sh, 'scope org /', FAST)
    sr(sh, 'scope org HumbledGeeks', FAST)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, look_for_keys=False, allow_agent=False)
sh = ssh.invoke_shell(width=200, height=50)
time.sleep(2); drain(sh)
print('Connected.')

# ─────────────────────────────────────────────────────────────────────────────
# Fix each vHBA template: replace the placeholder vnic-fc-if with the real VSAN
# ─────────────────────────────────────────────────────────────────────────────
templates = [
    ('hg-vmhba0', 'hg-vsan-a'),
    ('hg-vmhba1', 'hg-vsan-b'),
]

for tmpl, vsan in templates:
    print(f'\n=== {tmpl} → {vsan} ===')
    hg_org(sh)
    sr(sh, f'scope vhba-templ {tmpl}', FAST)

    # Show what vnic-fc-if children currently exist
    r = sr(sh, 'show vnic-fc-if detail', SLOW, 'show vnic-fc-if detail')
    print(f'  Current vnic-fc-if:\n{r}\n')

    # Probe: what's the exact existing object name?
    # Try deleting 'default' — the RN seen in the error
    sr(sh, 'delete vnic-fc-if default', SLOW, f'delete vnic-fc-if default')

    # Create the correct VSAN binding
    sr(sh, f'create vnic-fc-if {vsan}', SLOW, f'create vnic-fc-if {vsan}')

    if not safe_commit(sh):
        print(f'  Commit failed — trying alternate: scope + set name')
        hg_org(sh)
        sr(sh, f'scope vhba-templ {tmpl}', FAST)
        # Try rename approach instead
        sr(sh, 'scope vnic-fc-if default', FAST)
        sr(sh, f'set name {vsan}', FAST, f'set name {vsan}')
        safe_commit(sh)

# ─────────────────────────────────────────────────────────────────────────────
# VERIFY
# ─────────────────────────────────────────────────────────────────────────────
print('\n=== VERIFY ===')
for tmpl, vsan in templates:
    hg_org(sh)
    sr(sh, f'scope vhba-templ {tmpl}', FAST)
    r = sr(sh, 'show vnic-fc-if detail', SLOW, f'verify {tmpl}')
    print(f'\n  {tmpl} vnic-fc-if:\n{r}\n')
    r2 = sr(sh, 'show detail', SLOW, f'show detail {tmpl}')
    # Just grab the VSAN line
    for ln in r2.split('\n'):
        if 'vsan' in ln.lower() or 'fabric' in ln.lower() or 'type' in ln.lower():
            print(f'    {ln.strip()}')

top(sh)
ssh.close()

ok   = sum(1 for r in results if r['ok'])
warn = sum(1 for r in results if not r['ok'])
print(f'\n=== DONE  OK:{ok}  WARN:{warn} ===')
if warn:
    for r in results:
        if not r['ok']:
            print(f'  WARN: {repr(r["cmd"][:60])}')
