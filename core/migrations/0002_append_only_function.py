from django.db import migrations

CREATE = """
CREATE FUNCTION storeapp_forbid_change() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Rows in % are append-only history and cannot be changed or deleted', TG_TABLE_NAME
        USING ERRCODE = 'integrity_constraint_violation';
END;
$$ LANGUAGE plpgsql;
"""


class Migration(migrations.Migration):
    """Shared trigger function used to keep history tables append-only."""

    dependencies = [("core", "0001_initial")]

    operations = [migrations.RunSQL(CREATE, "DROP FUNCTION storeapp_forbid_change();")]
