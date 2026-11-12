# Engineering decision 0001: application stack

- **Date:** 12 November 2026
- **Status:** Accepted for the build. Revisit before production (O12).
- **Kind:** Engineering decision. This is not a business rule and the owner has not been asked to confirm it.

## Context

The specification selects no framework, database, deployment platform, offline strategy or hardware vendor. No repository existed. The spec asks for one application backend with a transactional relational data store and clear domain services, exact decimal arithmetic, once-only stock commands, server-side permission checks and usable screens.

## Decision

| Concern | Choice |
| - | - |
| Language and framework | Python 3.13, Django 5.2 (long-term support release) |
| Database | PostgreSQL 16 |
| Screens | Server-rendered HTML with a small amount of plain JavaScript; no front-end build step |
| Tests | pytest with pytest-django, run against a real PostgreSQL database |
| Local run | Docker Compose, or Python plus a local PostgreSQL |
| Web server | gunicorn, static files through WhiteNoise |

## Why

- **Exact numbers.** Python's `Decimal` and PostgreSQL's `NUMERIC` keep milligram weights and the 1 ct = 0.200 g conversion exact from the form to the database. Binary floats are refused at the boundary.
- **Concurrency that can be trusted.** PostgreSQL row locks, unique constraints, check constraints and triggers enforce the invariants inside the database, not only in screens. Two operators acting on the same record are serialised by the database.
- **One backend, little machinery.** Django supplies migrations, sessions, forms and transactions in one well-known framework, so the code written here is mostly business rules.
- **Consistent structure across many build sessions.** Django's conventions keep the project uniform as more modules are added by different sessions.
- **Room for the later modules.** The business commands live in service functions (`inventory/services.py`, `purchasing/services.py`), separate from the screens. The mobile app, e-commerce integration and device adapters can call the same commands through an API later without rewriting the rules.

## Deliberate departures from Django defaults

- **Django's admin site is not installed.** It would allow direct edits and deletes of receipts and history outside the audited commands, which C11 forbids.
- **Django's superuser flag and built-in permissions are not used for business actions.** Capabilities are separate data (`accounts`), so no flag grants anything implicitly.
- **History tables are append-only in the database.** Triggers refuse UPDATE and DELETE on the audit log and the stock ledger.

## Alternatives considered

- **TypeScript (Node) with a React front end.** One language across web and a future mobile app, but more hand-built plumbing, and JavaScript numbers are floats by default, which is a standing risk for weights. Rejected for the inventory core.
- **SQLite.** Simplest to run, but it would weaken the concurrency guarantees the spec asks to be exercised. Rejected.

## Consequences

- PostgreSQL is required to run the app and the tests. Docker Compose hides this for the demo.
- Screens are plain server-rendered pages. A richer tagging screen (stage B2) may add targeted JavaScript; that will be recorded as its own decision if it changes this one.
- Offline operation is not addressed. It remains part of O12.
