from typing import Annotated
from datetime import datetime

from sqlalchemy.orm import mapped_column
from sqlalchemy import Integer, DateTime, text

# Use Python-side defaults so existing SQLite tables with bad server defaults
# don't block ORM inserts, while keeping a cross-database SQL default for new tables.
CreateAt = Annotated[
    datetime,
    mapped_column(DateTime, default=datetime.now, server_default=text("CURRENT_TIMESTAMP"), nullable=False),
]
UpdateAt = Annotated[
    datetime,
    mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    ),
]
PrimaryKeyInteger = Annotated[int, mapped_column(Integer, primary_key=True, autoincrement=True, nullable=False)]
