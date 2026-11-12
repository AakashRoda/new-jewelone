from django.contrib.auth.decorators import login_not_required
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import JsonResponse


@login_not_required
def healthz(request):
    """Smoke check: the app is up, the database answers and migrations are applied."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    executor = MigrationExecutor(connection)
    pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
    ok = not pending
    return JsonResponse(
        {"status": "ok" if ok else "migrations_pending", "database": "ok", "pending_migrations": len(pending)},
        status=200 if ok else 503,
    )
