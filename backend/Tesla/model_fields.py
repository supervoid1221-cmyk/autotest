"""透明加解密的 Django 模型字段。"""

import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from Tesla.encryption import decrypt_text, encrypt_text, is_encrypted


class EncryptedTextField(models.TextField):
    description = "Application encrypted text"

    def from_db_value(self, value, expression, connection):
        return decrypt_text(value)

    def to_python(self, value):
        if value is None or not isinstance(value, str):
            return value
        return decrypt_text(value)

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        return encrypt_text(value)


class EncryptedURLField(models.URLField):
    """保留 URL 表单校验，但数据库使用 TEXT 防止密文长度溢出。"""

    description = "Application encrypted URL"

    def db_type(self, connection):
        return models.TextField().db_type(connection)

    def cast_db_type(self, connection):
        return models.TextField().cast_db_type(connection)

    def from_db_value(self, value, expression, connection):
        return decrypt_text(value)

    def to_python(self, value):
        if value is None or not isinstance(value, str):
            return value
        return decrypt_text(value)

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        return encrypt_text(value)


class EncryptedJSONField(models.JSONField):
    """将整个 JSON 文档加密后作为 JSON 字符串存储。"""

    description = "Application encrypted JSON"

    def from_db_value(self, value, expression, connection):
        parsed = super().from_db_value(value, expression, connection)
        if not is_encrypted(parsed):
            return parsed
        plaintext = decrypt_text(parsed)
        try:
            return json.loads(plaintext, cls=self.decoder)
        except (TypeError, ValueError) as exc:
            raise ValueError("已解密的 JSON 敏感字段格式无效。") from exc

    def get_db_prep_value(self, value, connection, prepared=False):
        if hasattr(value, "as_sql"):
            return value
        encoder = self.encoder or DjangoJSONEncoder
        plaintext = json.dumps(value, cls=encoder, ensure_ascii=False, separators=(",", ":"))
        encrypted = encrypt_text(plaintext)
        return connection.ops.adapt_json_value(encrypted, self.encoder)
