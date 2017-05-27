#!/usr/bin/env python

import os
import string
import glob
import re
import argparse
import subprocess

devices_dir = "/etc/dispatcher-config/devices"

template = string.Template("""# ${board_name};  device_type: ${device_type}
if [ -e /etc/lava-server/dispatcher-config/device-types/${device_type}.jinja2 ]; then \
  lava-server manage device-types add ${device_type}; \
  lava-server manage devices add --device-type ${device_type} --worker ${slave} ${board_name}; \
  lava-server manage device-dictionary --hostname ${board_name} --import /etc/dispatcher-config/devices/${board_name}.jinja2; \
else \
  echo "WARNING: Missing device-type jinja2 file for ${device_type}."; \
fi
""")

def main(args):
    os.chdir(devices_dir)
    for file in glob.glob("*.jinja2"):
        board_name, suffix = os.path.splitext(file)
        fp = open(file, "r")
        line = fp.readline()
        fp.close

        device_type = None
        m = re.search("extends \'(.*)\.jinja2\'", line)
        if m:
            device_type = m.group(1)
        else:
            print "ERROR: Unable to find device-type in %s." % file
            continue
        
        commands = template.substitute(slave=args.slave, board_name=board_name, device_type=device_type)
        for cmd in commands.splitlines():
#            print cmd
            subprocess.call(cmd, shell=True)
            
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--slave", required=True)
    args = parser.parse_args()
    main(args)
                    
