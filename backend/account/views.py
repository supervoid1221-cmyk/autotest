from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.authtoken.models import Token

from .models import Profile, Tenant, TenantMembership
from .access import is_system_admin
from .tenancy import get_request_tenant, is_tenant_admin, tenants_for_user
from .serializers import (
    LoginSerializer,
    ProfileSerializer,
    ResetPassSerializer,
    UserListSerializer,
    UserManageSerializer,
    TenantSerializer,
    TenantMembershipSerializer,
)
from .permissions import IsPlatformAdmin
from .authentication import platform_token_expires_at


@extend_schema(tags=["Account"])
class ProfileViewSet(viewsets.GenericViewSet):  # 没和model 进行强关联
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=LoginSerializer, responses=ProfileSerializer)
    @action(
        methods=["POST"],
        detail=False,
        permission_classes=[permissions.AllowAny],
        authentication_classes=[],
    )
    def login(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)  # 委托给序列化进行参数校验

        user = serializer.validated_data["user"]
        profile = Profile.objects.get(user=user)

        # 每次输入账号密码都视为一次新的会话激活，换发新令牌并废止旧令牌。
        Token.objects.filter(user=user).delete()
        login_token = Token.objects.create(user=user)

        serializer = ProfileSerializer(profile, context={"login_token": login_token})
        return Response(serializer.data)  # 委托给序列化进行字段和数据生成

    @action(methods=["POST"], detail=False, url_path="renew-session")
    def renew_session(self, request):
        """为正在活跃的已认证会话续期；过期令牌会在进入视图前被认证层拒绝。"""
        token = request.auth
        if not isinstance(token, Token):
            return Response({"detail": "当前会话无法续期。"}, status=status.HTTP_401_UNAUTHORIZED)
        token.created = timezone.now()
        token.save(update_fields=["created"])
        return Response({"token_expires_at": platform_token_expires_at(token).isoformat()})

    @extend_schema(request=ResetPassSerializer, responses={204: None})
    @action(methods=["POST"], detail=False)
    def reset_password(self, request):
        serializer = ResetPassSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)  # 委托给序列化进行参数校验

        user: User = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save()

        return Response({}, status=status.HTTP_204_NO_CONTENT)

    @extend_schema(responses=ProfileSerializer)
    @action(methods=["GET"], detail=False)
    def profile(self, request):
        """查询单个数，返回单个数据"""
        profile, _ = Profile.objects.get_or_create(user=request.user)

        serializer = ProfileSerializer(profile)
        return Response(serializer.data)  # 委托给序列化进行字段和数据生成

    @extend_schema(responses=UserListSerializer)
    @action(methods=["GET"], detail=False)
    def all_user(self, request):
        """查询多个数据，返回多个数据"""
        tenant = get_request_tenant(request)
        user_list = Profile.objects.filter(
            user__is_active=True,
            user__tenant_memberships__tenant=tenant,
            user__tenant_memberships__status=TenantMembership.Status.ACTIVE,
        ).distinct()  # 禁用用户不可再被加入项目
        serializer = UserListSerializer(user_list, many=True)
        return Response(serializer.data)  # 委托给序列化进行字段和数据生成


@extend_schema(tags=["Tenant"])
class TenantViewSet(viewsets.ModelViewSet):
    """租户查询、维护与成员管理。"""

    serializer_class = TenantSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        admin_actions = {"retrieve", "update", "partial_update", "destroy", "members", "member_detail"}
        if is_system_admin(self.request.user) and (
            self.request.query_params.get("include_inactive") == "true" or self.action in admin_actions
        ):
            queryset = Tenant.objects.all()
        else:
            queryset = tenants_for_user(self.request.user)
        return queryset.prefetch_related("memberships").order_by("created_at", "name")

    def perform_create(self, serializer):
        if not is_system_admin(self.request.user):
            raise PermissionDenied("仅平台管理员可以新建租户。")
        tenant = serializer.save()
        from .tenant_runtime import initialize_tenant_storage
        transaction.on_commit(lambda: initialize_tenant_storage(tenant))
        TenantMembership.objects.create(
            tenant=tenant,
            user=self.request.user,
            role=TenantMembership.Role.OWNER,
        )

    def perform_update(self, serializer):
        tenant = self.get_object()
        if not is_tenant_admin(self.request.user, tenant):
            raise PermissionDenied("仅租户管理员可以修改租户。")
        if not is_system_admin(self.request.user) and any(
            field in serializer.validated_data
            for field in (
                "max_regular_concurrent_executions",
                "max_performance_concurrent_executions",
                "storage_quota_bytes",
            )
        ):
            raise PermissionDenied("仅平台管理员可以调整租户执行与存储配额。")
        if tenant.slug == "default":
            if serializer.validated_data.get("slug", tenant.slug) != tenant.slug:
                raise ValidationError({"slug": "默认租户编码不能修改。"})
            if serializer.validated_data.get("status", tenant.status) != Tenant.Status.ACTIVE:
                raise ValidationError({"status": "默认租户不能停用。"})
        serializer.save()

    def perform_destroy(self, instance):
        if not is_system_admin(self.request.user):
            raise PermissionDenied("仅平台管理员可以删除租户。")
        if instance.slug == "default":
            raise ValidationError({"detail": "默认租户不能删除。"})
        if instance.projects.exists():
            raise ValidationError({"detail": "租户下存在项目，请先迁移或删除项目。"})
        instance.delete()

    @action(detail=False, methods=["get"])
    def current(self, request):
        tenant = get_request_tenant(request)
        return Response(self.get_serializer(tenant).data)

    def _managed_tenant(self):
        tenant = self.get_object()
        if not is_tenant_admin(self.request.user, tenant):
            raise PermissionDenied("仅租户管理员可以管理成员。")
        return tenant

    @action(detail=True, methods=["get"], url_path="member-candidates")
    def member_candidates(self, request, pk=None):
        """返回平台启用用户，供租户成员选择器检索。"""
        tenant = self._managed_tenant()
        keyword = str(request.query_params.get("search") or "").strip()[:150]
        users = User.objects.filter(is_active=True).order_by("username", "id")
        if keyword:
            users = users.filter(username__icontains=keyword)
        member_ids = set(tenant.memberships.values_list("user_id", flat=True))
        return Response([
            {
                "id": user.id,
                "username": user.username,
                "is_member": user.id in member_ids,
            }
            for user in users
        ])

    @action(detail=True, methods=["get", "post"], url_path="members")
    def members(self, request, pk=None):
        tenant = self._managed_tenant()
        if request.method == "GET":
            memberships = tenant.memberships.select_related("user").order_by("user__username")
            return Response(TenantMembershipSerializer(memberships, many=True).data)

        user_id = request.data.get("user")
        username = str(request.data.get("username") or "").strip()
        role = str(request.data.get("role") or TenantMembership.Role.MEMBER)
        if role not in TenantMembership.Role.values:
            raise ValidationError({"role": "租户角色不正确。"})
        if user_id not in (None, ""):
            try:
                user = User.objects.filter(pk=user_id, is_active=True).first()
            except (TypeError, ValueError):
                user = None
        else:
            user = User.objects.filter(username=username, is_active=True).first()
        if not user:
            field = "user" if user_id not in (None, "") else "username"
            raise ValidationError({field: "用户不存在或已禁用。"})
        membership, created = TenantMembership.objects.update_or_create(
            tenant=tenant,
            user=user,
            defaults={"role": role, "status": TenantMembership.Status.ACTIVE},
        )
        return Response(
            TenantMembershipSerializer(membership).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"members/(?P<user_id>[^/.]+)",
    )
    def member_detail(self, request, pk=None, user_id=None):
        tenant = self._managed_tenant()
        membership = tenant.memberships.select_related("user").filter(user_id=user_id).first()
        if not membership:
            return Response({"detail": "租户成员不存在。"}, status=status.HTTP_404_NOT_FOUND)

        if request.method == "DELETE":
            if membership.user_id == request.user.id:
                raise ValidationError({"detail": "不能移除当前操作账号。"})
            self._ensure_manager_remains(tenant, membership)
            membership.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = TenantMembershipSerializer(membership, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        target_role = serializer.validated_data.get("role", membership.role)
        target_status = serializer.validated_data.get("status", membership.status)
        if membership.user_id == request.user.id and target_status != TenantMembership.Status.ACTIVE:
            raise ValidationError({"status": "不能停用当前操作账号。"})
        if (
            membership.role in (TenantMembership.Role.OWNER, TenantMembership.Role.ADMIN)
            and (
                target_role not in (TenantMembership.Role.OWNER, TenantMembership.Role.ADMIN)
                or target_status != TenantMembership.Status.ACTIVE
            )
        ):
            self._ensure_manager_remains(tenant, membership)
        membership = serializer.save()
        return Response(TenantMembershipSerializer(membership).data)

    @staticmethod
    def _ensure_manager_remains(tenant, membership):
        if membership.role not in (TenantMembership.Role.OWNER, TenantMembership.Role.ADMIN):
            return
        other_managers = tenant.memberships.filter(
            status=TenantMembership.Status.ACTIVE,
            role__in=(TenantMembership.Role.OWNER, TenantMembership.Role.ADMIN),
        ).exclude(pk=membership.pk)
        if not other_managers.exists():
            raise ValidationError({"detail": "租户至少需要保留一名正常状态的所有者或管理员。"})


@extend_schema(tags=["Account"])
class UserManageViewSet(viewsets.ModelViewSet):
    """平台用户列表对登录用户开放；管理权限按请求动作区分。"""
    queryset = User.objects.select_related("profile").all().order_by("-id")
    serializer_class = UserManageSerializer

    def get_queryset(self):
        if is_system_admin(self.request.user):
            return self.queryset
        tenant = get_request_tenant(self.request)
        return self.queryset.filter(
            tenant_memberships__tenant=tenant,
            tenant_memberships__status=TenantMembership.Status.ACTIVE,
        ).distinct()

    def get_permissions(self):
        if self.action in ("list", "create", "reset_password"):
            return [permissions.IsAuthenticated()]
        return [IsPlatformAdmin()]

    def perform_create(self, serializer):
        # 普通用户可创建测试账号，但不能创建平台管理员。
        tenant = get_request_tenant(self.request)
        if not is_system_admin(self.request.user):
            user = serializer.save(is_staff=False)
        else:
            user = serializer.save()
        TenantMembership.objects.get_or_create(
            tenant=tenant,
            user=user,
            defaults={"role": TenantMembership.Role.MEMBER},
        )

    def perform_destroy(self, instance):
        if instance.pk == self.request.user.pk:
            raise serializers.ValidationError({"detail": "不能删除当前登录账号。"})
        instance.delete()

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        password = str(request.data.get("password") or "")
        if len(password) < 6:
            return Response({"password": "新密码至少 6 位。"}, status=status.HTTP_400_BAD_REQUEST)
        user = self.get_object()
        if not is_system_admin(request.user) and user.pk != request.user.pk:
            return Response({"detail": "普通用户只能重置自己的密码。"}, status=status.HTTP_403_FORBIDDEN)
        user.set_password(password)
        user.save(update_fields=["password"])
        return Response({"detail": "密码已重置。"})
