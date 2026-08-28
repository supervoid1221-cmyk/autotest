"""平台上传文件在运行期转换为 requests 的 multipart 参数。"""

from contextlib import contextmanager
from pathlib import Path

from django.conf import settings


UPLOAD_ROOT = (Path(settings.BASE_DIR) / "uploaded_api_files").resolve()


def _safe_file_path(value):
    """只允许读取平台上传目录中的文件，避免接口配置读取任意服务器文件。"""
    if not isinstance(value, dict):
        raise ValueError("上传文件配置格式不正确。")
    relative_path = str(value.get("path") or "")
    path = (Path(settings.BASE_DIR) / relative_path).resolve()
    if not relative_path or UPLOAD_ROOT not in path.parents or not path.is_file():
        raise ValueError("上传文件不存在或不属于平台文件目录，请重新上传文件。")
    return path


@contextmanager
def opened_request_files(file_config):
    """返回 requests 支持的 [(字段名, (文件名, 文件对象))]，并在请求结束后关闭文件。"""
    opened = []
    request_files = []
    try:
        for field_name, raw_entries in (file_config or {}).items():
            entries = raw_entries if isinstance(raw_entries, list) else [raw_entries]
            for entry in entries:
                path = _safe_file_path(entry)
                file_object = path.open("rb")
                opened.append(file_object)
                request_files.append((str(field_name), (str(entry.get("name") or path.name), file_object)))
        yield request_files
    finally:
        for file_object in opened:
            file_object.close()
