import csv
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from . import predictor
from .features import CLASSES, FEATURE_ORDER, SYMPTOMS
from .forms import AssessmentForm
from .models import Assessment

log = logging.getLogger(__name__)


def _visible(user):
    """Healthcare workers see their own assessments; supervisors (staff) see all."""
    qs = Assessment.objects.select_related("user")
    return qs if user.is_staff else qs.filter(user=user)


def _counts(qs):
    raw = dict(qs.values_list("predicted_category").annotate(n=Count("id")))
    return {c: raw.get(c, 0) for c in CLASSES}


@login_required
def home(request):
    qs = _visible(request.user)
    counts = _counts(qs)
    return render(request, "risk/home.html", {"counts": counts, "total": sum(counts.values()),
                                              "recent": qs[:5], "scope": "all users" if request.user.is_staff else "your"})


@login_required
@require_http_methods(["GET", "POST"])
def assess_new(request):
    form = AssessmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.user = request.user
        values = {f: getattr(obj, f) for f in FEATURE_ORDER}
        try:
            category, probs, version = predictor.predict(values)
        except predictor.ModelUnavailable:
            log.exception("model unavailable")  # message only; inputs are never logged
            messages.error(request, "The prediction model is not available right now. Please tell the administrator.")
            return render(request, "risk/assess_form.html", {"form": form}, status=503)
        obj.predicted_category, obj.class_probabilities, obj.model_version = category, probs, version
        obj.save()
        return redirect("assessment_detail", pk=obj.pk)
    return render(request, "risk/assess_form.html", {"form": form})


@login_required
def assessment_detail(request, pk):
    obj = get_object_or_404(_visible(request.user), pk=pk)
    symptoms = [label for key, label in SYMPTOMS if getattr(obj, key)]
    return render(request, "risk/assessment_detail.html", {"a": obj, "symptoms": symptoms})


@login_required
def history(request):
    qs = _visible(request.user)
    cat = request.GET.get("category", "")
    if cat in CLASSES:
        qs = qs.filter(predicted_category=cat)
    page = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(request, "risk/history.html", {"page": page, "category": cat, "classes": CLASSES})


@user_passes_test(lambda u: u.is_active and u.is_staff)
def export_csv(request):
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="assessments.csv"'
    w = csv.writer(resp)
    w.writerow(["study_code", "created_at", "entered_by", "predicted_category", "model_version"] + FEATURE_ORDER)
    for a in Assessment.objects.select_related("user").iterator():
        w.writerow([a.study_id, a.created_at.isoformat(timespec="seconds"), a.user.get_username(),
                    a.predicted_category, a.model_version] + [int(v) if isinstance(v, bool) else v for v in (getattr(a, f) for f in FEATURE_ORDER)])
    return resp


def about(request):
    m = predictor.metrics()
    rows = list(zip(m["test"]["confusion_matrix"]["labels"], m["test"]["confusion_matrix"]["matrix"])) if m else []
    return render(request, "risk/about.html", {"m": m, "matrix_rows": rows})


def healthz(request):
    try:
        version = predictor.model_version()
        ok = True
    except predictor.ModelUnavailable as exc:
        version, ok = str(exc), False
    return JsonResponse({"status": "ok" if ok else "model-unavailable", "model": version}, status=200 if ok else 503)
