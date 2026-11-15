from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tutor", "0011_emailotp"),
    ]

    operations = [
        migrations.AddField(
            model_name="emailotp",
            name="delivery_status",
            field=models.CharField(
                choices=[
                    ("queued", "Queued"),
                    ("sending", "Sending"),
                    ("accepted", "Accepted by provider"),
                    ("failed", "Failed"),
                ],
                default="accepted",
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="emailotp",
            name="delivery_attempts",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="emailotp",
            name="delivery_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="emailotp",
            name="delivery_enqueued_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="emailotp",
            name="delivery_completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="emailotp",
            name="delivery_error",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddIndex(
            model_name="emailotp",
            index=models.Index(
                fields=["delivery_status", "created_at"],
                name="tutor_email_deliver_25a690_idx",
            ),
        ),
    ]
