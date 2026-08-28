"""UI 自动化上传文件的安全存储与运行期解析。"""

from pathlib import Path
from django.conf import settings


UPLOAD_ROOT = (Path(settings.BASE_DIR) / "uploaded_ui_files").resolve()


def resolve_uploaded_file(file_id, project_id):
    """只返回当前项目下、位于平台上传目录内的实际文件路径。"""
    from case_ui.models import UiUploadedFile
    try:
        uploaded = UiUploadedFile.objects.get(pk=int(file_id), project_id=int(project_id))
    except (TypeError, ValueError, UiUploadedFile.DoesNotExist):
        raise ValueError("上传文件不存在、已删除或不属于当前项目，请重新选择文件。")
    path = (Path(settings.BASE_DIR) / uploaded.stored_path).resolve()
    if UPLOAD_ROOT not in path.parents or not path.is_file():
        raise ValueError("上传文件已不存在，请重新上传后再执行。")
    return path, uploaded
