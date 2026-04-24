#!/usr/bin/env python3
"""Fix vNIC VLAN bindings — delete stale entries by constructing DNs explicitly."""
import urllib.request, ssl, re, sys

HOST='10.103.12.20'; USER='admin'; PASS='HybridAdm1n&&'
URL=f'https://{HOST}/nuova'
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE

def post(xml):
    req=urllib.request.Request(URL,xml.encode(),{'Content-Type':'text/xml'})
    with urllib.request.urlopen(req,context=ctx,timeout=30) as r: return r.read().decode()

def qdn(ck,dn,hier='true'):
    return post(f'<configResolveDn cookie="{ck}" inHierarchical="{hier}" dn="{dn}"/>')

resp=post(f'<aaaLogin inName="{USER}" inPassword="{PASS}"/>')
ck=re.search(r'outCookie="([^"]+)"',resp).group(1)
print('Logged in.\n')

BASE = 'org-root/org-HumbledGeeks'

# New desired state
MGMT_VLANS     = [('default','yes'),('dc3-mgmt','no'),('dc3-vmotion','no')]
WORKLOAD_VLANS = [('default','yes'),('dc3-apps','no'),('dc3-core','no'),
                  ('dc3-docker','no'),('dc3-gns3-mgmt','no'),
                  ('dc3-gns3-data','no'),('dc3-jumbbox','no')]
NFS_VLANS      = [('dc3-nfs','yes')]

TEMPLATE_MAP = {
    'hg-vmnic0': MGMT_VLANS,
    'hg-vmnic1': MGMT_VLANS,
    'hg-vmnic2': WORKLOAD_VLANS,
    'hg-vmnic3': WORKLOAD_VLANS,
    'hg-vmnic4': NFS_VLANS,
    'hg-vmnic5': NFS_VLANS,
}

def get_current_vlan_names(ck, templ_dn):
    """Return list of VLAN names currently bound to this template."""
    r = qdn(ck, templ_dn, 'true')
    return re.findall(r'<vnicEtherIf[^>]+name="([^"]+)"', r)

def rebind_template(tmpl_name, want_vlans):
    templ_dn = f'{BASE}/lan-conn-templ-{tmpl_name}'
    print(f'\n=== {tmpl_name} ===')

    have = get_current_vlan_names(ck, templ_dn)
    want_names = {v[0] for v in want_vlans}
    print(f'  Have: {have}')
    print(f'  Want: {sorted(want_names)}')

    # Find stale VLANs (exist but not in desired set)
    stale = [v for v in have if v not in want_names]
    # Find missing VLANs (desired but not present)
    missing = [(n,d) for n,d in want_vlans if n not in have]

    # Delete stale entries
    if stale:
        dels = ''.join(f'''
    <pair key="{templ_dn}/if-{v}">
      <vnicEtherIf dn="{templ_dn}/if-{v}" status="deleted"/>
    </pair>''' for v in stale)
        r=post(f'<configConfMos cookie="{ck}" inHierarchical="false"><inConfigs>{dels}</inConfigs></configConfMos>')
        if 'errorCode' in r: print(f'  WARN del: {r[:300]}')
        else: print(f'  Deleted stale: {stale}')

    # Add missing entries
    if missing:
        adds = ''.join(f'''
    <pair key="{templ_dn}/if-{n}">
      <vnicEtherIf dn="{templ_dn}/if-{n}" name="{n}" defaultNet="{d}"
                   rn="if-{n}" status="created,modified"/>
    </pair>''' for n,d in missing)
        r=post(f'<configConfMos cookie="{ck}" inHierarchical="false"><inConfigs>{adds}</inConfigs></configConfMos>')
        if 'errorCode' in r: print(f'  WARN add: {r[:300]}')
        else: print(f'  Added: {[n for n,_ in missing]}')

    # Update defaultNet on any that exist but have wrong default flag
    for (n, want_dflt) in want_vlans:
        if n in have and n not in [x[0] for x in missing]:
            # check current defaultNet
            r = qdn(ck, f'{templ_dn}/if-{n}', 'false')
            cur_dflt = re.search(r'defaultNet="([^"]+)"', r)
            if cur_dflt and cur_dflt.group(1) != want_dflt:
                upd=post(f'''<configConfMos cookie="{ck}" inHierarchical="false">
  <inConfigs>
    <pair key="{templ_dn}/if-{n}">
      <vnicEtherIf dn="{templ_dn}/if-{n}" defaultNet="{want_dflt}" status="modified"/>
    </pair>
  </inConfigs>
</configConfMos>''')
                if 'errorCode' not in upd:
                    print(f'  Updated defaultNet: {n} → {want_dflt}')

    # Verify final state
    final = get_current_vlan_names(ck, templ_dn)
    ok = sorted(final) == sorted(list(want_names))
    icon = '✅' if ok else '⚠️ '
    print(f'  {icon} Final: {sorted(final)}')
    sys.stdout.flush()

for tmpl, vlans in TEMPLATE_MAP.items():
    rebind_template(tmpl, vlans)

post(f'<aaaLogout inCookie="{ck}"/>')
print('\nDone.')
