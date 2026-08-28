from django.contrib import admin

from . import models


@admin.register(models.Element)
class ElementAdmin(admin.ModelAdmin):
    ...

