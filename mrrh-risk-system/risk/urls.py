from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("assess/", views.assess_new, name="assess_new"),
    path("assessment/<int:pk>/", views.assessment_detail, name="assessment_detail"),
    path("history/", views.history, name="history"),
    path("history/export.csv", views.export_csv, name="export_csv"),
    path("about/", views.about, name="about"),
    path("healthz", views.healthz, name="healthz"),
    path("accounts/login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
]
