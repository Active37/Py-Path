import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def assign_public_ids(apps, schema_editor):
    LearnerProfile = apps.get_model("tutor", "LearnerProfile")
    for profile in LearnerProfile.objects.filter(public_id__isnull=True).iterator():
        profile.public_id = uuid.uuid4()
        profile.save(update_fields=["public_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("tutor", "0003_learnerprofile_dailyactivity_lessonbookmark_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="learnerprofile",
            name="daily_reminders",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="learnerprofile",
            name="public_profile",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="learnerprofile",
            name="public_id",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.CreateModel(
            name="StudyPlanItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("planned_for", models.DateField()),
                ("title", models.CharField(max_length=120)),
                ("target_minutes", models.PositiveSmallIntegerField(default=15)),
                ("is_completed", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="study_plan_items", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["planned_for", "created_at"],
                "constraints": [
                    models.UniqueConstraint(fields=("user", "planned_for", "title"), name="unique_user_study_plan_title"),
                ],
            },
        ),
        migrations.CreateModel(
            name="ProjectProgress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("project_slug", models.SlugField(max_length=80)),
                ("completed_milestones", models.JSONField(default=list)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="project_progress", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("user", "project_slug"), name="unique_user_project_progress"),
                ],
            },
        ),
        migrations.CreateModel(
            name="EarnedAchievement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("achievement_code", models.SlugField(max_length=80)),
                ("earned_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="earned_achievements", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["earned_at"],
                "constraints": [
                    models.UniqueConstraint(fields=("user", "achievement_code"), name="unique_user_achievement"),
                ],
            },
        ),
        migrations.RunPython(assign_public_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="learnerprofile",
            name="public_id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
