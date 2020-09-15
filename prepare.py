#!/usr/bin/python3

import os

# Make a temp directory
os.makedirs('/tmp/lightlink', exist_ok=True)

# Load the inventory file
HOSTS = []
with open('systems.txt', 'r') as systems:
    for system in systems:
        h = [x.strip() for x in system.split(';')]
        host = {
            'host': h[0],
            'ip': h[1],
            'id': h[2]
        }
        HOSTS.append(host)

# Generate tunnel IPs
i = 0
TUNNELS = {}
for localhost in HOSTS:
    for host in HOSTS:
        # Skip local system
        if localhost['host'] == host['host']:
            continue

        if (localhost['host'] + host['host']) in TUNNELS:
            TUNNELS[host['host'] + localhost['host']] = TUNNELS[localhost['host'] + host['host']][:-1] + '1'
        else:
            TUNNELS[host['host'] + localhost['host']] = f"10.20.{i}.0"
        i += 1


LINK_LOCALS = []
# Generate the command sets
for localhost in HOSTS:
    cmd = ""

    # Install Python
    cmd += "systemctl disable --now firewalld\n"
    cmd += "yum -y install epel-release\n"
    cmd += "yum -y install python3 bird mtr htop fping\n"

    for host in HOSTS:
        # Skip local system
        if localhost['host'] == host['host']:
            continue

        # Generate GRE tunnels
        ## Clear existing tunnels
        cmd += f"ip link del {host['host']}\n"
        ## Generate new tunnel config
        cmd += f"ip tunnel add {host['host']} mode gre remote {host['ip']} local {localhost['ip']} ttl 255\n"
        cmd += f"ip link set {host['host']} up\n"
        cmd += f"ip addr add {TUNNELS[host['host'] + localhost['host']]}/31 dev {host['host']}\n"

    # Generate link locals
    cmd += f"ip addr add 10.30.0.{localhost['id']}/32 dev lo\n"

    LINK_LOCALS.append({'id': localhost['id'], 'ip': f"10.30.0.{localhost['id']}", 'host': localhost['host']})

    # Set up sysctl.conf
    cmd += "echo 'net.ipv4.ip_forward = 1' > /etc/sysctl.conf\n"
    cmd += "echo 'net.ipv4.conf.all.rp_filter = 0' >> /etc/sysctl.conf\n"
    cmd += "echo 'net.ipv4.conf.default.rp_filter = 0' >> /etc/sysctl.conf\n"
    cmd += "sysctl -p\n\n"

    # Setup VXLANs
    ## Clear existing VXLAN
    cmd += "ip link del vxlan1\n"
    ## Generate new tunnel config
    cmd += f"ip link add vxlan1 type vxlan id 1 dstport 4789 local 10.30.0.{localhost['id']}\n"
    cmd += "ip link set vxlan1 up\n"
    cmd += "ip link set vxlan1 mtu 1400\n"
    cmd += f"ip addr add 10.30.4.{localhost['id']}/24 dev vxlan1\n\n"

    ## Add all VXLAN peers
    for host in HOSTS:
        # Skip local system
        if localhost['host'] == host['host']:
            continue

        cmd += f"bridge fdb append 00:00:00:00:00:00 dev vxlan1 dst 10.30.0.{host['id']}\n"

    # Setup IPTables
    cmd += "iptables -P INPUT ACCEPT\n"
    cmd += "iptables -P FORWARD ACCEPT\n"
    cmd += "iptables -P OUTPUT ACCEPT\n"
    cmd += "iptables -F\n"
    cmd += "iptables -A FORWARD -p tcp --tcp-flags SYN,RST SYN -j TCPMSS  --clamp-mss-to-pmtu\n\n"

    ## Setup NAT
    cmd += "iptables -t nat -F\n"
    cmd += "iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE\n"
    cmd += "iptables -t nat -A POSTROUTING -o ens3 -j MASQUERADE\n"

    with open(f"/tmp/lightlink/cmds.{localhost['host']}.txt", 'w+') as fout:
        fout.write(cmd)

with open(f"/tmp/lightlink/hosts", 'w+') as fout:
    fout.write(f"127.0.0.1   localhost localhost.localdomain localhost4 localhost4.localdomain4\n")
    fout.write(f"::1         localhost localhost.localdomain localhost6 localhost6.localdomain6\n\n")

    for row in LINK_LOCALS:
        fout.write(f"{row['ip']}   {row['host']}.lightlink.app\n")
        fout.write(f"10.30.4.{row['id']}   {row['host']}.overlay.lightlink.app\n")

with open(f"/tmp/lightlink/linklocals.txt", 'w+') as fout:
    for row in LINK_LOCALS:
        fout.write(f"{row['host']};{row['ip']}\n")
