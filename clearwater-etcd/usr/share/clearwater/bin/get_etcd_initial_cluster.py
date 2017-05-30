#!/usr/bin/python

# Copyright (C) Metaswitch Networks 2016
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

import httplib
import json
import sys
import uuid
import socket

def main(ip, servers):
    my_url = "http://{}:2380".format(ip)
    my_name = ip.replace(".", "-")
    for s in servers.split(","):
        try:
            cxn = httplib.HTTPConnection(s, 4000)
            cxn.request("GET", "/v2/members?consistent=false");
            member_data = json.loads(cxn.getresponse().read())
            for m in member_data['members']:
                if not m['name']:
                    m['name'] = str(uuid.uuid4())
            members = ["{}={}".format(m['name'], m['peerURLs'][0]) for m in member_data['members'] if m['peerURLs'][0] != my_url] + ["{}={}".format(my_name, my_url)]
            cluster = ",".join(members)
            print "{}".format(cluster)
            return
        except (OSError, socket.error):
            pass

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

