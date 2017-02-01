from django.conf.urls import url
from rest_framework.urlpatterns import format_suffix_patterns

from . import views
# from rest_framework.authtoken import views as authviews


urlpatterns = [
    url(r'^items/$', views.ItemView.as_view()),
    url(r'^items/(?P<pk>[0-9]+)/$', views.ItemView.as_view()),

    url(r'^requests/?$', views.RequestView.as_view()),
    url(r'^requests/(?P<status>[a-zA-Z]+)/?$', views.RequestView.as_view()),

    url(r'^cart/?$', views.CartView.as_view()),
    url(r'^cart/(?P<pk>[0-9]+)/$', views.CartView.as_view()),

    url(r'^tags/$', views.TagListView.as_view()),
    url(r'^currentuser/$', views.CurrentUserView.as_view())
]

urlpatterns = format_suffix_patterns(urlpatterns)
