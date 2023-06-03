import os
from django import setup
from pymysql import install_as_MySQLdb
from utils.orm.config import app

install_as_MySQLdb()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", f"{app}.config")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
setup()

from .models import *
from . import signals as _