from django.contrib import admin

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
    CourseModule,
    DiscussionPost,
    DiscussionReply,
    StudyGroup,
    StudyGroupMembership,
    SubscriptionPlan,
    UserSubscription,
)


class CourseModuleInline(admin.TabularInline):
    model = CourseModule
    extra = 0


class CourseLessonInline(admin.TabularInline):
    model = CourseLesson
    extra = 0
    fields = ("sort_order", "title", "slug", "level", "language")
    show_change_link = True


class CourseAssessmentQuestionInline(admin.TabularInline):
    model = CourseAssessmentQuestion
    extra = 0


class CourseAssignmentInline(admin.TabularInline):
    model = CourseAssignment
    extra = 0


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "track",
        "instructor",
        "is_published",
        "passing_score_percentage",
        "sort_order",
    )
    list_filter = ("is_published", "instructor")
    search_fields = ("title", "track", "description", "instructor__username")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [
        CourseModuleInline,
        CourseAssessmentQuestionInline,
        CourseAssignmentInline,
    ]


@admin.register(CourseModule)
class CourseModuleAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "sort_order")
    list_filter = ("course",)
    search_fields = ("title", "course__title")
    inlines = [CourseLessonInline]


@admin.register(CourseLesson)
class CourseLessonAdmin(admin.ModelAdmin):
    list_display = ("title", "module", "level", "language", "sort_order")
    list_filter = ("level", "language", "module__course")
    search_fields = ("title", "slug", "summary", "body", "exercise")


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ("assignment", "user", "status", "score", "submitted_at")
    list_filter = ("status", "assignment__course")
    search_fields = ("assignment__title", "user__username", "content")
    readonly_fields = ("assignment", "user", "content", "submitted_at")


@admin.register(CourseAssessmentAttempt)
class CourseAssessmentAttemptAdmin(admin.ModelAdmin):
    list_display = ("course", "user", "score", "total", "passed", "completed_at")
    list_filter = ("passed", "course")
    search_fields = ("user__username", "course__title")
    readonly_fields = ("user", "course", "score", "total", "passed", "answers", "completed_at")


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ("certificate_id", "user", "course", "issued_at")
    search_fields = ("user__username", "course__title", "certificate_id")
    readonly_fields = ("certificate_id", "issued_at")


@admin.register(DiscussionPost)
class DiscussionPostAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "is_published", "created_at")
    list_filter = ("is_published", "created_at")
    search_fields = ("title", "body", "author__username")


@admin.register(DiscussionReply)
class DiscussionReplyAdmin(admin.ModelAdmin):
    list_display = ("post", "author", "created_at")
    search_fields = ("post__title", "body", "author__username")


@admin.register(StudyGroup)
class StudyGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "created_by", "is_active", "max_members", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "description", "created_by__username")


@admin.register(StudyGroupMembership)
class StudyGroupMembershipAdmin(admin.ModelAdmin):
    list_display = ("group", "user", "role", "joined_at")
    list_filter = ("role",)
    search_fields = ("group__name", "user__username")


@admin.register(CareerPrompt)
class CareerPromptAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "is_active", "sort_order")
    list_filter = ("category", "is_active")
    search_fields = ("title", "prompt", "guidance")


@admin.register(CareerPracticeResponse)
class CareerPracticeResponseAdmin(admin.ModelAdmin):
    list_display = ("prompt", "user", "self_rating", "updated_at")
    list_filter = ("prompt__category",)
    search_fields = ("prompt__title", "user__username", "answer")


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ("title", "code", "monthly_price", "currency", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("title", "code", "description")


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "status", "provider", "started_at")
    list_filter = ("status", "plan")
    search_fields = ("user__username", "provider_subscription_id")
