"""Capability keys checked by the server before each action.

Capabilities are granted to roles and roles to users, all as data. No job
title, creator relationship or superuser flag grants a capability implicitly
(C08, C11). The keys are implementation names; exact production grants are an
open decision (O12).

Only capabilities that an existing command checks are listed. Later stages add
their own (lot.create, tag.create, supplier_return.dispatch, custody.issue,
verification.record, correction.approve, loss.approve, ...).
"""

CAPABILITIES: dict[str, str] = {
    "inward.create": "Enter a new inward and confirm a karigar inward",
    "inward.edit": "Edit an inward before its lock, giving a reason",
    "parcel.open": "Open a supplier parcel, verify its contents and confirm the receipt",
    "purchase_invoice.record": "Enter a supplier purchase invoice (book record)",
    "purchase_invoice.match": "Link a supplier invoice line to an existing receipt, or remove the link",
    "masters.manage": "Create and change master records",
    "access.manage": "Change role capabilities and user role assignments",
    "audit.view": "View the audit history",
}
