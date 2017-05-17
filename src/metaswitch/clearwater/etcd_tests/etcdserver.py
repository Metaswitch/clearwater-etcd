from subprocess import Popen, STDOUT
import httplib
import json
from time import sleep
from signal import SIGTERM, SIGABRT
import shlex
import etcd
from shutil import rmtree
import uuid

base_cmd =              """clearwater-etcd/usr/share/clearwater/clearwater-etcd/3.1.7/etcd --debug --listen-client-urls http://{0}:4000 --advertise-client-urls http://{0}:4000 --listen-peer-urls http://{0}:2380 --initial-advertise-peer-urls http://{0}:2380 --data-dir {2} --name {1}"""

first_member_cmd =      base_cmd + """ --initial-cluster-state new --initial-cluster {1}=http://{0}:2380"""
subsequent_member_cmd = base_cmd + """ --initial-cluster-state existing --initial-cluster {3},{1}=http://{0}:2380"""

class EtcdServer(object):
    def __init__(self, ip, datadir, existing=None, actually_start=True):
        self._ip = ip
        self._existing = existing

        # Save a reference to SIGTERM so we can use it in __del__
        self._exit_signal = SIGTERM
        self._name = ip.replace(".", "-")
        self._datadir = datadir + "/" + self._name

        self._logfile = open("etcd-{}.log".format(ip), "w")
        self.start_process(actually_start)

    def start_process(self, actually_start=True):
        if self._existing is None:
            self._cmd = shlex.split(first_member_cmd.format(self._ip, self._name, self._datadir))
        else:
            my_url = "http://{}:2380".format(self._ip)
            cxn = httplib.HTTPConnection(self._existing, 4000, timeout=10)

            cxn.request("GET", "/v2/members?consistent=false");
            member_data = json.loads(cxn.getresponse().read())
            replacement = False

            # Am I already in the cluster?
            already_there = [m for m in member_data['members'] if m['peerURLs'][0] == my_url]
            if len(already_there) == 1:
                replacement = True
                m = already_there[0]
                if m['name'] == "":
                    # If I failed to start previously, delete my data dir
                    rmtree(self._datadir, True)

            if not replacement:
                # Add this node to the cluster by POSTing to an existing node
                while True:
                    cxn = httplib.HTTPConnection(self._existing, 4000, timeout=10)
                    cxn.request("POST",
                                "/v2/members",
                                json.dumps({"name": self._name, "peerURLs": [my_url]}),
                                {"Content-Type": "application/json"})
                    response = cxn.getresponse()
                    if response.status != 500:
                        me = json.loads(response.read())
                        self._id = me['id']
                        break
                    sleep(1)

            # Learn about my peers
            cxn = httplib.HTTPConnection(self._existing, 4000, timeout=10)
            cxn.request("GET", "/v2/members?consistent=false");
            member_data = json.loads(cxn.getresponse().read())
            for m in member_data['members']:
                if not m['name']:
                    # Replace any empty names with UUIDs - see
                    # https://github.com/Metaswitch/clearwater-etcd/issues/203#issuecomment-156709911
                    m['name'] = str(uuid.uuid4())


            cluster = ",".join(["{}={}".format(m['name'], m['peerURLs'][0]) for m in member_data['members'] if m['peerURLs'][0] != my_url])
            self._cmd = shlex.split(subsequent_member_cmd.format(self._ip, self._name, self._datadir, cluster))

        if actually_start:
            self._subprocess = Popen(self._cmd,
                                     stdout=self._logfile,
                                     stderr=STDOUT)
        else:
            self._subprocess = None

    def recover(self):
        if self._subprocess.poll() is not None:
            self.start_process()

    def cluster_id(self):
        if self._id is None:
            # TODO: learn my ID (c.f. the code in start_process)
            members = self.memberList() # noqa
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
        return json.loads(rsp)['state'] == "StateLeader"

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
