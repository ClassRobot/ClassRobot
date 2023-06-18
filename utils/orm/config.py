import os

from nonebot import get_driver
from pydantic import BaseSettings

try:
    config = get_driver().config
except ValueError:
    # 读取pydantic读取.env文件
    class Config(BaseSettings):
        mysql_db: str = ""
        mysql_user: str = "root"
        mysql_host: str = "localhost"
        mysql_port: int = 3306
        mysql_password: str = ""

        class Config:
            env_file = ".env.dev"
            env_file_encoding = "utf-8"

    config = Config()

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
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
        "OPTIONS": {"connect_timeout": 60},
    }
}
