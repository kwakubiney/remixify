from .base_settings import *
from decouple import config

if config('REMIXIFY') == 'prod':
   from .prod_settings import *
else:
   from .dev_settings import *