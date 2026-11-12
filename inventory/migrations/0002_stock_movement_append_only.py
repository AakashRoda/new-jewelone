from django.db import migrations


class Migration(migrations.Migration):
    """The physical stock ledger can be added to but never rewritten."""

    dependencies = [("inventory", "0001_initial"), ("core", "0002_append_only_function")]

    operations = [
        migrations.RunSQL(
            "CREATE TRIGGER stock_movement_append_only BEFORE UPDATE OR DELETE ON inventory_stockmovement "
            "FOR EACH ROW EXECUTE FUNCTION storeapp_forbid_change();",
            "DROP TRIGGER stock_movement_append_only ON inventory_stockmovement;",
        )
    ]
