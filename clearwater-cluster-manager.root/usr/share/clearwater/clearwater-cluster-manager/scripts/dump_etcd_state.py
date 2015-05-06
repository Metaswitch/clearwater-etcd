import sys
import etcd

local_ip = sys.argv[1]
key = sys.argv[2]

c = etcd.Client(local_ip, 4000)
print c.get(key).value
