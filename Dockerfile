FROM kernelci/lava-docker:2017.06

# Additional packages
RUN DEBIAN_FRONTEND=noninteractive install_packages openssh-server

# Add local user w/sudo privs
RUN useradd -m baylibre && echo "baylibre:baylibre" | chpasswd && adduser baylibre sudo

# Update to latest lava-server
RUN /start.sh && \
  cd /root/lava-server && git remote update && git checkout -f origin/release && \
  git fetch https://review.linaro.org/lava/lava-server refs/changes/71/20171/1 && \
  git cherry-pick FETCH_HEAD && \
  /usr/share/lava-server/debian-dev-build.sh -p lava-server && \
  /stop.sh

# Add device configuration
COPY devices/* /etc/lava-server/dispatcher-config/devices/
COPY device-types/* /etc/lava-server/dispatcher-config/device-types/

# Fixup: set dispatcher IP to docker host instead of container (for TFTP)
COPY dispatcher.d/* /etc/lava-server/dispatcher.d/

RUN mkdir -p /tmp/tokens
COPY tokens/* /tmp/tokens/

COPY scripts/setup.sh .
COPY scripts/add-boards.py .

EXPOSE 22 80 3079 5555 5556

CMD /start.sh && /setup.sh && \
  /usr/sbin/service ssh start && \
  bash
