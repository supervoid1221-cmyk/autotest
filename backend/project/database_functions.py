import json
import jsonpath
import re
import time

from .models import DatabaseConnection
from .ssh_tunnel import ssh_tunnel


SQL_FUNCTION_PATTERN = re.compile(
    r'\$\{(?P<function>execute_sql_[A-Za-z_]\w*)\(\s*'
    r'(?P<sql_quote>["\'])(?P<sql>(?:\\.|(?!(?P=sql_quote)).)*)(?P=sql_quote)\s*\)\}',
    re.S,
)

# 兼容改造前已保存的 ${execute_sql_mysql("字段", "SQL")} 配置。
LEGACY_SQL_FUNCTION_PATTERN = re.compile(
    r'\$\{(?P<function>execute_sql_[A-Za-z_]\w*)\(\s*'
    r'(?P<selector_quote>["\'])(?P<selector>(?:\\.|(?!(?P=selector_quote)).)*)(?P=selector_quote)\s*,\s*'
    r'(?P<sql_quote>["\'])(?P<sql>(?:\\.|(?!(?P=sql_quote)).)*)(?P=sql_quote)\s*\)\}',
    re.S,
)


def _validate_sql(sql):
    """仅允许单条 SELECT 或带 WHERE 的 UPDATE。"""
    normalized = re.sub(r"/\*.*?\*/|--[^\n]*", "", sql, flags=re.S).strip()
    if normalized.count(";") > 1 or (";" in normalized and not normalized.endswith(";")):
        raise ValueError("数据库函数不允许执行多条 SQL。")
    normalized = normalized.rstrip(";").strip()
    if re.match(r"^select\b", normalized, re.I):
        return "select", normalized
    if re.match(r"^update\b", normalized, re.I):
        if not re.search(r"\bwhere\b", normalized, re.I):
            raise ValueError("UPDATE 必须包含 WHERE 条件。")
        return "update", normalized
    raise ValueError("数据库函数仅支持 SELECT 或 UPDATE SQL。")


def _infer_parameters(sql, variables):
    fields = re.findall(r"(?:^|\b)([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)\s*=\s*%s", sql, re.I)
    placeholder_count = sql.count("%s")
    if placeholder_count != len(fields):
        raise ValueError("每个 %s 前必须使用 field=%s 格式，平台才能从同名场景变量取值。")
    params = []
    for field in fields:
        variable_name = field.split(".")[-1]
        if variable_name not in variables:
            raise ValueError(f"SQL 参数变量「{variable_name}」不存在。")
        params.append(variables[variable_name])
    return params


def _connect(config, password):
    timeout = max(1, min(60, int(config.get("connect_timeout") or 10)))
    ssl_mode = config.get("ssl_mode") or DatabaseConnection.SSLMode.PREFERRED
    if config["database_type"] == DatabaseConnection.DatabaseType.MYSQL:
        try:
            import pymysql
        except ImportError as exc:
            raise ValueError("后端未安装 PyMySQL，请执行 pip install PyMySQL。") from exc
        ssl_options = None
        if ssl_mode != DatabaseConnection.SSLMode.DISABLED:
            # Warpgate、云数据库等网关要求先协商 TLS。未配置 CA 时只加密传输，
            # 不校验证书主机名；需要严格校验时可在后续扩展 CA 文件配置。
            ssl_options = {"check_hostname": False}
        return pymysql.connect(
            host=config["host"], port=int(config["port"]), user=config["username"],
            password=password, database=config["database"], connect_timeout=timeout,
            read_timeout=timeout, write_timeout=timeout, cursorclass=pymysql.cursors.DictCursor,
            ssl=ssl_options,
        )
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError as exc:
        raise ValueError("后端未安装 psycopg2-binary，请执行 pip install psycopg2-binary。") from exc
    pg_ssl_mode = {"preferred": "prefer", "required": "require", "disabled": "disable"}[ssl_mode]
    return psycopg2.connect(
        host=config["host"], port=int(config["port"]), user=config["username"],
        password=password, dbname=config["database"], connect_timeout=timeout,
        cursor_factory=RealDictCursor, sslmode=pg_ssl_mode,
    )


def _is_transient_connection_error(exc):
    """只重试连接类异常，不重试 SQL 语法、权限和字段错误。"""
    error_name = exc.__class__.__name__.lower()
    message = str(exc).lower()
    return (
        error_name in {"operationalerror", "interfaceerror", "timeouterror"}
        or any(fragment in message for fragment in (
            "can't connect", "cannot connect", "connection reset", "connection refused",
            "server closed", "lost connection", "timed out", "timeout", "ssl:", "tlsv1",
        ))
    )


def _execute_select(config, password, sql, params=None, fetch_one=True):
    """执行只读查询；连接或 TLS 异常时重新建连并额外尝试一次。"""
    for attempt in range(2):
        try:
            with ssh_tunnel(config) as connect_config:
                connection = _connect(connect_config, password)
                try:
                    with connection.cursor() as cursor:
                        if params:
                            cursor.execute(sql, params)
                        else:
                            cursor.execute(sql)
                        row = cursor.fetchone() if fetch_one else None
                        columns = [item[0] for item in (cursor.description or [])]
                finally:
                    connection.close()
            return row, columns
        except Exception as exc:
            if attempt == 0 and _is_transient_connection_error(exc):
                time.sleep(0.3)
                continue
            raise


def _execute_update(config, password, sql, params=None):
    """执行一次事务性 UPDATE；写操作不自动重试，避免网络异常造成重复写入。"""
    try:
        with ssh_tunnel(config) as connect_config:
            connection = _connect(connect_config, password)
            try:
                with connection.cursor() as cursor:
                    cursor.execute(sql, params or None)
                    affected_rows = cursor.rowcount
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()
        return affected_rows
    except Exception:
        raise


def test_database_connection(config, password):
    started = time.perf_counter()
    connection = None
    with ssh_tunnel(config) as connect_config:
        connection = _connect(connect_config, password)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        finally:
            connection.close()
    return round((time.perf_counter() - started) * 1000)


def test_database_query(config, password, sql, confirm_write=False):
    """在连接配置页校验 SQL；UPDATE 必须启用写权限并二次确认。"""
    operation, safe_sql = _validate_sql(sql)
    if "%s" in safe_sql:
        raise ValueError("SQL 校验不支持未绑定的 %s，请先填写固定测试条件。")
    started = time.perf_counter()
    if operation == "update":
        if not config.get("allow_write"):
            raise ValueError("当前数据库连接未开启“允许执行 UPDATE”。")
        if not confirm_write:
            raise ValueError("执行 UPDATE 校验需明确确认写入操作。")
        affected_rows = _execute_update(config, password, safe_sql)
        return {
            "operation": operation,
            "affected_rows": affected_rows,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
        }
    row, columns = _execute_select(config, password, safe_sql)
    normalized_row = None if row is None else (dict(row) if hasattr(row, "keys") else dict(zip(columns, row)))
    return {
        "operation": operation,
        "columns": columns,
        "row": normalized_row,
        "row_count": 1 if normalized_row is not None else 0,
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
    }


def execute_database_query(function_name, sql, variables, project_id, environment_name, selector=None):
    connection_config = DatabaseConnection.objects.filter(
        projects__id=project_id, environment_name=environment_name,
        function_name=function_name, enabled=True,
    ).distinct().first()
    if not connection_config:
        raise ValueError(
            f"项目当前环境未配置数据库调用函数「{function_name}」。"
        )
    operation, safe_sql = _validate_sql(sql)
    params = _infer_parameters(safe_sql, variables)
    config = {
        "database_type": connection_config.database_type,
        "host": connection_config.host,
        "port": connection_config.port,
        "username": connection_config.username,
        "database": connection_config.database,
        "connect_timeout": connection_config.connect_timeout,
        "ssl_mode": connection_config.ssl_mode,
        "use_ssh_tunnel": connection_config.use_ssh_tunnel,
        "ssh_host": connection_config.ssh_host,
        "ssh_port": connection_config.ssh_port,
        "ssh_username": connection_config.ssh_username,
        "ssh_private_key_path": connection_config.ssh_private_key_path,
        "ssh_private_key_passphrase": connection_config.ssh_private_key_passphrase,
        "ssh_strict_host_key": connection_config.ssh_strict_host_key,
    }
    if operation == "update":
        if not connection_config.allow_write:
            raise ValueError(f"数据库函数「{function_name}」未开启 UPDATE 写入权限。")
        _execute_update(config, connection_config.password, safe_sql, params)
        # 后置操作只需产生副作用，不将受影响行数拼进请求内容。
        return ""
    row, _ = _execute_select(config, connection_config.password, safe_sql, params)
    if row is None:
        return None
    row = dict(row)
    if not row:
        return None
    if selector and selector.startswith("$"):
        # JSONPath 默认针对第一行第一列；JSON 字符串会先反序列化。
        source = next(iter(row.values()))
        if isinstance(source, (bytes, bytearray)):
            source = source.decode("utf-8")
        if isinstance(source, str):
            try:
                source = json.loads(source)
            except json.JSONDecodeError as exc:
                raise ValueError("SQL 第一列不是有效 JSON，无法使用 JSONPath 提取。") from exc
        values = jsonpath.jsonpath(source, selector) or []
        if not values:
            raise ValueError(f"SQL 查询结果未匹配到 JSONPath「{selector}」。")
        return values[0]
    if selector:
        # 继续兼容旧格式中的普通字段名称。
        if selector not in row:
            raise ValueError(f"查询结果不存在字段「{selector}」，可用字段：{', '.join(row.keys())}")
        return row[selector]
    # 单参数格式固定返回第一行第一列。
    return next(iter(row.values()))


def substitute_database_functions(content, variables, project_id, environment_name):
    if not project_id or not environment_name or "${execute_sql_" not in content:
        return content

    def replace(match, legacy=False):
        sql = match.group("sql").replace(r'\"', '"').replace(r"\'", "'").replace(r"\\", "\\")
        value = execute_database_query(
            match.group("function"), sql, variables or {}, project_id, environment_name,
            match.groupdict().get("selector") if legacy else None,
        )
        return "null" if value is None else str(value)

    content = LEGACY_SQL_FUNCTION_PATTERN.sub(lambda match: replace(match, True), content)
    return SQL_FUNCTION_PATTERN.sub(replace, content)
