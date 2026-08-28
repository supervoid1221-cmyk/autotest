"""
URL configuration for Tesla project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path("admin_by_127_0_0_1/", admin.site.urls),
    path("api/account/", include("account.urls")),
    path("api/system/", include("system.urls")),
    path("api/project/", include("project.urls")),
    path("api/case_api/", include("case_api.urls")),
    path("api/case_ui/", include("case_ui.urls")),
    path("api/suite/", include("suite.urls")),
    path("api/ai/", include("ai_assistant.urls")),
    path("api/template/", include("execution_template.urls")),
    # OpenAPI
    path("api/schema/openapi.json", SpectacularAPIView.as_view(), name="schema"),
    # 在线文档
    path(
        "api/schema/swagger/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/schema/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]
