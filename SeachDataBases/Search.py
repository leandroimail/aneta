from config.api_config import *
from xplore.xploreapi import XPLORE as ieee

print(ieee_key)
query = ieee(ieee_key)
query.abstractText(ieee_key)

