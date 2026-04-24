#!/usr/bin/env python3
"""Replace pool.ntp.org with internal NTP server 10.103.20.11."""
import urllib.request, ssl, re

HOST='10.103.12.20'; USER='admin'; PASS='HybridAdm1n&&'
URL=f'https://{HOST}/nuova'
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE

def post(xml):
    req=urllib.request.Request(URL,xml.encode(),{'Content-Type':'text/xml'})
    with urllib.request.urlopen(req,context=ctx,timeout=30) as r: return r.read().decode()

def qclass(ck,cls):
    return post(f'<configResolveClass cookie="{ck}" inHierarchical="false" classId="{cls}"/>')

def objs(xml,tag):
    return [dict(re.findall(r'(\w+)="([^"]*)"',s)) for s in re.findall(rf'<{tag}(\s[^>]*?)/>', xml)]

resp=post(f'<aaaLogin inName="{USER}" inPassword="{PASS}"/>')
ck=re.search(r'outCookie="([^"]+)"',resp).group(1)
print('Logged in.\n')

# Show current NTP
print('Current NTP servers:')
r=qclass(ck,'commNtpProvider')
ntps=objs(r,'commNtpProvider')
for n in ntps: print(f"  {n.get('dn')}  name={n.get('name')}")

# ── Remove old pool.ntp.org entries ───────────────────────────────────────
old_ntps = ['0.pool.ntp.org', '1.pool.ntp.org']
for name in old_ntps:
    for parent_dn in ['sys/svc-ext/datetime-svc', 'org-root/comm-pol-system/datetime-svc']:
        dn = f'{parent_dn}/ntp-{name}'
        print(f'\nDeleting: {dn}')
        r=post(f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{dn}">
      <commNtpProvider dn="{dn}" status="deleted"/>
    </pair>
  </inConfigs>
</configConfMos>''')
        if 'errorCode' in r: print(f'  WARN: {r[:200]}')
        else: print(f'  OK (deleted or not found)')

# ── Add internal NTP server ────────────────────────────────────────────────
new_ntp = '10.103.20.11'
print(f'\nAdding NTP server: {new_ntp}')
for parent_dn in ['sys/svc-ext/datetime-svc', 'org-root/comm-pol-system/datetime-svc']:
    dn = f'{parent_dn}/ntp-{new_ntp}'
    r=post(f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{dn}">
      <commNtpProvider dn="{dn}" name="{new_ntp}" descr="Internal NTP" rn="ntp-{new_ntp}" status="created,modified"/>
    </pair>
  </inConfigs>
</configConfMos>''')
    if 'errorCode' in r: print(f'  WARN adding to {parent_dn}: {r[:300]}')
    else: print(f'  OK added to {parent_dn}')

# ── Verify ────────────────────────────────────────────────────────────────
print('\nNTP servers after update:')
r=qclass(ck,'commNtpProvider')
for n in objs(r,'commNtpProvider'):
    print(f"  {n.get('dn')}  name={n.get('name')}")

post(f'<aaaLogout inCookie="{ck}"/>')
print('\nDone.')
