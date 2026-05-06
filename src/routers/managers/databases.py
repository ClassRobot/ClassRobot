from __future__ import annotations

import copy
import math
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import (
    JSON,
    Date,
    Time,
    Table,
    Float,
    String,
    Boolean,
    Integer,
    Numeric,
    MetaData,
    DateTime,
    LargeBinary,
    Text,
    func,
    inspect,
    select,
    update,
)
from sqlalchemy.exc import DataError, IntegrityError, SQLAlchemyError, StatementError
from nonebot_plugin_orm import get_session


PRIMARY_DATABASE_ID = "primary"
SENSITIVE_COLUMN_HINTS = ("password", "token", "secret", "credential", "authorization")
DatabaseCacheKey = tuple[str, str | None]
_SCHEMA_CACHE: dict[DatabaseCacheKey, dict[str, Any]] = {}
_TABLE_LIST_CACHE: dict[DatabaseCacheKey, dict[str, Any]] = {}


class DatabaseNotFoundError(KeyError):
    """数据库连接标识不存在时抛出的异常。"""

    pass


class TableNotFoundError(KeyError):
    """目标数据表不存在时抛出的异常。"""

    pass


class RowUpdateError(ValueError):
    """数据库行编辑失败时抛出的结构化异常。"""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        column: str | None = None,
        columns: list[str] | None = None,
        hint: str | None = None,
        detail: str | None = None,
        **extra: Any,
    ) -> None:
        """初始化数据库行更新异常。

        Args:
            code: 机器可读错误码。
            message: 面向前端展示的错误消息。
            column: 相关字段名。
            columns: 相关字段名列表。
            hint: 可选的修复建议。
            detail: 可选的底层错误详情。
            **extra: 需要附加返回给前端的额外字段。
        """
        super().__init__(message)
        self.code = code
        self.message = message
        self.column = column
        self.columns = columns
        self.hint = hint
        self.detail = detail
        self.extra = extra

    def to_payload(self) -> dict[str, Any]:
        """把异常转换成适合 HTTP 返回的结构化 payload。

        Returns:
            dict[str, Any]: 包含错误码、字段信息和修复提示的结果。
        """
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.column is not None:
            payload["column"] = self.column
        if self.columns:
            payload["columns"] = self.columns
        if self.hint:
            payload["hint"] = self.hint
        if self.detail:
            payload["detail"] = self.detail
        payload.update(
            {key: value for key, value in self.extra.items() if value is not None}
        )
        return payload


def _database_cache_key(database_id: str, schema: str | None) -> DatabaseCacheKey:
    """生成数据库结构缓存键。

    Args:
        database_id: 数据库标识。
        schema: 可选 schema 名称。

    Returns:
        DatabaseCacheKey: 用于缓存索引的键。
    """
    return (database_id, schema)


def _clone_cache_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """返回缓存 payload 的深拷贝。

    Args:
        payload: 缓存中的原始字典。

    Returns:
        dict[str, Any]: 可安全返回给调用方的独立副本。
    """
    return copy.deepcopy(payload)


def clear_database_metadata_cache(database_id: str | None = None, schema: str | None = None) -> None:
    """清理数据库结构与表列表缓存。

    Args:
        database_id: 可选数据库标识；为空时清空全部缓存。
        schema: 可选 schema 名称；为空且指定数据库时清空该数据库下全部 schema。
    """
    if database_id is None:
        _SCHEMA_CACHE.clear()
        _TABLE_LIST_CACHE.clear()
        return

    if schema is None:
        schema_keys = [key for key in _SCHEMA_CACHE if key[0] == database_id]
        table_keys = [key for key in _TABLE_LIST_CACHE if key[0] == database_id]
        for key in schema_keys:
            _SCHEMA_CACHE.pop(key, None)
        for key in table_keys:
            _TABLE_LIST_CACHE.pop(key, None)
        return

    cache_key = _database_cache_key(database_id, schema)
    _SCHEMA_CACHE.pop(cache_key, None)
    _TABLE_LIST_CACHE.pop(cache_key, None)


def _mask_url(url: Any) -> str | None:
    """对数据库连接串做密码脱敏。

    Args:
        url: SQLAlchemy URL 或任意可转字符串对象。

    Returns:
        str | None: 脱敏后的连接串。
    """
    if url is None:
        return None
    if hasattr(url, "render_as_string"):
        return url.render_as_string(hide_password=True)
    return str(url)


def _is_sensitive_column(name: str) -> bool:
    """判断列名是否可能包含敏感信息。

    Args:
        name: 数据表列名。

    Returns:
        bool: 命中敏感关键字时返回 ``True``。
    """
    lowered = name.lower()
    return any(hint in lowered for hint in SENSITIVE_COLUMN_HINTS)


def _value_preview(column_name: str, value: Any) -> str:
    """生成用于错误提示的字段值预览。

    Args:
        column_name: 列名。
        value: 原始字段值。

    Returns:
        str: 截断后的预览字符串；敏感字段直接返回 ``<masked>``。
    """
    if _is_sensitive_column(column_name):
        return "<masked>"
    text = repr(value)
    return f"{text[:117]}..." if len(text) > 120 else text


def _invalid_value_error(
    column,
    code: str,
    expected: str,
    value: Any,
    *,
    hint: str | None = None,
) -> RowUpdateError:
    """构造字段类型不匹配时的统一异常。

    Args:
        column: SQLAlchemy 列对象。
        code: 错误码。
        expected: 期望的值类型说明。
        value: 实际提交的值。
        hint: 可选的修复提示。

    Returns:
        RowUpdateError: 结构化错误对象。
    """
    return RowUpdateError(
        code,
        f"字段 {column.name} 的值格式不正确，期望 {expected}。",
        column=column.name,
        hint=hint or "请检查输入值与字段类型是否匹配，然后重新保存。",
        expected=expected,
        received_type=type(value).__name__,
        received_value=_value_preview(column.name, value),
    )


def _safe_database_detail(error: SQLAlchemyError) -> str:
    """提取适合返回给前端的数据库错误详情。"""
    original = getattr(error, "orig", None)
    if original is not None:
        return str(original)
    return str(error).splitlines()[0]


def _database_error_hint(detail: str) -> str:
    """根据底层错误文本推断更友好的修复提示。"""
    lowered = detail.lower()
    if "foreign key" in lowered:
        return "外键约束未通过，请确认关联表中存在对应记录。"
    if "unique" in lowered or "duplicate" in lowered:
        return "唯一约束未通过，请检查该字段组合是否已经存在。"
    if "not null" in lowered or "null value" in lowered:
        return "非空约束未通过，请为必填字段填写有效值。"
    if "check constraint" in lowered or "check failed" in lowered:
        return "检查约束未通过，请按表结构或业务规则调整字段值。"
    return "请结合错误详情检查字段类型、约束、外键关系或数据库连接状态。"


def _database_error_from_exception(
    error: SQLAlchemyError,
    code: str,
    message: str,
) -> RowUpdateError:
    """把 SQLAlchemy 异常统一包装成 ``RowUpdateError``。"""
    detail = _safe_database_detail(error)
    return RowUpdateError(
        code,
        message,
        hint=_database_error_hint(detail),
        detail=detail,
        database_error_type=error.__class__.__name__,
    )


def _serialize_value(value: Any) -> Any:
    """把数据库值转换成 JSON 友好的形式。"""
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return {"type": "bytes", "size": len(value)}
    return value


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    """序列化一整行数据。"""
    return {key: _serialize_value(value) for key, value in row.items()}


def _column_payload(column: dict[str, Any], primary_keys: set[str]) -> dict[str, Any]:
    """把 inspector 返回的列信息转换成前端结构。"""
    name = column["name"]
    return {
        "name": name,
        "type": str(column.get("type")),
        "nullable": bool(column.get("nullable", True)),
        "default": str(column["default"]) if column.get("default") is not None else None,
        "primary_key": name in primary_keys,
        "sensitive": _is_sensitive_column(name),
    }


def _foreign_key_payload(table_name: str, foreign_key: dict[str, Any]) -> dict[str, Any]:
    """把外键信息转换成前端 ER 关系结构。"""
    constrained_columns = list(foreign_key.get("constrained_columns") or [])
    referred_columns = list(foreign_key.get("referred_columns") or [])
    return {
        "name": foreign_key.get("name"),
        "source_table": table_name,
        "source_columns": constrained_columns,
        "target_schema": foreign_key.get("referred_schema"),
        "target_table": foreign_key.get("referred_table"),
        "target_columns": referred_columns,
        "label": " -> ".join(
            [
                f"{table_name}.{','.join(constrained_columns) or '?'}",
                f"{foreign_key.get('referred_table')}.{','.join(referred_columns) or '?'}",
            ]
        ),
    }


async def _get_primary_bind():
    """获取主数据库绑定对象。"""
    async with get_session() as session:
        bind = session.bind
        if bind is None:
            bind = session.get_bind()
        return bind


def _assert_database_id(database_id: str) -> None:
    """校验当前只支持的数据库连接标识。

    Args:
        database_id: 前端请求的数据库标识。

    Raises:
        DatabaseNotFoundError: 当数据库标识不是 ``primary`` 时抛出。
    """
    if database_id != PRIMARY_DATABASE_ID:
        raise DatabaseNotFoundError(database_id)


async def list_connections() -> dict[str, Any]:
    """列出管理端可见的数据库连接。

    Returns:
        dict[str, Any]: 当前数据库连接列表。
    """
    bind = await _get_primary_bind()
    url = getattr(bind, "url", None)
    dialect = getattr(bind, "dialect", None)
    return {
        "items": [
            {
                "id": PRIMARY_DATABASE_ID,
                "name": "主数据库",
                "status": "connected" if bind is not None else "error",
                "kind": "sqlalchemy",
                "dialect": getattr(dialect, "name", None),
                "driver": getattr(dialect, "driver", None),
                "url": _mask_url(url),
                "database": getattr(url, "database", None) if url is not None else None,
                "editable": True,
            }
        ],
        "total": 1,
    }


async def get_schema(
    database_id: str,
    *,
    schema: str | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """读取指定数据库的表结构与外键关系。

    Args:
        database_id: 数据库标识。
        schema: 可选的 schema 名称。
        force_refresh: 是否跳过缓存并强制重新反射数据库结构。

    Returns:
        dict[str, Any]: 表、列、主键和外键关系描述。

    Raises:
        DatabaseNotFoundError: 当数据库标识不存在时抛出。
    """
    _assert_database_id(database_id)
    cache_key = _database_cache_key(database_id, schema)
    if force_refresh:
        clear_database_metadata_cache(database_id, schema=schema)
    elif cache_key in _SCHEMA_CACHE:
        return _clone_cache_payload(_SCHEMA_CACHE[cache_key])

    async with get_session() as session:
        connection = await session.connection()

        def inspect_schema(sync_connection):
            inspector = inspect(sync_connection)
            table_names = inspector.get_table_names(schema=schema)
            tables = []
            relationships = []
            for table_name in table_names:
                pk_constraint = inspector.get_pk_constraint(table_name, schema=schema) or {}
                primary_keys = set(pk_constraint.get("constrained_columns") or [])
                columns = [
                    _column_payload(column, primary_keys)
                    for column in inspector.get_columns(table_name, schema=schema)
                ]
                foreign_keys = [
                    _foreign_key_payload(table_name, foreign_key)
                    for foreign_key in inspector.get_foreign_keys(table_name, schema=schema)
                ]
                relationships.extend(foreign_keys)
                tables.append(
                    {
                        "name": table_name,
                        "schema": schema,
                        "columns": columns,
                        "primary_key": list(primary_keys),
                        "foreign_keys": foreign_keys,
                    }
                )
            try:
                schemas = inspector.get_schema_names()
            except Exception:  # noqa: BLE001
                schemas = []
            return {
                "database_id": database_id,
                "schema": schema,
                "default_schema": inspector.default_schema_name,
                "schemas": schemas,
                "tables": tables,
                "relationships": relationships,
            }

        payload = await connection.run_sync(inspect_schema)

    _SCHEMA_CACHE[cache_key] = payload
    return _clone_cache_payload(payload)


async def list_tables(
    database_id: str,
    *,
    schema: str | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """列出指定数据库中可见数据表的摘要。

    Args:
        database_id: 数据库标识。
        schema: 可选的 schema 名称。
        force_refresh: 是否跳过缓存并强制重新读取表目录。

    Returns:
        dict[str, Any]: 数据表摘要列表。
    """
    cache_key = _database_cache_key(database_id, schema)
    if force_refresh:
        clear_database_metadata_cache(database_id, schema=schema)
    elif cache_key in _TABLE_LIST_CACHE:
        return _clone_cache_payload(_TABLE_LIST_CACHE[cache_key])

    schema_payload = await get_schema(database_id, schema=schema)
    table_payloads = []
    async with get_session() as session:
        connection = await session.connection()
        for table_info in schema_payload["tables"]:
            table = await _reflect_table(
                connection,
                table_info["name"],
                schema=schema,
                validate_exists=False,
            )
            row_count = None
            try:
                row_count = await session.scalar(select(func.count()).select_from(table))
            except SQLAlchemyError:
                row_count = None
            table_payloads.append(
                {
                    "name": table_info["name"],
                    "schema": table_info["schema"],
                    "column_count": len(table_info["columns"]),
                    "row_count": row_count,
                    "primary_key": table_info["primary_key"],
                    "foreign_key_count": len(table_info["foreign_keys"]),
                    "editable": bool(table_info["primary_key"]),
                }
            )
    payload = {
        "database_id": database_id,
        "schema": schema,
        "items": table_payloads,
        "total": len(table_payloads),
    }
    _TABLE_LIST_CACHE[cache_key] = payload
    return _clone_cache_payload(payload)


async def _reflect_table(
    connection,
    table_name: str,
    *,
    schema: str | None = None,
    validate_exists: bool = True,
) -> Table:
    """反射读取单个数据表定义。

    Args:
        connection: 当前数据库连接。
        table_name: 表名。
        schema: 可选的 schema 名称。
        validate_exists: 是否在反射前校验目标表仍然存在。

    Returns:
        Table: SQLAlchemy 反射得到的数据表对象。

    Raises:
        TableNotFoundError: 当目标表不存在时抛出。
    """
    def reflect(sync_connection):
        if validate_exists:
            inspector = inspect(sync_connection)
            if table_name not in inspector.get_table_names(schema=schema):
                raise TableNotFoundError(table_name)
        metadata = MetaData()
        return Table(table_name, metadata, schema=schema, autoload_with=sync_connection)

    return await connection.run_sync(reflect)


async def get_table_rows(
    database_id: str,
    table_name: str,
    *,
    schema: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """分页读取指定表的数据行。

    Args:
        database_id: 数据库标识。
        table_name: 表名。
        schema: 可选的 schema 名称。
        page: 页码，从 1 开始。
        page_size: 每页条目数。

    Returns:
        dict[str, Any]: 表结构列信息和分页数据。
    """
    _assert_database_id(database_id)
    offset = max(page - 1, 0) * page_size
    async with get_session() as session:
        connection = await session.connection()
        table = await _reflect_table(connection, table_name, schema=schema)
        columns = [_table_column_payload(column) for column in table.columns]
        primary_key = [column.name for column in table.primary_key.columns]
        query = select(table)
        if primary_key:
            query = query.order_by(*(table.c[name] for name in primary_key))
        rows_result = await session.execute(query.offset(offset).limit(page_size))
        total = await session.scalar(select(func.count()).select_from(table)) or 0
        rows = [_serialize_row(dict(row)) for row in rows_result.mappings().all()]

    return {
        "database_id": database_id,
        "schema": schema,
        "table": table_name,
        "columns": columns,
        "primary_key": primary_key,
        "items": rows,
        "page": page,
        "page_size": page_size,
        "total": total,
    }


def _table_column_payload(column) -> dict[str, Any]:
    """序列化 SQLAlchemy 列对象。"""
    return {
        "name": column.name,
        "type": str(column.type),
        "nullable": bool(column.nullable),
        "default": str(column.default.arg) if column.default is not None else None,
        "primary_key": bool(column.primary_key),
        "sensitive": _is_sensitive_column(column.name),
    }


def _coerce_value(column, value: Any) -> Any:
    """按列类型把前端值转换成数据库可接受的 Python 值。

    Args:
        column: SQLAlchemy 列对象。
        value: 前端提交的原始字段值。

    Returns:
        Any: 通过校验并转换后的 Python 值。

    Raises:
        RowUpdateError: 当字段值为空、类型不匹配或该列不允许编辑时抛出。
    """
    if value is None:
        if column.primary_key:
            raise RowUpdateError(
                "primary_key_null",
                f"主键字段 {column.name} 不能为空。",
                column=column.name,
                hint="请确认行数据仍然存在，或刷新表数据后重新选择记录。",
            )
        if not column.nullable:
            raise RowUpdateError(
                "null_not_allowed",
                f"字段 {column.name} 不允许为空。",
                column=column.name,
                hint="该字段在数据库中被标记为非空，请填写有效值或调整表结构后再保存。",
            )
        return None
    column_type = column.type
    if isinstance(column_type, Boolean):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "on"}:
                return True
            if lowered in {"false", "0", "no", "off"}:
                return False
        raise _invalid_value_error(
            column,
            "invalid_boolean",
            "布尔值 true/false、1/0、yes/no 或 on/off",
            value,
        )
    if isinstance(column_type, Integer):
        if isinstance(value, bool):
            raise _invalid_value_error(column, "invalid_integer", "整数", value)
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, ValueError) as error:
            raise _invalid_value_error(column, "invalid_integer", "整数", value) from error
        if not decimal_value.is_finite() or decimal_value != decimal_value.to_integral_value():
            raise _invalid_value_error(column, "invalid_integer", "整数", value)
        return int(decimal_value)
    if isinstance(column_type, Float):
        if isinstance(value, bool):
            raise _invalid_value_error(column, "invalid_number", "数字", value)
        try:
            float_value = float(value)
        except (TypeError, ValueError) as error:
            raise _invalid_value_error(column, "invalid_number", "数字", value) from error
        if not math.isfinite(float_value):
            raise _invalid_value_error(column, "invalid_number", "有限数字", value)
        return float_value
    if isinstance(column_type, Numeric):
        if isinstance(value, bool):
            raise _invalid_value_error(column, "invalid_number", "数字", value)
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, ValueError) as error:
            raise _invalid_value_error(column, "invalid_number", "数字", value) from error
        if not decimal_value.is_finite():
            raise _invalid_value_error(column, "invalid_number", "有限数字", value)
        return decimal_value
    if isinstance(column_type, DateTime):
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as error:
            raise _invalid_value_error(
                column,
                "invalid_datetime",
                "日期时间，例如 2026-05-04T12:30:00",
                value,
            ) from error
    if isinstance(column_type, Date):
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value))
        except ValueError as error:
            raise _invalid_value_error(
                column,
                "invalid_date",
                "日期，例如 2026-05-04",
                value,
            ) from error
    if isinstance(column_type, Time):
        if isinstance(value, time):
            return value
        try:
            return time.fromisoformat(str(value))
        except ValueError as error:
            raise _invalid_value_error(
                column,
                "invalid_time",
                "时间，例如 12:30:00",
                value,
            ) from error
    if isinstance(column_type, JSON):
        return value
    if isinstance(column_type, LargeBinary):
        raise RowUpdateError(
            "binary_column_forbidden",
            f"二进制字段 {column.name} 暂不支持在管理端直接编辑。",
            column=column.name,
            hint="请通过专门的数据迁移脚本或业务接口维护二进制内容。",
        )
    if isinstance(column_type, (String, Text)):
        return str(value)
    return value


async def update_table_row(
    database_id: str,
    table_name: str,
    *,
    pk: dict[str, Any],
    values: dict[str, Any],
    schema: str | None = None,
) -> dict[str, Any]:
    """更新指定表中的一行数据。

    Args:
        database_id: 数据库标识。
        table_name: 表名。
        pk: 主键字段和值映射。
        values: 需要更新的列和值映射。
        schema: 可选的 schema 名称。

    Returns:
        dict[str, Any]: 更新结果和刷新后的行数据。

    Raises:
        DatabaseNotFoundError: 当数据库标识不存在时抛出。
        TableNotFoundError: 当目标表不存在时抛出。
        RowUpdateError: 当主键不完整、字段不合法或数据库写入失败时抛出。
    """
    _assert_database_id(database_id)
    if not pk:
        raise RowUpdateError(
            "primary_key_required",
            "缺少主键值，无法定位要修改的行。",
            hint="请刷新表数据后重新选择一行，系统会自动携带主键。",
        )
    if not values:
        raise RowUpdateError(
            "update_values_required",
            "缺少要更新的字段值。",
            hint="请至少修改或提交一个可编辑字段。",
        )

    async with get_session() as session:
        connection = await session.connection()
        table = await _reflect_table(connection, table_name, schema=schema)
        table_columns = {column.name: column for column in table.columns}
        primary_key = [column.name for column in table.primary_key.columns]
        if not primary_key:
            raise RowUpdateError(
                "table_without_primary_key",
                f"数据表 {table_name} 没有主键，管理端无法安全编辑。",
                hint="请先为该表添加主键，或通过专门的数据维护脚本处理。",
            )

        missing_pk = [name for name in primary_key if name not in pk]
        unknown_pk = [name for name in pk if name not in primary_key]
        if missing_pk:
            raise RowUpdateError(
                "missing_primary_key",
                f"缺少主键字段：{', '.join(missing_pk)}。",
                columns=missing_pk,
                hint="请刷新表数据后重新选择记录，避免使用过期的行数据。",
            )
        if unknown_pk:
            raise RowUpdateError(
                "unknown_primary_key",
                f"请求中包含未知主键字段：{', '.join(unknown_pk)}。",
                columns=unknown_pk,
                hint="请确认前端缓存的表结构是否已经过期，并刷新后重试。",
            )

        unknown_values = [name for name in values if name not in table_columns]
        if unknown_values:
            raise RowUpdateError(
                "unknown_update_column",
                f"请求中包含未知更新字段：{', '.join(unknown_values)}。",
                columns=unknown_values,
                hint="请刷新表结构后重试，或确认字段名是否仍然存在。",
            )
        primary_key_updates = [name for name in values if name in primary_key]
        if primary_key_updates:
            raise RowUpdateError(
                "primary_key_update_forbidden",
                f"主键字段不允许在管理端直接修改：{', '.join(primary_key_updates)}。",
                columns=primary_key_updates,
                hint="主键修改风险较高，请通过数据迁移或专门维护脚本处理。",
            )

        where_clause = [
            table_columns[name] == _coerce_value(table_columns[name], pk[name])
            for name in primary_key
        ]
        update_values = {
            name: _coerce_value(table_columns[name], value)
            for name, value in values.items()
        }
        try:
            result = await session.execute(update(table).where(*where_clause).values(**update_values))
            if result.rowcount == 0:
                await session.rollback()
                raise RowUpdateError(
                    "row_not_found",
                    "没有找到匹配主键的行，修改未保存。",
                    hint="该记录可能已被删除或主键已变化，请刷新数据后重新选择。",
                )
            await session.commit()
        except RowUpdateError:
            raise
        except IntegrityError as error:
            await session.rollback()
            raise _database_error_from_exception(
                error,
                "integrity_error",
                "数据库约束校验失败，修改未保存。",
            ) from error
        except DataError as error:
            await session.rollback()
            raise _database_error_from_exception(
                error,
                "data_error",
                "数据库拒绝了该字段值，修改未保存。",
            ) from error
        except StatementError as error:
            await session.rollback()
            raise _database_error_from_exception(
                error,
                "statement_error",
                "数据库语句执行失败，修改未保存。",
            ) from error
        except SQLAlchemyError as error:
            await session.rollback()
            raise _database_error_from_exception(
                error,
                "database_error",
                "数据库写入失败，修改未保存。",
            ) from error

        refreshed = await session.execute(select(table).where(*where_clause).limit(1))
        row = refreshed.mappings().first()

    return {
        "updated": True,
        "database_id": database_id,
        "schema": schema,
        "table": table_name,
        "pk": pk,
        "row": _serialize_row(dict(row)) if row is not None else None,
    }
