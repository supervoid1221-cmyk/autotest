import os
import select
import socket
import socketserver
import threading
from contextlib import contextmanager
from Tesla.ssh import configured_ssh_client, ssh_connection_options


class _ForwardServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def _handler_for(transport, remote_host, remote_port):
    class ForwardHandler(socketserver.BaseRequestHandler):
        def handle(self):
            channel = transport.open_channel(
                "direct-tcpip",
                (remote_host, remote_port),
                self.request.getpeername(),
            )
            if channel is None:
                raise ConnectionError("SSH 隧道无法打开数据库转发通道。")
            try:
                while True:
                    readable, _, _ = select.select([self.request, channel], [], [], 1)
                    if self.request in readable:
                        data = self.request.recv(65536)
                        if not data:
                            break
                        channel.sendall(data)
                    if channel in readable:
                        data = channel.recv(65536)
                        if not data:
                            break
                        self.request.sendall(data)
            finally:
                channel.close()

    return ForwardHandler


@contextmanager
def ssh_tunnel(config):
    """建立仅绑定本机随机端口的临时 SSH 隧道，并在退出时可靠关闭。"""
    if not config.get("use_ssh_tunnel"):
        yield config
        return

    try:
        import paramiko
    except ImportError as exc:
        raise ValueError("后端未安装 Paramiko，无法建立 SSH 隧道。") from exc

    key_path = os.path.expanduser(str(config.get("ssh_private_key_path") or "").strip())
    if not os.path.isfile(key_path):
        raise ValueError(f"SSH 私钥不存在或后端不可访问：{key_path}")

    client = configured_ssh_client(paramiko, config.get("ssh_strict_host_key", True), load_host_keys=True)

    server = None
    thread = None
    try:
        timeout = max(1, min(60, int(config.get("connect_timeout") or 10)))
        client.connect(
            **ssh_connection_options(config["ssh_host"], int(config.get("ssh_port") or 22), config["ssh_username"], timeout),
            key_filename=key_path,
            passphrase=config.get("ssh_private_key_passphrase") or None,
        )
        transport = client.get_transport()
        if not transport or not transport.is_active():
            raise ConnectionError("SSH 会话建立后未处于可用状态。")
        transport.set_keepalive(30)
        server = _ForwardServer(
            ("127.0.0.1", 0),
            _handler_for(transport, config["host"], int(config["port"])),
        )
        thread = threading.Thread(target=server.serve_forever, name="database-ssh-tunnel", daemon=True)
        thread.start()
        tunneled = dict(config)
        tunneled["host"] = "127.0.0.1"
        tunneled["port"] = server.server_address[1]
        yield tunneled
    except (OSError, socket.error, paramiko.SSHException) as exc:
        raise ValueError(f"SSH 隧道建立失败：{exc}") from exc
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=2)
        client.close()
