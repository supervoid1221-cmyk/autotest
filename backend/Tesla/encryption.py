"""应用层静态数据加密。

数据库仅保存带版本前缀的 Fernet 密文。配置多个密钥时，第一个密钥用于
新写入，其余密钥仅用于解密旧数据，从而支持无停机密钥轮换。
"""

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


ENCRYPTED_VALUE_PREFIX = "enc:v1:"


class DataEncryptionError(RuntimeError):
    """密文损坏或当前密钥无法解密。"""


@lru_cache(maxsize=1)
def _fernet():
    keys = getattr(settings, "DATA_ENCRYPTION_KEYS", ())
    if not keys:
        raise ImproperlyConfigured("未配置 DATA_ENCRYPTION_KEYS，无法读写敏感数据。")
    try:
        return MultiFernet([Fernet(str(key).encode("ascii")) for key in keys])
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured("DATA_ENCRYPTION_KEYS 包含无效的 Fernet 密钥。") from exc


def is_encrypted(value):
    return isinstance(value, str) and value.startswith(ENCRYPTED_VALUE_PREFIX)


def encrypt_text(value):
    if value is None or value == "":
        return value
    value = str(value)
    if is_encrypted(value):
        return value
    token = _fernet().encrypt(value.encode("utf-8")).decode("ascii")
    return f"{ENCRYPTED_VALUE_PREFIX}{token}"


def decrypt_text(value):
    if value is None or value == "" or not is_encrypted(value):
        # 兼容升级前的明文；数据迁移或下一次保存时会转换成密文。
        return value
    token = value[len(ENCRYPTED_VALUE_PREFIX):]
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, ValueError) as exc:
        raise DataEncryptionError("敏感数据无法解密，请检查 DATA_ENCRYPTION_KEYS 是否完整且顺序正确。") from exc
