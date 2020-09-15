#!/usr/bin/python3

import os
import json
import subprocess
from pprint import pprint
from heapq import nlargest

# Optimize only the top n routes
OPTIMIZE_TOP = 4

# What percentage of hosts need to be reachable to consider optimizer (0.0 - 1.0)
THRESHOLD_REACHABILITY = 0.7

# Change to the correct working directory
os.chdir('/root')


parsed = {}
with open('/tmp/pmacct_avg.json', 'r') as f:
    data = f.read()

# Load the data file
for row in data.split('\n'):
    # Skip blank lines
    if row.strip() == "": continue

    # Parse JSON
    p = json.loads(row)

    # Hash the flow
    src_h = int.from_bytes(p['ip_src'].encode('ascii'), "little")
    dst_h = int.from_bytes(p['ip_dst'].encode('ascii'), "little")
    hsh = src_h * dst_h

    # Figure out the destination IP
    dst = ""
    if '10.254.0' not in p['ip_src']:
        dst = p['ip_src']
    else:
        dst = p['ip_dst']

    # Discard multicast
    if '239.255.255.' in dst: continue
    if '224.0.0.' in dst: continue

    # Discard local IPs
    if '10.254.0.' in dst: continue
    if '10.20.0.' in dst: continue
    if '10.30.0.' in dst: continue
    if '10.30.4.' in dst: continue

    # If this is a new flow
    if hsh not in parsed:
        parsed[hsh] = {
            'dst': dst,
            'packets': p['packets'],
            'bytes': p['bytes']
        }

    else: # Existing flow
        parsed[hsh]['packets'] += p['packets']
        parsed[hsh]['bytes'] += p['bytes']

# Find routes to optimize
## Sort by number of packets
sortedkeys = sorted(parsed, key=lambda i: parsed[i]['packets'], reverse=True)
result = list(map(lambda x: parsed[x], sortedkeys))[:OPTIMIZE_TOP]
targets = [x['dst'] for x in result]

print("Going to optimize %s" % targets)

# Prepare inventory
## Insert local system
HOSTS = [{
    'host': 'local',
    'ip': '127.0.0.1',
    'id': '0'
}]

## Load the inventory file
with open('systems.txt', 'r') as systems:
    for system in systems:
        h = [x.strip() for x in system.split(';')]
        host = {
            'host': h[0],
            'ip': h[1],
            'id': h[2]
        }
        HOSTS.append(host)

# Try pinging the targets
for target in targets:
    latencies = []
    for host in HOSTS:
        out = ""

        popenout = subprocess.Popen(["fping", "-c3", "-q", target, "-i 500", "-p 500", "-S", f"10.99.0.{host['id']}"], stderr=subprocess.PIPE, stdout=subprocess.PIPE)

        out = popenout.stderr.read().decode('ascii')

        if '100%' in out:
            print(f"Target {target} unreachable through host {host['host']}, ignoring")
            continue

        if 'min/avg/max' not in out:
            print(out)
            raise ValueError('fping returned wrong output!')

        latency = float(out.split('=')[2].strip().split('/')[0])
        latencies.append({'latency': latency, 'id': host['id'], 'host': host['host']})
        print(f"Latency to {target} over {host['host']} is {latency}")

    # Pick the lowest latency route
    if len(latencies) < (len(HOSTS)*THRESHOLD_REACHABILITY):
        print(f"{target} responded to under {THRESHOLD_REACHABILITY*100}% hosts, not optimizing!")
        continue

    best = min(latencies, key=lambda x: x['latency'])
    print(f"The best route to {target} is over {best['host']} - {best['latency']}")

    # Insert the optimized route
    ## Check if the same one is already in there, ignore
    ### Ignore localhost
    if best['host'] != "local":
        if(f"from 10.254.0.0/16 to {target} lookup {100 + int(best['id'])}" in subprocess.check_output(["ip", "rule"]).decode('ascii')):
            continue

    ## Check if the host is already in there, remove it
    if(f"from 10.254.0.0/16 to {target}" in subprocess.check_output(["ip", "rule"]).decode('ascii')):
        print("Removing current rule...")
        subprocess.call(["ip", "rule", "del", "from", "10.254.0.0/16", "to", target])

    ## Add the new rule
    ### Ignore localhost
    if best['host'] != "local":
        subprocess.call(["ip", "rule", "add", "from", "10.254.0.0/16", "to", target, "lookup", f"{100 + int(best['id'])}"])
        print(f"Rerouted {target} via {best['host']}")