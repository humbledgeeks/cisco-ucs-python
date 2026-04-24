#!/usr/bin/env python3
"""
UCSM Policy Gather Script
Connects to UCSM FI and retrieves detailed policy configurations
for the Humbledgeeks sub-org plus root-level VLANs/VSANs.
"""

import paramiko
import time

HOST = '10.103.12.20'
USER = 'admin'
PASS = 'HybridAdm1n&&'

def send_and_read(shell, cmd, delay=2.5):
    shell.send(cmd + '\n')
    time.sleep(delay)
    out = b''
    while shell.recv_ready():
        chunk = shell.recv(65535)
        out += chunk
        time.sleep(0.3)
    return out.decode('utf-8', errors='replace')

def connect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=15)
    shell = client.invoke_shell(width=250, height=5000)
    time.sleep(2)
    while shell.recv_ready():
        shell.recv(65535)
    return client, shell


def main():
    print("Connecting to UCSM at", HOST)
    client, shell = connect()
    print("Connected.\n")
    sections = {}

    # Root: VLANs
    print("Fetching VLANs...")
    send_and_read(shell, 'top', 1)
    send_and_read(shell, 'scope eth-uplink', 1)
    sections['vlans'] = send_and_read(shell, 'show vlan detail', 5)

    # Root: VSANs
    print("Fetching VSANs...")
    send_and_read(shell, 'top', 1)
    send_and_read(shell, 'scope fc-uplink', 1)
    sections['vsans'] = send_and_read(shell, 'show vsan detail', 4)

    # Scope into Humbledgeeks
    print("Scoping into org Humbledgeeks...")
    send_and_read(shell, 'top', 1)
    send_and_read(shell, 'scope org /', 1)
    send_and_read(shell, 'scope org Humbledgeeks', 1)

    # vNIC templates
    print("Fetching vNIC templates...")
    sections['vnic_templates'] = send_and_read(shell, 'show vnic-templ detail', 6)

    # vHBA templates
    print("Fetching vHBA templates...")
    sections['vhba_templates'] = send_and_read(shell, 'show vhba-templ detail', 5)


    # Boot policies
    print("Fetching boot policies...")
    sections['boot_policies'] = send_and_read(shell, 'show boot-policy detail', 5)

    # BIOS policy
    print("Fetching BIOS policies...")
    sections['bios_policies'] = send_and_read(shell, 'show bios-policy detail', 3)

    # Maintenance policy
    print("Fetching maintenance policies...")
    sections['maint_policies'] = send_and_read(shell, 'show maint-policy detail', 3)

    # Power policy
    print("Fetching power policies...")
    sections['power_policies'] = send_and_read(shell, 'show power-policy detail', 3)

    # Local disk config policy
    print("Fetching local disk policies...")
    sections['localdisk_policies'] = send_and_read(shell, 'show local-disk-config-policy detail', 3)

    # Host firmware packages
    print("Fetching firmware packages...")
    sections['fw_packages'] = send_and_read(shell, 'show host-fw-pack detail', 3)

    # vCon placement
    print("Fetching vCon placement policies...")
    sections['vcon_policies'] = send_and_read(shell, 'show vcon-policy detail', 3)

    # UUID pools
    print("Fetching UUID pools...")
    sections['uuid_pools'] = send_and_read(shell, 'show uuid-suffix-pool detail', 4)


    # MAC pools
    print("Fetching MAC pools...")
    sections['mac_pools'] = send_and_read(shell, 'show mac-pool detail', 4)

    # WWNN pools
    print("Fetching WWNN pools...")
    sections['wwnn_pools'] = send_and_read(shell, 'show wwnn-pool detail', 3)

    # WWPN pools
    print("Fetching WWPN pools...")
    sections['wwpn_pools'] = send_and_read(shell, 'show wwpn-pool detail', 3)

    # Network control policy
    print("Fetching network control policies...")
    sections['net_ctrl_policies'] = send_and_read(shell, 'show network-control-policy detail', 3)

    # QoS policy
    print("Fetching QoS policies...")
    sections['qos_policies'] = send_and_read(shell, 'show qos-policy detail', 3)

    client.close()
    print("\n=== DONE ===\n")

    for section, data in sections.items():
        print(f"\n{'='*70}")
        print(f"  SECTION: {section.upper()}")
        print(f"{'='*70}")
        print(data)

if __name__ == '__main__':
    main()
