#!/usr/bin/env python3
"""
1. Show all VSANs across all scopes (fc-uplink A/B, fc-storage A/B)
2. Probe all commands in vhba-templ scope (set ?, scope ?, show ?)
3. Try correct CLI syntax to set VSAN on both vHBA templates
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
    sh.send(cmd + '\n'); time.sleep(delay)
    resp = drain(sh).strip()
    bad = any(x in resp for x in ['Error','error','Invalid','invalid','Failed','failed','Ambiguous','ambiguous'])
    lbl = label or repr(cmd[:60])
    results.append({'cmd': cmd, 'resp': resp, 'ok': not bad})
    if bad:
        print(f'  [WARN] {lbl}')
        for ln in resp.split('\n'):
            s = ln.strip()
            if s and not s.startswith('dc3-fi'): print(f'         >> {s}')
    else:
        print(f'  [OK]   {lbl}')
    sys.stdout.flush()
    return resp

def safe_commit(sh):
    sh.send('commit-buffer\n'); time.sleep(SLOW * 2)
    resp = drain(sh).strip()
    bad = any(x in resp for x in ['Error','error','Invalid','invalid','Failed','failed'])
    if bad:
        print('  [WARN] commit-buffer')
        for ln in resp.split('\n'):
            s = ln.strip()
            if s and not s.startswith('dc3-fi'): print(f'         >> {s}')
        sh.send('discard-buffer\n'); time.sleep(SLOW); drain(sh)
        print('  [OK]   discard-buffer [recovery]')
        results.append({'cmd': 'commit-buffer', 'resp': resp, 'ok': False})
        return False
    print('  [OK]   commit-buffer')
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

# ── 1. Show VSANs in ALL scopes ────────────────────────────────────────────
print('\n=== VSANs in fc-uplink A/B ===')
for fab in ['a', 'b']:
    top(sh)
    sr(sh, 'scope fc-uplink', FAST)
    sr(sh, f'scope fabric {fab}', FAST)
    r = sr(sh, 'show vsan detail', SLOW, f'fc-uplink fabric {fab} vsans')
    print(f'\n  fc-uplink fabric {fab}:\n{r}\n')

print('\n=== VSANs in fc-storage A/B ===')
for fab in ['a', 'b']:
    top(sh)
    sr(sh, 'scope fc-storage', FAST)
    sr(sh, f'scope fabric {fab}', FAST)
    r = sr(sh, 'show vsan detail', SLOW, f'fc-storage fabric {fab} vsans')
    print(f'\n  fc-storage fabric {fab}:\n{r}\n')

# ── 2. Probe vhba-templ scope commands ────────────────────────────────────
print('\n=== Probe vhba-templ hg-vmhba0 scope ===')
hg_org(sh)
sr(sh, 'scope vhba-templ hg-vmhba0', FAST)

# set ?
sh.send('set ?\n'); time.sleep(SLOW)
p = drain(sh).strip(); print(f'  set ?:\n{p}\n')

# scope ?
sh.send('scope ?\n'); time.sleep(SLOW)
p2 = drain(sh).strip(); print(f'  scope ?:\n{p2}\n')

# show ?
sh.send('show ?\n'); time.sleep(SLOW)
p3 = drain(sh).strip(); print(f'  show ?:\n{p3}\n')

# create ?
sh.send('create ?\n'); time.sleep(SLOW)
p4 = drain(sh).strip(); print(f'  create ?:\n{p4}\n')

# show detail to see current VSAN field
r = sr(sh, 'show detail', SLOW, 'vhba0 show detail')
print(f'\n  hg-vmhba0 detail:\n{r}\n')
sr(sh, 'discard-buffer', FAST)

# ── 3. Try fc-if scope  ───────────────────────────────────────────────────
print('\n=== Try scope fc-if default ===')
hg_org(sh)
sr(sh, 'scope vhba-templ hg-vmhba0', FAST)
r = sr(sh, 'scope fc-if default', FAST, 'scope fc-if default')
if '[OK]' in f'{"ok" if "error" not in r.lower() and "invalid" not in r.lower() else ""}':
    sh.send('set ?\n'); time.sleep(SLOW)
    p5 = drain(sh).strip(); print(f'  set ? inside fc-if:\n{p5}\n')
sr(sh, 'discard-buffer', FAST)

# ── 4. Try set fc-if-name / set vsan-ref / set fabric-if ─────────────────
print('\n=== Try various set commands for VSAN ===')
for attempt in ['set fc-if-name hg-vsan-a', 'set vsan-ref hg-vsan-a',
                'set fabric-if hg-vsan-a', 'set vsan hg-vsan-a',
                'set fc-if default hg-vsan-a']:
    hg_org(sh)
    sr(sh, 'scope vhba-templ hg-vmhba0', FAST)
    r = sr(sh, attempt, FAST, attempt)
    if 'ok' not in r.lower() and 'invalid' not in r.lower() and 'error' not in r.lower():
        print(f'  *** POSSIBLE HIT: {attempt}')
    sr(sh, 'discard-buffer', FAST)

top(sh); ssh.close()

ok   = sum(1 for r in results if r['ok'])
warn = sum(1 for r in results if not r['ok'])
print(f'\n=== DONE  OK:{ok}  WARN:{warn} ===')
