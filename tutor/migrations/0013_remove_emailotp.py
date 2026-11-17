from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("tutor", "0012_emailotp_delivery_tracking"),
    ]

    operations = [
        migrations.DeleteModel(
            name="EmailOTP",
        ),
    ]
