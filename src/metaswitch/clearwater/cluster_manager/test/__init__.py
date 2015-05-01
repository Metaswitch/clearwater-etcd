import logging
import sys
import os

logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
logging.getLogger().setLevel(logging.ERROR)
if os.environ.get('NOISY'):
    logging.getLogger().setLevel(logging.DEBUG)
