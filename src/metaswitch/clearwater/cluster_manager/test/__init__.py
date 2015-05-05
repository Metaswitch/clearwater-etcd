import logging
import sys
import os
import random

logging.getLogger().addHandler(logging.StreamHandler(sys.stderr))
logging.getLogger().setLevel(logging.ERROR)
if os.environ.get('NOISY'):
    logging.getLogger().setLevel(logging.DEBUG)

seed = random.randrange(2000)
print "\n\n===\nGenerated random seed {}\n===\n\n".format(seed)
random.seed(seed)
