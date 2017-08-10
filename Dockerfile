FROM kernelci/lava-docker:2017.06

# Additional packages
RUN DEBIAN_FRONTEND=noninteractive install_packages openssh-server

# Add local user w/sudo privs
RUN useradd -m baylibre && echo "baylibre:baylibre" | chpasswd && adduser baylibre sudo

# Update to latest lava-server
RUN /start.sh && \
  cd /root/lava-server && git remote update && git checkout -f origin/lab-baylibre && \
  /usr/share/lava-server/debian-dev-build.sh -p lava-server && \
  /stop.sh

# Add device configuration
COPY devices/* /etc/lava-server/dispatcher-config/devices/
COPY device-types/* /etc/lava-server/dispatcher-config/device-types/

# Fixup: set dispatcher IP to docker host instead of container (for TFTP)
COPY dispatcher.d/* /etc/lava-server/dispatcher.d/

# add environment variables to lava-server/lava-dispatcher
COPY config/env.yaml.append /etc/lava-server
RUN cat /etc/lava-server/env.yaml.append >> /etc/lava-server/env.yaml

RUN mkdir -p /tmp/tokens
COPY tokens/* /tmp/tokens/

# kCI callback tokens
COPY config/kci-callback-token /tmp
COPY config/kci-staging-token /tmp

COPY scripts/setup.sh .
COPY scripts/add-boards.py .

EXPOSE 22 80 3079 5555 5556

CMD /start.sh && /setup.sh && \
  /usr/sbin/service ssh start && \
  bash
