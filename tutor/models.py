import uuid

from django.conf import settings
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator


class Course(models.Model):
    slug = models.SlugField(max_length=100, unique=True)
    track = models.CharField(max_length=100, unique=True)
    title = models.CharField(max_length=120)
    description = models.TextField()
    objectives = models.JSONField(default=list, blank=True)
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="instructed_courses",
        null=True,
        blank=True,
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    passing_score_percentage = models.PositiveSmallIntegerField(
        default=70,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
    )

    class Meta:
        ordering = ["sort_order", "title"]

    def __str__(self):
        return self.title


class CourseModule(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="modules",
    )
    title = models.CharField(max_length=100)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["course", "title"],
                name="unique_course_module_title",
            )
        ]

    def __str__(self):
        return f"{self.course.title}: {self.title}"


class CourseLesson(models.Model):
    module = models.ForeignKey(
        CourseModule,
        on_delete=models.CASCADE,
        related_name="lessons",
    )
    slug = models.SlugField(max_length=100, unique=True)
    title = models.CharField(max_length=160)
    level = models.CharField(max_length=32, default="Beginner")
    language = models.CharField(max_length=40, default="Python")
    summary = models.CharField(max_length=240)
    body = models.TextField()
    example = models.TextField()
    exercise = models.TextField()
    hint = models.TextField()
    quiz_question = models.TextField()
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        indexes = [
            models.Index(fields=["module", "sort_order"]),
        ]

    def __str__(self):
        return self.title


class CourseAssessmentQuestion(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="assessment_questions",
    )
    prompt = models.TextField()
    choices = models.JSONField(default=list)
    correct_choice = models.PositiveSmallIntegerField()
    explanation = models.TextField(blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["course", "sort_order"],
                name="unique_course_assessment_question_order",
            )
        ]

    def __str__(self):
        return f"{self.course.title}: {self.prompt[:60]}"


class CourseAssessmentAttempt(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="course_assessment_attempts",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="assessment_attempts",
    )
    score = models.PositiveSmallIntegerField()
    total = models.PositiveSmallIntegerField()
    passed = models.BooleanField(default=False)
    answers = models.JSONField(default=list)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-completed_at"]
        indexes = [
            models.Index(fields=["user", "course", "passed"]),
        ]


class CourseAssignment(models.Model):
    class SubmissionType(models.TextChoices):
        TEXT = "text", "Written response or project notes"
        URL = "url", "Project URL"

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    slug = models.SlugField(max_length=100, unique=True)
    title = models.CharField(max_length=160)
    description = models.TextField()
    instructions = models.TextField()
    submission_type = models.CharField(
        max_length=8,
        choices=SubmissionType.choices,
        default=SubmissionType.TEXT,
    )
    points = models.PositiveSmallIntegerField(default=100)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.course.title}: {self.title}"


class AssignmentSubmission(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        REVIEWED = "reviewed", "Reviewed"

    assignment = models.ForeignKey(
        CourseAssignment,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assignment_submissions",
    )
    content = models.TextField(max_length=20000)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.SUBMITTED,
    )
    score = models.PositiveSmallIntegerField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_assignment_submissions",
    )
    submitted_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-submitted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "user"],
                name="unique_user_assignment_submission",
            )
        ]


class LessonProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    lesson_slug = models.SlugField(max_length=80)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "lesson_slug"],
                name="unique_user_lesson_progress",
            )
        ]
        ordering = ["completed_at"]

    def __str__(self):
        return f"{self.user} completed {self.lesson_slug}"


class TutorMessage(models.Model):
    class Role(models.TextChoices):
        LEARNER = "learner", "Learner"
        TUTOR = "tutor", "Tutor"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tutor_messages",
    )
    lesson_slug = models.SlugField(max_length=80)
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["user", "lesson_slug", "created_at"]),
        ]


class LearnerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="learning_profile",
    )
    display_name = models.CharField(max_length=80, blank=True)
    daily_goal = models.PositiveSmallIntegerField(default=1)
    daily_reminders = models.BooleanField(default=True)
    public_profile = models.BooleanField(default=False)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    def __str__(self):
        return f"Learning profile for {self.user}"


class LessonBookmark(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="lesson_bookmarks",
    )
    lesson_slug = models.SlugField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "lesson_slug"],
                name="unique_user_lesson_bookmark",
            )
        ]


class LessonNote(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="lesson_notes",
    )
    lesson_slug = models.SlugField(max_length=80)
    content = models.TextField(max_length=10000, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "lesson_slug"],
                name="unique_user_lesson_note",
            )
        ]


class LessonQuickCheck(models.Model):
    CONFIDENCE_CHOICES = [
        ("still_learning", "I need more practice"),
        ("getting_there", "I’m getting there"),
        ("confident", "I feel confident"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="lesson_quick_checks",
    )
    lesson_slug = models.SlugField(max_length=80)
    answer = models.TextField(max_length=2000)
    confidence = models.CharField(max_length=20, choices=CONFIDENCE_CHOICES)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "lesson_slug"],
                name="unique_user_lesson_quick_check",
            )
        ]


class QuizAttempt(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quiz_attempts",
    )
    lesson_slug = models.SlugField(max_length=80)
    score = models.PositiveSmallIntegerField()
    total = models.PositiveSmallIntegerField()
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-completed_at"]
        indexes = [
            models.Index(fields=["user", "completed_at"]),
        ]


class DailyActivity(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="learning_activity",
    )
    activity_date = models.DateField()
    lessons_completed = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-activity_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "activity_date"],
                name="unique_user_learning_activity_day",
            )
        ]


class StudyPlanItem(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="study_plan_items",
    )
    planned_for = models.DateField()
    title = models.CharField(max_length=120)
    target_minutes = models.PositiveSmallIntegerField(default=15)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["planned_for", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "planned_for", "title"],
                name="unique_user_study_plan_title",
            )
        ]


class ProjectProgress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="project_progress",
    )
    project_slug = models.SlugField(max_length=80)
    completed_milestones = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "project_slug"],
                name="unique_user_project_progress",
            )
        ]


class EarnedAchievement(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="earned_achievements",
    )
    achievement_code = models.SlugField(max_length=80)
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["earned_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "achievement_code"],
                name="unique_user_achievement",
            )
        ]


class Certificate(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="certificates",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name="certificates",
    )
    certificate_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "course"],
                name="unique_user_course_certificate",
            )
        ]


class DiscussionPost(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="discussion_posts",
    )
    title = models.CharField(max_length=140)
    body = models.TextField(max_length=10000)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class DiscussionReply(models.Model):
    post = models.ForeignKey(
        DiscussionPost,
        on_delete=models.CASCADE,
        related_name="replies",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="discussion_replies",
    )
    body = models.TextField(max_length=5000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class StudyGroup(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=110, unique=True)
    description = models.TextField(max_length=2000)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_study_groups",
    )
    max_members = models.PositiveSmallIntegerField(
        default=30,
        validators=[MinValueValidator(2), MaxValueValidator(100)],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class StudyGroupMembership(models.Model):
    class Role(models.TextChoices):
        ORGANIZER = "organizer", "Organizer"
        MEMBER = "member", "Member"

    group = models.ForeignKey(
        StudyGroup,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="study_group_memberships",
    )
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["joined_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "user"],
                name="unique_study_group_member",
            )
        ]


class CareerPrompt(models.Model):
    class Category(models.TextChoices):
        INTERVIEW = "interview", "Interview practice"
        RESUME = "resume", "Resume"
        PORTFOLIO = "portfolio", "Portfolio"

    category = models.CharField(max_length=12, choices=Category.choices)
    title = models.CharField(max_length=140)
    prompt = models.TextField()
    guidance = models.TextField()
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category", "sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["category", "title"],
                name="unique_career_prompt_title",
            )
        ]

    def __str__(self):
        return self.title


class CareerPracticeResponse(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="career_practice_responses",
    )
    prompt = models.ForeignKey(
        CareerPrompt,
        on_delete=models.CASCADE,
        related_name="responses",
    )
    answer = models.TextField(max_length=10000)
    self_rating = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    reflection = models.TextField(max_length=2000, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "prompt"],
                name="unique_user_career_response",
            )
        ]


class SubscriptionPlan(models.Model):
    code = models.SlugField(max_length=40, unique=True)
    title = models.CharField(max_length=80)
    description = models.TextField()
    monthly_price = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
    )
    currency = models.CharField(max_length=3, default="USD")
    features = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.title


class UserSubscription(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PENDING = "pending", "Pending"
        CANCELED = "canceled", "Canceled"
        PAST_DUE = "past_due", "Past due"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    provider = models.CharField(max_length=32, blank=True)
    provider_subscription_id = models.CharField(max_length=160, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user}: {self.plan.title} ({self.status})"
