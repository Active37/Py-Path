from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from tutor import views


urlpatterns = [
    path("admin/", admin.site.urls),
    path("service-worker.js", views.service_worker, name="service_worker"),
    path("", views.home, name="home"),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/signup/", views.signup, name="signup"),
    path("learn/", include("tutor.urls")),
]
