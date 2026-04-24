#!/usr/bin/env python3
"""Probe FC storage port interface syntax and list available interfaces."""
import paramiko, time

HOST='10.103.12.20'; USER='admin'; PASS='HybridAdm1n&&'

def drain(sh, rounds=4, pause=0.4):
    buf=b''
    for _ in range(rounds):
        time.sleep(pause)
        while sh.recv_ready(): buf+=sh.recv(65535)
    return buf.decode('utf-8','replace')

def go(sh, cmd, delay=1.5):
    sh.send(cmd+'\n'); time.sleep(delay)
    resp=drain(sh)
    print(f"CMD: {cmd!r}\n{resp}\n")
    return resp

c=paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,username=USER,password=PASS,timeout=20)
sh=c.invoke_shell(width=300,height=9000)
time.sleep(2); drain(sh)

# Explore fc-storage/fabric a interface listing
go(sh,'top',0.5); go(sh,'scope fc-storage',0.5)
go(sh,'scope fabric a',0.5)

# List all interfaces in fc-storage/fabric a
print("=== show interface ===")
go(sh,'show interface',3)

print("=== show interface detail ===")
go(sh,'show interface detail',4)

# Probe scope interface fc ?
print("=== scope interface fc ? ===")
sh.send('scope interface fc ?\n'); time.sleep(2); print(drain(sh))

# Try fc 1/29
sh.send('scope interface fc 1/29\n'); time.sleep(1.5); r=drain(sh); print(f"fc 1/29: {r}")
sh.send('discard-buffer\n'); time.sleep(1); drain(sh)
go(sh,'top',0.5); go(sh,'scope fc-storage',0.5); go(sh,'scope fabric a',0.5)

# Try fc 1 29
sh.send('scope interface fc 1 29\n'); time.sleep(1.5); r=drain(sh); print(f"fc 1 29: {r}")
sh.send('discard-buffer\n'); time.sleep(1); drain(sh)
go(sh,'top',0.5); go(sh,'scope fc-storage',0.5); go(sh,'scope fabric a',0.5)

# Try fc 29 (no slot)
sh.send('scope interface fc 29\n'); time.sleep(1.5); r=drain(sh); print(f"fc 29: {r}")
sh.send('discard-buffer\n'); time.sleep(1); drain(sh)
go(sh,'top',0.5); go(sh,'scope fc-storage',0.5); go(sh,'scope fabric a',0.5)

# Try fc 1/1 through 1/4 (sequential FC port numbering)
for p in range(1,6):
    sh.send(f'scope interface fc 1/{p}\n'); time.sleep(1.5)
    r=drain(sh); print(f"fc 1/{p}: {r[:120]}")
    sh.send('discard-buffer\n'); time.sleep(0.8); drain(sh)
    go(sh,'top',0.5); go(sh,'scope fc-storage',0.5); go(sh,'scope fabric a',0.5)

c.close()
print("\nDone.")
