def cleanup_expired_inspection_sessions():
    # 延迟导入避免 Django 加载 URL 时产生循环依赖。
    from .views import _cleanup_expired_inspections

    return {"closed": _cleanup_expired_inspections()}
