from django.conf import settings


def site(request):
    return {"DEMO_MODE": settings.DEMO_MODE}
