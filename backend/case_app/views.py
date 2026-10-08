import base64
import struct
import shutil
import time
import uuid
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import models, transaction
from django.http import FileResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from project.access import project_access_q, require_project_access
from suite.run_metrics import build_overview
from account.tenancy import TenantScopedViewSetMixin, get_request_tenant, validate_tenant_relations
from account.tenant_runtime import (
    ensure_tenant_storage_capacity,
    is_managed_storage_path,
    legacy_tenant_path,
    tenant_path,
)

from .appium_client import AppiumClient
from .health import check_appium_node
from .inspector import parse_page_source
from .models import (
    AppApplication, AppArtifact, AppCase, AppDevice, AppElement, AppExecutionNode,
    AppInspectionSession, AppRun, AppStep, AppVersion,
)
from .serializers import (
    AppApplicationSerializer, AppCaseSerializer, AppDeviceSerializer, AppElementSerializer,
    AppExecutionNodeSerializer, AppRunSerializer, AppStepSerializer, AppVersionSerializer,
)


class ProjectOwnedViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    project_path = "project__"

    def get_queryset(self):
        queryset = self.queryset.filter(
            **{f"{self.project_path}tenant": self.current_tenant()},
        ).filter(project_access_q(self.request.user, self.project_path)).distinct()
        if any(field.name == "tenant" for field in queryset.model._meta.fields):
            queryset = self.tenant_scope(queryset)
        project = self.request.query_params.get("project")
        name = str(self.request.query_params.get("name") or "").strip()
        if project:
            queryset = queryset.filter(**{f"{self.project_path}id": project})
        if name and hasattr(queryset.model, "name"):
            queryset = queryset.filter(name__icontains=name)
        return queryset

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        require_project_access(self.request.user, project)
        tenant = validate_tenant_relations(self.request, project=project)
        if any(field.name == "tenant" for field in serializer.Meta.model._meta.fields):
            serializer.save(tenant=tenant, created_by=self.request.user)
        else:
            serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        require_project_access(self.request.user, instance.project)
        project = serializer.validated_data.get("project", instance.project)
        require_project_access(self.request.user, project)
        if any(field.name == "tenant" for field in serializer.Meta.model._meta.fields):
            serializer.save(tenant=validate_tenant_relations(self.request, instance=instance, project=project))
        else:
            serializer.save()


class AppApplicationViewSet(ProjectOwnedViewSet):
    queryset = AppApplication.objects.select_related("project", "created_by").prefetch_related("versions")
    serializer_class = AppApplicationSerializer

    @action(detail=True, methods=["post"], url_path="upload-version", parser_classes=[MultiPartParser, FormParser])
    def upload_version(self, request, pk=None):
        application = self.get_object()
        require_project_access(request.user, application.project)
        upload = request.FILES.get("file")
        version_name = str(request.data.get("version_name") or "").strip()
        if not upload or not version_name:
            return Response({"detail": "请填写版本名称并选择 APK 文件。"}, status=status.HTTP_400_BAD_REQUEST)
        if not upload.name.lower().endswith(".apk"):
            return Response({"file": "第一期仅支持 APK 文件。"}, status=status.HTTP_400_BAD_REQUEST)
        if upload.size > 1024 * 1024 * 1024:
            return Response({"file": "APK 文件不能超过 1GB。"}, status=status.HTTP_400_BAD_REQUEST)
        if application.versions.filter(version_name=version_name).exists():
            return Response({"version_name": "该版本名称已存在。"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            ensure_tenant_storage_capacity(application.project.tenant, upload.size)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        root = tenant_path(
            Path(settings.BASE_DIR) / "app_uploads",
            application.project.tenant_id,
            application.project_id,
        )
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{uuid.uuid4().hex}.apk"
        with path.open("wb") as destination:
            for chunk in upload.chunks():
                destination.write(chunk)
        version = AppVersion.objects.create(
            application=application, version_name=version_name,
            version_code=str(request.data.get("version_code") or "")[:64],
            original_name=Path(upload.name).name, file_path=str(path.relative_to(settings.BASE_DIR)),
            file_size=upload.size, created_by=request.user,
        )
        return Response(AppVersionSerializer(version).data, status=status.HTTP_201_CREATED)


class AppVersionViewSet(mixins.DestroyModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = AppVersion.objects.select_related("application__project", "created_by")
    serializer_class = AppVersionSerializer

    def get_queryset(self):
        queryset = self.queryset.filter(
            application__project__tenant=get_request_tenant(self.request),
        ).filter(project_access_q(self.request.user, "application__project__")).distinct()
        application = self.request.query_params.get("application")
        return queryset.filter(application_id=application) if application else queryset

    def perform_destroy(self, instance):
        require_project_access(self.request.user, instance.application.project)
        path = (Path(settings.BASE_DIR) / instance.file_path).resolve() if instance.file_path else None
        tenant_id = instance.application.project.tenant_id
        instance.delete()
        if path and is_managed_storage_path(path, "app_uploads", tenant=tenant_id):
            path.unlink(missing_ok=True)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        version = self.get_object()
        path = Path(settings.BASE_DIR) / version.file_path
        if not path.exists():
            return Response({"detail": "安装包文件不存在。"}, status=status.HTTP_404_NOT_FOUND)
        return FileResponse(path.open("rb"), as_attachment=True, filename=version.original_name or path.name)


class AppExecutionNodeViewSet(ProjectOwnedViewSet):
    queryset = AppExecutionNode.objects.select_related("project", "created_by").prefetch_related("devices")
    serializer_class = AppExecutionNodeSerializer

    @action(detail=True, methods=["post"])
    def test(self, request, pk=None):
        node = self.get_object()
        connected, value = check_appium_node(node, timeout=8)
        return Response({"connected": connected, "message": node.last_message, "status": value}, status=status.HTTP_200_OK if connected else status.HTTP_400_BAD_REQUEST)


class AppDeviceViewSet(ProjectOwnedViewSet):
    queryset = AppDevice.objects.select_related("project", "node", "created_by")
    serializer_class = AppDeviceSerializer

    def list(self, request, *args, **kwargs):
        _cleanup_expired_inspections()
        return super().list(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def test(self, request, pk=None):
        device = self.get_object()
        if device.state in {AppDevice.State.BUSY, AppDevice.State.INSPECTING}:
            return Response({"detail": "设备正在被任务或元素检查占用。"}, status=status.HTTP_409_CONFLICT)
        client = AppiumClient(device.node.server_url, timeout=45)
        try:
            capabilities = client.start_session({
                "platformName": "Android", "appium:automationName": "UiAutomator2",
                "appium:udid": device.udid, "appium:deviceName": device.name,
                "appium:autoLaunch": False, "appium:noReset": True, "appium:newCommandTimeout": 30,
            })
            device.platform_version = str(capabilities.get("platformVersion") or capabilities.get("appium:platformVersion") or device.platform_version)
            device.model = str(capabilities.get("deviceModel") or capabilities.get("appium:deviceModel") or device.model)
            width = capabilities.get("deviceScreenSize") or capabilities.get("appium:deviceScreenSize")
            if width:
                device.resolution = str(width)
            device.state, device.last_message, device.last_seen_at = AppDevice.State.ONLINE, "设备连接成功", timezone.now()
            connected = True
        except Exception as exc:
            device.state, device.last_message = AppDevice.State.OFFLINE, str(exc)[:500]
            connected = False
        finally:
            client.close()
        device.save(update_fields=["platform_version", "model", "resolution", "state", "last_message", "last_seen_at", "updated_at"])
        return Response({"connected": connected, "message": device.last_message, "device": self.get_serializer(device).data}, status=status.HTTP_200_OK if connected else status.HTTP_400_BAD_REQUEST)


class AppElementViewSet(ProjectOwnedViewSet):
    queryset = AppElement.objects.select_related("project", "application", "module", "created_by")
    serializer_class = AppElementSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        application = self.request.query_params.get("application")
        module = self.request.query_params.get("module")
        locator_type = str(self.request.query_params.get("locator_type") or "").strip()
        search = str(self.request.query_params.get("search") or "").strip()
        if application:
            queryset = queryset.filter(application_id=application)
        if module:
            queryset = queryset.filter(module_id=module)
        if locator_type:
            queryset = queryset.filter(locator_type=locator_type)
        if search:
            queryset = queryset.filter(
                models.Q(name__icontains=search)
                | models.Q(page_name__icontains=search)
                | models.Q(activity__icontains=search)
                | models.Q(locator_value__icontains=search)
            )
        return queryset

    def perform_destroy(self, instance):
        require_project_access(self.request.user, instance.project)
        if instance.steps.exists():
            raise serializers.ValidationError("元素正在被用例步骤使用，不能删除。")
        instance.delete()


def _inspection_client(session):
    return AppiumClient(session.device.node.server_url, timeout=45).attach(session.remote_session_id)


def _close_inspection(session, status_value=AppInspectionSession.Status.CLOSED, error=""):
    if session.remote_session_id:
        try:
            _inspection_client(session).close()
        except Exception:
            pass
    session.status = status_value
    session.last_error = str(error or "")[:2000]
    session.closed_at = timezone.now()
    session.last_activity_at = timezone.now()
    session.remote_session_id = ""
    session.save(update_fields=["status", "last_error", "closed_at", "last_activity_at", "remote_session_id"])
    AppDevice.objects.filter(pk=session.device_id, state=AppDevice.State.INSPECTING).update(
        state=AppDevice.State.ONLINE, last_message="元素检查已结束", last_seen_at=timezone.now()
    )


def _cleanup_expired_inspections():
    cutoff = timezone.now() - timedelta(minutes=10)
    sessions = AppInspectionSession.objects.select_related("device__node").filter(
        status__in=[AppInspectionSession.Status.STARTING, AppInspectionSession.Status.ACTIVE],
        last_activity_at__lt=cutoff,
    )
    count = 0
    for session in sessions:
        _close_inspection(session, error="超过 10 分钟无操作，会话已自动释放。")
        count += 1
    return count


def _png_size(content):
    if len(content) >= 24 and content[:8] == b"\x89PNG\r\n\x1a\n":
        return list(struct.unpack(">II", content[16:24]))
    return [0, 0]


def _inspection_snapshot(session):
    client = _inspection_client(session)
    screenshot = client.screenshot()
    source = client.page_source()
    try:
        activity = client.current_activity()
    except Exception:
        activity = session.application.main_activity
    try:
        package_name = client.current_package()
    except Exception:
        package_name = session.application.package_name
    session.last_activity_at = timezone.now()
    session.save(update_fields=["last_activity_at"])
    return {
        "id": str(session.id), "status": session.status,
        "project": session.project_id, "application": session.application_id,
        "device": session.device_id, "version": session.version_id,
        "activity": activity,
        "package_name": package_name, "screen": dict(zip(("width", "height"), _png_size(screenshot))),
        "screenshot": f"data:image/png;base64,{base64.b64encode(screenshot).decode('ascii')}",
        "elements": parse_page_source(source), "updated_at": timezone.now().isoformat(),
    }


def _inspection_snapshot_after_action(session, delay=0.45):
    # Appium 命令完成时 Android 可能尚未完成下一帧绘制，稍候再抓取可避免返回旧画面。
    time.sleep(delay)
    return _inspection_snapshot(session)


def _recording_element(session, request, user):
    locator_type = str(request.data.get("locator_type") or "").strip()
    locator_value = str(request.data.get("locator_value") or "").strip()
    if not locator_type or not locator_value:
        raise serializers.ValidationError({"element": "录制元素缺少有效定位信息。"})
    element = AppElement.objects.filter(
        project=session.project, application=session.application,
        locator_type=locator_type, locator_value=locator_value,
    ).first()
    if element:
        return element
    base_name = str(request.data.get("element_name") or "页面元素").strip()[:96] or "页面元素"
    name = base_name
    index = 2
    while AppElement.objects.filter(project=session.project, application=session.application, name=name).exists():
        suffix = f" ({index})"
        name = f"{base_name[:96-len(suffix)]}{suffix}"
        index += 1
    payload = {
        "project": session.project_id, "application": session.application_id,
        "name": name, "page_name": str(request.data.get("page_name") or "")[:128],
        "activity": str(request.data.get("activity") or "")[:255],
        "locator_type": locator_type, "locator_value": locator_value,
        "fallback_locator": request.data.get("fallback_locator") or [],
        "element_class": str(request.data.get("element_class") or "")[:255],
        "snapshot": request.data.get("snapshot") or {},
        "description": "由检查并录制自动创建",
    }
    serializer = AppElementSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    return serializer.save(created_by=user)


def _recorded_step(action, element=None, target=None, value=""):
    return {
        "action": action, "element": element.id if element else None,
        "element_name": element.name if element else "", "target": target or {},
        "value": value, "options": {}, "continue_on_failure": False,
    }


class AppInspectionSessionViewSet(viewsets.GenericViewSet):
    queryset = AppInspectionSession.objects.select_related("project", "application", "version", "device__node", "created_by")

    def get_queryset(self):
        return self.queryset.filter(
            project__tenant=get_request_tenant(self.request),
        ).filter(project_access_q(self.request.user, "project__")).distinct()

    @action(detail=False, methods=["get"])
    def current(self, request):
        _cleanup_expired_inspections()
        session = self.get_queryset().filter(
            created_by=request.user, status=AppInspectionSession.Status.ACTIVE
        ).first()
        if not session:
            return Response({"active": False})
        try:
            return Response({"active": True, "session": _inspection_snapshot(session)})
        except Exception as exc:
            _close_inspection(session, AppInspectionSession.Status.ERROR, exc)
            return Response({"active": False, "message": "上次元素检查会话已失效，请重新启动。"})

    def create(self, request):
        _cleanup_expired_inspections()
        project_id = request.data.get("project")
        application = AppApplication.objects.filter(pk=request.data.get("application"), project_id=project_id, enabled=True).first()
        device = AppDevice.objects.select_related("node", "project").filter(
            pk=request.data.get("device"), project_id=project_id, enabled=True
        ).first()
        if not application:
            return Response({"application": "请选择当前项目可用的应用。"}, status=status.HTTP_400_BAD_REQUEST)
        if not device:
            return Response({"device": "请选择当前项目可用的设备。"}, status=status.HTTP_400_BAD_REQUEST)
        require_project_access(request.user, application.project)
        version = None
        if request.data.get("version"):
            version = AppVersion.objects.filter(pk=request.data["version"], application=application, enabled=True).first()
            if not version:
                return Response({"version": "所选应用版本不可用。"}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            locked_device = AppDevice.objects.select_for_update().get(pk=device.pk)
            if locked_device.state in {AppDevice.State.BUSY, AppDevice.State.INSPECTING}:
                return Response({"device": "设备正在执行任务或元素检查，请选择其他设备。"}, status=status.HTTP_409_CONFLICT)
            locked_device.state = AppDevice.State.INSPECTING
            locked_device.last_message = "正在进行元素检查"
            locked_device.save(update_fields=["state", "last_message", "updated_at"])
            session = AppInspectionSession.objects.create(
                project=application.project, application=application, device=locked_device,
                version=version, created_by=request.user,
            )
        client = AppiumClient(device.node.server_url, timeout=60)
        try:
            capabilities = {
                "platformName": "Android", "appium:automationName": "UiAutomator2",
                "appium:udid": device.udid, "appium:deviceName": device.name,
                "appium:noReset": not bool(request.data.get("reset_app", False)),
                "appium:appPackage": application.package_name,
                "appium:newCommandTimeout": 660,
            }
            if application.main_activity:
                capabilities["appium:appActivity"] = application.main_activity
            if version and version.file_path:
                path = (Path(settings.BASE_DIR) / version.file_path).resolve()
                if path.exists():
                    capabilities["appium:app"] = str(path)
            client.start_session(capabilities)
            session.remote_session_id = client.session_id
            session.status = AppInspectionSession.Status.ACTIVE
            session.last_activity_at = timezone.now()
            session.save(update_fields=["remote_session_id", "status", "last_activity_at"])
            return Response(_inspection_snapshot(session), status=status.HTTP_201_CREATED)
        except Exception as exc:
            client.close()
            _close_inspection(session, AppInspectionSession.Status.ERROR, exc)
            return Response({"detail": f"元素检查启动失败：{exc}"}, status=status.HTTP_400_BAD_REQUEST)

    def retrieve(self, request, pk=None):
        session = self.get_object()
        if session.status != AppInspectionSession.Status.ACTIVE:
            return Response({"detail": "元素检查会话已结束。"}, status=status.HTTP_409_CONFLICT)
        try:
            return Response(_inspection_snapshot(session))
        except Exception as exc:
            _close_inspection(session, AppInspectionSession.Status.ERROR, exc)
            return Response({"detail": f"页面获取失败：{exc}"}, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, pk=None):
        session = self.get_object()
        _close_inspection(session)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def refresh(self, request, pk=None):
        return self.retrieve(request, pk)

    @action(detail=True, methods=["post"])
    def tap(self, request, pk=None):
        session = self.get_object()
        try:
            client = _inspection_client(session)
            locator_type = str(request.data.get("locator_type") or "").strip()
            locator_value = str(request.data.get("locator_value") or "").strip()
            if locator_type == "coordinate" and locator_value:
                coordinates = [part.strip() for part in locator_value.split(",")]
                if len(coordinates) != 2:
                    raise ValueError("坐标定位格式应为 x,y。")
                client.tap(int(coordinates[0]), int(coordinates[1]))
            elif locator_type and locator_value:
                client.click_element(locator_type, locator_value)
            else:
                client.tap(int(request.data.get("x")), int(request.data.get("y")))
            result = _inspection_snapshot_after_action(session)
            if request.data.get("record"):
                result["recorded_step"] = _recorded_step("click", _recording_element(session, request, request.user))
            return Response(result)
        except (TypeError, ValueError):
            return Response({"detail": "点击坐标不正确。"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({"detail": f"设备点击失败：{exc}"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def back(self, request, pk=None):
        session = self.get_object()
        try:
            _inspection_client(session).command("POST", "/back", {})
            result = _inspection_snapshot_after_action(session)
            if request.data.get("record"):
                result["recorded_step"] = _recorded_step("back")
            return Response(result)
        except Exception as exc:
            return Response({"detail": f"返回操作失败：{exc}"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="input")
    def input_text(self, request, pk=None):
        session = self.get_object()
        text = str(request.data.get("text") or "")
        try:
            element = _recording_element(session, request, request.user)
            client = _inspection_client(session)
            if element.locator_type == "coordinate":
                coordinates = [part.strip() for part in element.locator_value.split(",")]
                if len(coordinates) != 2:
                    raise ValueError("坐标定位格式应为 x,y。")
                client.tap(int(coordinates[0]), int(coordinates[1]))
                client.command("POST", "/keys", {"text": text, "value": list(text)})
            else:
                client.input_text(element.locator_type, element.locator_value, text, bool(request.data.get("clear", True)))
            result = _inspection_snapshot_after_action(session)
            result["recorded_step"] = _recorded_step("input", element, value=text)
            return Response(result)
        except Exception as exc:
            return Response({"detail": f"输入操作失败：{exc}"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="swipe")
    def swipe(self, request, pk=None):
        session = self.get_object()
        try:
            target = {
                "start_x": int(request.data.get("start_x")), "start_y": int(request.data.get("start_y")),
                "end_x": int(request.data.get("end_x")), "end_y": int(request.data.get("end_y")),
            }
            _inspection_client(session).swipe(**target, duration=int(request.data.get("duration") or 500))
            result = _inspection_snapshot_after_action(session)
            result["recorded_step"] = _recorded_step("swipe", target=target)
            return Response(result)
        except (TypeError, ValueError):
            return Response({"detail": "滑动坐标不正确。"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({"detail": f"滑动操作失败：{exc}"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="finish-recording")
    def finish_recording(self, request, pk=None):
        session = self.get_object()
        items = request.data.get("steps") or []
        if not isinstance(items, list) or not items:
            return Response({"steps": "至少录制一个步骤后才能生成用例草稿。"}, status=status.HTTP_400_BAD_REQUEST)
        base_name = str(request.data.get("name") or f"{session.application.name} 录制草稿").strip()[:96]
        name = base_name
        index = 2
        while AppCase.objects.filter(tenant=session.project.tenant, project=session.project, name=name).exists():
            suffix = f" ({index})"
            name = f"{base_name[:96-len(suffix)]}{suffix}"
            index += 1
        with transaction.atomic():
            case = AppCase.objects.create(
                tenant=session.project.tenant, project=session.project, application=session.application, default_device=session.device,
                name=name, description="由检查并录制自动生成，请确认步骤后启用。",
                enabled=False, created_by=request.user,
            )
            for order, item in enumerate(items, start=1):
                payload = {
                    "case": case.id, "order": order, "action": item.get("action"),
                    "element": item.get("element"), "target": item.get("target") or {},
                    "value": item.get("value") or "", "options": item.get("options") or {},
                    "continue_on_failure": bool(item.get("continue_on_failure", False)),
                }
                serializer = AppStepSerializer(data=payload)
                serializer.is_valid(raise_exception=True)
                serializer.save()
        data = AppCaseSerializer(case).data
        _close_inspection(session)
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def validate(self, request, pk=None):
        session = self.get_object()
        using = str(request.data.get("locator_type") or "").strip()
        value = str(request.data.get("locator_value") or "").strip()
        if not using or not value:
            return Response({"detail": "请选择定位方式并填写定位表达式。"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            if using == "coordinate":
                coordinates = [part.strip() for part in value.split(",")]
                if len(coordinates) != 2:
                    return Response({"detail": "坐标定位格式应为 x,y。"}, status=status.HTTP_400_BAD_REQUEST)
                x, y = int(coordinates[0]), int(coordinates[1])
                width, height = _png_size(_inspection_client(session).screenshot())
                matched = int(0 <= x <= width and 0 <= y <= height)
                return Response({"matched": matched, "unique": bool(matched)})
            if using in {"ocr_text", "image_text"}:
                match = _inspection_client(session).locate_visual_text(using, value)
                return Response({"matched": 1, "unique": True, "match": match})
            matches = _inspection_client(session).elements(using, value)
            session.last_activity_at = timezone.now()
            session.save(update_fields=["last_activity_at"])
            return Response({"matched": len(matches), "unique": len(matches) == 1})
        except Exception as exc:
            return Response({"detail": f"定位验证失败：{exc}"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="save-element")
    def save_element(self, request, pk=None):
        session = self.get_object()
        payload = {
            "project": session.project_id, "application": session.application_id,
            "name": request.data.get("name"), "page_name": request.data.get("page_name", ""),
            "activity": request.data.get("activity", ""), "locator_type": request.data.get("locator_type"),
            "locator_value": request.data.get("locator_value"),
            "fallback_locator": request.data.get("fallback_locator", []),
            "element_class": request.data.get("element_class", ""),
            "snapshot": request.data.get("snapshot", {}), "description": request.data.get("description", ""),
        }
        serializer = AppElementSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user)
        session.last_activity_at = timezone.now()
        session.save(update_fields=["last_activity_at"])
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AppCaseViewSet(ProjectOwnedViewSet):
    queryset = AppCase.objects.select_related("project", "application", "default_device", "created_by").prefetch_related("steps__element")
    serializer_class = AppCaseSerializer

    @extend_schema(tags=["Case_App"])
    @action(detail=False, methods=["get"])
    def overview(self, request):
        """App 用例列表页的聚合数据：平台 KPI + 每个用例的最近执行与通过率。

        用例级结果只能从测试计划的执行报告里取（即席试跑不落库），因此本接口
        反映的是「用例被编排进计划后的运行情况」。聚合逻辑见 suite/run_metrics.py。
        """
        tenant = get_request_tenant(request)
        rows = list(
            AppCase.objects
            .filter(tenant=tenant)
            .filter(project_access_q(request.user, self.project_path))
            .values_list("id", "project_id")
        )
        return Response(build_overview(
            request.user, tenant,
            cache_scope="app_case_overview",
            key_prefix="app-",  # suite/models.py 组装计划时写成 f"app-{id}"
            case_rows=rows,
        ))

    @action(detail=True, methods=["post"], url_path="sync-steps")
    def sync_steps(self, request, pk=None):
        case = self.get_object()
        items = request.data.get("steps", [])
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            return Response({"steps": "步骤列表格式不正确。"}, status=status.HTTP_400_BAD_REQUEST)
        ids = [item.get("id") for item in items if item.get("id")]
        if len(ids) != len(set(ids)):
            return Response({"steps": "步骤不能重复。"}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            existing = {step.id: step for step in AppStep.objects.select_for_update().filter(case=case)}
            if any(step_id not in existing for step_id in ids):
                raise serializers.ValidationError({"steps": "存在不属于当前用例的步骤。"})
            AppStep.objects.filter(case=case).exclude(id__in=ids).delete()
            if ids:
                AppStep.objects.filter(id__in=ids).update(order=models.F("order") + len(items) + 1000)
            for order, item in enumerate(items, start=1):
                payload = dict(item)
                step_id = payload.pop("id", None)
                for readonly in ("action_name", "element_name"):
                    payload.pop(readonly, None)
                payload.update({"case": case.id, "order": order})
                serializer = AppStepSerializer(instance=existing.get(step_id), data=payload)
                serializer.is_valid(raise_exception=True)
                serializer.save()
        return Response(AppStepSerializer(case.steps.all(), many=True).data)

    @action(detail=True, methods=["post"])
    def run(self, request, pk=None):
        _cleanup_expired_inspections()
        case = self.get_object()
        if not case.enabled:
            return Response({"detail": "App 用例已停用。"}, status=status.HTTP_400_BAD_REQUEST)
        if not case.steps.exists():
            return Response({"detail": "App 用例没有可执行步骤。"}, status=status.HTTP_400_BAD_REQUEST)
        device_id = request.data.get("device") or case.default_device_id
        device = AppDevice.objects.filter(pk=device_id, project=case.project, enabled=True).first()
        if not device:
            return Response({"device": "请选择当前项目可用的执行设备。"}, status=status.HTTP_400_BAD_REQUEST)
        version = None
        if request.data.get("version"):
            version = AppVersion.objects.filter(pk=request.data["version"], application=case.application, enabled=True).first()
            if not version:
                return Response({"version": "所选应用版本不可用。"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            ensure_tenant_storage_capacity(case.tenant)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        run = AppRun.objects.create(
            tenant=case.tenant, case=case, project=case.project, application=case.application, version=version, device=device,
            options={
                "auto_install": bool(request.data.get("auto_install", case.application.auto_install)),
                "clear_data": bool(request.data.get("clear_data", case.application.clear_data)),
            }, created_by=request.user,
        )
        from execution_control.dispatcher import dispatch_waiting_tasks
        transaction.on_commit(dispatch_waiting_tasks)
        return Response(AppRunSerializer(run).data, status=status.HTTP_201_CREATED)


class AppStepViewSet(ProjectOwnedViewSet):
    queryset = AppStep.objects.select_related("case__project", "element")
    serializer_class = AppStepSerializer
    project_path = "case__project__"

    def get_queryset(self):
        queryset = self.queryset.filter(project_access_q(self.request.user, self.project_path)).distinct()
        queryset = queryset.filter(case__tenant=self.current_tenant())
        case = self.request.query_params.get("case")
        return queryset.filter(case_id=case) if case else queryset

    def perform_create(self, serializer):
        require_project_access(self.request.user, serializer.validated_data["case"].project)
        serializer.save()

    def perform_update(self, serializer):
        require_project_access(self.request.user, self.get_object().case.project)
        serializer.save()


class AppRunViewSet(TenantScopedViewSetMixin, mixins.DestroyModelMixin, viewsets.ReadOnlyModelViewSet):
    queryset = AppRun.objects.select_related("case", "project", "application", "version", "device", "created_by").prefetch_related("step_results__artifacts", "artifacts")
    serializer_class = AppRunSerializer

    def get_queryset(self):
        queryset = self.tenant_scope(self.queryset).filter(project_access_q(self.request.user, "project__")).distinct()
        for key in ("project", "case", "device", "status"):
            value = self.request.query_params.get(key)
            if value:
                queryset = queryset.filter(**{f"{key}_id" if key != "status" else key: value})
        return queryset

    def perform_destroy(self, instance):
        require_project_access(self.request.user, instance.project)
        if instance.status in {AppRun.Status.QUEUED, AppRun.Status.PREPARING, AppRun.Status.INSTALLING, AppRun.Status.RUNNING, AppRun.Status.REPORTING}:
            raise serializers.ValidationError("执行中的任务不能删除。")
        path = tenant_path(
            Path(settings.BASE_DIR) / "app_runs", instance.tenant_id, instance.execution_no
        )
        if not path.exists():
            path = legacy_tenant_path(
                Path(settings.BASE_DIR) / "app_runs", instance.tenant_id, instance.execution_no
            )
        instance.delete()
        shutil.rmtree(path, ignore_errors=True)

    @action(detail=True, methods=["post"])
    def stop(self, request, pk=None):
        run = self.get_object()
        run.stop_requested = True
        if run.status == AppRun.Status.QUEUED:
            run.status, run.finished_at = AppRun.Status.STOPPED, timezone.now()
        run.save(update_fields=["stop_requested", "status", "finished_at", "updated_at"])
        return Response({"detail": "已发送停止指令。"})

    @action(detail=True, methods=["get"])
    def log(self, request, pk=None):
        return Response({"content": self.get_object().log_content})

    @action(detail=True, methods=["get"], url_path=r"artifact/(?P<artifact_id>[^/.]+)")
    def artifact(self, request, pk=None, artifact_id=None):
        run = self.get_object()
        item = AppArtifact.objects.filter(pk=artifact_id, run=run).first()
        if not item:
            return Response({"detail": "附件不存在。"}, status=status.HTTP_404_NOT_FOUND)
        path = (Path(settings.BASE_DIR) / item.file_path).resolve()
        if not is_managed_storage_path(
            path, "app_runs", tenant=run.tenant_id
        ) or not path.exists():
            return Response({"detail": "附件文件不存在。"}, status=status.HTTP_404_NOT_FOUND)
        return FileResponse(path.open("rb"), as_attachment=False, filename=item.name)
