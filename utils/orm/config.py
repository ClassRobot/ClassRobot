import os
from nonebot import get_driver

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
config = get_driver().config
app = "utils.orm"

INSTALLED_APPS = [app]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": str(config.mysql_db),
        "USER": str(config.mysql_user),
        "HOST": str(config.mysql_host),
        "PORT": str(config.mysql_port),
        "PASSWORD": str(config.mysql_password),
        "CONN_MAX_AGE": 7.5 * 360,
        "OPTIONS": {
            "connect_timeout": 60
        }
    }
}
