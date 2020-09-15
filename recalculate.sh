#!/bin/bash

echo > /etc/bird_ospf.conf

for system in `cat systems.txt`; do
    HOST=$(echo $system | cut -d';' -f1)
    IP=$(echo $system | cut -d';' -f2)
    NUMBER=$(echo $system | cut -d';' -f3)

    LOCALIP=$(ip a show dev ${HOST} | grep -Po "inet [0-9]{1,3}.[0-9]{1,3}.[0-9]{1,3}.[0-9]{1,3}" | cut -d' ' -f2)
    LOCALIP_PREFIX=$(echo ${LOCALIP} | cut -d'.' -f1-3)
    if [[ `echo ${LOCALIP} | cut -d'.' -f4` == "1" ]]; then
        TESTIP=${LOCALIP_PREFIX}".0"
    else
        TESTIP=${LOCALIP_PREFIX}".1"
    fi

    LATENCY=$(ping -i0.1 -c20 ${TESTIP} | grep 'min/avg' | cut -d'=' -f2 | cut -d'/' -f2)
    COST=$(echo ${LATENCY}*100 | bc | cut -d '.' -f1)

    echo "Setting cost to ${HOST} / ${IP} to ${COST}"

    echo """
    interface \"${HOST}\" {
        type ptp;
        cost ${COST};
    };
    """ >> /etc/bird_ospf.conf
done

systemctl enable --now bird
birdc conf
