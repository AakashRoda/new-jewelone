# Store App

A jewellery store application, built inventory first. This is the owner's independent AI-assisted build. It is separate from the consultancy's implementation and follows `docs/spec/store-app-build-spec-v0.1.md`.

**Status: stages B0 and B1 (project foundation and stock receiving).** This is a local demo with synthetic data. It is not a production release and must not be used with real stock yet.

## What works today

- **Masters**: metals, purities, items, varieties, units, HSN references, making-charge rule names, other-charge definitions, suppliers, karigars and locations.
- **Inwards (physical receipts)**: enter what actually arrived from a supplier purchase, a supplier approval memo or a karigar, with the source's declared quantities next to the actual ones and the difference shown.
- **Receive into stock, once**: confirming an inward adds its quantities to physical stock exactly once, even on a double click or a retry.
- **Weight-only stock**: goes straight into the item's weight balance, with no tags and no piece count, and its inward locks at that moment.
- **Inward locks**: before the lock, an edit needs the edit permission and a written reason. After the lock there is no edit and no unlock.
- **Supplier invoices (book records)**: enter what the supplier's invoice states and link its lines to receipts. This never changes physical stock.
- **Permissions**: every action is checked on the server against the permissions in the user's roles. Refused attempts are recorded.
- **History**: who did what, when, why, with old and new values. History and the stock ledger cannot be edited or deleted, even directly in the database.

What is not built yet, and what is waiting on an owner decision, is listed in `docs/register.md`.

## Run it

### With Docker (simplest)

```
docker compose up --build
```

Open http://localhost:8000. Demo data is loaded automatically.

### Without Docker

Needs Python 3.12 or newer and PostgreSQL 16.

```
# 1. A database (once)
createuser --createdb --pwprompt storeapp      # password: storeapp
createdb --owner storeapp storeapp

# 2. The app
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Open http://127.0.0.1:8000. Settings come from environment variables; see `.env.example`.

### Demo logins

All use the password `demo-pass-1234`. These users and their roles are demo configuration, not agreed production grants.

| Login | Can do |
| - | - |
| `demo_owner` | Everything |
| `demo_receiver` | Enter and edit inwards; receive karigar inwards |
| `demo_verifier` | Also open supplier parcels and receive them into stock |
| `demo_accounts` | Enter supplier invoices and link them to receipts |
| `demo_viewer` | View only |

### A five-minute walkthrough

1. Sign in as `demo_receiver`. Open **Inwards** and the draft from Synthetic Karigar K. Note the declared 50.000 g against the actual 49.950 g.
2. Edit it. Try saving without a reason, then with one. The reason and the old and new values appear in its history.
3. Create **New inward: weight-only stock** for Gold Balls from a supplier. As the receiver you can save the draft but cannot receive it, because a supplier parcel needs `parcel.open`.
4. Sign in as `demo_verifier` and receive it. It locks immediately and the Stock screen shows the new weight.
5. Sign in as `demo_accounts`. Open **Supplier invoices**, enter an invoice for that supplier and link its line to the receipt. Stock does not change.
6. Sign in as `demo_owner` and open **History** to see every step, including the refused attempts.

## Tests

```
python -m pytest
```

Tests need the PostgreSQL role to be allowed to create databases (the test database is created and dropped each run). Acceptance scenarios from the spec live in `tests/acceptance/` and are named by their T reference.

```
./scripts/check_persistence.sh
```

This shows that the same data survives an application restart and a database dump and reload.

## Where things are

| Path | Contents |
| - | - |
| `docs/spec/` | The build specification this project follows |
| `docs/register.md` | Requirements (C), open decisions (O) and acceptance tests (T) with their current status |
| `docs/decisions/` | Engineering decisions, starting with the stack choice |
| `docs/technical-assumptions.md` | Technical assumptions, kept apart from business requirements |
| `docs/changelog.md` | Change log for business decisions |
| `docs/handover/` | What each increment delivered |
| `inventory/` | Inwards, the physical stock ledger and their commands |
| `purchasing/` | Supplier invoice book records and matching |
| `masters/`, `accounts/`, `audit/` | Masters, users/roles/permissions, history |
| `core/` | Exact numbers, once-only command handling, shared helpers |
| `demo/` | Synthetic fixtures used by both the demo and the tests |
