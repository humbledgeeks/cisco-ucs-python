#!/usr/bin/env python3
"""Comprehensive HumbledGeeks UCSM config audit for recommendations."""
import requests, urllib3, re, json
urllib3.disable_warnings()

HOST='10.103.12.20'; USER='admin'; PASSWD='HybridAdm1n&&'
ORG='org-root/org-HumbledGeeks'
BASE=f'https://{HOST}/nuova'

def post(xml):
    return requests.post(BASE, data=xml, verify=False, timeout=15).text

def resolve_class(ck, cls):
    return post(f'<configResolveClass cookie="{ck}" classId="{cls}" inHierarchical="false"/>')

def resolve_dn(ck, dn, hier="false"):
    return post(f'<configResolveDn cookie="{ck}" dn="{dn}" inHierarchical="{hier}"/>')

def children(ck, dn, hier="true"):
    return post(f'<configResolveChildren cookie="{ck}" inDn="{dn}" inHierarchical="{hier}"/>')

def attrs(xml, *names):
    return {n: (re.search(rf'{n}="([^"]*)"', xml) or [None,None])[1] for n in names}

resp = post(f'<aaaLogin inName="{USER}" inPassword="{PASSWD}"/>')
ck = re.search(r'outCookie="([^"]+)"', resp).group(1)
print(f"[+] Logged in\n")

print("=" * 60)
print("POOLS")
print("=" * 60)

# MAC pools
r = resolve_class(ck, "macpoolPool")
for m in re.finditer(r'<macpoolPool ([^/]+)/>', r):
    a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
    if 'HumbledGeeks' in a.get('dn','') or 'hg-' in a.get('name',''):
        blk = children(ck, a['dn'])
        blocks = re.findall(r'from="([^"]+)"[^>]+to="([^"]+)"', blk)
        print(f"  MAC  {a['name']:30s} size={a.get('size','?'):4s} blocks={blocks}")

# UUID pool
r = resolve_class(ck, "uuidpoolPool")
for m in re.finditer(r'<uuidpoolPool ([^/]+)/>', r):
    a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
    if 'hg-' in a.get('name','') or 'HumbledGeeks' in a.get('dn',''):
        print(f"  UUID {a['name']:30s} size={a.get('size','?'):4s} dn={a['dn']}")

# WWN pools
r = resolve_class(ck, "fcpoolInitiators")
for m in re.finditer(r'<fcpoolInitiators ([^/]+)/>', r):
    a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
    if 'hg-' in a.get('name',''):
        blk = children(ck, a['dn'])
        blocks = re.findall(r'from="([^"]+)"[^>]+to="([^"]+)"', blk)
        print(f"  WWN  {a['name']:30s} size={a.get('size','?'):4s} blocks={blocks}")

# IP pool
r = resolve_class(ck, "ippoolPool")
for m in re.finditer(r'<ippoolPool ([^/]+)/>', r):
    a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
    if 'hg-' in a.get('name',''):
        blk = children(ck, a['dn'])
        gw  = re.findall(r'from="([^"]+)"[^>]+gateway="([^"]+)"[^>]+subnet="([^"]+)"[^>]+to="([^"]+)"', blk)
        print(f"  IP   {a['name']:30s} size={a.get('size','?'):4s} blocks={gw}")

print("\n" + "=" * 60)
print("vNIC TEMPLATES")
print("=" * 60)
r = resolve_class(ck, "vnicLanConnTempl")
for m in re.finditer(r'<vnicLanConnTempl ([^>]+?)/?>', r):
    a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
    if 'hg-' in a.get('name',''):
        vlans_r = children(ck, a['dn'], hier="false")
        vlans = sorted(re.findall(r'name="([^"]+)"', vlans_r))
        dflt = re.findall(r'defaultNet="yes"[^>]+name="([^"]+)"', vlans_r) or \
               re.findall(r'name="([^"]+)"[^>]+defaultNet="yes"', vlans_r)
        print(f"  {a['name']:25s} fab={a.get('switchId','?')} mtu={a.get('mtu','?'):4s} "
              f"nwctrl={a.get('nwCtrlPolicyName','?')} pingrp={a.get('pinToBiD','?')}")
        print(f"    VLANs: {vlans}  native={dflt}")

print("\n" + "=" * 60)
print("vHBA TEMPLATES")
print("=" * 60)
r = resolve_class(ck, "vnicSanConnTempl")
for m in re.finditer(r'<vnicSanConnTempl ([^>]+?)/?>', r):
    a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
    if 'hg-' in a.get('name',''):
        fc_r = children(ck, a['dn'], hier="false")
        vsan = re.findall(r'name="([^"]+)"', fc_r)
        print(f"  {a['name']:25s} fab={a.get('switchId','?')} "
              f"adapter={a.get('adaptorProfileName','?')} "
              f"maxdata={a.get('maxDataFieldSize','?')} vsan={vsan}")

print("\n" + "=" * 60)
print("SERVICE PROFILE TEMPLATE")
print("=" * 60)
r = resolve_dn(ck, f"{ORG}/ls-hg-esx-template", hier="false")
a = dict(re.findall(r'(\w+)="([^"]*)"', r))
for k in ['name','type','bootPolicyName','maintPolicyName','powerPolicyName',
          'hostFwPolicyName','localDiskPolicyName','scrubPolicyName',
          'biosProfileName','statsPolicyName','extIPState','extIPPoolName']:
    print(f"  {k:30s}: {a.get(k,'(not set)')}")

print("\n" + "=" * 60)
print("POLICIES")
print("=" * 60)

# Network Control
r = resolve_dn(ck, f"{ORG}/nwctrl-hg-netcon")
a = dict(re.findall(r'(\w+)="([^"]*)"', r))
print(f"  NetCtrl hg-netcon: cdp={a.get('cdp')} lldpTx={a.get('lldpTransmit')} "
      f"lldpRx={a.get('lldpReceive')} uplinkFail={a.get('uplinkFailAction')}")

# Maintenance
r = resolve_dn(ck, f"{ORG}/maint-hg-maint")
a = dict(re.findall(r'(\w+)="([^"]*)"', r))
print(f"  Maint  hg-maint:  uptimeDisr={a.get('uptimeDisr')} dataDisr={a.get('dataDisr')}")

# Boot policy
r = resolve_dn(ck, f"{ORG}/boot-policy-hg-flexflash", hier="true")
has_local = 'lsbootDefaultLocalImage' in r
print(f"  Boot   hg-flexflash: local-any={'PRESENT' if has_local else 'MISSING'}")

# Check other policies referenced
for pol_type, pol_class in [
    ('localDiskPolicyName','lstorageDiskGroupConfigPolicy'),
    ('powerPolicyName',    'powerGroupPolicy'),
    ('biosProfileName',    'biosProfile'),
]:
    pol_name = dict(re.findall(r'(\w+)="([^"]*)"',
                    resolve_dn(ck,f"{ORG}/ls-hg-esx-template"))).get(pol_type,'')
    print(f"  {pol_type:30s}: '{pol_name}'")

print("\n" + "=" * 60)
print("ACTIVE FAULTS (non-cleared)")
print("=" * 60)
r = resolve_class(ck, "faultInst")
faults = re.findall(r'<faultInst ([^>]+?)/>', r)
for f in faults:
    a = dict(re.findall(r'(\w+)="([^"]*)"', f))
    if a.get('severity','') in ('critical','major','minor','warning') and a.get('ack','') != 'yes':
        tag = 'HG' if 'HumbledGeeks' in a.get('dn','') else '  '
        print(f"  [{tag}][{a.get('severity','?'):8s}] {a.get('code','?')} {a.get('descr','?')[:70]}")

print("\n" + "=" * 60)
print("VSANs + FC PORT ASSIGNMENTS")
print("=" * 60)
r = resolve_class(ck, "fabricVsan")
for m in re.finditer(r'<fabricVsan ([^>]+?)/>', r):
    a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
    if 'hg-' in a.get('name',''):
        print(f"  VSAN {a['name']:20s} id={a.get('id','?'):5s} "
              f"dn={a.get('dn','?')}")

# FC member ports per VSAN
for fab in ['A','B']:
    vsan_name = f"hg-vsan-{fab.lower()}"
    r = resolve_class(ck, "fabricVsanMemberEp")
    ports = [dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
             for m in re.finditer(r'<fabricVsanMemberEp ([^>]+?)/>', r)
             if vsan_name in m.group(1) or
                f'fc-estc/{fab}' in m.group(1)]
    print(f"  VSAN {vsan_name} member ports: {len(ports)}")

post(f'<aaaLogout inCookie="{ck}"/>')
print("\n[+] Audit complete")
