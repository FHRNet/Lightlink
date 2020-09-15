#!/bin/bash
#
# Subnetting
# 10.20.X.{0,1} :: GRE tunnels
# 10.30.0.X     :: Loopbacks
# 10.30.4.X     :: VXLAN overlay
# 10.254/16     :: VPNs

CLIENT_NODE="1.2.3.4"

# Clear the configs
rm -r /tmp/lightlink
mkdir -p /tmp/lightlink

# Generate configs
python3 prepare.py

# DEPLOY!!!!!!!
for system in `cat systems.txt`; do
    HOST=$(echo $system | cut -d';' -f1)
    IP=$(echo $system | cut -d';' -f2)
    NUMBER=$(echo $system | cut -d';' -f3)
    IP_LOOPBACK=$(cat /tmp/lightlink/linklocals.txt | grep ${HOST} | cut -d';' -f2)

    echo "Copying files to ${HOST} - ${IP}"

    scp recalculate.sh root@${IP}:/etc/cron.hourly/recalculate.sh
    scp /tmp/lightlink/hosts root@${IP}:/etc/hosts
    cat bird.conf | sed "s/<<LOOPBACK>>/${IP_LOOPBACK}/g" | ssh root@${IP} "cat > /etc/bird.conf"
    cat systems.txt | grep -iv ${IP} | ssh root@${IP} "cat > /root/systems.txt"

done

echo ""
echo "Deploying tunnels..."

# Execute the deployment
for system in `cat systems.txt`; do
    HOST=$(echo $system | cut -d';' -f1)
    IP=$(echo $system | cut -d';' -f2)
    NUMBER=$(echo $system | cut -d';' -f3)

    ssh root@${IP} "bash -s" < /tmp/lightlink/cmds.${HOST}.txt
done

echo ""
echo "Deployment finished, recalculating paths..."

# Recalculate weights
for system in `cat systems.txt`; do
    HOST=$(echo $system | cut -d';' -f1)
    IP=$(echo $system | cut -d';' -f2)
    NUMBER=$(echo $system | cut -d';' -f3)

    echo "$HOST / $IP - Recalculating weights..."
    ssh root@${IP} "chmod a+x /etc/cron.hourly/recalculate.sh && bash /etc/cron.hourly/recalculate.sh"
done

echo "Deploying the optimizer"
scp optimizer.py root@${CLIENT_NODE}:~
scp deploy_optimizer.sh root@${CLIENT_NODE}:~
ssh root@${CLIENT_NODE} "chmod a+x /root/optimizer.py"
ssh root@${CLIENT_NODE} "bash /root/deploy_optimizer.sh"
