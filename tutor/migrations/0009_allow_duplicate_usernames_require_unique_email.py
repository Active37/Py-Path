from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("tutor", "0008_rename_sqlite_lesson_to_postgresql"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE auth_user DROP CONSTRAINT auth_user_username_key",
            reverse_sql=(
                "ALTER TABLE auth_user ADD CONSTRAINT auth_user_username_key "
                "UNIQUE (username)"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "CREATE UNIQUE INDEX auth_user_email_ci_unique "
                "ON auth_user (LOWER(email)) WHERE email <> ''"
            ),
            reverse_sql="DROP INDEX auth_user_email_ci_unique",
        ),
    ]
