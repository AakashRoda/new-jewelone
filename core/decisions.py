"""Open business decisions that currently hold back something on a screen.

The full register lives in docs/register.md. This short list is what the
Settings screen shows so that staff can see why an action is unavailable.
"""

GATED_BY_OPEN_DECISIONS = [
    ("O01", "Corrections to a locked inward", "Locked inwards can be viewed but not corrected. No unlock exists."),
    ("O01", "Mixed inwards", "One inward holds either tagged pieces or weight-only stock, not both."),
    ("O02", "Weight tolerances", "Tolerances are named demo settings and are not applied to any posting."),
    ("O04", "Metal, category and purity relationships", "Masters are independent lists until the relationships are agreed."),
    ("O06", "Store locations and custody", "Locations are demo records. Handover and custody screens are not built yet."),
    ("O11", "Purchase and karigar details", "Invoices are simple book records linked to receipts. No settlement or GST treatment."),
    ("O12", "Production operation and permission grants", "Roles are demo configuration. This is a local demo, not a production release."),
]
