import sys
if sys.version_info < (3, 5):
    print("3.4")
    from .aiolifx34 import LifxDiscovery
else:
    print("3.5")
    from .aiolifx import LifxDiscovery
from .message import *
from .msgtypes import *
from .unpack import unpack_lifx_message
