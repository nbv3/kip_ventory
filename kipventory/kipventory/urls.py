"""kipventory URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url, include
from django.contrib import admin
from django.contrib.auth import views as auth_views

from . import views

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    # URLs for our REST API endpoints
    url(r'^api/', include('api.urls')),
    # Django built in Auth views to handle user login/logout
    url(r'^login/?', auth_views.login, {'template_name': 'kipventory/login.html'}, name='login'),
    url(r'^logout/?', auth_views.logout, name='logout'),

    # Main view for our Single Page App (React, client side)
    # url(r'^app/cart/?', views.cart, name='cart'),
    url(r'^app/?', views.app, name='app'),
    # Landing page (no auth necessary)
    url(r'$', views.landing, name='landing'),
]
