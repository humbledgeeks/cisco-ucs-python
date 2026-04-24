#!/usr/bin/env python3
"""
Apply three UCSM changes via XML API:
  1. Create hg-maint maintenance policy (user-ack) + bind to hg-esx-template
  2. Enable CDP on hg-netcon network control policy
  3. Create hg-flexflash boot policy (SD card / FlexFlash) + bind to hg-esx-template
"""

import requests, urllib3, re
urllib3.disable_warnings()

HOST   = "10.103.12.20"
USER   = "admin"
PASSWD = "HybridAdm1n&&"
ORG    = "org-root/org-HumbledGeeks"
BASE   = f"https://{HOST}/nuova"

def post(xml):
    r = requests.post(BASE, data=xml, verify=False, timeout=15)
    r.raise_for_status()
    m_code  = re.search(r'errorCode="([^"]+)"', r.text)
    m_descr = re.search(r'errorDescr="([^"]+)"', r.text)
    if m_code and m_code.group(1) != "0":
        raise RuntimeError(f"UCSM {m_code.group(1)}: {m_descr.group(1) if m_descr else r.text[:200]}")
    return r.text

def login():
    resp = post(f'<aaaLogin inName="{USER}" inPassword="{PASSWD}"/>')
    ck = re.search(r'outCookie="([^"]+)"', resp)
    if not ck:
        raise RuntimeError("Login failed: " + resp[:300])
    print(f"[+] Logged in — cookie: {ck.group(1)[:20]}…")
    return ck.group(1)

def logout(ck):
    post(f'<aaaLogout inCookie="{ck}"/>')
    print("[+] Logged out")

def cfg(ck, label, xml):
    print(f"\n>>> {label}")
    resp = post(xml)
    print(f"    OK")
    return resp

ck = login()

# ── 1. Maintenance policy ────────────────────────────────────────────────────
cfg(ck, "Create hg-maint (user-ack) maintenance policy",
f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{ORG}/maint-hg-maint">
      <lsmaintMaintPolicy dn="{ORG}/maint-hg-maint" name="hg-maint"
        rebootPolicy="user-ack" uplinkFailAction="immediate"
        descr="User acknowledgement required before reboot"
        status="created,modified"/>
    </pair>
  </inConfigs>
</configConfMos>''')

cfg(ck, "Bind hg-maint to hg-esx-template",
f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{ORG}/ls-hg-esx-template">
      <lsServer dn="{ORG}/ls-hg-esx-template"
        maintPolicyName="hg-maint" status="modified"/>
    </pair>
  </inConfigs>
</configConfMos>''')

# ── 2. Enable CDP on hg-netcon ───────────────────────────────────────────────
cfg(ck, "Enable CDP on hg-netcon",
f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{ORG}/nwctrl-hg-netcon">
      <nwctrlDefinition dn="{ORG}/nwctrl-hg-netcon"
        cdpPolicy="enabled" status="modified"/>
    </pair>
  </inConfigs>
</configConfMos>''')

# ── 3. FlexFlash / SD-card boot policy ──────────────────────────────────────
cfg(ck, "Create hg-flexflash boot policy",
f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{ORG}/boot-hg-flexflash">
      <lsbootPolicy dn="{ORG}/boot-hg-flexflash" name="hg-flexflash"
        descr="Boot from FlexFlash SD card" enforceVnicName="yes"
        rebootOnUpdate="no" status="created,modified"/>
    </pair>
  </inConfigs>
</configConfMos>''')

cfg(ck, "Add local storage container (order 1)",
f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{ORG}/boot-hg-flexflash/storage">
      <lsbootStorage dn="{ORG}/boot-hg-flexflash/storage"
        order="1" status="created,modified"/>
    </pair>
  </inConfigs>
</configConfMos>''')

cfg(ck, "Add lsbootLocalStorage",
f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{ORG}/boot-hg-flexflash/storage/local-storage">
      <lsbootLocalStorage dn="{ORG}/boot-hg-flexflash/storage/local-storage"
        status="created,modified"/>
    </pair>
  </inConfigs>
</configConfMos>''')

cfg(ck, "Add SD card (USB flash storage) image — order 1",
f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{ORG}/boot-hg-flexflash/storage/local-storage/usb-flash">
      <lsbootUsbFlashStorageImage
        dn="{ORG}/boot-hg-flexflash/storage/local-storage/usb-flash"
        order="1" status="created,modified"/>
    </pair>
  </inConfigs>
</configConfMos>''')

cfg(ck, "Bind hg-flexflash boot policy to hg-esx-template",
f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{ORG}/ls-hg-esx-template">
      <lsServer dn="{ORG}/ls-hg-esx-template"
        bootPolicyName="hg-flexflash" status="modified"/>
    </pair>
  </inConfigs>
</configConfMos>''')

# ── 4. Verify ────────────────────────────────────────────────────────────────
print("\n\n=== VERIFICATION ===")

resp = post(f'<configResolveDn cookie="{ck}" dn="{ORG}/ls-hg-esx-template" inHierarchical="false"/>')
maint = re.search(r'maintPolicyName="([^"]*)"', resp)
boot  = re.search(r'bootPolicyName="([^"]*)"', resp)
print(f"SP Template — maintPolicyName : {maint.group(1) if maint else 'NOT FOUND'}")
print(f"SP Template — bootPolicyName  : {boot.group(1) if boot else 'NOT FOUND'}")

resp = post(f'<configResolveDn cookie="{ck}" dn="{ORG}/maint-hg-maint" inHierarchical="false"/>')
rp = re.search(r'rebootPolicy="([^"]*)"', resp)
print(f"Maint Policy — rebootPolicy   : {rp.group(1) if rp else 'NOT FOUND'}")

resp = post(f'<configResolveDn cookie="{ck}" dn="{ORG}/nwctrl-hg-netcon" inHierarchical="false"/>')
cdp = re.search(r'cdpPolicy="([^"]*)"', resp)
print(f"NetCtrl hg-netcon — cdpPolicy : {cdp.group(1) if cdp else 'NOT FOUND'}")

resp = post(f'<configResolveChildren cookie="{ck}" inDn="{ORG}/boot-hg-flexflash" inHierarchical="true"/>')
has_usb = "lsbootUsbFlashStorageImage" in resp
print(f"Boot policy usb-flash entry   : {'PRESENT' if has_usb else 'MISSING'}")

logout(ck)
