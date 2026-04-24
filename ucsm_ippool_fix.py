#!/usr/bin/env python3
"""
Fix hg-ext-mgmt IP pool block — probe scope block + try all subnet formats.
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
    tag = '[WARN]' if bad else '[OK]  '
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
    else:
        print(f'  [OK]   commit-buffer')
        results.append({'cmd': 'commit-buffer', 'resp': resp, 'ok': True})
        return True

def top(sh):
    sh.send('top\n'); time.sleep(FAST); drain(sh)

def hg_ip_pool(sh):
    top(sh)
    sr(sh, 'scope org /', FAST)
    sr(sh, 'scope org HumbledGeeks', FAST)
    sr(sh, 'scope ip-pool hg-ext-mgmt', FAST)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, look_for_keys=False, allow_agent=False)
sh = ssh.invoke_shell(width=200, height=50)
time.sleep(2); drain(sh)
print('Connected.')

FROM_IP = '10.103.12.180'
TO_IP   = '10.103.12.188'
SUBNET  = '255.255.255.0'
GW      = '10.103.12.1'

# ─────────────────────────────────────────────────────────────────────────────
# 1. Check if block already exists; delete it if so (clean slate)
# ─────────────────────────────────────────────────────────────────────────────
print('\n=== Step 1: Clean up any existing block ===')
hg_ip_pool(sh)
r = sr(sh, 'show block detail', SLOW, 'show block detail')
print(f'  Existing blocks:\n{r}\n')

# Try to scope into the block
r2 = sr(sh, f'scope block {FROM_IP} {TO_IP}', FAST, f'scope block {FROM_IP} {TO_IP}')
if 'error' not in r2.lower() and 'invalid' not in r2.lower():
    print('  Block scope entered — probing set ?')
    sh.send('set ?\n'); time.sleep(SLOW)
    probe = drain(sh).strip()
    print(f'  set ? inside block scope:\n{probe}\n')
    # Try setting subnet + gw from inside block scope
    sr(sh, f'set subnet {SUBNET}', FAST, 'set subnet from block scope')
    sr(sh, f'set default-gw {GW}', FAST, 'set default-gw from block scope')
    if safe_commit(sh):
        print('  ✅ Block subnet/gw set from block scope!')
    else:
        print('  ❌ Still failing from block scope')
        hg_ip_pool(sh)
        sr(sh, f'delete block {FROM_IP} {TO_IP}', SLOW, 'delete existing block')
        safe_commit(sh)
else:
    print('  No existing block to scope into, proceeding to create.')
    sr(sh, 'discard-buffer', FAST)

# ─────────────────────────────────────────────────────────────────────────────
# 2. Probe create block ? to see full parameter list
# ─────────────────────────────────────────────────────────────────────────────
print('\n=== Step 2: Probe create block ? ===')
hg_ip_pool(sh)
sh.send(f'create block {FROM_IP} {TO_IP} ?\n'); time.sleep(SLOW)
probe = drain(sh).strip()
print(f'  create block <from> <to> ?:\n{probe}\n')
sr(sh, 'discard-buffer', FAST)

# ─────────────────────────────────────────────────────────────────────────────
# 3. Try create block with gateway FIRST (different order)
# ─────────────────────────────────────────────────────────────────────────────
print('\n=== Step 3: Try gateway-first order ===')
hg_ip_pool(sh)
r = sr(sh, f'create block {FROM_IP} {TO_IP} {GW} {SUBNET}', SLOW, 'create block gw-first')
if safe_commit(sh):
    print('  ✅ Block created with gateway-first order!')
else:
    print('  ❌ gateway-first failed too, trying subnet-first...')
    hg_ip_pool(sh)
    r = sr(sh, f'create block {FROM_IP} {TO_IP} {SUBNET} {GW}', SLOW, 'create block subnet-first')
    if safe_commit(sh):
        print('  ✅ Block created with subnet-first order!')
    else:
        # ─────────────────────────────────────────────────────────────────
        # 4. Fallback: create block from/to only, then scope in and set
        # ─────────────────────────────────────────────────────────────────
        print('\n=== Step 4: Create block from/to only, then set inside scope ===')
        hg_ip_pool(sh)
        sr(sh, f'create block {FROM_IP} {TO_IP}', SLOW, 'create block no-subnet')
        safe_commit(sh)
        # Now scope into the block
        hg_ip_pool(sh)
        sr(sh, f'scope block {FROM_IP} {TO_IP}', FAST, 'scope into new block')
        sh.send('set ?\n'); time.sleep(SLOW)
        p2 = drain(sh).strip()
        print(f'  set ? in new block scope:\n{p2}\n')
        sr(sh, f'set subnet {SUBNET}', FAST, 'set subnet in block scope')
        sr(sh, f'set default-gw {GW}', FAST, 'set gw in block scope')
        safe_commit(sh)

# ─────────────────────────────────────────────────────────────────────────────
# 5. VERIFY
# ─────────────────────────────────────────────────────────────────────────────
print('\n=== VERIFY ===')
hg_ip_pool(sh)
r = sr(sh, 'show block detail', SLOW, 'final verify block')
print(f'\n{r}\n')

# Also verify the pool itself shows a size
top(sh)
sr(sh, 'scope org /', FAST)
sr(sh, 'scope org HumbledGeeks', FAST)
r2 = sr(sh, 'show ip-pool hg-ext-mgmt detail', SLOW, 'final verify pool')
print(f'\n{r2}\n')

top(sh)
ssh.close()

ok   = sum(1 for r in results if r['ok'])
warn = sum(1 for r in results if not r['ok'])
print(f'\n=== DONE  OK:{ok}  WARN:{warn} ===')
if warn:
    for r in results:
        if not r['ok']:
            print(f'  WARN: {repr(r["cmd"][:60])}')
