# cisco-ucs-python

Python automation for Cisco UCS infrastructure using the `ucsmsdk` library — inventory gathering, configuration auditing, pool management, SAN/vHBA configuration, and fault clearing.

## Contents

| File | Purpose |
|------|---------|
| `ucsm_audit_final.py` | Full UCS configuration audit |
| `ucsm_boot_order_final.py` | Boot order inspection and management |
| `ucsm_clear_faults.py` | Clear UCS faults |
| `ucsm_create_hg_v2.py` | Create HumbledGeeks UCS config v2 |
| `ucsm_fc_ports_vsan.py` | FC port and VSAN configuration |
| `ucsm_final4.py` | Final configuration pass (iteration 4) |
| `ucsm_final_audit.py` | Final audit script |
| `ucsm_fix_final.py` | Final fix pass |
| `ucsm_fix_ntp.py` | Fix NTP configuration |
| `ucsm_gather.py` | Gather UCS inventory data |
| `ucsm_ippool_fix.py` | IP pool fix and validation |
| `ucsm_last_two.py` | Last two configuration items |
| `ucsm_maint_cdp_boot.py` | Maintenance, CDP, and boot policy config |
| `ucsm_patch_final.py` | Final patch pass |
| `ucsm_probe_ports.py` | Probe and inspect port configuration |
| `ucsm_vhba_probe.py` | vHBA inspection and validation |
| `ucsm_vhba_vsan.py` | vHBA and VSAN binding |
| `ucsm_vnic_rebind2.py` | vNIC rebinding (v2) |
| `ucsm_vsan10_fix.py` | VSAN 10 fix |
| `ucsm_vsan_members_v2.py` | VSAN membership management v2 |
| `ucsm_vsan_storage.py` | VSAN storage configuration |
| `ucsm_vsan_v2.py` | VSAN configuration v2 |
| `ucsm_xmlapi_vhba.py` | vHBA management via XML API |
| `ucs_audit_data.json` | Audit reference data |

## Prerequisites

- Python 3.8+
- `pip install ucsmsdk`

## Quick Start

```bash
export UCSM_HOST="192.168.1.10"
export UCSM_USER="admin"
export UCSM_PASSWORD="your-password"

python ucsm_gather.py
```

## CI/CD

All PRs validated by flake8, secret scan, and header compliance.

## Owner

humbledgeeks-allen | [HumbledGeeks.com](https://humbledgeeks.com)
