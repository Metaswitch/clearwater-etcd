# clearwater-etcd

This package contains packaging wrappers around [`etcd`
](https://github.com/coreos/etcd) that allow for easy installation, clustering
and management of an `etcd` cluster.

## Configuration

Configuration for the `clearwater-etcd` cluster is done through the standard
`/etc/clearwater/local_config` file, the following values must be provided:

 * `etcd_cluster` - See below
 * `local_ip` - The local IP address

You can also provide a `etcd_key` value. This controls what key is used to store the clustering and configuration values in etcd. It defaults to `clearwater` if it isn't set.

## Creating a Cluster

`clearwater-etcd` forms a cluster across your nodes to allow configuration to be easily shared.  Most of the extra function added by the `clearwater-etcd` wrapper is to simplify the management of the cluster.  The operations that can be performed are:

 * Create a new cluster
 * Join an existing cluster
 * Decommission a node (remove it permanently from the cluster)

### Create a Cluster

Creating a cluster is as easy as determining the list of nodes that will be in the cluster and populating the `etcd_cluster` configuration parameter with the comma-separated list of nodes:

    etcd_cluster=10.0.0.1,10.0.0.2,10.0.0.3

When you now install `clearwater-etcd` on each of these nodes, the cluster will automatically form.

### Join an Existing Cluster

Joining an existing cluster requires determining the list of nodes that are currently in the cluster and providing that list in the `etcd_cluster`.  Note that the newly added node MUST NOT be included in this list (otherwise we'll attempt to form the cluster from scratch).

### Decommissioning

To decommission a node run `sudo service clearwater-etcd decommission` which will gracefully remove the local node, stop the local `etcd` service and destroy the node's state.  At this point, the `etcd` service can be re-attached to that (or another) `etcd` cluster by updating `etcd_cluster` and starting the `clearwater-etcd` service.

## etcd sources

* `etcd` and `etcdctl` are the versions downloaded from <https://github.com/coreos/etcd/releases/download/v2.2.5/etcd-v2.2.5-linux-amd64.tar.gz>
* `etcd-dump-logs` is built from <https://github.com/coreos/etcd/blob/v2.2.5/tools/etcd-dump-logs/main.go>
