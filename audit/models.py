from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    """Append-only record of who did what, to which record, and why.

    A database trigger refuses UPDATE and DELETE on this table.
    """

    SUCCEEDED = "succeeded"
    DENIED = "denied"
    OUTCOMES = [(SUCCEEDED, "Succeeded"), (DENIED, "Denied (no permission)")]

    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="audit_events"
    )
    action = models.CharField(max_length=64, db_index=True)
    outcome = models.CharField(max_length=16, choices=OUTCOMES, default=SUCCEEDED)
    capability = models.CharField(max_length=64, blank=True)
    target_type = models.CharField(max_length=64, blank=True)
    target_id = models.BigIntegerField(null=True)
    target_label = models.CharField(max_length=120, blank=True)
    reason = models.TextField(blank=True)
    payload = models.JSONField(default=dict)
    retry_key = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-occurred_at", "-id"]
        indexes = [models.Index(fields=["target_type", "target_id"])]

    def __str__(self):
        return f"{self.action} {self.target_label} ({self.outcome})"

    ACTION_LABELS = {
        "inward.create": "Inward entered as a draft",
        "inward.edit": "Inward edited",
        "inward.confirm": "Received into stock",
        "inward.lock": "Inward locked",
        "purchase_invoice.record": "Supplier invoice entered",
        "purchase_invoice.match": "Invoice line linked to a receipt",
        "purchase_invoice.unmatch": "Invoice link removed",
        "master.create": "Master record added",
        "master.update": "Master record changed",
        "role.create": "Role added",
        "role.update": "Role changed",
        "user.create": "User added",
        "user.update": "User changed",
        "user.grant_full_access": "Full access granted from the server",
    }

    @property
    def label(self) -> str:
        return self.ACTION_LABELS.get(self.action, self.action)

    @property
    def changes(self) -> list[tuple[str, str, str]]:
        """Readable (what, old value, new value) rows from a before/after payload."""
        before, after = self.payload.get("before"), self.payload.get("after")
        if not isinstance(before, dict) or not isinstance(after, dict):
            return []

        def show(value):
            if value is None or value == "":
                return "—"
            if isinstance(value, list):
                return ", ".join(str(v) for v in value) or "—"
            if isinstance(value, bool):
                return "yes" if value else "no"
            return str(value)

        def label(key):
            return key.replace("_", " ")

        rows = []
        for key in dict.fromkeys([*before, *after]):
            if key == "lines":
                continue
            if before.get(key) != after.get(key):
                rows.append((label(key), show(before.get(key)), show(after.get(key))))
        old_lines = {line.get("line_no"): line for line in before.get("lines") or []}
        new_lines = {line.get("line_no"): line for line in after.get("lines") or []}
        for line_no in sorted(set(old_lines) | set(new_lines)):
            old, new = old_lines.get(line_no), new_lines.get(line_no)
            if old is None:
                rows.append((f"line {line_no}", "—", "added"))
            elif new is None:
                rows.append((f"line {line_no}", "present", "removed"))
            else:
                for key in new:
                    if key != "line_no" and old.get(key) != new.get(key):
                        rows.append((f"line {line_no} {label(key)}", show(old.get(key)), show(new.get(key))))
        return rows
