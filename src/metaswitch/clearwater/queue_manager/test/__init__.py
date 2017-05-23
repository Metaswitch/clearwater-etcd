# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

import random
from metaswitch.common.logging_config import configure_test_logging
import logging

configure_test_logging()

# Avoid spamming etcd logs.
logging.getLogger('etcd').setLevel(logging.ERROR)

seed = random.randrange(2000)
print "\n\n===\nGenerated random seed {}\n===\n\n".format(seed)
random.seed(seed)
