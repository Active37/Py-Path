from datetime import timedelta

from django.db.models import F
from django.utils import timezone

from .models import DailyActivity, EarnedAchievement, LessonProgress, ProjectProgress, QuizAttempt
from .projects import get_project


ACHIEVEMENTS = {
    "first-steps": {
        "title": "First steps",
        "description": "Complete your first lesson.",
        "icon": "✦",
    },
    "five-lessons": {
        "title": "Finding your flow",
        "description": "Complete five lessons.",
        "icon": "↗",
    },
    "ten-lessons": {
        "title": "Building momentum",
        "description": "Complete ten lessons.",
        "icon": "⚡",
    },
    "quiz-ready": {
        "title": "Quiz ready",
        "description": "Submit your first course quiz.",
        "icon": "✓",
    },
    "perfect-score": {
        "title": "Perfect score",
        "description": "Get every answer right in a quiz.",
        "icon": "★",
    },
    "steady-learner": {
        "title": "Steady learner",
        "description": "Keep a learning streak for three days.",
        "icon": "✺",
    },
    "project-builder": {
        "title": "Project builder",
        "description": "Complete every milestone in a guided project.",
        "icon": "⌘",
    },
}


def refresh_achievements(user):
    lesson_count = LessonProgress.objects.filter(user=user).count()
    quiz_attempts = QuizAttempt.objects.filter(user=user)
    active_dates = set(
        DailyActivity.objects.filter(user=user, lessons_completed__gt=0)
        .values_list("activity_date", flat=True)
    )
    today = timezone.localdate()
    current_day = today if today in active_dates else today - timedelta(days=1)
    streak = 0
    while current_day in active_dates:
        streak += 1
        current_day -= timedelta(days=1)

    eligible = set()
    if lesson_count >= 1:
        eligible.add("first-steps")
    if lesson_count >= 5:
        eligible.add("five-lessons")
    if lesson_count >= 10:
        eligible.add("ten-lessons")
    if quiz_attempts.exists():
        eligible.add("quiz-ready")
    if quiz_attempts.filter(score__gt=0, score=F("total")).exists():
        eligible.add("perfect-score")
    if streak >= 3:
        eligible.add("steady-learner")
    for progress in ProjectProgress.objects.filter(user=user):
        project = get_project(progress.project_slug)
        if project and {
            milestone["slug"] for milestone in project["milestones"]
        }.issubset(set(progress.completed_milestones)):
            eligible.add("project-builder")
            break

    EarnedAchievement.objects.bulk_create(
        [
            EarnedAchievement(user=user, achievement_code=code)
            for code in eligible
        ],
        ignore_conflicts=True,
    )
    return EarnedAchievement.objects.filter(user=user).order_by("earned_at")
