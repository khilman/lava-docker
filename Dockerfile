FROM kernelci/lava-docker:2017.05

# Update to latest lava-server
RUN /start.sh && \
  cd /root/lava-server && git remote update && git checkout -f 2f6287e71cf5 && \
  /usr/share/lava-server/debian-dev-build.sh -p lava-server && \
  /stop.sh

# Add local devices and device-types
COPY devices/* /etc/dispatcher-config/devices/
COPY device-types/* /etc/lava-server/dispatcher-config/device-types/

# Fixup: set dispatcher IP to docker host instead of container (for TFTP)
COPY dispatcher.d/* /etc/lava-server/dispatcher.d/

COPY scripts/setup.sh .
COPY scripts/add-boards.py .

EXPOSE 69/udp 80 3079 5555 5556

CMD /start.sh && /setup.sh && bash
