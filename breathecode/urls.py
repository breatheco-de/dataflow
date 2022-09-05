"""breathecode URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
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
import os
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView
from django.conf.urls.static import static
from django.conf import settings

apps = [
    ('v1/auth/', 'breathecode.authenticate.urls', 'auth'),
    # ('v1/pipline/', 'breathecode.pipeline.urls', 'admissions'),
]

urlpatterns_apps = [path(url, include(urlconf, namespace=namespace))
                    for url, urlconf, namespace in apps]

urlpatterns_django = [
    path('admin/', admin.site.urls),
    path('explorer/', include('explorer.urls')),
]

urlpatterns_static = static(
    settings.STATIC_URL, document_root=settings.STATIC_ROOT)

urlpatterns = (urlpatterns_apps + urlpatterns_django +
               urlpatterns_static)
