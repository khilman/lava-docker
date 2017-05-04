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
#lava-server manage workers add $(hostname)

# Add devices on master
#lava-server manage device-types add qemu
#lava-server manage devices add --device-type qemu --worker $(hostname) qemu-01
#lava-server manage device-dictionary --hostname qemu-01 --import /etc/dispatcher-config/devices/qemu-device-dictionary.jinja2
#lava-server manage devices add --device-type qemu --worker $(hostname) qemu-02
#lava-server manage device-dictionary --hostname qemu-02 --import /etc/dispatcher-config/devices/qemu-device-dictionary.jinja2

# add remote workers
SLAVE=lab-slave-0
lava-server manage workers add $SLAVE

# add remote devices
/add-boards.py --slave $SLAVE
