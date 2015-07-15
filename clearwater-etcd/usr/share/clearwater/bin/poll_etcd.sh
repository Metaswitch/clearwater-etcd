#!/bin/bash

# @file poll_etcd.sh
#
# Project Clearwater - IMS in the Cloud
# Copyright (C) 2015  Metaswitch Networks Ltd
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version, along with the "Special Exception" for use of
# the program along with SSL, set forth below. This program is distributed
# in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details. You should have received a copy of the GNU General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
# The author can be reached by email at clearwater@metaswitch.com or by
# post at Metaswitch Networks Ltd, 100 Church St, Enfield EN2 6BQ, UK
#
# Special Exception
# Metaswitch Networks Ltd  grants you permission to copy, modify,
# propagate, and distribute a work formed by combining OpenSSL with The
# Software, or a work derivative of such a combination, even if such
# copying, modification, propagation, or distribution would otherwise
# violate the terms of the GPL. You must comply with the GPL in all
# respects for all of the code used other than OpenSSL.
# "OpenSSL" means OpenSSL toolkit software distributed by the OpenSSL
# Project and licensed under the OpenSSL Licenses, or a work based on such
# software and licensed under the OpenSSL Licenses.
# "OpenSSL Licenses" means the OpenSSL License and Original SSLeay License
# under which the OpenSSL Project distributes the OpenSSL toolkit software,
# as those licenses appear in the file LICENSE-OPENSSL.

# This script polls the local etcd process and checks whether it is healthy by
# checking that the 4000 port is open.
. /etc/clearwater/config
/usr/share/clearwater/bin/poll-tcp 4000 ${management_local_ip:-$local_ip}
sta=$?
if [ $sta -ne 0 ]; then
    exit $sta
fi

if [ -d /var/lib/clearwater-etcd/${management_local_ip:-$local_ip} ]; then
    # If we can talk to etcd, check to see if we can write a key value and exit
    # with bad status, if we can't. This is done because there have been
    # occasions where etcd was listening to its port, but wasn't functioning
    # properly, so doing this check lets monit restart it.
    curl -L http://${management_local_ip:-$local_ip}:4000/v2/keys/${management_local_ip:-$local_ip} -XPUT -d value="Hello world" 2>&1|grep -q '"value":"Hello world"'
    exit $?
fi

exit 0

