from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db import models

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
    DailyActivity,
    DiscussionPost,
    DiscussionReply,
    EarnedAchievement,
    LearnerProfile,
    LessonBookmark,
    LessonNote,
    LessonProgress,
    LessonQuickCheck,
    ProjectProgress,
    QuizAttempt,
    StudyGroup,
    StudyGroupMembership,
    StudyPlanItem,
    SubscriptionPlan,
    TutorMessage,
    UserSubscription,
)

admin.site.site_header = "PyPath administration"
admin.site.site_title = "PyPath admin"
admin.site.index_title = "Platform oversight"


class ReadOnlyAuditAdmin(admin.ModelAdmin):
    list_per_page = 50

    def get_list_display(self, request):
        field_names = {field.name for field in self.model._meta.fields}
        preferred = (
            "id",
            "user",
            "course",
            "lesson",
            "module",
            "group",
            "title",
            "name",
            "status",
            "role",
            "is_active",
            "created_at",
            "updated_at",
            "completed_at",
        )
        return tuple(name for name in preferred if name in field_names)

    def get_list_filter(self, request):
        return tuple(
            field.name
            for field in self.model._meta.fields
            if isinstance(field, models.BooleanField) or field.choices
        )

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields) + tuple(
            field.name for field in self.model._meta.many_to_many
        )

    def get_search_fields(self, request):
        fields = [
            field.name
            for field in self.model._meta.fields
            if isinstance(field, models.CharField)
        ]
        user_model = get_user_model()
        for field in self.model._meta.fields:
            if (
                isinstance(field, models.ForeignKey)
                and field.remote_field.model == user_model
            ):
                fields.append(f"{field.name}__username")
        return tuple(fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class AccountAdmin(DjangoUserAdmin):
    list_display = (
        "username",
        "email",
        "is_active",
        "is_staff",
        "date_joined",
        "last_login",
    )
    list_filter = ("is_active", "is_staff", "is_superuser", "date_joined")
    search_fields = ("username", "email")
    ordering = ("-date_joined",)


user_model = get_user_model()
if admin.site.is_registered(user_model):
    admin.site.unregister(user_model)
admin.site.register(user_model, AccountAdmin)
admin.site.register(
    [
        CourseAssessmentQuestion,
        CourseAssignment,
        DailyActivity,
        EarnedAchievement,
        LearnerProfile,
        LessonBookmark,
        LessonNote,
        LessonProgress,
        LessonQuickCheck,
        ProjectProgress,
        QuizAttempt,
        StudyPlanItem,
        TutorMessage,
    ],
    ReadOnlyAuditAdmin,
)


@admin.register(LogEntry)
class AdminLogEntryAdmin(ReadOnlyAuditAdmin):
    list_display = ("action_time", "user", "content_type", "object_repr", "action_flag")
    list_filter = ("action_flag", "action_time", "content_type")
    search_fields = ("object_repr", "change_message", "user__username")


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
