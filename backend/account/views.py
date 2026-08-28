from django.contrib.auth.models import User
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Profile
from .access import is_system_admin
from .serializers import (
    LoginSerializer,
    ProfileSerializer,
    ResetPassSerializer,
    UserListSerializer,
    UserManageSerializer,
)
from .permissions import IsPlatformAdmin


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

        profile = Profile.objects.get(user=serializer.validated_data["user"])

        serializer = ProfileSerializer(profile)
        return Response(serializer.data)  # 委托给序列化进行字段和数据生成

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
        user_list = Profile.objects.filter(user__is_active=True)  # 禁用用户不可再被加入项目
        serializer = UserListSerializer(user_list, many=True)
        return Response(serializer.data)  # 委托给序列化进行字段和数据生成


@extend_schema(tags=["Account"])
class UserManageViewSet(viewsets.ModelViewSet):
    """平台用户列表对登录用户开放；管理权限按请求动作区分。"""
    queryset = User.objects.select_related("profile").all().order_by("-id")
    serializer_class = UserManageSerializer
    def get_permissions(self):
        if self.action in ("list", "create", "reset_password"):
            return [permissions.IsAuthenticated()]
        return [IsPlatformAdmin()]

    def perform_create(self, serializer):
        # 普通用户可创建测试账号，但不能创建平台管理员。
        if not is_system_admin(self.request.user):
            serializer.save(is_staff=False)
        else:
            serializer.save()

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
