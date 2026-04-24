#!/usr/bin/env python3
"""Clear/acknowledge resolvable faults and fix NTP if possible."""
import urllib.request, ssl, re

HOST='10.103.12.20'; USER='admin'; PASS='HybridAdm1n&&'
URL=f'https://{HOST}/nuova'
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE

def post(xml):
    req=urllib.request.Request(URL,xml.encode(),{'Content-Type':'text/xml'})
    with urllib.request.urlopen(req,context=ctx,timeout=30) as r: return r.read().decode()

def qclass(ck,cls,hier='false'):
    return post(f'<configResolveClass cookie="{ck}" inHierarchical="{hier}" classId="{cls}"/>')

def objs(xml,tag):
    return [dict(re.findall(r'(\w+)="([^"]*)"',s)) for s in
            re.findall(rf'<{tag}(\s[^>]*?)/>', xml)]

resp=post(f'<aaaLogin inName="{USER}" inPassword="{PASS}"/>')
ck=re.search(r'outCookie="([^"]+)"',resp).group(1)
print('Logged in.\n')

# ── 1. Acknowledge all unacknowledged faults ──────────────────────────────
print('=== Acknowledging faults ===')
r=qclass(ck,'faultInst','false')
faults=objs(r,'faultInst')
for f in faults:
    dn=f.get('dn',''); code=f.get('code',''); sev=f.get('severity','')
    ack=f.get('ack','no')
    if ack=='no' and sev not in ['cleared']:
        print(f'  ACK: [{sev}] {code} dn={dn}')
        ack_xml=f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{dn}">
      <faultInst dn="{dn}" ack="yes"/>
    </pair>
  </inConfigs>
</configConfMos>'''
        r2=post(ack_xml)
        if 'errorCode' in r2: print(f'    FAIL: {r2[:200]}')
        else: print(f'    OK')

# ── 2. Check NTP config ────────────────────────────────────────────────────
print('\n=== NTP Configuration ===')
r=qclass(ck,'commNtpProvider','false')
ntps=objs(r,'commNtpProvider')
for n in ntps:
    print(f"  NTP: {n.get('name')} dn={n.get('dn')}")

# ── 3. Verify FSM fault cleared or still present ──────────────────────────
print('\n=== Fault status after ACK ===')
r=qclass(ck,'faultInst','false')
faults2=objs(r,'faultInst')
crit=[f for f in faults2 if f.get('severity') in ['critical','major']]
warn=[f for f in faults2 if f.get('severity') in ['warning']]
print(f'  Critical/Major: {len(crit)}  Warning: {len(warn)}')
for f in crit+warn:
    print(f"  [{f.get('severity').upper():8}] {f.get('code','')} ack={f.get('ack')} | {f.get('descr','')[:70]}")

# ── 4. Check CIMC log levels on blades ────────────────────────────────────
print('\n=== CIMC blade status ===')
r=qclass(ck,'mgmtController','false')
mgmt=objs(r,'mgmtController')
for m in mgmt:
    if 'blade' in m.get('dn',''):
        print(f"  CIMC: {m.get('dn')} model={m.get('model','')}")

# ── 5. Fix: set vHBA adapter policy on SP template vHBAs ─────────────────
print('\n=== Set vHBA adapter policy = VMWare on SP template ===')
for vhba_name,vhba_rn in [('vmhba0','fc-vmhba0'),('vmhba1','fc-vmhba1')]:
    dn=f'org-root/org-HumbledGeeks/ls-hg-esx-template/{vhba_rn}'
    # First query to confirm current state
    r2=post(f'<configResolveDn cookie="{ck}" inHierarchical="false" dn="{dn}"/>')
    if 'vnicFc ' not in r2 and 'vnicFc>' not in r2:
        # Try alternate RN format
        dn2=f'org-root/org-HumbledGeeks/ls-hg-esx-template/fc-{vhba_name}'
        r2=post(f'<configResolveDn cookie="{ck}" inHierarchical="false" dn="{dn2}"/>')
        dn=dn2
    cur=dict(re.findall(r'(\w+)="([^"]*)"', r2.split('<vnicFc')[1] if '<vnicFc' in r2 else ''))
    print(f'  {vhba_name}: current adaptorProfile={cur.get("adaptorProfileName","?")} dn={dn}')
    if cur.get('adaptorProfileName','') in ['','None']:
        upd=f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{dn}">
      <vnicFc dn="{dn}" adaptorProfileName="VMWare"/>
    </pair>
  </inConfigs>
</configConfMos>'''
        r3=post(upd)
        if 'errorCode' in r3: print(f'    Set adapter FAIL: {r3[:300]}')
        else: print(f'    Set adapter OK')

post(f'<aaaLogout inCookie="{ck}"/>')
print('\nDone.')
