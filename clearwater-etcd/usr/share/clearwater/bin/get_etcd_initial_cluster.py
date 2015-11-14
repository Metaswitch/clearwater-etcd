import httplib
import json
import sys

def main(ip, servers):
    my_url = "http://{}:2380".format(ip)
    for s in servers.split(","):
        try:
            cxn = httplib.HTTPConnection(s, 4000)
            cxn.request("GET", "/v2/members?consistent=false");
            member_data = json.loads(cxn.getresponse().read())
            for m in member_data['members']:
                if not m['name']:
                    m['name'] = str(uuid.uuid4())
            cluster = ",".join(["{}={}".format(m['name'], m['peerURLs'][0]) for m in member_data['members'] if m['peerURLs'][0] != my_url])
            print "{}".format(cluster)
            return
        except OSError:
            pass

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2]

