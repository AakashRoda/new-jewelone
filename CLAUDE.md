# Instructions for coding agents

Read `docs/spec/store-app-build-spec-v0.1.md` before changing code, then `docs/register.md` for the current status of every requirement (C), open decision (O) and acceptance test (T).

## Hard rules from the spec

- Physical stock and book records are separate. An inward adds stock once. Entering or matching a supplier invoice never adds stock.
- Do not add purchase metal-rate tracking, per-piece metal acquisition cost or metal-cost margins.
- Do not add an import of old tags. All stock and tags are created in this application.
- Do not add an unlock button, an administrator rewrite, an automatic loss write-off or any edit path around the inward lock.
- Do not turn an engineering choice into a claim that the owner confirmed a business rule. Open decisions stay open until the owner decides; leave the affected stock-changing action unavailable.
- Use only synthetic stock, suppliers and customers.

## How this codebase works

- Business rules live in service functions (`inventory/services.py`, `purchasing/services.py`), never only in views or templates. Views call services.
- Every stock-changing or book-changing command: checks a capability with `accounts.permissions.require`, runs through `core.idempotency.run_once` with a retry key, locks the rows it depends on with `select_for_update`, and writes an audit event.
- Weights, carats, percentages and money are `Decimal`. Never use floats. Do not round silently.
- `inventory.StockMovement` and `audit.AuditEvent` are append-only (database triggers). Corrections are new rows.
- Stage B2's CreateLot must call `inventory.services.apply_first_lot_lock` inside its transaction with the inward row locked.
- Django's admin site is deliberately not installed. Django's superuser flag grants no business capability.
- Screens use store-facing words (inward, lot, tag, weight-only stock), not ledger or database terms.

## Working here

- Run `python -m pytest` (needs PostgreSQL; see README). Add tests named by T reference under `tests/acceptance/`.
- Demo fixtures in `demo/fixtures.py` are shared by the demo and the tests. Extend them rather than writing parallel ones.
- After a model change run `python manage.py makemigrations` and commit the migration. CI fails if one is missing.
- At the end of each stage update `docs/register.md`, add a handover note under `docs/handover/`, and record technical assumptions in `docs/technical-assumptions.md`. Record owner decisions in `docs/changelog.md`.
