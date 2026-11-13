from django.db.models import Prefetch
from django.utils.text import slugify

from .courses import COURSES as COURSE_SEED
from .curriculum import LESSONS as LESSON_SEED, get_lesson as get_static_lesson, get_tracks as get_static_tracks
from .models import (
    CareerPrompt,
    Course,
    CourseAssessmentQuestion,
    CourseAssignment,
    CourseLesson,
    CourseModule,
    SubscriptionPlan,
)
from .quizzes import TRACK_QUIZZES


ASSIGNMENT_SEED = {
    "object-oriented-python": {
        "slug": "oop-library-project",
        "title": "Design a small library",
        "description": "Use classes, composition, and tests to model a simple library.",
        "instructions": (
            "Describe your Book and Library classes, the methods they provide, and "
            "how you would test adding and finding books."
        ),
    },
    "javascript": {
        "slug": "javascript-interactive-checklist",
        "title": "Build an interactive checklist",
        "description": "Create a small accessible checklist that responds to user input.",
        "instructions": (
            "Share the project URL or describe how your page adds, completes, and "
            "removes checklist items. Include one accessibility decision."
        ),
    },
    "html-css": {
        "slug": "html-css-responsive-portfolio",
        "title": "Create a responsive portfolio page",
        "description": "Build a semantic portfolio page that works on mobile and desktop.",
        "instructions": (
            "Share the project URL or describe its semantic sections, responsive "
            "layout, and one accessibility check you completed."
        ),
    },
}

CAREER_PROMPT_SEED = [
    {
        "category": CareerPrompt.Category.INTERVIEW,
        "title": "Explain a project you built",
        "prompt": "Choose a project and explain the problem, your contribution, and the result.",
        "guidance": "Use a concise situation, action, and result. Be specific about your own decisions.",
    },
    {
        "category": CareerPrompt.Category.INTERVIEW,
        "title": "Debugging scenario",
        "prompt": "Describe how you would investigate a bug that only appears for some users.",
        "guidance": "Mention reproduction, logs or diagnostics, a minimal test case, and how you would verify a fix.",
    },
    {
        "category": CareerPrompt.Category.RESUME,
        "title": "Turn a project into a resume bullet",
        "prompt": "Write one resume bullet for a project, focusing on your action and its measurable outcome.",
        "guidance": "Start with an action verb. Do not invent metrics; use a concrete technical result if no measured metric exists.",
    },
    {
        "category": CareerPrompt.Category.PORTFOLIO,
        "title": "Review a portfolio project",
        "prompt": "Pick a project and list its purpose, setup instructions, key decisions, and next improvement.",
        "guidance": "A reviewer should be able to run the project and understand what you learned from it.",
    },
]

SUBSCRIPTION_PLAN_SEED = [
    {
        "code": "free",
        "title": "Free",
        "description": "Core learning tools for getting started.",
        "monthly_price": "0.00",
        "features": [
            "Selected learning paths",
            "Basic coding playground",
            "Daily learning challenges",
            "Progress tracking",
        ],
        "sort_order": 0,
    },
    {
        "code": "premium",
        "title": "Premium",
        "description": "Premium plan structure; payment processing is not connected yet.",
        "monthly_price": None,
        "features": [
            "Expanded course access",
            "Advanced projects",
            "Interview preparation",
            "Additional learning analytics",
        ],
        "sort_order": 1,
    },
]


def _module_title(level):
    return "Beginner" if level == "Start here" else level


def _lesson_data(lesson):
    return {
        "slug": lesson.slug,
        "track": lesson.module.course.track,
        "language": lesson.language,
        "title": lesson.title,
        "level": lesson.level,
        "summary": lesson.summary,
        "body": lesson.body,
        "example": lesson.example,
        "exercise": lesson.exercise,
        "hint": lesson.hint,
        "quiz": lesson.quiz_question,
    }


def get_lessons():
    if not Course.objects.exists():
        return list(LESSON_SEED)
    records = CourseLesson.objects.filter(
        module__course__is_published=True,
    ).select_related("module__course").order_by(
        "module__course__sort_order",
        "module__sort_order",
        "sort_order",
        "id",
    )
    return [_lesson_data(lesson) for lesson in records]


def get_lesson(slug):
    if not Course.objects.exists():
        return get_static_lesson(slug)
    lesson = (
        CourseLesson.objects.filter(
            slug=slug,
            module__course__is_published=True,
        )
        .select_related("module__course")
        .first()
    )
    return _lesson_data(lesson) if lesson else None


def get_tracks(completed_slugs=()):
    courses = Course.objects.filter(is_published=True).prefetch_related(
        Prefetch(
            "modules",
            queryset=CourseModule.objects.order_by("sort_order", "id").prefetch_related(
                Prefetch(
                    "lessons",
                    queryset=CourseLesson.objects.order_by("sort_order", "id"),
                )
            ),
        )
    )
    if not Course.objects.exists():
        return get_static_tracks(completed_slugs)

    completed = set(completed_slugs)
    tracks = []
    for course in courses:
        lessons = []
        modules = []
        for module in course.modules.all():
            module_lessons = []
            for record in module.lessons.all():
                lesson = _lesson_data(record)
                lesson["completed"] = lesson["slug"] in completed
                lessons.append(lesson)
                module_lessons.append(lesson)
            if module_lessons:
                modules.append({"title": module.title, "lessons": module_lessons})
        if lessons:
            tracks.append(
                {
                    "title": course.track,
                    "lessons": lessons,
                    "modules": modules,
                }
            )
    return tracks


def seed_courses():
    seed_tracks = get_static_tracks()
    metadata_by_track = {
        course["track"]: (slug, course)
        for slug, course in COURSE_SEED.items()
    }

    for course_order, track in enumerate(seed_tracks):
        track_lessons = track["lessons"]
        seed_metadata = metadata_by_track.get(track["title"])
        course_slug, metadata = seed_metadata or (slugify(track["title"]), {})
        objectives = metadata.get(
            "objectives",
            [lesson["title"] for lesson in track_lessons[:5]],
        )
        course, _ = Course.objects.update_or_create(
            track=track["title"],
            defaults={
                "slug": course_slug,
                "title": metadata.get("title", track["title"]),
                "description": metadata.get(
                    "description",
                    f"Build practical skills in {track['title']} through guided lessons and exercises.",
                ),
                "objectives": objectives,
                "sort_order": course_order,
                "is_published": True,
            },
        )
        for question_order, question in enumerate(TRACK_QUIZZES.get(track["title"], [])):
            CourseAssessmentQuestion.objects.update_or_create(
                course=course,
                sort_order=question_order,
                defaults={
                    "prompt": question["question"],
                    "choices": question["choices"],
                    "correct_choice": question["answer"],
                    "explanation": "",
                },
            )
        module_orders = {}
        for lesson_order, lesson in enumerate(track_lessons):
            module_title = _module_title(lesson["level"])
            if module_title not in module_orders:
                module_orders[module_title] = len(module_orders)
            module, _ = CourseModule.objects.update_or_create(
                course=course,
                title=module_title,
                defaults={"sort_order": module_orders[module_title]},
            )
            CourseLesson.objects.update_or_create(
                slug=lesson["slug"],
                defaults={
                    "module": module,
                    "title": lesson["title"],
                    "level": lesson["level"],
                    "language": lesson.get("language", "Python"),
                    "summary": lesson["summary"],
                    "body": lesson["body"],
                    "example": lesson["example"],
                    "exercise": lesson["exercise"],
                    "hint": lesson["hint"],
                    "quiz_question": lesson["quiz"],
                    "sort_order": lesson_order,
                },
            )

    for course_slug, assignment_data in ASSIGNMENT_SEED.items():
        course = Course.objects.get(slug=course_slug)
        CourseAssignment.objects.update_or_create(
            slug=assignment_data["slug"],
            defaults={
                "course": course,
                "title": assignment_data["title"],
                "description": assignment_data["description"],
                "instructions": assignment_data["instructions"],
                "submission_type": CourseAssignment.SubmissionType.TEXT,
                "sort_order": 0,
                "is_published": True,
            },
        )

    for prompt_order, prompt in enumerate(CAREER_PROMPT_SEED):
        CareerPrompt.objects.update_or_create(
            category=prompt["category"],
            title=prompt["title"],
            defaults={
                "prompt": prompt["prompt"],
                "guidance": prompt["guidance"],
                "sort_order": prompt_order,
                "is_active": True,
            },
        )

    for plan in SUBSCRIPTION_PLAN_SEED:
        SubscriptionPlan.objects.update_or_create(
            code=plan["code"],
            defaults={
                **plan,
                "is_active": True,
            },
        )

    return (
        len(seed_tracks),
        len(LESSON_SEED),
        CourseAssessmentQuestion.objects.count(),
        len(ASSIGNMENT_SEED),
        len(CareerPrompt.objects.filter(is_active=True)),
        len(SUBSCRIPTION_PLAN_SEED),
    )
