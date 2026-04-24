#!/usr/bin/env python3
"""Comprehensive as-built audit — HumbledGeeks UCS Manager."""
import requests, urllib3, re, json
urllib3.disable_warnings()
HOST='10.103.12.20'; USER='admin'; PASSWD='HybridAdm1n&&'
ORG='org-root/org-HumbledGeeks'; BASE=f'https://{HOST}/nuova'

def post(xml): return requests.post(BASE,data=xml,verify=False,timeout=15).text
def resolve(ck,dn,hier='false'): return post(f'<configResolveDn cookie="{ck}" dn="{dn}" inHierarchical="{hier}"/>')
def rclass(ck,cls): return post(f'<configResolveClass cookie="{ck}" classId="{cls}" inHierarchical="false"/>')
def children(ck,dn,hier='true'): return post(f'<configResolveChildren cookie="{ck}" inDn="{dn}" inHierarchical="{hier}"/>')
def a(xml,name): m=re.search(rf'{name}="([^"]*)"',xml); return m.group(1) if m else ''
def all_attrs(xml): return dict(re.findall(r'(\w+)="([^"]*)"',xml))

resp=post(f'<aaaLogin inName="{USER}" inPassword="{PASSWD}"/>'); ck=re.search(r'outCookie="([^"]+)"',resp).group(1)
print(f'[+] Connected to UCSM {HOST}\n')

SEP='='*65
print(SEP); print('IDENTITY POOLS'); print(SEP)

# MAC pools
for r in re.finditer(r'<macpoolPool ([^>]+?)/>', rclass(ck,'macpoolPool')):
    d=all_attrs(r.group(1))
    if 'hg-' in d.get('name',''):
        blks=re.findall(r'from="([^"]+)"[^>]+to="([^"]+)"',children(ck,d['dn']))
        print(f"  MAC   {d['name']:30s} size={d.get('size','?'):3s}  blocks={blks}")

# UUID pool
for r in re.finditer(r'<uuidpoolPool ([^>]+?)/>', rclass(ck,'uuidpoolPool')):
    d=all_attrs(r.group(1))
    if 'hg-' in d.get('name',''):
        blks=re.findall(r'from="([^"]+)"[^>]+to="([^"]+)"',children(ck,d['dn']))
        print(f"  UUID  {d['name']:30s} size={d.get('size','?'):3s}  blocks={blks}")

# WWN pools
for r in re.finditer(r'<fcpoolInitiators ([^>]+?)/>', rclass(ck,'fcpoolInitiators')):
    d=all_attrs(r.group(1))
    if 'hg-' in d.get('name',''):
        blks=re.findall(r'from="([^"]+)"[^>]+to="([^"]+)"',children(ck,d['dn']))
        print(f"  WWN   {d['name']:30s} size={d.get('size','?'):3s}  blocks={blks}")

# IP pool
for r in re.finditer(r'<ippoolPool ([^>]+?)/>', rclass(ck,'ippoolPool')):
    d=all_attrs(r.group(1))
    if 'hg-' in d.get('name',''):
        ch=children(ck,d['dn'])
        blks=re.findall(r'from="([^"]+)"[^>]+gateway="([^"]+)"[^>]+subnet="([^"]+)"[^>]+to="([^"]+)"',ch)
        print(f"  IP    {d['name']:30s} size={d.get('size','?'):3s}  {blks}")

print(f'\n{SEP}'); print('VLANs (HumbledGeeks + fabric-wide)'); print(SEP)
for r in re.finditer(r'<fabricVlan ([^>]+?)/>', rclass(ck,'fabricVlan')):
    d=all_attrs(r.group(1))
    if 'dc3-' in d.get('name','') or d.get('id','') in ('1',):
        print(f"  VLAN {d.get('id','?'):5s}  {d.get('name','?'):25s}  mtu={d.get('defaultNet','?')}  dn={d.get('dn','?').split('/')[-1]}")

print(f'\n{SEP}'); print('VSANs'); print(SEP)
for r in re.finditer(r'<fabricVsan ([^>]+?)/>', rclass(ck,'fabricVsan')):
    d=all_attrs(r.group(1))
    if 'hg-' in d.get('name',''):
        # Get member ports
        mems=re.findall(r'dn="([^"]+)"',children(ck,d['dn']))
        ports=[m.split('/')[-1] for m in mems if 'member' in m or 'phys' in m]
        print(f"  VSAN {d.get('id','?'):5s}  {d.get('name','?'):20s}  fabric={d.get('dn','?').split('/')[2]}  members={len(ports)}")

print(f'\n{SEP}'); print('PORT CHANNELS'); print(SEP)
for r in re.finditer(r'<fabricEthLanPc ([^>]+?)/>', rclass(ck,'fabricEthLanPc')):
    d=all_attrs(r.group(1))
    ports=re.findall(r'portId="([^"]+)"',children(ck,d['dn']))
    print(f"  PC{d.get('portId','?'):3s}  fabric={d.get('switchId','?')}  oper={d.get('operState','?'):10s}  speed={d.get('operSpeed','?'):8s}  members={sorted(ports)}")

print(f'\n{SEP}'); print('vNIC TEMPLATES'); print(SEP)
for r in re.finditer(r'<vnicLanConnTempl ([^>]+?)/?>', rclass(ck,'vnicLanConnTempl')):
    d=all_attrs(r.group(1))
    if 'hg-' in d.get('name',''):
        ch=children(ck,d['dn'],hier='false')
        vlans=sorted(re.findall(r'name="([^"]+)"',ch))
        native=[v for v in re.findall(r'defaultNet="yes"[^>]+name="([^"]+)"',ch)]
        print(f"  {d['name']:15s} fab={d.get('switchId','?')} mtu={d.get('mtu','?'):4s} "
              f"templ={d.get('templType','?'):20s} nwctrl={d.get('nwCtrlPolicyName','?')}")
        print(f"    VLANs : {vlans}")
        print(f"    Native: {native}")

print(f'\n{SEP}'); print('vHBA TEMPLATES'); print(SEP)
for r in re.finditer(r'<vnicSanConnTempl ([^>]+?)/?>', rclass(ck,'vnicSanConnTempl')):
    d=all_attrs(r.group(1))
    if 'hg-' in d.get('name',''):
        ch=children(ck,d['dn'],hier='false')
        vsan=re.findall(r'name="([^"]+)"',ch)
        print(f"  {d['name']:15s} fab={d.get('switchId','?')} "
              f"adapter={d.get('adaptorProfileName','(none)'):10s} "
              f"maxdata={d.get('maxDataFieldSize','?')} "
              f"templ={d.get('templType','?')}  vsan={vsan}")

print(f'\n{SEP}'); print('POLICIES'); print(SEP)

r=resolve(ck,f'{ORG}/nwctrl-hg-netcon'); d=all_attrs(r)
print(f"  NetCtrl  hg-netcon   cdp={d.get('cdp')} lldpTx={d.get('lldpTransmit')} lldpRx={d.get('lldpReceive')} uplinkFail={d.get('uplinkFailAction')}")

r=resolve(ck,f'{ORG}/maint-hg-maint'); d=all_attrs(r)
print(f"  Maint    hg-maint    uptimeDisr={d.get('uptimeDisr')} dataDisr={d.get('dataDisr')}")

r=resolve(ck,f'{ORG}/local-disk-config-hg-local-disk'); d=all_attrs(r)
print(f"  LocalDsk hg-local-disk  mode={d.get('mode')} flexFlashState={d.get('flexFlashState')} flexFlashRAID={d.get('flexFlashRAIDReportingState')}")

r=resolve(ck,f'{ORG}/boot-policy-hg-flexflash',hier='true')
print(f"  Boot     hg-flexflash   bootMode={a(r,'bootMode')}")
entries=[]
for cls,lbl in [('lsbootVirtualMedia','DVD'),('lsbootEmbeddedLocalDiskImage','SSD'),('lsbootUsbFlashStorageImage','FlexFlash SD')]:
    for m in re.finditer(rf'<{cls}[^>]+>',r):
        ad=all_attrs(m.group(0)); entries.append((int(ad.get('order',99)),lbl,ad.get('rn','?')))
for o,l,rn in sorted(entries): print(f"    [{o}] {l:20s} rn={rn}")

r=resolve(ck,f'{ORG}/power-policy-hg-power'); d=all_attrs(r)
print(f"  Power    hg-power    prio={d.get('prio')}")

r=resolve(ck,f'{ORG}/bios-prof-hg-bios'); d=all_attrs(r)
print(f"  BIOS     hg-bios     dn={d.get('dn','not found')}")

print(f'\n{SEP}'); print('SERVICE PROFILE TEMPLATE'); print(SEP)
r=resolve(ck,f'{ORG}/ls-hg-esx-template'); d=all_attrs(r)
for k in ['name','type','bootPolicyName','maintPolicyName','localDiskPolicyName',
          'powerPolicyName','biosProfileName','extIPState','extIPPoolName',
          'identPoolName','nodeWwnPoolName']:
    print(f"  {k:30s}: {d.get(k,'(not set)')}")

print(f'\n{SEP}'); print('BLADES / CHASSIS'); print(SEP)
for r in re.finditer(r'<computeBlade ([^>]+?)/>', rclass(ck,'computeBlade')):
    d=all_attrs(r.group(1))
    print(f"  Blade {d.get('serverId','?'):5s}  model={d.get('model','?'):20s}  "
          f"memory={d.get('totalMemory','?')}MB  cores={d.get('numOfCpus','?')}x{d.get('numOfCores','?')}  "
          f"assoc={d.get('assignedToDn','(none)').split('/')[-1] or '(none)'}")

print(f'\n{SEP}'); print('NTP'); print(SEP)
for dn in [f'sys/svc-ext/datetime-svc', f'{ORG}/comm-pol-system/datetime-svc']:
    ch=children(ck,dn,hier='false')
    servers=re.findall(r'name="([^"]+)"',ch)
    print(f"  {dn.split('/')[-2]:20s}: {servers}")

print(f'\n{SEP}'); print('ACTIVE FAULTS (unacked, non-cleared)'); print(SEP)
faults=[]
for f in re.finditer(r'<faultInst ([^>]+?)/>', rclass(ck,'faultInst')):
    d=all_attrs(f.group(1))
    if d.get('severity','') in ('critical','major','minor') and d.get('ack','')!='yes':
        faults.append(d)
if faults:
    for d in sorted(faults,key=lambda x:x.get('severity','')):
        print(f"  [{d.get('severity'):8s}] {d.get('code','?')} {d.get('descr','?')[:70]}")
else:
    print("  No unacknowledged active faults  ✓")

post(f'<aaaLogout inCookie="{ck}"/>'); print('\n[+] Audit complete')
