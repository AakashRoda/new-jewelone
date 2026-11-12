from django.core.paginator import Paginator
from django.shortcuts import render

from core.web import capability_required

from .models import AuditEvent


@capability_required("audit.view")
def audit_list(request):
    events = AuditEvent.objects.select_related("actor")
    action = request.GET.get("action", "").strip()
    outcome = request.GET.get("outcome", "").strip()
    query = request.GET.get("q", "").strip()
    if action:
        events = events.filter(action=action)
    if outcome in dict(AuditEvent.OUTCOMES):
        events = events.filter(outcome=outcome)
    if query:
        events = events.filter(target_label__icontains=query)
    page = Paginator(events, 50).get_page(request.GET.get("page"))
    actions = AuditEvent.objects.order_by("action").values_list("action", flat=True).distinct()
    return render(
        request,
        "audit/list.html",
        {"page": page, "actions": actions, "action": action, "outcome": outcome, "q": query},
    )
