import os

from django import setup
from utils.orm.config import app

try:
    import pymysql

    pymysql.install_as_MySQLdb()
except:
    ...
os.environ.setdefault("DJANGO_SETTINGS_MODULE", f"{app}.config")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
setup()

from .models import *
from . import signals as _
