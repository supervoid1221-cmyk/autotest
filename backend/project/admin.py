from django.contrib import admin

from . import models


@admin.register(models.Project)
class ProjectAdmin(admin.ModelAdmin):
    ...


@admin.register(models.ProjectVariable)
class ProjectVariableAdmin(admin.ModelAdmin):
    list_display = ("project", "name", "value")
    list_filter = ("project",)
    search_fields = ("project__name", "name")
