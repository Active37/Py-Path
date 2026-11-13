from django.db import transaction
from django.core.management.base import BaseCommand

from tutor.catalog import seed_courses
from tutor.models import Course


class Command(BaseCommand):
    help = "Create or update the starter course catalog and lessons."

    def add_arguments(self, parser):
        parser.add_argument(
            "--if-empty",
            action="store_true",
            help="Seed only when the database has no courses, without overwriting existing content.",
        )

    def handle(self, *args, **options):
        if options["if_empty"]:
            with transaction.atomic():
                if Course.objects.exists():
                    self.stdout.write(
                        "Course catalog already exists; starter content was left unchanged."
                    )
                    return
                self._seed()
            return
        self._seed()

    def _seed(self):
        (
            course_count,
            lesson_count,
            question_count,
            assignment_count,
            prompt_count,
            plan_count,
        ) = seed_courses()
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {course_count} courses, {lesson_count} lessons, "
                f"{question_count} assessment questions, {assignment_count} assignments, "
                f"{prompt_count} career prompts, and {plan_count} subscription plans."
            )
        )
