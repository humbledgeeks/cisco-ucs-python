#!/usr/bin/env python3
"""
Use UCSM XML API to fix vHBA template VSAN bindings.
Deletes the stale vnicFcIf 'if-default' and creates the correct one.
  hg-vmhba0 → hg-vsan-a
  hg-vmhba1 → hg-vsan-b
"""
import urllib.request, urllib.error, ssl, sys, re

HOST   = '10.103.12.20'
USER   = 'admin'
PASS   = 'HybridAdm1n&&'
URL    = f'https://{HOST}/nuova'

# Ignore self-signed cert
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode    = ssl.CERT_NONE

def post(xml_str):
    data = xml_str.encode('utf-8')
    req  = urllib.request.Request(URL, data=data,
                                  headers={'Content-Type': 'text/xml'})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
            return r.read().decode('utf-8')
    except Exception as e:
        return f'<error>{e}</error>'

def get_attr(xml, attr):
    m = re.search(rf'{attr}="([^"]*)"', xml)
    return m.group(1) if m else None

# ── Login ─────────────────────────────────────────────────────────────────
print('Logging in...')
resp = post(f'<aaaLogin inName="{USER}" inPassword="{PASS}"/>')
cookie = get_attr(resp, 'outCookie')
if not cookie:
    print(f'Login failed:\n{resp}')
    sys.exit(1)
print(f'  Cookie: {cookie[:20]}...')

# ── Query current state of both templates ─────────────────────────────────
print('\n=== Query vHBA templates ===')
for tmpl in ['hg-vmhba0', 'hg-vmhba1']:
    dn = f'org-root/org-HumbledGeeks/san-conn-templ-{tmpl}'
    q = f'<configResolveDn cookie="{cookie}" inHierarchical="true" dn="{dn}"/>'
    r = post(q)
    print(f'\n  {tmpl}:\n{r[:800]}\n')

# ── Fix each template ──────────────────────────────────────────────────────
fixes = [
    ('hg-vmhba0', 'hg-vsan-a'),
    ('hg-vmhba1', 'hg-vsan-b'),
]

for tmpl, vsan in fixes:
    templ_dn  = f'org-root/org-HumbledGeeks/san-conn-templ-{tmpl}'
    old_if_dn = f'{templ_dn}/if-default'
    new_if_dn = f'{templ_dn}/if-{vsan}'

    print(f'\n=== Fix {tmpl} → {vsan} ===')

    # Step 1: Delete the stale if-default (ignore errors if it doesn't exist)
    print(f'  Deleting {old_if_dn} ...')
    del_xml = f'''<configConfMos cookie="{cookie}" inHierarchical="false">
  <inConfigs>
    <pair key="{old_if_dn}">
      <vnicFcIf dn="{old_if_dn}" status="deleted"/>
    </pair>
  </inConfigs>
</configConfMos>'''
    r = post(del_xml)
    if 'errorCode' in r or 'error' in r.lower():
        print(f'    Delete result (may be OK if not found): {r[:300]}')
    else:
        print(f'    Deleted OK')

    # Step 2: Create the correct vnicFcIf
    print(f'  Creating {new_if_dn} ...')
    create_xml = f'''<configConfMos cookie="{cookie}" inHierarchical="false">
  <inConfigs>
    <pair key="{new_if_dn}">
      <vnicFcIf dn="{new_if_dn}" name="{vsan}" rn="if-{vsan}" status="created"/>
    </pair>
  </inConfigs>
</configConfMos>'''
    r = post(create_xml)
    if 'errorCode' in r or ('error' in r.lower() and 'outStatus' not in r):
        print(f'    Create FAILED: {r[:500]}')
    else:
        print(f'    Created OK')
        print(f'    Response: {r[:300]}')

# ── Verify ─────────────────────────────────────────────────────────────────
print('\n=== Verify ===')
for tmpl, vsan in fixes:
    dn = f'org-root/org-HumbledGeeks/san-conn-templ-{tmpl}'
    q = f'<configResolveDn cookie="{cookie}" inHierarchical="true" dn="{dn}"/>'
    r = post(q)
    # Pull out vnicFcIf lines
    lines = [ln.strip() for ln in r.split('\n') if 'vnicFcIf' in ln or 'name=' in ln]
    print(f'\n  {tmpl}:')
    for ln in lines[:10]: print(f'    {ln}')
    print(f'  Full response: {r[:600]}')

# ── Logout ─────────────────────────────────────────────────────────────────
post(f'<aaaLogout inCookie="{cookie}"/>')
print('\nLogged out. Done.')
