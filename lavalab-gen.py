#!/usr/bin/env python
#
from __future__ import print_function
import os, sys, time
import subprocess
import yaml
import string
import socket
import shutil

# Defaults
boards_yaml = "boards.yaml"
tokens_yaml = "tokens.yaml"
baud_default = 115200
ser2net_port_start = 63001
ser2net_ports = {}
allowed_hosts_list = [ '"127.0.0.1"' ]

template_conmux = string.Template("""#
# auto-generated by lavalab-gen.py for ${board}
#
listener ${board}
application console '${board} console' 'exec sg dialout "cu-loop /dev/${board} ${baud}"'
""")

#no comment it is volontary
template_device = string.Template("""{% extends '${devicetype}.jinja2' %}
""")

template_device_conmux = string.Template("""
{% set connection_command = 'conmux-console ${board}' %}
""")
template_device_connection_command = string.Template("""#
{% set connection_command = '${connection_command}' %}
""")
template_device_pdu_generic = string.Template("""
{% set hard_reset_command = '${hard_reset_command}' %}
{% set power_off_command = '${power_off_command}' %}
{% set power_on_command = '${power_on_command}' %}
""")

template_device_ser2net = string.Template("""
{% set connection_command = 'telnet 127.0.0.1 ${port}' %}
""")

template_device_screen = string.Template("""
{% set connection_command = 'ssh -o StrictHostKeyChecking=no -t root@127.0.0.1 "TERM=xterm screen -x ${board}"' %}
""")

template_settings_conf = string.Template("""
{
    "DEBUG": false,
    "STATICFILES_DIRS": [
        ["lava-server", "/usr/share/pyshared/lava_server/htdocs/"]
    ],
    "MEDIA_ROOT": "/var/lib/lava-server/default/media",
    "ARCHIVE_ROOT": "/var/lib/lava-server/default/archive",
    "STATIC_ROOT": "/usr/share/lava-server/static",
    "STATIC_URL": "/static/",
    "MOUNT_POINT": "/",
    "HTTPS_XML_RPC": false,
    "LOGIN_URL": "/accounts/login/",
    "LOGIN_REDIRECT_URL": "/",
    "ALLOWED_HOSTS": [ $allowed_hosts ],
    "CSRF_TRUSTED_ORIGINS": ["$lava_http_fqdn"],
    "CSRF_COOKIE_SECURE": $cookie_secure,
    "SESSION_COOKIE_SECURE": $session_cookie_secure,
    "SERVER_EMAIL": "admin@baylibre.com",
    "EMAIL_HOST": "10.1.1.3",
    "EMAIL_PORT": 25,
    "EMAIL_USE_TLS": true
}
""")

def dockcomp_add_device(dockcomp, worker_name, devicemap):
    if "devices" in dockcomp["services"][worker_name]:
        dc_devices = dockcomp["services"][worker_name]["devices"]
    else:
        dockcomp["services"][worker_name]["devices"] = []
        dc_devices = dockcomp["services"][worker_name]["devices"]
    for dmap in dc_devices:
        if dmap == devicemap:
            return
    dc_devices.append(devicemap)

def usage():
    print("%s [boardsfile.yaml]" % sys.argv[0])

def main():
    need_zmq_auth_gen = False
    fp = open(boards_yaml, "r")
    workers = yaml.load(fp)
    fp.close()

    os.mkdir("output")
    zmq_auth_genlist = open("zmqauth/zmq_auth_gen/zmq_genlist", 'w')

    if "masters" not in workers:
        masters = {}
    else:
        masters = workers["masters"]
    for master in masters:
        keywords_master = [ "name", "type", "host", "users", "groups", "tokens", "webadmin_https", "persistent_db", "zmq_auth", "zmq_auth_key", "zmq_auth_key_secret", "http_fqdn", "slave_keys", "slaveenv", "loglevel", "allowed_hosts" ]
        for keyword in master:
            if not keyword in keywords_master:
                print("WARNING: unknown keyword %s" % keyword)
        name = master["name"]
        print("Handle %s\n" % name)
        if not "host" in master:
            host = "local"
        else:
            host = master["host"]
        workerdir = "output/%s/%s" % (host, name)
        os.mkdir("output/%s" % host)
        shutil.copy("deploy.sh", "output/%s/" % host)
        dockcomp = {}
        dockcomp["version"] = "2.0"
        dockcomp["services"] = {}
        dockcomposeymlpath = "output/%s/docker-compose.yml" % host
        dockcomp["services"][name] = {}
        dockcomp["services"][name]["hostname"] = name
        dockcomp["services"][name]["ports"] = [ "10080:80", "5555:5555", "5556:5556", "5500:5500" ]
        dockcomp["services"][name]["volumes"] = [ "/boot:/boot", "/lib/modules:/lib/modules" ]
        dockcomp["services"][name]["build"] = {}
        dockcomp["services"][name]["build"]["context"] = name
        persistent_db = False
        if "persistent_db" in master:
            persistent_db = master["persistent_db"]
        if persistent_db:
            pg_volume_name = "pgdata_" + name
            dockcomp["services"][name]["volumes"].append(pg_volume_name + ":/var/lib/postgresql")
            dockcomp["services"][name]["volumes"].append("lava_job_output:/var/lib/lava-server/default/media/job-output/")
            dockcomp["volumes"] = {}
            dockcomp["volumes"][pg_volume_name] = {}
            dockcomp["volumes"]["lava_job_output"] = {}
        with open(dockcomposeymlpath, 'w') as f:
            yaml.dump(dockcomp, f)

        shutil.copytree("lava-master", workerdir)
        os.mkdir("%s/devices" % workerdir)
        # handle users / tokens
        userdir = "%s/users" % workerdir
        os.mkdir(userdir)
        groupdir = "%s/groups" % workerdir
        os.mkdir(groupdir)
        worker = master
        webadmin_https = False
        if "webadmin_https" in worker:
            webadmin_https = worker["webadmin_https"]
        if webadmin_https:
            cookie_secure = "true"
            session_cookie_secure = "true"
        else:
            cookie_secure = "false"
            session_cookie_secure = "false"
        if "http_fqdn" in worker:
            lava_http_fqdn = worker["http_fqdn"]
            allowed_hosts_list.append('"%s"' % lava_http_fqdn)
        else:
            lava_http_fqdn = "127.0.0.1"
        allowed_hosts_list.append('"%s"' % name)
        if "allowed_hosts" in worker:
            for allow_host in worker["allowed_hosts"]:
                allowed_hosts_list.append('"%s"' % allow_host)
        allowed_hosts = ','.join(allowed_hosts_list)
        f_fqdn = open("%s/lava_http_fqdn" % workerdir, 'w')
        f_fqdn.write(lava_http_fqdn)
        f_fqdn.close()
        fsettings = open("%s/settings.conf" % workerdir, 'w')
        fsettings.write(template_settings_conf.substitute(cookie_secure=cookie_secure, session_cookie_secure=session_cookie_secure, lava_http_fqdn=lava_http_fqdn, allowed_hosts=allowed_hosts))
        fsettings.close()
        master_use_zmq_auth = False
        if "zmq_auth" in worker:
            master_use_zmq_auth = worker["zmq_auth"]
        if master_use_zmq_auth:
            if "zmq_auth_key" in worker:
                shutil.copy(worker["zmq_auth_key"], "%s/zmq_auth/%s.key" % (workerdir, name))
                shutil.copy(worker["zmq_auth_key_secret"], "%s/zmq_auth/%s.key_secret" % (workerdir, name))
            else:
                zmq_auth_genlist.write("%s/%s\n" % (host, name))
                need_zmq_auth_gen = True
            if "slave_keys" in worker:
                src_files = os.listdir(worker["slave_keys"])
                for file_name in src_files:
                    full_file_name = os.path.join(worker["slave_keys"], file_name)
                    shutil.copy(full_file_name, "%s/zmq_auth/" % workerdir)
        if "users" in worker:
            for user in worker["users"]:
                keywords_users = [ "name", "staff", "superuser", "password", "token", "email", "groups" ]
                for keyword in user:
                    if not keyword in keywords_users:
                        print("WARNING: unknown keyword %s" % keyword)
                username = user["name"]
                ftok = open("%s/%s" % (userdir, username), "w")
                if "token" in user:
                    token = user["token"]
                    ftok.write("TOKEN=" + token + "\n")
                if "password" in user:
                    password = user["password"]
                    ftok.write("PASSWORD=" + password + "\n")
                    # libyaml convert yes/no to true/false...
                if "email" in user:
                    email = user["email"]
                    ftok.write("EMAIL=" + email + "\n")
                if "staff" in user:
                    value = user["staff"]
                    if value is True:
                        ftok.write("STAFF=1\n")
                if "superuser" in user:
                    value = user["superuser"]
                    if value is True:
                        ftok.write("SUPERUSER=1\n")
                ftok.close()
                if "groups" in user:
                    for group in user["groups"]:
                        groupname = group["name"]
                        print("\tAdd user %s to %s" % (username, groupname))
                        fgrp_userlist = open("%s/%s.group.list" % (groupdir, groupname), "a")
                        fgrp_userlist.write("%s\n" % username)
                        fgrp_userlist.close()
        if "groups" in worker:
            for group in worker["groups"]:
                groupname = group["name"]
                print("\tAdding group %s" % groupname)
                fgrp = open("%s/%s.group" % (groupdir, groupname), "w")
                fgrp.write("GROUPNAME=%s\n" % groupname)
                submitter = False
                if "submitter" in group:
                    submitter = group["submitter"]
                if submitter:
                    fgrp.write("SUBMIT=1\n")
                fgrp.close()
        tokendir = "%s/tokens" % workerdir
        os.mkdir(tokendir)
        if "tokens" in worker:
            filename_num = {}
            print("Found tokens")
            for token in worker["tokens"]:
                keywords_tokens = [ "username", "token", "description" ]
                for keyword in token:
                    if not keyword in keywords_tokens:
                        print("WARNING: unknown keyword %s" % keyword)
                username = token["username"]
                description = token["description"]
                if username in filename_num:
                    number = filename_num[username]
                    filename_num[username] = filename_num[username] + 1
                else:
                    filename_num[username] = 1
                    number = 0
                filename = "%s-%d" % (username, number)
                print("\tAdd token for %s in %s" % (username, filename))
                ftok = open("%s/%s" % (tokendir, filename), "w")
                ftok.write("USER=" + username + "\n")
                vtoken = token["token"]
                ftok.write("TOKEN=" + vtoken + "\n")
                ftok.write("DESCRIPTION=\"%s\"" % description)
                ftok.close()
        if "slaveenv" in worker:
            for slaveenv in worker["slaveenv"]:
                slavename = slaveenv["name"]
                envdir = "%s/env/%s" % (workerdir, slavename)
                os.mkdir(envdir)
                fenv = open("%s/env.yaml" % envdir, 'w')
                fenv.write("overrides:\n")
                for line in slaveenv["env"]:
                    fenv.write("  %s\n" % line)
                fenv.close()
        if "loglevel" in worker:
            for component in worker["loglevel"]:
                if component != "lava-master" and component != "lava-logs" and component != 'lava-server-gunicorn':
                    print("ERROR: invalid loglevel component %s" % component)
                    sys.exit(1)
                loglevel = worker["loglevel"][component]
                if loglevel != 'DEBUG' and loglevel != 'INFO' and loglevel != 'WARN' and loglevel != 'ERROR':
                    print("ERROR: invalid loglevel %s for %s" % (loglevel, component))
                    sys.exit(1)
                fcomponent = open("%s/default/%s" % (workerdir, component), 'w')
                fcomponent.write("LOGLEVEL=%s\n" % loglevel)
                fcomponent.close()

    default_slave = "lab-slave-0"
    if "slaves" not in workers:
        slaves = {}
    else:
        slaves = workers["slaves"]
    for slave in slaves:
        keywords_slaves = [ "name", "host", "dispatcher_ip", "remote_user", "remote_master", "remote_address", "remote_rpc_port", "remote_proto", "extra_actions", "zmq_auth_key", "zmq_auth_key_secret", "default_slave", "export_ser2net", "expose_ser2net", "remote_user_token", "zmq_auth_master_key", "expose_ports", "env", "bind_dev", "loglevel", "use_nfs", "arch", "devices" ]
        for keyword in slave:
            if not keyword in keywords_slaves:
                print("WARNING: unknown keyword %s" % keyword)
        name = slave["name"]
        if len(slaves) == 1:
            default_slave = name
        print("Handle %s" % name)
        if not "host" in slave:
            host = "local"
        else:
            host = slave["host"]
        if slave.get("default_slave") and slave["default_slave"]:
             default_slave = name
        workerdir = "output/%s/%s" % (host, name)
        dockcomposeymlpath = "output/%s/docker-compose.yml" % host
        if not os.path.isdir("output/%s" % host):
            os.mkdir("output/%s" % host)
            shutil.copy("deploy.sh", "output/%s/" % host)
            dockcomp = {}
            dockcomp["version"] = "2.0"
            dockcomp["services"] = {}
        else:
            #master exists
            fp = open(dockcomposeymlpath, "r")
            dockcomp = yaml.load(fp)
            fp.close()
        dockcomp["services"][name] = {}
        dockcomp["services"][name]["hostname"] = name
        dockcomp["services"][name]["dns_search"] = ""
        dockcomp["services"][name]["ports"] = [ "69:69/udp", "80:80", "61950-62000:61950-62000" ]
        dockcomp["services"][name]["volumes"] = [ "/boot:/boot", "/lib/modules:/lib/modules" ]
        dockcomp["services"][name]["environment"] = {}
        dockcomp["services"][name]["build"] = {}
        dockcomp["services"][name]["build"]["context"] = name
        # insert here remote

        shutil.copytree("lava-slave", workerdir)
        fp = open("%s/phyhostname" % workerdir, "w")
        fp.write(host)
        fp.close()
        conmuxpath = "%s/conmux" % workerdir
        if not os.path.isdir(conmuxpath):
            os.mkdir(conmuxpath)

        worker = slave
        worker_name = name
        slave_master = None
        if "arch" in worker:
            if worker["arch"] == 'arm64':
                dockerfile = open("%s/Dockerfile" % workerdir, "r+")
                dockerfilec = dockerfile.read().replace("lava-slave-base", "lava-slave-base-arm64")
                dockerfile.seek(0)
                dockerfile.write(dockerfilec)
                dockerfile.close()
        #NOTE remote_master is on slave
        if not "remote_master" in worker:
            remote_master = "lava-master"
        else:
            remote_master = worker["remote_master"]
        if not "remote_address" in worker:
            remote_address = remote_master
        else:
            remote_address = worker["remote_address"]
        if not "remote_rpc_port" in worker:
            remote_rpc_port = "80"
        else:
            remote_rpc_port = worker["remote_rpc_port"]
        dockcomp["services"][worker_name]["environment"]["LAVA_MASTER"] = remote_address
        remote_user = worker["remote_user"]
        # find master
        remote_token = "BAD"
        if "masters" in workers:
            masters = workers["masters"]
        else:
            masters = {}
            if "remote_user_token" in worker:
                remote_token = worker["remote_user_token"]
                if "zmq_auth_key" in worker:
                    shutil.copy(worker["zmq_auth_key"], "%s/zmq_auth/" % workerdir)
                    shutil.copy(worker["zmq_auth_key_secret"], "%s/zmq_auth/" % workerdir)
                    shutil.copy(worker["zmq_auth_master_key"], "%s/zmq_auth/" % workerdir)
        for fm in masters:
            if fm["name"] == remote_master:
                slave_master = fm
                for fuser in fm["users"]:
                    if fuser["name"] == remote_user:
                        remote_token = fuser["token"]
                if "zmq_auth" in fm:
                    master_use_zmq_auth = fm["zmq_auth"]
                if master_use_zmq_auth:
                    if "zmq_auth_key" in fm:
                        shutil.copy(fm["zmq_auth_key"], "%s/zmq_auth/%s.key" % (workerdir, remote_address))
                    if "zmq_auth_key" in worker:
                        shutil.copy(worker["zmq_auth_key"], "%s/zmq_auth/%s.key" % (workerdir, name))
                        shutil.copy(worker["zmq_auth_key_secret"], "%s/zmq_auth/%s.key_secret" % (workerdir, name))
                        if "zmq_auth_key" in fm:
                            shutil.copy(worker["zmq_auth_key"], "output/%s/%s/zmq_auth/%s.key" % (fm["host"], fm["name"], name))
                    else:
                        zmq_auth_genlist.write("%s/%s %s/%s\n" % (host, name, fm["host"], fm["name"]))
                        need_zmq_auth_gen = True
        if remote_token is "BAD":
            print("Cannot find %s on %s" % (remote_user, remote_master))
            sys.exit(1)
        if "env" in slave:
            if not slave_master:
                print("Cannot set env without master")
                sys.exit(1)
            envdir = "output/%s/%s/env/%s" % (slave_master["host"], slave_master["name"], name)
            os.mkdir(envdir)
            fenv = open("%s/env.yaml" % envdir, 'w')
            fenv.write("overrides:\n")
            for line in slave["env"]:
                fenv.write("  %s\n" % line)
            fenv.close()
        if not "remote_proto" in worker:
            remote_proto = "http"
        else:
            remote_proto = worker["remote_proto"]
        remote_uri = "%s://%s:%s@%s:%s/RPC2" % (remote_proto, remote_user, remote_token, remote_address, remote_rpc_port)
        dockcomp["services"][worker_name]["environment"]["LAVA_MASTER_URI"] = remote_uri

        if "dispatcher_ip" in worker:
            dockcomp["services"][worker_name]["environment"]["LAVA_DISPATCHER_IP"] = worker["dispatcher_ip"]
        if "expose_ports" in worker:
            for eports in worker["expose_ports"]:
                dockcomp["services"][name]["ports"].append("%s" % eports)
        if "bind_dev" in worker:
            dockcomp["services"][worker_name]["volumes"].append("/dev:/dev")
            dockcomp["services"][worker_name]["privileged"] = True
        with open(dockcomposeymlpath, 'w') as f:
            yaml.dump(dockcomp, f)
        if "extra_actions" in worker:
            fp = open("%s/scripts/extra_actions" % workerdir, "w")
            for eaction in worker["extra_actions"]:
                fp.write(eaction)
                fp.write("\n")
            fp.close()
            os.chmod("%s/scripts/extra_actions" % workerdir, 0o755)

        if "devices" in worker:
            if not os.path.isdir("output/%s/udev" % host):
                os.mkdir("output/%s/udev" % host)
            for udev_dev in worker["devices"]:
                udev_line = 'SUBSYSTEM=="tty", ATTRS{idVendor}=="%04x", ATTRS{idProduct}=="%04x",' % (udev_dev["idvendor"], udev_dev["idproduct"])
                if "serial" in udev_dev:
                    udev_line += 'ATTRS{serial}=="%s", ' % udev_dev["serial"]
                if "devpath" in udev_dev:
                    udev_line += 'ATTRS{devpath}=="%s", ' % udev_dev["devpath"]
                udev_line += 'MODE="0664", OWNER="uucp", SYMLINK+="%s"\n' % udev_dev["name"]
                fudev = open("output/%s/udev/99-lavaworker-udev.rules" % host, "a")
                fudev.write(udev_line)
                fudev.close()
                if not "bind_dev" in slave:
                    dockcomp_add_device(dockcomp, worker_name, "/dev/%s:/dev/%s" % (udev_dev["name"], udev_dev["name"]))
        use_nfs = False
        if "use_nfs" in worker:
            use_nfs = worker["use_nfs"]
        if use_nfs:
            dockcomp["services"][worker_name]["volumes"].append("/var/lib/lava/dispatcher/tmp:/var/lib/lava/dispatcher/tmp")
            fp = open("%s/scripts/extra_actions" % workerdir, "a")
            fp.write("apt-get -y install nfs-kernel-server\n")
            fp.close()
            os.chmod("%s/scripts/extra_actions" % workerdir, 0o755)
        if "loglevel" in worker:
            for component in worker["loglevel"]:
                if component != "lava-slave":
                    print("ERROR: invalid loglevel component %s" % component)
                    sys.exit(1)
                loglevel = worker["loglevel"][component]
                if loglevel != 'DEBUG' and loglevel != 'INFO' and loglevel != 'WARN' and loglevel != 'ERROR':
                    print("ERROR: invalid loglevel %s for %s" % (loglevel, component))
                    sys.exit(1)
                fcomponent = open("%s/default/%s" % (workerdir, component), 'w')
                fcomponent.write("LOGLEVEL=%s\n" % loglevel)
                fcomponent.close()

    if "boards" not in workers:
        boards = {}
    else:
        boards = workers["boards"]
    for board in boards:
        board_name = board["name"]
        if "slave" in board:
            worker_name = board["slave"]
        else:
            worker_name = default_slave
        print("\tFound %s on %s" % (board_name, worker_name))
        found_slave = False
        for fs in workers["slaves"]:
            if fs["name"] == worker_name:
                slave = fs
                found_slave = True
        if not found_slave:
            print("Cannot find slave %s" % worker_name)
            sys.exit(1)
        if not "host" in slave:
            host = "local"
        else:
            host = slave["host"]
        workerdir = "output/%s/%s" % (host, worker_name)
        dockcomposeymlpath = "output/%s/docker-compose.yml" % host
        fp = open(dockcomposeymlpath, "r")
        dockcomp = yaml.load(fp)
        fp.close()
        device_path = "%s/devices/" % workerdir
        devices_path = "%s/devices/%s" % (workerdir, worker_name)
        devicetype = board["type"]
        device_line = template_device.substitute(devicetype=devicetype)
        if "pdu_generic" in board:
            hard_reset_command = board["pdu_generic"]["hard_reset_command"]
            power_off_command = board["pdu_generic"]["power_off_command"]
            power_on_command = board["pdu_generic"]["power_on_command"]
            device_line += template_device_pdu_generic.substitute(hard_reset_command=hard_reset_command, power_off_command=power_off_command, power_on_command=power_on_command)
        use_kvm = False
        if "kvm" in board:
            use_kvm = board["kvm"]
        if use_kvm:
            dockcomp_add_device(dockcomp, worker_name, "/dev/kvm:/dev/kvm")
            # board specific hacks
        use_tap = False
        if "tap" in board:
            use_tap = board["tap"]
        if use_tap:
            dockcomp_add_device(dockcomp, worker_name, "/dev/net/tun:/dev/net/tun")
        if devicetype == "qemu" and not use_kvm:
            device_line += "{% set no_kvm = True %}\n"
        if "uart" in board:
            uart = board["uart"]
            baud = board["uart"].get("baud", baud_default)
            idvendor = board["uart"]["idvendor"]
            idproduct = board["uart"]["idproduct"]
            if type(idproduct) == str:
                print("Please put hexadecimal IDs for product %s (like 0x%s)" % (board_name, idproduct))
                sys.exit(1)
            if type(idvendor) == str:
                print("Please put hexadecimal IDs for vendor %s (like 0x%s)" % (board_name, idvendor))
                sys.exit(1)
            udev_line = 'SUBSYSTEM=="tty", ATTRS{idVendor}=="%04x", ATTRS{idProduct}=="%04x",' % (idvendor, idproduct)
            if "serial" in uart:
                udev_line += 'ATTRS{serial}=="%s", ' % board["uart"]["serial"]
            if "devpath" in uart:
                udev_line += 'ATTRS{devpath}=="%s", ' % board["uart"]["devpath"]
            if "interfacenum" in uart:
                udev_line += 'ENV{ID_USB_INTERFACE_NUM}=="%s", ' % board["uart"]["interfacenum"]
            udev_line += 'MODE="0664", OWNER="uucp", SYMLINK+="%s"\n' % board_name
            if not os.path.isdir("output/%s/udev" % host):
                os.mkdir("output/%s/udev" % host)
            fp = open("output/%s/udev/99-lavaworker-udev.rules" % host, "a")
            fp.write(udev_line)
            fp.close()
            if not "bind_dev" in slave:
                dockcomp_add_device(dockcomp, worker_name, "/dev/%s:/dev/%s" % (board_name, board_name))
            use_conmux = False
            use_ser2net = False
            use_screen = False
            if "use_screen" in uart:
                use_screen = uart["use_screen"]
            if "use_conmux" in uart:
                use_conmux = uart["use_conmux"]
            if "use_ser2net" in uart:
                use_ser2net = uart["use_ser2net"]
            if (use_conmux and use_ser2net) or (use_conmux and use_screen) or (use_screen and use_ser2net):
                print("ERROR: Only one uart handler must be configured")
                sys.exit(1)
            if not use_conmux and not use_screen and not use_ser2net:
                use_ser2net = True
            if use_conmux:
                conmuxline = template_conmux.substitute(board=board_name, baud=baud)
                device_line += template_device_conmux.substitute(board=board_name)
                fp = open("%s/conmux/%s.cf" % (workerdir, board_name), "w")
                fp.write(conmuxline)
                fp.close()
            if use_ser2net:
                if not worker_name in ser2net_ports:
                    ser2net_ports[worker_name] = ser2net_port_start
                    fp = open("%s/ser2net.conf" % workerdir, "a")
                    fp.write("DEFAULT:max-connections:10\n")
                    fp.close()
                ser2net_line = "%d:telnet:600:/dev/%s:%d 8DATABITS NONE 1STOPBIT" % (ser2net_ports[worker_name], board_name, baud)
                if "ser2net_options" in uart:
                    for ser2net_option in uart["ser2net_options"]:
                        ser2net_line += " %s" % ser2net_option
                device_line += template_device_ser2net.substitute(port=ser2net_ports[worker_name])
                ser2net_ports[worker_name] += 1
                fp = open("%s/ser2net.conf" % workerdir, "a")
                fp.write(ser2net_line + " banner\n")
                fp.close()
            if use_screen:
                device_line += template_device_screen.substitute(board=board_name)
                fp = open("%s/lava-screen.conf" % workerdir, "a")
                fp.write("%s\n" % board_name)
                fp.close()
        elif "connection_command" in board:
            connection_command = board["connection_command"]
            device_line += template_device_connection_command.substitute(connection_command=connection_command)
        if "uboot_ipaddr" in board:
            device_line += "{%% set uboot_ipaddr_cmd = 'setenv ipaddr %s' %%}\n" % board["uboot_ipaddr"]
        if "uboot_macaddr" in board:
            device_line += '{% set uboot_set_mac = true %}'
            device_line += "{%% set uboot_mac_addr = '%s' %%}\n" % board["uboot_macaddr"]
        if "fastboot_serial_number" in board:
            fserial = board["fastboot_serial_number"]
            device_line += "{%% set fastboot_serial_number = '%s' %%}" % fserial
        if "tags" in board:
            tagdir = "%s/tags/" % workerdir
            ftag = open("%s/%s" % (tagdir, board_name), 'w')
            for tag in board["tags"]:
                ftag.write("%s\n" % tag)
            ftag.close()
        if "user" in board:
            deviceinfo = open("%s/deviceinfo/%s" % (workerdir, board_name), 'w')
            deviceinfo.write("DEVICE_USER=%s\n" % board["user"])
            deviceinfo.close()
        if "group" in board:
            if "user" in board:
                    print("user and group are exclusive")
                    sys.exit(1)
            deviceinfo = open("%s/deviceinfo/%s" % (workerdir, board_name), 'w')
            deviceinfo.write("DEVICE_GROUP=%s\n" % board["group"])
            deviceinfo.close()
        if "custom_option" in board:
            if type(board["custom_option"]) == list:
                for coption in board["custom_option"]:
                    device_line += "{%% %s %%}\n" % coption
            else:
                for line in board["custom_option"].splitlines():
                    device_line += "{%% %s %%}\n" % line
        if not os.path.isdir(device_path):
            os.mkdir(device_path)
        if not os.path.isdir(devices_path):
            os.mkdir(devices_path)
        board_device_file = "%s/%s.jinja2" % (devices_path, board_name)
        fp = open(board_device_file, "w")
        fp.write(device_line)
        fp.close()
        with open(dockcomposeymlpath, 'w') as f:
            yaml.dump(dockcomp, f)
        #end for board

    for slave_name in ser2net_ports:
        expose_ser2net = False
        for fs in workers["slaves"]:
            if fs["name"] == slave_name:
                if not "host" in fs:
                    host = "local"
                else:
                    host = fs["host"]
                if "expose_ser2net" in fs:
                    expose_ser2net = fs["expose_ser2net"]
                if "export_ser2net" in fs:
                    print("export_ser2net is deprecated, please use expose_ser2net")
                    expose_ser2net = fs["export_ser2net"]
        if not expose_ser2net:
            continue
        print("Add ser2net ports for %s (%s) %s-%s" % (slave_name, host, ser2net_port_start, ser2net_ports[slave_name]))
        dockcomposeymlpath = "output/%s/docker-compose.yml" % host
        fp = open(dockcomposeymlpath, "r")
        dockcomp = yaml.load(fp)
        fp.close()
        ser2net_port_max = ser2net_ports[slave_name] - 1
        dockcomp["services"][slave_name]["ports"].append("%s-%s:%s-%s" % (ser2net_port_start, ser2net_port_max, ser2net_port_start, ser2net_port_max))
        with open(dockcomposeymlpath, 'w') as f:
            yaml.dump(dockcomp, f)

    zmq_auth_genlist.close()
    if need_zmq_auth_gen:
        print("Gen ZMQ auth files")
        subprocess.check_call(["./zmqauth/zmq_auth_fill.sh"], stdin=None)

if len(sys.argv) > 1:
    if sys.argv[1] == '-h' or sys.argv[1] == '--help':
        usage()
        sys.exit(0)
    boards_yaml = sys.argv[1]

if __name__ == "__main__":
    main()

