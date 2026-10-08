from django.contrib import admin

from .models import PerformanceEndpointMetric, PerformanceMetricBucket, PerformanceNotificationDelivery, PerformanceRun, PerformanceScenario

admin.site.register(PerformanceScenario)
admin.site.register(PerformanceRun)
admin.site.register(PerformanceMetricBucket)
admin.site.register(PerformanceEndpointMetric)
admin.site.register(PerformanceNotificationDelivery)
