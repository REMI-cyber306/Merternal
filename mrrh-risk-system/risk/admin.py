from django.contrib import admin

from .models import Assessment


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ("study_id", "predicted_category", "user", "model_version", "created_at")
    list_filter = ("predicted_category", "model_version")
    search_fields = ("study_id", "user__username")
    readonly_fields = [f.name for f in Assessment._meta.fields]

    def has_add_permission(self, request):
        return False  # assessments are created only through the validated form

    def has_change_permission(self, request, obj=None):
        return False  # keep the audit trail intact
