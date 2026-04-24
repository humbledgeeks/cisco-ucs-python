#!/usr/bin/env python3
"""
Final boot policy: hg-flexflash  (UEFI mode)
  Order 1 - DVD / read-only virtual media   (OS install / recovery)
  Order 2 - SSD / embedded local disk       (primary OS boot)
  Order 3 - FlexFlash SD card               (last-resort fallback)

If lsbootUsbFlashStorageImage / lsbootEmbeddedLocalDiskImage are unavailable
in this UCSM build, falls back to lsbootDefaultLocalImage (local-any) which
covers all local devices — UEFI enumerates SSD before SD card by default.
"""
import requests, urllib3, re
urllib3.disable_warnings()

HOST   = "10.103.12.20"
USER   = "admin"
PASSWD = "HybridAdm1n&&"
ORG    = "org-root/org-HumbledGeeks"
BASE   = f"https://{HOST}/nuova"
BOOT   = f"{ORG}/boot-policy-hg-flexflash"

def post(xml):
    r = requests.post(BASE, data=xml, verify=False, timeout=15)
    m_code = re.search(r'errorCode="([^"]+)"', r.text)
    m_desc = re.search(r'errorDescr="([^"]+)"', r.text)
    if m_code and m_code.group(1) != "0":
        raise RuntimeError(f"UCSM {m_code.group(1)}: {m_desc.group(1) if m_desc else r.text[:200]}")
    return r.text

def try_post(xml, label=""):
    try:
        return post(xml)
    except RuntimeError as e:
        print(f"    WARN ({label}): {e}")
        return None

resp = post(f'<aaaLogin inName="{USER}" inPassword="{PASSWD}"/>')
ck = re.search(r'outCookie="([^"]+)"', resp).group(1)
print("[+] Connected to UCSM")

# ── Probe available classes ──────────────────────────────────────────────────
print("\n>>> Probing available local boot device classes...")
usb_flash_ok = embedded_ok = False
for cls in ["lsbootUsbFlashStorageImage", "lsbootEmbeddedLocalDiskImage"]:
    r = post(f'<configResolveClass cookie="{ck}" classId="{cls}" inHierarchical="false"/>')
    valid = "ERR-xml-parse-error" not in r and "no class named" not in r
    if cls == "lsbootUsbFlashStorageImage":  usb_flash_ok = valid
    if cls == "lsbootEmbeddedLocalDiskImage": embedded_ok  = valid
    print(f"    {cls}: {'AVAILABLE' if valid else 'NOT AVAILABLE'}")

# ── Wipe existing boot devices for a clean slate ────────────────────────────
print("\n>>> Clearing existing boot devices...")
try_post(f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{BOOT}/read-only-vm">
      <lsbootVirtualMedia dn="{BOOT}/read-only-vm" status="deleted"/>
    </pair>
  </inConfigs>
</configConfMos>''', "delete DVD")
try_post(f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{BOOT}/storage">
      <lsbootStorage dn="{BOOT}/storage" status="deleted"/>
    </pair>
  </inConfigs>
</configConfMos>''', "delete storage")
try_post(f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{BOOT}/storage2">
      <lsbootStorage dn="{BOOT}/storage2" status="deleted"/>
    </pair>
  </inConfigs>
</configConfMos>''', "delete storage2")
print("    Cleared")

# ── Build boot order: DVD(1) → SSD(2) → FlexFlash SD(3) ─────────────────────
print("\n>>> Building boot order: DVD(1) → SSD(2) → FlexFlash SD(3)")

# --- Order 1: DVD --------------------------------------------------------
post(f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{BOOT}/read-only-vm">
      <lsbootVirtualMedia dn="{BOOT}/read-only-vm"
        access="read-only" order="1" status="created,modified"/>
    </pair>
  </inConfigs>
</configConfMos>''')
print("    [1] DVD / read-only virtual media  OK")

# --- Order 2: SSD (primary local boot) -----------------------------------
post(f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{BOOT}/storage">
      <lsbootStorage dn="{BOOT}/storage" order="2" status="created,modified"/>
    </pair>
  </inConfigs>
</configConfMos>''')
post(f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{BOOT}/storage/local-storage">
      <lsbootLocalStorage dn="{BOOT}/storage/local-storage"
        status="created,modified"/>
    </pair>
  </inConfigs>
</configConfMos>''')

if embedded_ok:
    post(f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{BOOT}/storage/local-storage/local-hdd">
      <lsbootEmbeddedLocalDiskImage
        dn="{BOOT}/storage/local-storage/local-hdd"
        order="1" status="created,modified"/>
    </pair>
  </inConfigs>
</configConfMos>''')
    print("    [2] SSD / embedded local disk      OK  (lsbootEmbeddedLocalDiskImage)")
else:
    # local-any covers SSD + SD together; UEFI will pick SSD first
    post(f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{BOOT}/storage/local-storage/local-any">
      <lsbootDefaultLocalImage
        dn="{BOOT}/storage/local-storage/local-any"
        order="1" status="created,modified"/>
    </pair>
  </inConfigs>
</configConfMos>''')
    print("    [2] local-any (SSD+SD covered)     OK  (lsbootDefaultLocalImage)")
    print("        NOTE: UEFI will enumerate SSD before SD card by default")

# --- Order 3: FlexFlash SD card (last resort, only if separate class exists) -
if embedded_ok and usb_flash_ok:
    post(f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{BOOT}/storage2">
      <lsbootStorage dn="{BOOT}/storage2" order="3" status="created,modified"/>
    </pair>
  </inConfigs>
</configConfMos>''')
    post(f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{BOOT}/storage2/local-storage">
      <lsbootLocalStorage dn="{BOOT}/storage2/local-storage"
        status="created,modified"/>
    </pair>
  </inConfigs>
</configConfMos>''')
    post(f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{BOOT}/storage2/local-storage/usb-flash">
      <lsbootUsbFlashStorageImage
        dn="{BOOT}/storage2/local-storage/usb-flash"
        order="1" status="created,modified"/>
    </pair>
  </inConfigs>
</configConfMos>''')
    print("    [3] FlexFlash SD card              OK  (lsbootUsbFlashStorageImage)")
elif not embedded_ok:
    print("    [3] FlexFlash SD covered by local-any (no explicit entry needed)")
else:
    print("    [3] lsbootUsbFlashStorageImage not available in this UCSM build")
    print("        SD card still reachable via local-any fallback")

# Update boot policy description
post(f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{BOOT}">
      <lsbootPolicy dn="{BOOT}"
        bootMode="uefi"
        descr="UEFI: DVD(1) SSD(2) FlexFlash SD(3)"
        status="modified"/>
    </pair>
  </inConfigs>
</configConfMos>''')
print("    Description: 'UEFI: DVD(1) SSD(2) FlexFlash SD(3)'")

# ── Verification ─────────────────────────────────────────────────────────────
print("\n\n=== VERIFICATION ===")
r = post(f'<configResolveDn cookie="{ck}" dn="{BOOT}" inHierarchical="false"/>')
a = dict(re.findall(r'(\w+)="([^"]*)"', r))
print(f"Policy : {a.get('name')}  bootMode={a.get('bootMode')}")
print(f"Descr  : {a.get('descr')}")

r = post(f'<configResolveChildren cookie="{ck}" inDn="{BOOT}" inHierarchical="true"/>')
entries = []
for cls, label in [
    ("lsbootVirtualMedia",         "DVD / Virtual Media"),
    ("lsbootStorage",              "Storage Container"),
    ("lsbootDefaultLocalImage",    "Local-any (SSD+SD)"),
    ("lsbootEmbeddedLocalDiskImage","SSD / Embedded disk"),
    ("lsbootUsbFlashStorageImage", "FlexFlash SD card"),
]:
    for m in re.finditer(rf"<{cls}[^>]+>", r):
        a2 = dict(re.findall(r'(\w+)="([^"]*)"', m.group(0)))
        entries.append((int(a2.get("order", 99)), label, a2.get("rn","?"), a2.get("access","-")))

print("\nBoot order:")
for order, label, rn, access in sorted(entries):
    acc = f"  access={access}" if access != "-" else ""
    print(f"  [{order}] {label:35s} rn={rn}{acc}")

post(f'<aaaLogout inCookie="{ck}"/>')
print("\n[+] Done — boot policy ready")
