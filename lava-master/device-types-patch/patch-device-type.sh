#!/bin/sh
#shellcheck disable=SC2045

DEVTYPE_PATH=/etc/lava-server/dispatcher-config/device-types/
if [ -e /usr/share/lava-server/device-types/ ];then
	DEVTYPE_PATH=/usr/share/lava-server/device-types/
fi

cd "$DEVTYPE_PATH" || exit $?
for patch in $(ls /root/device-types-patch/*patch)
do
	echo "DEBUG: patch with $patch"
	sed -i 's,lava_scheduler_app/tests/device-types/,,' "$patch" || exit $?
	sed -i 's,etc/dispatcher-config/device-types/,,' "$patch" || exit $?
	patch -p1 < "$patch" || exit $?
done
chown -R lavaserver:lavaserver "$DEVTYPE_PATH"
