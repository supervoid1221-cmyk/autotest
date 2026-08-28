from django.contrib import admin

from . import models


@admin.register(models.Suite)
class SuiteAdmin(admin.ModelAdmin):
    ...


@admin.register(models.RunResult)
class RunResultAdmin(admin.ModelAdmin):
    ...
