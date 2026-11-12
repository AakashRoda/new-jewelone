from django.db import migrations


class Migration(migrations.Migration):
    """Audit events can be added but never changed or deleted."""

    dependencies = [("audit", "0001_initial"), ("core", "0002_append_only_function")]

    operations = [
        migrations.RunSQL(
            "CREATE TRIGGER audit_event_append_only BEFORE UPDATE OR DELETE ON audit_auditevent "
            "FOR EACH ROW EXECUTE FUNCTION storeapp_forbid_change();",
            "DROP TRIGGER audit_event_append_only ON audit_auditevent;",
        )
    ]
