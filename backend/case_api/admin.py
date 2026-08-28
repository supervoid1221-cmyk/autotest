from django.contrib import admin

from . import models


@admin.register(models.Endpoint)
class EndpointAdmin(admin.ModelAdmin):
    ...

