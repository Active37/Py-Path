import html
import json
import re
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import transaction
from django.db.models import Count, F, IntegerField, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from .achievements import ACHIEVEMENTS, refresh_achievements
from .catalog import get_lesson, get_lessons, get_tracks
from .models import (
    AssignmentSubmission,
    CareerPracticeResponse,
    CareerPrompt,
    Certificate,
    Course,
    CourseAssessmentAttempt,
    CourseAssessmentQuestion,
    CourseAssignment,
    CourseLesson,
    DailyActivity,
    DiscussionPost,
    DiscussionReply,
    EarnedAchievement,
    LearnerProfile,
    LessonBookmark,
    LessonNote,
    LessonProgress,
    ProjectProgress,
    QuizAttempt,
    StudyGroup,
    StudyGroupMembership,
    StudyPlanItem,
    SubscriptionPlan,
    TutorMessage,
    UserSubscription,
)
from .projects import PROJECTS, get_project
from .quizzes import quiz_for_track
from .resources import RESOURCE_GROUPS
from .services import TutorServiceError, get_ai_reply, run_python_code


def service_worker(request):
    worker_path = Path(settings.BASE_DIR, "static", "service-worker.js")
    response = HttpResponse(worker_path.read_text(encoding="utf-8"), content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response


def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "home.html")


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = UserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


@login_required
def dashboard(request):
    completed = set(
        LessonProgress.objects.filter(user=request.user).values_list("lesson_slug", flat=True)
    )
    query = request.GET.get("q", "").strip()[:100]
    selected_track = request.GET.get("track", "").strip()
    all_tracks = get_tracks(completed)
    track_names = [track["title"] for track in all_tracks]
    tracks = []
    for track in all_tracks:
        if selected_track and track["title"] != selected_track:
            continue
        matching_lessons = [
            lesson
            for lesson in track["lessons"]
            if not query
            or any(
                query.casefold() in str(lesson.get(field, "")).casefold()
                for field in ("title", "summary", "track", "language")
            )
        ]
        course_match = query and query.casefold() in track["title"].casefold()
        if course_match:
            tracks.append(track)
        elif matching_lessons:
            track["lessons"] = matching_lessons
            tracks.append(track)
    courses = list(Course.objects.filter(is_published=True))
    if query:
        normalized_query = query.casefold()
        courses = [
            course
            for course in courses
            if normalized_query in course.title.casefold()
            or normalized_query in course.track.casefold()
            or normalized_query in course.description.casefold()
        ]
    profile = LearnerProfile.objects.get_or_create(user=request.user)[0]
    activity, current_streak = _daily_learning_stats(request.user)
    earned_achievements = refresh_achievements(request.user)
    week_start = timezone.localdate() - timedelta(days=timezone.localdate().weekday())
    planned_items = list(
        StudyPlanItem.objects.filter(
            user=request.user,
            planned_for__gte=timezone.localdate(),
            planned_for__lte=timezone.localdate() + timedelta(days=6),
        )[:4]
    )
    calendar_cells = _activity_calendar(request.user)
    return render(
        request,
        "tutor/dashboard.html",
        {
            "tracks": tracks,
            "lesson_count": len(get_lessons()),
            "completed_count": len(completed),
            "courses": courses,
            "is_course_instructor": Course.objects.filter(
                instructor=request.user,
            ).exists(),
            "query": query,
            "selected_track": selected_track,
            "track_names": track_names,
            "profile": profile,
            "today_completed": activity.lessons_completed if activity else 0,
            "current_streak": current_streak,
            "earned_achievements": _achievement_cards(earned_achievements[:4]),
            "calendar_cells": calendar_cells,
            "planned_items": planned_items,
            "week_start": week_start,
            "today_reminder": (
                profile.daily_reminders
                and (not activity or activity.lessons_completed < profile.daily_goal)
            ),
        },
    )


def _activity_calendar(user, days=84):
    today = timezone.localdate()
    start_date = today - timedelta(days=days - 1)
    activity_by_date = {
        activity.activity_date: activity.lessons_completed
        for activity in DailyActivity.objects.filter(
            user=user,
            activity_date__gte=start_date,
            activity_date__lte=today,
        )
    }
    cells = []
    for offset in range(days):
        activity_date = start_date + timedelta(days=offset)
        count = activity_by_date.get(activity_date, 0)
        cells.append(
            {
                "date": activity_date,
                "count": count,
                "level": min(count, 4),
                "is_future": activity_date > today,
            }
        )
    return cells


def _achievement_cards(earned):
    cards = []
    for record in earned:
        definition = ACHIEVEMENTS.get(record.achievement_code)
        if definition:
            cards.append({"code": record.achievement_code, **definition})
    return cards


def _daily_learning_stats(user):
    today = timezone.localdate()
    activity = DailyActivity.objects.filter(user=user, activity_date=today).first()
    active_dates = set(
        user.learning_activity.filter(
            lessons_completed__gt=0,
            activity_date__lte=today,
        ).values_list("activity_date", flat=True)
    )
    current_day = today if today in active_dates else today - timedelta(days=1)
    streak = 0
    while current_day in active_dates:
        streak += 1
        current_day -= timedelta(days=1)
    return activity, streak


@login_required
def object_oriented_course(request):
    return _render_course(request, "object-oriented-python")


@login_required
def course_detail(request, slug):
    return _render_course(request, slug)


def _render_course(request, slug):
    course = get_object_or_404(Course, slug=slug, is_published=True)
    completed = set(
        LessonProgress.objects.filter(user=request.user).values_list("lesson_slug", flat=True)
    )
    track = next(
        (track for track in get_tracks(completed) if track["title"] == course.track),
        None,
    )
    if track is None:
        raise Http404("Course lessons not found")
    completed_count = sum(lesson["completed"] for lesson in track["lessons"])
    questions = list(course.assessment_questions.all())
    assignments = list(course.assignments.filter(is_published=True))
    submissions = {
        submission.assignment_id: submission
        for submission in AssignmentSubmission.objects.filter(
            user=request.user,
            assignment__course=course,
        )
    }
    for assignment in assignments:
        assignment.user_submission = submissions.get(assignment.pk)
    return render(
        request,
        "tutor/course.html",
        {
            "course": course,
            "track": track,
            "completed_count": completed_count,
            "lesson_count": len(track["lessons"]),
            "assessment_questions": questions,
            "latest_assessment": CourseAssessmentAttempt.objects.filter(
                user=request.user,
                course=course,
            ).first(),
            "assignments": assignments,
        },
    )


def _issue_certificate_if_eligible(user, course):
    required_lessons = set(
        CourseLesson.objects.filter(module__course=course).values_list("slug", flat=True)
    )
    if not required_lessons:
        return None
    completed_lessons = set(
        LessonProgress.objects.filter(
            user=user,
            lesson_slug__in=required_lessons,
        ).values_list("lesson_slug", flat=True)
    )
    passed_assessment = CourseAssessmentAttempt.objects.filter(
        user=user,
        course=course,
        passed=True,
    ).exists()
    if required_lessons.issubset(completed_lessons) and passed_assessment:
        certificate, _ = Certificate.objects.get_or_create(user=user, course=course)
        return certificate
    return None


@login_required
@require_POST
def submit_course_assessment(request, slug):
    course = get_object_or_404(Course, slug=slug, is_published=True)
    questions = list(course.assessment_questions.all())
    if not questions:
        messages.error(request, "This course does not have a final assessment yet.")
        return redirect("course", slug=course.slug)

    answers = []
    for index, question in enumerate(questions):
        try:
            answer = int(request.POST.get(f"answer_{index}", ""))
        except (TypeError, ValueError):
            messages.error(request, "Choose an answer for every assessment question.")
            return redirect("course", slug=course.slug)
        if not 0 <= answer < len(question.choices):
            messages.error(request, "One of your assessment answers is invalid.")
            return redirect("course", slug=course.slug)
        answers.append(answer)

    score = sum(
        answer == question.correct_choice
        for answer, question in zip(answers, questions)
    )
    passed = score * 100 >= course.passing_score_percentage * len(questions)
    CourseAssessmentAttempt.objects.create(
        user=request.user,
        course=course,
        score=score,
        total=len(questions),
        passed=passed,
        answers=answers,
    )
    certificate = _issue_certificate_if_eligible(request.user, course) if passed else None
    if passed:
        message = f"Assessment passed: {score} of {len(questions)} correct."
        if certificate:
            message += " Your course certificate is ready."
        else:
            message += " Complete every lesson to qualify for your certificate."
        messages.success(request, message)
    else:
        messages.info(
            request,
            f"Assessment score: {score} of {len(questions)}. "
            f"Review the course and try again.",
        )
    return redirect("course", slug=course.slug)


@login_required
@require_POST
def submit_assignment(request, course_slug, assignment_slug):
    assignment = get_object_or_404(
        CourseAssignment,
        slug=assignment_slug,
        course__slug=course_slug,
        course__is_published=True,
        is_published=True,
    )
    content = request.POST.get("content", "").strip()
    if not content or len(content) > 20000:
        messages.error(request, "Provide a submission of 1–20,000 characters.")
        return redirect("course", slug=course_slug)
    if assignment.submission_type == CourseAssignment.SubmissionType.URL:
        try:
            URLValidator()(content)
        except ValidationError:
            messages.error(request, "Enter a valid project URL.")
            return redirect("course", slug=course_slug)

    submission, created = AssignmentSubmission.objects.get_or_create(
        assignment=assignment,
        user=request.user,
        defaults={"content": content},
    )
    if not created:
        submission.content = content
        submission.status = AssignmentSubmission.Status.SUBMITTED
        submission.score = None
        submission.feedback = ""
        submission.reviewer = None
        submission.save(
            update_fields=[
                "content",
                "status",
                "score",
                "feedback",
                "reviewer",
                "submitted_at",
            ]
        )
    messages.success(request, "Your assignment submission was saved.")
    return redirect("course", slug=course_slug)


@login_required
def resources(request):
    return render(
        request,
        "tutor/resources.html",
        {"resource_groups": RESOURCE_GROUPS},
    )


@login_required
def web_playground(request):
    return render(
        request,
        "tutor/playground.html",
        {
            "starter_html": (
                '<main class="demo-card">\n'
                '  <span class="eyebrow">YOUR FIRST WEB PROJECT</span>\n'
                '  <h1>Hello, builder.</h1>\n'
                '  <p>Change this page, then press <strong>Run preview</strong>.</p>\n'
                '  <button id="hello-button" type="button">Try the button</button>\n'
                '  <p id="hello-message" aria-live="polite"></p>\n'
                "</main>"
            ),
            "starter_css": (
                "body { font: 16px/1.6 system-ui, sans-serif; background: #edf6f0; "
                "color: #172521; padding: 2rem; }\n"
                ".demo-card { max-width: 32rem; margin: 3rem auto; padding: 2rem; "
                "border-radius: 1.25rem; background: white; box-shadow: 0 1rem 3rem #173a2918; }\n"
                ".eyebrow { color: #187c60; font-size: .75rem; font-weight: 800; "
                "letter-spacing: .12em; }\n"
                "button { border: 0; border-radius: .75rem; padding: .8rem 1rem; "
                "background: #187c60; color: white; font: inherit; cursor: pointer; }"
            ),
            "starter_js": (
                'document.querySelector("#hello-button").addEventListener("click", () => {\n'
                '  document.querySelector("#hello-message").textContent = "Nice work — your JavaScript is running!";\n'
                '  console.log("Button clicked. Your preview is interactive.");\n'
                "});"
            ),
        },
    )


@login_required
def lesson_detail(request, slug):
    lesson = get_lesson(slug)
    if lesson is None:
        raise Http404("Lesson not found")
    completed = LessonProgress.objects.filter(
        user=request.user, lesson_slug=lesson["slug"]
    ).exists()
    chat_messages = list(
        TutorMessage.objects.filter(user=request.user, lesson_slug=lesson["slug"])
        .order_by("-created_at")[:12]
    )
    chat_messages.reverse()
    quiz_questions = quiz_for_track(lesson["track"])
    lessons = get_lessons()
    lesson_index = next(index for index, item in enumerate(lessons) if item["slug"] == slug)
    previous_lesson = lessons[lesson_index - 1] if lesson_index else None
    next_lesson = lessons[lesson_index + 1] if lesson_index + 1 < len(lessons) else None
    return render(
        request,
        "tutor/lesson.html",
        {
            "lesson": lesson,
            "completed": completed,
            "chat_messages": chat_messages,
            "is_bookmarked": LessonBookmark.objects.filter(
                user=request.user, lesson_slug=lesson["slug"]
            ).exists(),
            "note": LessonNote.objects.filter(
                user=request.user, lesson_slug=lesson["slug"]
            ).first(),
            "quiz_questions": quiz_questions,
            "latest_quiz": QuizAttempt.objects.filter(
                user=request.user, lesson_slug=lesson["slug"]
            ).first(),
            "previous_lesson": previous_lesson,
            "next_lesson": next_lesson,
            "lesson_number": lesson_index + 1,
            "lesson_total": len(lessons),
        },
    )


@login_required
@require_POST
def complete_lesson(request, slug):
    lesson = get_lesson(slug)
    if lesson is None:
        raise Http404("Lesson not found")
    with transaction.atomic():
        _, created = LessonProgress.objects.get_or_create(
            user=request.user, lesson_slug=lesson["slug"]
        )
        if created:
            activity, _ = DailyActivity.objects.get_or_create(
                user=request.user, activity_date=timezone.localdate()
            )
            DailyActivity.objects.filter(pk=activity.pk).update(
                lessons_completed=F("lessons_completed") + 1
            )
    if created:
        refresh_achievements(request.user)
        course_lesson = (
            CourseLesson.objects.filter(slug=lesson["slug"])
            .select_related("module__course")
            .first()
        )
        if course_lesson:
            _issue_certificate_if_eligible(request.user, course_lesson.module.course)
        messages.success(request, "Lesson marked complete. Nice work!")
    else:
        messages.info(request, "You’ve already completed this lesson.")
    return redirect("lesson", slug=lesson["slug"])


@login_required
@require_POST
def toggle_bookmark(request, slug):
    lesson = get_lesson(slug)
    if lesson is None:
        raise Http404("Lesson not found")
    bookmark, created = LessonBookmark.objects.get_or_create(
        user=request.user, lesson_slug=lesson["slug"]
    )
    if created:
        messages.success(request, "Lesson saved to your bookmarks.")
    else:
        bookmark.delete()
        messages.info(request, "Lesson removed from your bookmarks.")
    return redirect("lesson", slug=lesson["slug"])


@login_required
def bookmarks(request):
    saved_lessons = [
        lesson
        for bookmark in LessonBookmark.objects.filter(user=request.user)
        if (lesson := get_lesson(bookmark.lesson_slug)) is not None
    ]
    return render(request, "tutor/bookmarks.html", {"saved_lessons": saved_lessons})


@login_required
def study_planner(request):
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    if request.method == "POST":
        action = request.POST.get("action", "add")
        if action in {"complete", "delete"}:
            try:
                item_id = int(request.POST.get("item_id", ""))
            except (TypeError, ValueError):
                messages.error(request, "Choose a valid study plan item.")
                return redirect("study_planner")
            item = get_object_or_404(
                StudyPlanItem,
                pk=item_id,
                user=request.user,
                planned_for__gte=week_start,
                planned_for__lte=week_end,
            )
            if action == "delete":
                item.delete()
                messages.success(request, "Study plan item removed.")
            else:
                item.is_completed = not item.is_completed
                item.save(update_fields=["is_completed"])
                messages.success(
                    request,
                    "Study session marked complete."
                    if item.is_completed
                    else "Study session moved back to your plan.",
                )
            return redirect("study_planner")

        title = request.POST.get("title", "").strip()
        planned_for_raw = request.POST.get("planned_for", "")
        try:
            planned_for = date.fromisoformat(planned_for_raw)
            target_minutes = int(request.POST.get("target_minutes", ""))
        except (TypeError, ValueError):
            messages.error(request, "Enter a valid day and study duration.")
            return redirect("study_planner")
        if not title or len(title) > 120:
            messages.error(request, "Give your study session a title of 1–120 characters.")
        elif not today <= planned_for <= week_end:
            messages.error(request, "Choose a day from today through the end of this week.")
        elif not 5 <= target_minutes <= 240:
            messages.error(request, "Choose a session length from 5 to 240 minutes.")
        else:
            _, created = StudyPlanItem.objects.get_or_create(
                user=request.user,
                planned_for=planned_for,
                title=title,
                defaults={"target_minutes": target_minutes},
            )
            messages.success(
                request,
                "Study session added to your week."
                if created
                else "That study session is already on your plan.",
            )
        return redirect("study_planner")

    items = list(
        StudyPlanItem.objects.filter(
            user=request.user,
            planned_for__gte=week_start,
            planned_for__lte=week_end,
        )
    )
    week_days = [
        {
            "date": week_start + timedelta(days=offset),
            "items": [
                item for item in items if item.planned_for == week_start + timedelta(days=offset)
            ],
        }
        for offset in range(7)
    ]
    return render(
        request,
        "tutor/planner.html",
        {
            "week_days": week_days,
            "today": today,
            "week_start": week_start,
            "week_end": week_end,
            "default_minutes": 20,
        },
    )


@login_required
def projects(request):
    progress_by_slug = {
        item.project_slug: item
        for item in ProjectProgress.objects.filter(user=request.user)
    }
    project_cards = []
    for project in PROJECTS:
        progress = progress_by_slug.get(project["slug"])
        completed = set(progress.completed_milestones) if progress else set()
        project_cards.append(
            {
                **project,
                "completed_count": sum(
                    milestone["slug"] in completed for milestone in project["milestones"]
                ),
                "milestone_count": len(project["milestones"]),
            }
        )
    return render(request, "tutor/projects.html", {"projects": project_cards})


@login_required
def project_detail(request, slug):
    project = get_project(slug)
    if project is None:
        raise Http404("Project not found")
    progress = ProjectProgress.objects.filter(user=request.user, project_slug=slug).first()
    completed = set(progress.completed_milestones) if progress else set()
    return render(
        request,
        "tutor/project.html",
        {
            "project": project,
            "completed": completed,
            "completed_count": len(completed),
        },
    )


@login_required
@require_POST
def toggle_project_milestone(request, slug, milestone_slug):
    project = get_project(slug)
    if project is None:
        raise Http404("Project not found")
    milestone_slugs = {milestone["slug"] for milestone in project["milestones"]}
    if milestone_slug not in milestone_slugs:
        raise Http404("Project milestone not found")
    progress, _ = ProjectProgress.objects.get_or_create(
        user=request.user,
        project_slug=slug,
    )
    completed = set(progress.completed_milestones)
    if milestone_slug in completed:
        completed.remove(milestone_slug)
    else:
        completed.add(milestone_slug)
    progress.completed_milestones = sorted(completed & milestone_slugs)
    progress.save(update_fields=["completed_milestones", "updated_at"])
    refresh_achievements(request.user)
    messages.success(
        request,
        "Project milestone updated. Nice work!"
        if milestone_slug in completed
        else "Project milestone moved back to in progress.",
    )
    return redirect("project_detail", slug=slug)


@login_required
def offline_download(request):
    track_title = request.GET.get("track", "").strip()
    lessons = [lesson for lesson in get_lessons() if lesson["track"] == track_title]
    if not lessons:
        raise Http404("Learning path not found")

    lesson_sections = []
    for index, lesson in enumerate(lessons, start=1):
        lesson_sections.append(
            f"""
            <article class="lesson">
              <p class="meta">LESSON {index:02d} · {html.escape(lesson.get("level", ""))}</p>
              <h2>{html.escape(lesson["title"])}</h2>
              <p class="summary">{html.escape(lesson.get("summary", ""))}</p>
              <h3>The idea</h3><p>{html.escape(lesson["body"])}</p>
              <h3>Example</h3><pre><code>{html.escape(lesson["example"])}</code></pre>
              <h3>Your turn</h3><p>{html.escape(lesson["exercise"])}</p>
            </article>
            """
        )
    document = f"""<!doctype html>
    <html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{html.escape(track_title)} · PyPath Offline Lessons</title>
    <style>
      * {{ box-sizing: border-box; }}
      body {{ margin: 0; padding: 32px 18px; background: #f5faf7; color: #172521;
        font: 16px/1.7 "Segoe UI", sans-serif; }}
      main {{ max-width: 760px; margin: auto; }}
      .intro, .lesson {{ padding: clamp(20px, 5vw, 36px); border: 1px solid #e1ece5;
        border-radius: 20px; background: #fff; box-shadow: 0 12px 30px #173a2910; }}
      .lesson {{ margin-top: 16px; }}
      h1 {{ font-size: clamp(30px, 7vw, 44px); line-height: 1.1; letter-spacing: -1.5px; }}
      h2 {{ margin: 4px 0 8px; font-size: 24px; }}
      h3 {{ margin: 22px 0 4px; font-size: 15px; }}
      p {{ margin: 8px 0; }}
      .meta {{ color: #187c60; font-size: 11px; font-weight: 800; letter-spacing: 1px; }}
      .summary {{ color: #6f7d77; }}
      pre {{ overflow-x: auto; padding: 16px; border-radius: 12px; background: #10251f;
        color: #e4f2e9; white-space: pre-wrap; }}
      @media print {{ body {{ background: white; }} .intro, .lesson {{ box-shadow: none; break-inside: avoid; }} }}
    </style></head>
    <body><main>
      <header class="intro"><p class="meta">PYPATH · OFFLINE LEARNING PACK</p>
        <h1>{html.escape(track_title)}</h1>
        <p>{len(lessons)} lessons · Save this file and open it any time, even offline.</p>
      </header>
      {''.join(lesson_sections)}
    </main></body></html>"""
    response = HttpResponse(document, content_type="text/html; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="pypath-{slugify(track_title)}-offline.html"'
    )
    response["Cache-Control"] = "private, no-store"
    return response


def _public_learner_queryset():
    lesson_totals = (
        LessonProgress.objects.filter(user=OuterRef("user"))
        .values("user")
        .annotate(total=Count("id"))
        .values("total")[:1]
    )
    quiz_totals = (
        QuizAttempt.objects.filter(user=OuterRef("user"))
        .values("user")
        .annotate(total=Sum("score"))
        .values("total")[:1]
    )
    return (
        LearnerProfile.objects.filter(public_profile=True)
        .select_related("user")
        .annotate(
            completed_count=Coalesce(
                Subquery(lesson_totals, output_field=IntegerField()),
                Value(0),
            ),
            quiz_points=Coalesce(
                Subquery(quiz_totals, output_field=IntegerField()),
                Value(0),
            ),
        )
        .annotate(xp=F("completed_count") * 10 + F("quiz_points") * 2)
        .order_by("-xp", "user__username")
    )


def leaderboard(request):
    return render(
        request,
        "tutor/leaderboard.html",
        {"learners": _public_learner_queryset()[:25]},
    )


def public_learner_profile(request, public_id):
    profile = get_object_or_404(
        _public_learner_queryset(),
        public_id=public_id,
    )
    earned_codes = set(
        EarnedAchievement.objects.filter(user=profile.user).values_list(
            "achievement_code", flat=True
        )
    )
    profile.earned_badges = [
        {"code": code, **definition}
        for code, definition in ACHIEVEMENTS.items()
        if code in earned_codes
    ]
    return render(request, "tutor/public_profile.html", {"learner_profile": profile})


@login_required
@require_POST
def save_note(request, slug):
    lesson = get_lesson(slug)
    if lesson is None:
        raise Http404("Lesson not found")
    content = request.POST.get("content", "")
    if len(content) > 10000:
        messages.error(request, "Keep lesson notes to 10,000 characters or fewer.")
    else:
        LessonNote.objects.update_or_create(
            user=request.user,
            lesson_slug=lesson["slug"],
            defaults={"content": content},
        )
        messages.success(request, "Your lesson note was saved.")
    return redirect("lesson", slug=lesson["slug"])


@login_required
@require_POST
def submit_quiz(request, slug):
    lesson = get_lesson(slug)
    if lesson is None:
        raise Http404("Lesson not found")
    questions = quiz_for_track(lesson["track"])
    answers = []
    for index, question in enumerate(questions):
        try:
            answer = int(request.POST.get(f"answer_{index}", ""))
        except (TypeError, ValueError):
            messages.error(request, "Choose an answer for every quiz question.")
            return redirect("lesson", slug=lesson["slug"])
        if answer < 0 or answer >= len(question["choices"]):
            messages.error(request, "One of your selected answers is invalid.")
            return redirect("lesson", slug=lesson["slug"])
        answers.append(answer)
    score = sum(
        answer == question["answer"]
        for answer, question in zip(answers, questions)
    )
    QuizAttempt.objects.create(
        user=request.user,
        lesson_slug=lesson["slug"],
        score=score,
        total=len(questions),
    )
    refresh_achievements(request.user)
    messages.success(request, f"Quiz saved: {score} out of {len(questions)} correct.")
    return redirect("lesson", slug=lesson["slug"])


@login_required
def profile(request):
    learner_profile, _ = LearnerProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        display_name = request.POST.get("display_name", "").strip()
        try:
            daily_goal = int(request.POST.get("daily_goal", ""))
        except (TypeError, ValueError):
            daily_goal = 0
        if len(display_name) > 80:
            messages.error(request, "Your display name must be 80 characters or fewer.")
        elif not 1 <= daily_goal <= 10:
            messages.error(request, "Choose a daily lesson goal from 1 to 10.")
        else:
            learner_profile.display_name = display_name
            learner_profile.daily_goal = daily_goal
            learner_profile.daily_reminders = request.POST.get("daily_reminders") == "on"
            learner_profile.public_profile = request.POST.get("public_profile") == "on"
            learner_profile.save(
                update_fields=[
                    "display_name",
                    "daily_goal",
                    "daily_reminders",
                    "public_profile",
                ]
            )
            messages.success(request, "Your learning profile was updated.")
            return redirect("profile")

    completed = set(
        LessonProgress.objects.filter(user=request.user).values_list("lesson_slug", flat=True)
    )
    tracks = get_tracks(completed)
    track_progress = [
        {
            "title": track["title"],
            "completed": sum(lesson["completed"] for lesson in track["lessons"]),
            "total": len(track["lessons"]),
        }
        for track in tracks
    ]
    activity, current_streak = _daily_learning_stats(request.user)
    earned_achievements = _achievement_cards(refresh_achievements(request.user))
    calendar_cells = _activity_calendar(request.user)
    latest_attempts = list(QuizAttempt.objects.filter(user=request.user)[:10])
    total_quiz_score = (
        QuizAttempt.objects.filter(user=request.user).aggregate(total=Sum("score"))["total"]
        or 0
    )
    for attempt in latest_attempts:
        lesson = get_lesson(attempt.lesson_slug)
        attempt.lesson_title = lesson["title"] if lesson else attempt.lesson_slug
    return render(
        request,
        "tutor/profile.html",
        {
            "profile": learner_profile,
            "completed_count": len(completed),
            "lesson_count": len(get_lessons()),
            "bookmark_count": LessonBookmark.objects.filter(user=request.user).count(),
            "quiz_count": QuizAttempt.objects.filter(user=request.user).count(),
            "today_completed": activity.lessons_completed if activity else 0,
            "current_streak": current_streak,
            "track_progress": track_progress,
            "latest_attempts": latest_attempts,
            "earned_achievements": earned_achievements,
            "calendar_cells": calendar_cells,
            "xp": len(completed) * 10 + total_quiz_score * 2,
            "public_url": (
                request.build_absolute_uri(
                    reverse("public_learner_profile", args=[learner_profile.public_id])
                )
                if learner_profile.public_profile
                else ""
            ),
        },
    )


@login_required
def community(request):
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        body = request.POST.get("body", "").strip()
        if not 5 <= len(title) <= 140:
            messages.error(request, "Give your discussion a title of 5–140 characters.")
        elif not 20 <= len(body) <= 10000:
            messages.error(request, "Write a post of 20–10,000 characters.")
        else:
            post = DiscussionPost.objects.create(
                author=request.user,
                title=title,
                body=body,
            )
            messages.success(request, "Your discussion was posted.")
            return redirect("discussion_detail", post_id=post.pk)

    posts = (
        DiscussionPost.objects.filter(is_published=True)
        .select_related("author")
        .annotate(reply_count=Count("replies"))
    )
    return render(request, "tutor/community.html", {"posts": posts})


@login_required
def discussion_detail(request, post_id):
    post = get_object_or_404(
        DiscussionPost.objects.select_related("author").prefetch_related(
            "replies__author"
        ),
        pk=post_id,
        is_published=True,
    )
    if request.method == "POST":
        body = request.POST.get("body", "").strip()
        if not 2 <= len(body) <= 5000:
            messages.error(request, "Write a reply of 2–5,000 characters.")
        else:
            DiscussionReply.objects.create(
                post=post,
                author=request.user,
                body=body,
            )
            messages.success(request, "Your reply was added.")
            return redirect("discussion_detail", post_id=post.pk)
    return render(request, "tutor/discussion.html", {"post": post})


@login_required
def study_groups(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        try:
            max_members = int(request.POST.get("max_members", ""))
        except (TypeError, ValueError):
            max_members = 0
        group_slug = slugify(name)
        if not 3 <= len(name) <= 100:
            messages.error(request, "Give your study group a name of 3–100 characters.")
        elif not 10 <= len(description) <= 2000:
            messages.error(request, "Describe your group in 10–2,000 characters.")
        elif not 2 <= max_members <= 100:
            messages.error(request, "Choose a group size from 2 to 100 members.")
        elif not group_slug or StudyGroup.objects.filter(slug=group_slug).exists():
            messages.error(request, "That group name is already in use; choose another.")
        else:
            with transaction.atomic():
                group = StudyGroup.objects.create(
                    name=name,
                    slug=group_slug,
                    description=description,
                    created_by=request.user,
                    max_members=max_members,
                )
                StudyGroupMembership.objects.create(
                    group=group,
                    user=request.user,
                    role=StudyGroupMembership.Role.ORGANIZER,
                )
            messages.success(request, "Your study group is ready.")
            return redirect("study_groups")

    groups = StudyGroup.objects.filter(is_active=True).select_related("created_by").annotate(
        member_count=Count("memberships")
    )
    joined_ids = set(
        StudyGroupMembership.objects.filter(user=request.user).values_list(
            "group_id", flat=True
        )
    )
    for group in groups:
        group.is_joined = group.pk in joined_ids
    return render(request, "tutor/study_groups.html", {"groups": groups})


@login_required
@require_POST
def toggle_study_group_membership(request, slug):
    group = get_object_or_404(StudyGroup, slug=slug, is_active=True)
    membership = StudyGroupMembership.objects.filter(
        group=group,
        user=request.user,
    ).first()
    if membership:
        if membership.role == StudyGroupMembership.Role.ORGANIZER and not (
            group.memberships.filter(role=StudyGroupMembership.Role.ORGANIZER)
            .exclude(user=request.user)
            .exists()
        ):
            messages.error(request, "Assign another organizer before leaving this group.")
        else:
            membership.delete()
            messages.success(request, "You left the study group.")
        return redirect("study_groups")

    with transaction.atomic():
        group = StudyGroup.objects.select_for_update().get(pk=group.pk)
        member_count = group.memberships.count()
        if member_count >= group.max_members:
            messages.error(request, "This study group is full.")
        else:
            _, created = StudyGroupMembership.objects.get_or_create(
                group=group,
                user=request.user,
                defaults={"role": StudyGroupMembership.Role.MEMBER},
            )
            if created:
                messages.success(request, "You joined the study group.")
            else:
                messages.info(request, "You are already a member of this group.")
    return redirect("study_groups")


@login_required
def career_center(request):
    prompts = list(CareerPrompt.objects.filter(is_active=True))
    responses = {
        response.prompt_id: response
        for response in CareerPracticeResponse.objects.filter(
            user=request.user,
            prompt__in=prompts,
        )
    }
    for prompt in prompts:
        prompt.user_response = responses.get(prompt.pk)
    return render(request, "tutor/career.html", {"prompts": prompts})


@login_required
@require_POST
def save_career_response(request, prompt_id):
    prompt = get_object_or_404(CareerPrompt, pk=prompt_id, is_active=True)
    answer = request.POST.get("answer", "").strip()
    reflection = request.POST.get("reflection", "").strip()
    rating_value = request.POST.get("self_rating", "").strip()
    if not 20 <= len(answer) <= 10000:
        messages.error(request, "Write an answer of 20–10,000 characters.")
        return redirect("career_center")
    if len(reflection) > 2000:
        messages.error(request, "Keep your reflection to 2,000 characters or fewer.")
        return redirect("career_center")
    try:
        rating = int(rating_value) if rating_value else None
    except ValueError:
        rating = 0
    if rating is not None and not 1 <= rating <= 5:
        messages.error(request, "Choose a self-review rating from 1 to 5.")
        return redirect("career_center")
    CareerPracticeResponse.objects.update_or_create(
        user=request.user,
        prompt=prompt,
        defaults={
            "answer": answer,
            "self_rating": rating,
            "reflection": reflection,
        },
    )
    messages.success(request, "Your private career-practice response was saved.")
    return redirect("career_center")


@login_required
def certificates(request):
    records = Certificate.objects.filter(user=request.user).select_related("course")
    return render(request, "tutor/certificates.html", {"certificates": records})


def verify_certificate(request, certificate_id):
    certificate = get_object_or_404(
        Certificate.objects.select_related("user", "course"),
        certificate_id=certificate_id,
    )
    learner_name = (
        LearnerProfile.objects.filter(user=certificate.user)
        .values_list("display_name", flat=True)
        .first()
        or certificate.user.get_full_name()
        or certificate.user.get_username()
    )
    return render(
        request,
        "tutor/verify_certificate.html",
        {
            "certificate": certificate,
            "learner_name": learner_name,
        },
    )


@login_required
def download_certificate(request, certificate_id):
    certificate = get_object_or_404(
        Certificate.objects.select_related("user", "course"),
        certificate_id=certificate_id,
    )
    if certificate.user_id != request.user.id and not request.user.is_staff:
        raise Http404("Certificate not found")

    learner_name = (
        LearnerProfile.objects.filter(user=certificate.user)
        .values_list("display_name", flat=True)
        .first()
        or certificate.user.get_full_name()
        or certificate.user.get_username()
    )
    verify_url = request.build_absolute_uri(
        reverse("verify_certificate", args=[certificate.certificate_id])
    )
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=64,
        leftMargin=64,
        topMargin=58,
        bottomMargin=58,
        title=f"PyPath certificate - {certificate.course.title}",
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="CertificateSubtitle",
            parent=styles["Normal"],
            alignment=1,
            fontSize=14,
            leading=20,
            textColor=colors.HexColor("#42645a"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="CertificateLearner",
            parent=styles["Title"],
            alignment=1,
            fontSize=30,
            leading=38,
            textColor=colors.HexColor("#123c30"),
        )
    )
    story = [
        Paragraph("PYPATH · CERTIFICATE OF COMPLETION", styles["Heading2"]),
        Spacer(1, 24),
        Paragraph("This certifies that", styles["CertificateSubtitle"]),
        Spacer(1, 12),
        Paragraph(escape(learner_name), styles["CertificateLearner"]),
        Spacer(1, 12),
        Paragraph("successfully completed the assessed course", styles["CertificateSubtitle"]),
        Spacer(1, 12),
        Paragraph(escape(certificate.course.title), styles["Heading1"]),
        Spacer(1, 24),
        Paragraph(
            f"Issued {certificate.issued_at:%B %d, %Y} · "
            f"Certificate ID {certificate.certificate_id}",
            styles["CertificateSubtitle"],
        ),
        Spacer(1, 8),
        Paragraph(f"Verify: {escape(verify_url)}", styles["Normal"]),
    ]
    document.build(story)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="pypath-certificate-{certificate.certificate_id}.pdf"'
    )
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
def subscription_plans(request):
    free_plan = SubscriptionPlan.objects.filter(code="free", is_active=True).first()
    current_subscription = (
        UserSubscription.objects.filter(user=request.user)
        .select_related("plan")
        .first()
    )
    if request.method == "POST":
        if request.POST.get("plan") != "free" or free_plan is None:
            messages.error(
                request,
                "Online payments are not connected. Only the free plan is available.",
            )
            return redirect("subscription_plans")
        UserSubscription.objects.update_or_create(
            user=request.user,
            defaults={
                "plan": free_plan,
                "status": UserSubscription.Status.ACTIVE,
                "provider": "",
                "provider_subscription_id": "",
            },
        )
        messages.success(request, "Your free plan is active.")
        return redirect("subscription_plans")
    return render(
        request,
        "tutor/subscriptions.html",
        {
            "plans": SubscriptionPlan.objects.filter(is_active=True),
            "current_subscription": current_subscription,
            "free_plan": free_plan,
        },
    )


@login_required
def admin_dashboard(request):
    if not request.user.is_staff:
        raise Http404("Dashboard not found")
    return render(
        request,
        "tutor/admin_dashboard.html",
        {
            "course_count": Course.objects.count(),
            "learner_count": LearnerProfile.objects.count(),
            "assignment_count": CourseAssignment.objects.count(),
            "submission_count": AssignmentSubmission.objects.count(),
            "discussion_count": DiscussionPost.objects.count(),
            "certificate_count": Certificate.objects.count(),
            "subscription_count": UserSubscription.objects.count(),
        },
    )


@login_required
def instructor_assignments(request):
    instructor_courses = Course.objects.filter(instructor=request.user)
    if not instructor_courses.exists():
        raise Http404("Instructor dashboard not found")
    if request.method == "POST":
        try:
            submission_id = int(request.POST.get("submission_id", ""))
            score = int(request.POST.get("score", ""))
        except (TypeError, ValueError):
            messages.error(request, "Choose a valid submission and score.")
            return redirect("instructor_assignments")
        submission = get_object_or_404(
            AssignmentSubmission.objects.select_related("assignment"),
            pk=submission_id,
            assignment__course__instructor=request.user,
        )
        feedback = request.POST.get("feedback", "").strip()
        if not 0 <= score <= submission.assignment.points:
            messages.error(
                request,
                f"Score must be from 0 to {submission.assignment.points}.",
            )
        elif len(feedback) > 5000:
            messages.error(request, "Keep feedback to 5,000 characters or fewer.")
        else:
            submission.score = score
            submission.feedback = feedback
            submission.status = AssignmentSubmission.Status.REVIEWED
            submission.reviewer = request.user
            submission.save(
                update_fields=[
                    "score",
                    "feedback",
                    "status",
                    "reviewer",
                    "submitted_at",
                ]
            )
            messages.success(request, "Assignment feedback was saved.")
        return redirect("instructor_assignments")

    submissions = (
        AssignmentSubmission.objects.filter(
            assignment__course__instructor=request.user,
        )
        .select_related("assignment__course", "user")
        .order_by("status", "-submitted_at")
    )
    return render(
        request,
        "tutor/instructor_assignments.html",
        {"submissions": submissions},
    )


def make_tutor_reply(question, lesson):
    text = question.strip()
    normalized = text.casefold()
    if not text:
        return "Ask me a Python question, or try “give me a hint” or “quiz me.”"
    if "quiz" in normalized:
        return f"Quick check: {lesson['quiz']}"
    if "hint" in normalized or "stuck" in normalized:
        return f"Hint: {lesson['hint']}"
    if re.search(r"\b(?:hello|hi|hey)\b", normalized):
        return f"Hi! We’re working on {lesson['title']}. What would you like explained?"
    if "example" in normalized or "show me" in normalized:
        return f"Here’s an example from this lesson:\n{lesson['example']}"
    return (
        f"Let’s connect that to {lesson['title']}: {lesson['body']}\n\n"
        f"Try this: {lesson['exercise']} If you get stuck, ask me for a hint."
    )


@login_required
@require_POST
def chat(request):
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Send a valid JSON request."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "The request must be a JSON object."}, status=400)
    question = payload.get("message", "")
    lessons = get_lessons()
    slug = payload.get("lesson", lessons[0]["slug"] if lessons else "")
    if not isinstance(question, str) or not isinstance(slug, str):
        return JsonResponse({"error": "Message and lesson must be text."}, status=400)
    if len(question) > 2000:
        return JsonResponse({"error": "Keep messages to 2,000 characters or fewer."}, status=400)
    lesson = get_lesson(slug)
    if lesson is None:
        return JsonResponse({"error": "That lesson could not be found."}, status=404)
    history_rows = list(
        TutorMessage.objects.filter(user=request.user, lesson_slug=lesson["slug"])
        .order_by("-created_at")[:10]
    )
    history = [
        {
            "role": "user" if message.role == TutorMessage.Role.LEARNER else "assistant",
            "content": message.content,
        }
        for message in reversed(history_rows)
    ]
    normalized = question.casefold()
    if "quiz" in normalized or "hint" in normalized or "stuck" in normalized:
        reply = make_tutor_reply(question, lesson)
    else:
        try:
            reply = get_ai_reply(question, lesson, history)
        except TutorServiceError as error:
            return JsonResponse({"error": str(error)}, status=503)
    TutorMessage.objects.bulk_create(
        [
            TutorMessage(
                user=request.user,
                lesson_slug=lesson["slug"],
                role=TutorMessage.Role.LEARNER,
                content=question,
            ),
            TutorMessage(
                user=request.user,
                lesson_slug=lesson["slug"],
                role=TutorMessage.Role.TUTOR,
                content=reply,
            ),
        ]
    )
    return JsonResponse({"reply": reply})


@login_required
@require_POST
def run_code(request):
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Send a valid JSON request."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "The request must be a JSON object."}, status=400)
    source_code = payload.get("code", "")
    stdin = payload.get("stdin", "")
    if not isinstance(source_code, str) or not isinstance(stdin, str):
        return JsonResponse({"error": "Code and input must be text."}, status=400)
    if not source_code.strip():
        return JsonResponse({"error": "Enter some Python code to run."}, status=400)
    if len(source_code) > 4000:
        return JsonResponse({"error": "Keep code to 4,000 characters or fewer."}, status=400)
    if len(stdin) > 1000:
        return JsonResponse({"error": "Keep program input to 1,000 characters or fewer."}, status=400)
    try:
        result = run_python_code(source_code, stdin)
    except TutorServiceError as error:
        return JsonResponse({"error": str(error)}, status=503)
    return JsonResponse(result)
