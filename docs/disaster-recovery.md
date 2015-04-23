## Disaster recovery ##

If your etcd cluster loses half or more of its nodes permanently, it will enter a read-only state. This document describes how to recover from this state.

In this example, your initial cluster consists of servers A, B, C, D, E and F. D, E and F die permanently, and A, B and C enter a read-only state (because they lack quorum). Recent changes may have been permanently lost at this point (if they were not replicated to the surviving nodes).

You should follow this process completely - the behaviour is unspecified if this process is started but not completed. It is always safe to restart this process from the beginning (for example, if you encounter an error partway through).

To recover from this state:

* stop etcd on A, B and C by running 'service clearwater-etcd stop'
* create a new cluster, only on A, by:
    * editing etcd_cluster in /etc/clearwater/config to just contain A's IP (e.g. `etcd_cluster=10.0.0.1`)
    * running `service clearwater-etcd force-new-cluster`. This will warn that this is dangerous and should only be run during this process; choose to proceed.
    * running `etcdctl -C 10.0.0.1:4000 member list` to check that the cluster only has A in
    * running `etcdctl -C 10.0.0.1:4000 cluster-health` to check that the cluster is healthy
    * running `etcdctl -C 10.0.0.1:4000 get ims_domain` to check that the data is safe
* get B to join that cluster by:
    * editing etcd_cluster in /etc/clearwater/config to just contain A's IP (e.g. `etcd_cluster=10.0.0.1`)
    * running `service clearwater-etcd force-decommission`. This will warn that this is dangerous and offer the chance to cancel; do not cancel.
    * running `service clearwater-etcd start`.
* get C to join that cluster by following the same steps as for B:
    * editing etcd_cluster in /etc/clearwater/config to just contain A's IP (e.g. `etcd_cluster=10.0.0.1`)
    * running `service clearwater-etcd force-decommission`. This will warn that this is dangerous and should only be run during this process; choose to proceed.
    * running `service clearwater-etcd start`.
* check that the cluster is now OK
    * running `etcdctl -C $local_ip:4000 member list` to check that the cluster now has A, B and C in
    * running `etcdctl -C $local_ip:4000 cluster-health` to check that the cluster is healthy
    * running `etcdctl -C $local_ip:4000 get ims_domain` to check that the data is safe


