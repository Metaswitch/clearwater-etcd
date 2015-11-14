from subprocess import Popen, PIPE, STDOUT
import httplib
import json
from time import sleep
from signal import SIGTERM, SIGABRT
import shlex
import etcd
from shutil import rmtree

base_cmd =              """clearwater-etcd/usr/bin/etcd --debug --listen-client-urls http://{0}:4000 --advertise-client-urls http://{0}:4000 --listen-peer-urls http://{0}:2380 --initial-advertise-peer-urls http://{0}:2380 --data-dir {2}/{1} --name {1}"""

first_member_cmd =      base_cmd + """ --initial-cluster-state new --initial-cluster {1}=http://{0}:2380"""
subsequent_member_cmd = base_cmd + """ --initial-cluster-state existing --initial-cluster {3},{1}=http://{0}:2380"""

class EtcdServer(object):
    datadir = "./etcd_test_data"


    @classmethod
    def delete_datadir(cls):
        rmtree(cls.datadir)

    def __init__(self, ip, existing=None, replacement=False):
        self._ip = ip
        self._exit_signal = SIGTERM
        name = ip.replace(".", "-")

        logfile = open("etcd-{}.log".format(ip), "w")

        if existing is None:
            self._subprocess = Popen(shlex.split(first_member_cmd.format(ip, name, EtcdServer.datadir)),
                                     stdout=logfile,
                                     stderr=STDOUT
                                     )
        else:
            my_url = "http://{}:2380".format(ip)
            cxn = httplib.HTTPConnection(existing, 4000)
            if not replacement:
                cxn.request("POST",
                            "/v2/members",
                            json.dumps({"name": name, "peerURLs": [my_url]}),
                            {"Content-Type": "application/json"})
                me = json.loads(cxn.getresponse().read())
                self._id = me['id']

            cxn.request("GET", "/v2/members?consistent=false");
            member_data = json.loads(cxn.getresponse().read())
            cluster = ",".join(["{}={}".format(m['name'], m['peerURLs'][0]) for m in member_data['members'] if m['peerURLs'][0] != my_url])
            self._subprocess = Popen(shlex.split(subsequent_member_cmd.format(ip, name, EtcdServer.datadir, cluster)),
                                     stdout=logfile,
                                     stderr=STDOUT
                                     )

    def cluster_id(self):
        if self._id is None:
            members = self.memberList()
            pass
        return self._id

    def isAlive(self):
        try:
            return self.write_test_key()
        except (IOError, ValueError):
            return False

    def waitUntilAlive(self):
        for _ in range(50):
            if self.isAlive():
                return True
            else:
                sleep(0.1)
        return False

    def write_test_key(self):
        cxn = httplib.HTTPConnection(self._ip, 4000)
        cxn.request("PUT",
                    "/v2/keys/init_test",
                    "hello world")
        rsp = cxn.getresponse()
        return ((rsp.status == 200) or (rsp.status == 201))

    def isLeader(self):
        cxn = httplib.HTTPConnection(self._ip, 4000)
        cxn.request("GET", "/v2/stats/self");
        rsp = cxn.getresponse().read()
        return json.loads(rsp)['state'] == "stateLeader"

    def __del__(self):
        # Kill the etcd subprocess on destruction
        self.exit()

    def memberList(self):
        cxn = httplib.HTTPConnection(self._ip, 4000)
        cxn.request("GET", "/v2/members");
        return json.loads(cxn.getresponse().read())['members']

    def exit(self):
        if self._subprocess:
            self._subprocess.send_signal(self._exit_signal)
            self._subprocess.communicate()
            self._subprocess = None

    def crash(self):
        if self._subprocess:
            self._subprocess.send_signal(SIGABRT)
            self._subprocess.communicate()
            self._subprocess = None

    def delete(self, peer):
        cxn = httplib.HTTPConnection(peer, 4000)
        cxn.request("DELETE", "/v2/members/{}".format(self._id));
        cxn.getresponse().read()

    def client(self):
        return etcd.Client(self._ip, port=4000)
