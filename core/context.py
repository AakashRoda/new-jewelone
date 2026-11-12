from django.conf import settings

NAV_BY_URL_PREFIX = [
    ("stock", "stock"),
    ("inward", "inwards"),
    ("invoice", "invoices"),
    ("master", "masters"),
    ("audit", "history"),
    ("access", "access"),
    ("role", "access"),
    ("user", "access"),
]


def app_context(request):
    user = getattr(request, "user", None)
    capabilities = set()
    if user is not None and user.is_authenticated:
        capabilities = user.capability_keys()
    url_name = getattr(getattr(request, "resolver_match", None), "url_name", "") or ""
    nav = next((section for prefix, section in NAV_BY_URL_PREFIX if url_name.startswith(prefix)), "")
    return {"DEMO_MODE": settings.DEMO_MODE, "caps": capabilities, "nav": nav}
