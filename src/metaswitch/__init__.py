# This turns this package into a namespace package, allowing us to
# have metaswitch.common and metaswitch.clearwater.cluster_manager in different eggs.
import pkg_resources
pkg_resources.declare_namespace(__name__)
