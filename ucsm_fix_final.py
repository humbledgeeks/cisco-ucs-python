#!/usr/bin/env python3
"""
Final UCSM fix pass — all correct DNs and class names confirmed by probing:
  1. Build hg-flexflash boot policy children (storage/local-storage/local-any)
  2. Bind hg-flexflash + hg-maint to SP template
  3. Enable CDP + LLDP on hg-netcon  (attr: cdp, lldpTransmit, lldpReceive)
  4. Fix vmnic4/vmnic5 MTU -> 1500
  5. Fix description fields on all HG objects
"""
import requests, urllib3, re
urllib3.disable_warnings()

HOST='10.103.12.20'; USER='admin'; PASSWD='HybridAdm1n&&'
ORG='org-root/org-HumbledGeeks'
BASE=f'https://{HOST}/nuova'
BOOT_DN = f'{ORG}/boot-policy-hg-flexflash'   # confirmed RN

def post(xml):
    r = requests.post(BASE, data=xml, verify=False, timeout=15)
    m_code = re.search(r'errorCode="([^"]+)"', r.text)
    m_desc = re.search(r'errorDescr="([^"]+)"', r.text)
    if m_code and m_code.group(1) != "0":
        raise RuntimeError(f"UCSM {m_code.group(1)}: {m_desc.group(1) if m_desc else r.text[:200]}")
    return r.text

resp = post(f'<aaaLogin inName="{USER}" inPassword="{PASSWD}"/>')
ck = re.search(r'outCookie="([^"]+)"', resp).group(1)
print(f"[+] Logged in")

# ── 1. Boot policy children ──────────────────────────────────────────────────
print("\n>>> Building hg-flexflash boot policy hierarchy")

post(f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{BOOT_DN}/storage">
      <lsbootStorage dn="{BOOT_DN}/storage" order="1" status="created,modified"/>
    </pair>
  </inConfigs>
</configConfMos>''')
print("    OK - lsbootStorage (order 1)")

post(f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{BOOT_DN}/storage/local-storage">
      <lsbootLocalStorage dn="{BOOT_DN}/storage/local-storage"
        status="created,modified"/>
    </pair>
  </inConfigs>
</configConfMos>''')
print("    OK - lsbootLocalStorage")

post(f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{BOOT_DN}/storage/local-storage/local-any">
      <lsbootDefaultLocalImage dn="{BOOT_DN}/storage/local-storage/local-any"
        order="1" status="created,modified"/>
    </pair>
  </inConfigs>
</configConfMos>''')
print("    OK - lsbootDefaultLocalImage (local-any, order 1)")

# ── 2. Bind boot + maint to SP template ─────────────────────────────────────
print("\n>>> Bind hg-flexflash + hg-maint to hg-esx-template")
post(f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{ORG}/ls-hg-esx-template">
      <lsServer dn="{ORG}/ls-hg-esx-template"
        bootPolicyName="hg-flexflash"
        maintPolicyName="hg-maint"
        status="modified"/>
    </pair>
  </inConfigs>
</configConfMos>''')
print("    OK")

# ── 3. CDP + LLDP ────────────────────────────────────────────────────────────
print("\n>>> Enable CDP + LLDP on hg-netcon")
post(f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{ORG}/nwctrl-hg-netcon">
      <nwctrlDefinition dn="{ORG}/nwctrl-hg-netcon"
        cdp="enabled" lldpTransmit="enabled" lldpReceive="enabled"
        status="modified"/>
    </pair>
  </inConfigs>
</configConfMos>''')
print("    OK")

# ── 4. vmnic4/5 MTU 1500 ─────────────────────────────────────────────────────
print("\n>>> Fix MTU: hg-vmnic4 + hg-vmnic5 -> 1500")
for tmpl in ["hg-vmnic4", "hg-vmnic5"]:
    dn = f"{ORG}/lan-conn-templ-{tmpl}"
    post(f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{dn}">
      <vnicLanConnTempl dn="{dn}" mtu="1500" status="modified"/>
    </pair>
  </inConfigs>
</configConfMos>''')
    print(f"    OK - {tmpl} MTU=1500")

# ── 5. Descriptions ──────────────────────────────────────────────────────────
print("\n>>> Updating descriptions")
desc_map = [
    ("vnicLanConnTempl",   f"{ORG}/lan-conn-templ-hg-vmnic0",        "Fabric-A vNIC: MGMT and vMotion traffic"),
    ("vnicLanConnTempl",   f"{ORG}/lan-conn-templ-hg-vmnic1",        "Fabric-B vNIC: MGMT and vMotion traffic"),
    ("vnicLanConnTempl",   f"{ORG}/lan-conn-templ-hg-vmnic2",        "Fabric-A vNIC: VM workload trunk"),
    ("vnicLanConnTempl",   f"{ORG}/lan-conn-templ-hg-vmnic3",        "Fabric-B vNIC: VM workload trunk"),
    ("vnicLanConnTempl",   f"{ORG}/lan-conn-templ-hg-vmnic4",        "Fabric-A vNIC: NFS storage only, MTU 1500"),
    ("vnicLanConnTempl",   f"{ORG}/lan-conn-templ-hg-vmnic5",        "Fabric-B vNIC: NFS storage only, MTU 1500"),
    ("vnicSanConnTempl",   f"{ORG}/san-conn-templ-hg-vmhba0",        "Fabric-A vHBA: FC initiator, VSAN hg-vsan-a"),
    ("vnicSanConnTempl",   f"{ORG}/san-conn-templ-hg-vmhba1",        "Fabric-B vHBA: FC initiator, VSAN hg-vsan-b"),
    ("lsbootPolicy",       f"{ORG}/boot-policy-hg-flexflash",        "Boot from FlexFlash SD card (local disk)"),
    ("lsbootPolicy",       f"{ORG}/boot-policy-hg-boot",             "Legacy boot: CD then local disk"),
    ("lsmaintMaintPolicy", f"{ORG}/maint-hg-maint",                  "User-ack required before disruptive changes"),
    ("macpoolPool",        f"{ORG}/mac-pool-hg-mac-a",               "MAC pool for Fabric-A vNICs"),
    ("macpoolPool",        f"{ORG}/mac-pool-hg-mac-b",               "MAC pool for Fabric-B vNICs"),
    ("uuidpoolPool",       f"{ORG}/uuid-pool-hg-uuid",               "UUID pool for HumbledGeeks ESXi blades"),
    ("fcpoolInitiators",   f"{ORG}/wwn-pool-hg-wwpn-a",              "WWPN pool for Fabric-A vHBAs"),
    ("fcpoolInitiators",   f"{ORG}/wwn-pool-hg-wwpn-b",              "WWPN pool for Fabric-B vHBAs"),
    ("ippoolPool",         f"{ORG}/ip-pool-hg-ext-mgmt",             "OOB CIMC management IPs 10.103.12.180-188"),
    ("nwctrlDefinition",   f"{ORG}/nwctrl-hg-netcon",                "CDP enabled, LLDP Tx/Rx enabled, forged MAC deny"),
    ("lsServer",           f"{ORG}/ls-hg-esx-template",              "ESXi blade template: FlexFlash boot, user-ack maint"),
]
for cls, dn, descr in desc_map:
    try:
        post(f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{dn}">
      <{cls} dn="{dn}" descr="{descr}" status="modified"/>
    </pair>
  </inConfigs>
</configConfMos>''')
        print(f"    OK - {dn.split('/')[-1]}")
    except RuntimeError as e:
        print(f"    WARN - {dn.split('/')[-1]}: {e}")

# ── 6. Verify ────────────────────────────────────────────────────────────────
print("\n\n=== VERIFICATION ===")

def get(dn):
    return post(f'<configResolveDn cookie="{ck}" dn="{dn}" inHierarchical="false"/>')

def attr(xml, name):
    m = re.search(rf'{name}="([^"]*)"', xml)
    return m.group(1) if m else "NOT FOUND"

r = get(f"{ORG}/ls-hg-esx-template")
print(f"SP Template bootPolicyName  : {attr(r,'bootPolicyName')}")
print(f"SP Template maintPolicyName : {attr(r,'maintPolicyName')}")

r = get(f"{ORG}/maint-hg-maint")
print(f"Maint uptimeDisr            : {attr(r,'uptimeDisr')}")
print(f"Maint dataDisr              : {attr(r,'dataDisr')}")

r = get(f"{ORG}/nwctrl-hg-netcon")
print(f"NetCtrl cdp                 : {attr(r,'cdp')}")
print(f"NetCtrl lldpTransmit        : {attr(r,'lldpTransmit')}")
print(f"NetCtrl lldpReceive         : {attr(r,'lldpReceive')}")

r = post(f'<configResolveChildren cookie="{ck}" inDn="{BOOT_DN}" inHierarchical="true"/>')
print(f"Boot local-any entry        : {'PRESENT' if 'lsbootDefaultLocalImage' in r else 'MISSING'}")

for t in ["hg-vmnic4","hg-vmnic5"]:
    r = get(f"{ORG}/lan-conn-templ-{t}")
    print(f"{t} MTU                 : {attr(r,'mtu')}")

post(f'<aaaLogout inCookie="{ck}"/>')
print("\n[+] All done")

print("\n" + "=" * 60)
print("ACTIVE FAULTS (severity != cleared)")
print("=" * 60)
r = resolve_class(ck, "faultInst")
faults = re.findall(r'<faultInst ([^>]+?)/>', r)
hg_faults = []
other_faults = []
for f in faults:
    a = dict(re.findall(r'(\w+)="([^"]*)"', f))
    if a.get('severity','') in ('critical','major','minor','warning'):
        entry = (a.get('severity','?'), a.get('code','?'), a.get('descr','?')[:80], a.get('dn','?')[:60])
        if 'HumbledGeeks' in a.get('dn',''):
            hg_faults.append(entry)
        else:
            other_faults.append(entry)

print(f"\n  HumbledGeeks org faults ({len(hg_faults)}):")
for sev, code, desc, dn in sorted(hg_faults):
    print(f"    [{sev:8s}] {code} {desc}")
print(f"\n  Other faults ({len(other_faults)}):")
for sev, code, desc, dn in sorted(other_faults)[:10]:
    print(f"    [{sev:8s}] {code} {desc[:60]}")

post(f'<aaaLogout inCookie="{ck}"/>')
print("\n[+] Audit complete")
