from typing import Annotated
from datetime import datetime
from sqlalchemy import DateTime, func, Integer
from sqlalchemy.orm import mapped_column


CreateAt = Annotated[
    datetime, mapped_column(DateTime, server_default=func.now(), nullable=False)
]
UpdateAt = Annotated[
    datetime,
    mapped_column(
        DateTime, server_default=func.now(), server_onupdate=func.now(), nullable=False
    ),
]
PrimaryKeyInteger = Annotated[
    int, mapped_column(Integer, primary_key=True, autoincrement=True, nullable=False)
]
