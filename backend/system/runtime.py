"""运行期平台配置读取。"""

from django.conf import settings
from django.db import DatabaseError


def configured_max_worker_count():
    """返回当前平台 Worker 上限，数据库不可用时回退到启动配置。"""
    fallback = max(1, int(settings.Q_CLUSTER.get("workers", 2)))
    try:
        from .models import SystemConfiguration

        configured = SystemConfiguration.objects.filter(pk=1).values_list(
            "max_worker_count", flat=True,
        ).first()
    except DatabaseError:
        return fallback
    return max(1, min(64, int(configured or fallback)))


def configured_max_performance_worker_count():
    """返回性能测试可并发运行的 k6 Worker 数。"""
    try:
        from .models import SystemConfiguration

        configured = SystemConfiguration.objects.filter(pk=1).values_list(
            "max_performance_worker_count", flat=True,
        ).first()
    except DatabaseError:
        return 1
    return max(1, min(32, int(configured or 1)))
