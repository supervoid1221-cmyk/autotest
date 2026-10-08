from django.contrib import admin

from . import models


@admin.register(models.Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "pm")
    list_filter = ("tenant",)
    search_fields = ("name", "tenant__name")


@admin.register(models.ProjectVariable)
class ProjectVariableAdmin(admin.ModelAdmin):
    list_display = ("project", "name", "value")
    list_filter = ("project",)
    search_fields = ("project__name", "name")
