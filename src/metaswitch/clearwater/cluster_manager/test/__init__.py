import logging
import sys
import os

if os.environ.get('NOISY'):
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
