from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "MRRH maternal risk prototype: administration"
admin.site.site_title = "MRRH risk admin"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("risk.urls")),
]
