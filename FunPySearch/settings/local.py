# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'ai)@h9(g+y6qxh#43^t^u+#kvhn8!n6ry94n$_n27*(ml9jcus'
from .base import *

# try:
#     var = os.environ["not_use_docker"]
#     UseDocker = False
# except KeyError:
#     UseDocker = True
# if UseDocker:
#     ES_HOST = "mtianyan_elasticsearch"
#     REDIS_HOST = "mtianyan_redis"
#     REDIS_PASSWORD = "mtianyanRedisRoot"
# else:
#     ES_HOST = "127.0.0.1"
#     REDIS_HOST = "127.0.0.1"
#     REDIS_PASSWORD = "mtianyanRedisRoot"

ES_HOST = "127.0.0.1"
REDIS_HOST = "127.0.0.1"
REDIS_PASSWORD = "mtianyanRedisRoot"