"""共用 SSH 主机验证策略与连接参数；连接及资源释放由调用方管理。"""


def configured_ssh_client(paramiko, strict_host_key, *, load_host_keys=False):
    client = paramiko.SSHClient()
    if strict_host_key or load_host_keys:
        client.load_system_host_keys()
    policy = paramiko.RejectPolicy if strict_host_key else paramiko.AutoAddPolicy
    client.set_missing_host_key_policy(policy())
    return client


def ssh_connection_options(host, port, username, timeout):
    return {
        "hostname": host, "port": port, "username": username,
        "timeout": timeout, "banner_timeout": timeout, "auth_timeout": timeout,
        "look_for_keys": False, "allow_agent": False,
    }
