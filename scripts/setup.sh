#!/bin/bash
# Set LAVA Server IP
if [[ -n "$LAVA_SERVER_IP" ]]; then
	sed -i "s/.*LAVA_SERVER_IP =.*/LAVA_SERVER_IP = $LAVA_SERVER_IP/g" /etc/lava-dispatcher/lava-dispatcher.conf
fi
# Create users
echo "from django.contrib.auth.models import User; User.objects.create_superuser('kernel-ci', 'admin@localhost.com', 'kernel-ci')" | lava-server manage shell
echo "from django.contrib.auth.models import User; User.objects.create_superuser('khilman', 'admin@localhost.com', 'lava4me')" | lava-server manage shell

# Set the kernelci user's API token
if [[ -n "$LAVA_API_TOKEN" ]]; then
	lava-server manage tokens add --user kernel-ci --secret $LAVA_API_TOKEN
else
	lava-server manage tokens add --user kernel-ci
fi

# By default add a worker on the master
lava-server manage workers add $(hostname)

# Add devices on master
lava-server manage device-types add qemu
lava-server manage devices add  --device-type qemu --worker $(hostname) qemu-01
lava-server manage devices add --device-type qemu --worker $(hostname) qemu-02

# add remote workers
SLAVE=lab-slave-0
lava-server manage pipeline-worker --hostname $SLAVE

# add remote devices

# Array of <board name>:<LAVA device-type>
#lava-server manage device-types add beaglebone-black
#lava-server manage devices add --device-type beaglebone-black --worker $SLAVE am335x-boneblack
#lava-server manage device-dictionary --hostname am335x-boneblack --import /etc/dispatcher-config/devices/am335x-boneblack.jinja2
#exit 0

#BOARDS="am335x-boneblack:beaglebone-black"
BOARDS="am335x-boneblack:beaglebone-black omap4-panda-es:panda"
#BOARDS="am335x-boneblack:beaglebone-black omap4-panda-es:panda meson8b-odroidc1-0:meson8b-odroidc1"


for board_type in ${BOARDS}; do
  IFS=':' read -a arr <<< "$board_type"
  board_name=${arr[0]}
  device_type=${arr[1]}
  IFS=$OIFS

  lava-server manage device-types add ${device_type}
  lava-server manage devices add --device-type ${device_type} --worker $SLAVE ${board_name}
  lava-server manage device-dictionary --hostname ${board_name} --import /etc/dispatcher-config/devices/${board_name}.jinja2
done
