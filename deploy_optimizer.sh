#!/bin/bash

# Install dependencies
yum -y install fping

# Setup routing rules
## Localhost
ip addr add 10.99.0.0/32 dev lo

## Through other systems
for system in `cat systems.txt`; do
    HOST=$(echo $system | cut -d';' -f1)
    IP=$(echo $system | cut -d';' -f2)
    NUMBER=$(echo $system | cut -d';' -f3)

    ip addr add 10.99.0.${NUMBER}/32 dev lo
    ip route add default via 10.30.4.${NUMBER} table 10${NUMBER}

    # Add IP rules if they don't already exist
    if [[ `ip rule | grep "from 10.99.0.${NUMBER} lookup 10${NUMBER}"` ]]; then
        # They do exist
        echo -n ""
    else
        ip rule add from 10.99.0.${NUMBER} lookup 10${NUMBER}
    fi
done
