import json
from datetime import date, timedelta
from io import BytesIO
from urllib.error import HTTPError
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.contrib.staticfiles.finders import find
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import resolve, reverse
from django.utils import timezone

from .curriculum import LESSONS, get_tracks
from .models import (
    AssignmentSubmission,
    CareerPracticeResponse,
    CareerPrompt,
    Certificate,
    Course,
    CourseAssessmentAttempt,
    CourseAssignment,
    CourseLesson,
    DailyActivity,
    DiscussionPost,
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
    UserSubscription,
    TutorMessage,
)
from .projects import PROJECTS
from .quizzes import quiz_for_track
from .resources import RESOURCE_GROUPS
from .services import TutorServiceError, get_ai_reply, run_python_code
from .middleware import RequestAuditMiddleware
from .views import make_tutor_reply


class LearningPlatformTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_courses", verbosity=0)

    def setUp(self):
        self.user = User.objects.create_user(username="learner", password="safe-test-password")
        self.client.force_login(self.user)

    def test_seeded_course_content_is_database_backed_and_repeatable(self):
        course_count = Course.objects.count()
        lesson_count = CourseLesson.objects.count()
        self.assertEqual(course_count, 13)
        self.assertEqual(lesson_count, len(LESSONS))

        lesson = CourseLesson.objects.get(slug=LESSONS[0]["slug"])
        lesson.body = "Updated directly in the course database."
        lesson.save(update_fields=["body"])
        response = self.client.get(reverse("lesson", args=[lesson.slug]))
        self.assertContains(response, "Updated directly in the course database.")

        call_command("seed_courses", verbosity=0)
        self.assertEqual(Course.objects.count(), course_count)
        self.assertEqual(CourseLesson.objects.count(), lesson_count)

    def test_seed_courses_if_empty_preserves_existing_edits(self):
        lesson = CourseLesson.objects.get(slug=LESSONS[0]["slug"])
        lesson.title = "Custom course title"
        lesson.save(update_fields=["title"])

        call_command("seed_courses", "--if-empty", verbosity=0)

        lesson.refresh_from_db()
        self.assertEqual(lesson.title, "Custom course title")

    def test_seed_courses_missing_only_adds_java_without_overwriting_existing_lessons(self):
        lesson = CourseLesson.objects.get(slug=LESSONS[0]["slug"])
        lesson.title = "Existing custom lesson"
        lesson.save(update_fields=["title"])
        Course.objects.get(slug="java").delete()

        call_command("seed_courses", "--missing-only", verbosity=0)

        lesson.refresh_from_db()
        self.assertEqual(lesson.title, "Existing custom lesson")
        java = Course.objects.get(slug="java")
        self.assertEqual(java.track, "Java")
        self.assertEqual(java.lessons.count(), 36)
        self.assertTrue(
            CourseAssignment.objects.filter(
                slug="java-oop-library-catalog",
                course=java,
            ).exists()
        )

    def test_seed_courses_missing_only_repairs_partial_course_without_overwriting_edits(self):
        java = Course.objects.get(slug="java")
        custom_lesson = java.lessons.first()
        custom_lesson.title = "My Java lesson"
        custom_lesson.save(update_fields=["title"])
        java.lessons.exclude(pk=custom_lesson.pk).delete()
        java.assessment_questions.all().delete()
        java.assignments.all().delete()

        call_command("seed_courses", "--missing-only", verbosity=0)

        java.refresh_from_db()
        custom_lesson.refresh_from_db()
        self.assertEqual(java.lessons.count(), 36)
        self.assertEqual(custom_lesson.title, "My Java lesson")
        self.assertGreater(java.assessment_questions.count(), 0)
        self.assertTrue(
            java.assignments.filter(slug="java-oop-library-catalog").exists()
        )

    def test_chat_returns_lesson_specific_hint_and_quiz(self):
        lesson = LESSONS[0]
        hint = make_tutor_reply("give me a hint", lesson)
        quiz = make_tutor_reply("quiz me", lesson)
        explanation = make_tutor_reply("Explain this lesson", lesson)

        self.assertIn(lesson["hint"], hint)
        self.assertIn(lesson["quiz"], quiz)
        self.assertIn(lesson["body"], explanation)

    def test_chat_rejects_malformed_and_unknown_lesson(self):
        url = reverse("chat")
        malformed = self.client.post(url, data="{", content_type="application/json")
        unknown = self.client.post(
            url,
            data=json.dumps({"message": "help", "lesson": "not-a-lesson"}),
            content_type="application/json",
        )

        self.assertEqual(malformed.status_code, 400)
        self.assertEqual(unknown.status_code, 404)

    def test_completion_is_saved_once_per_user_and_lesson(self):
        url = reverse("complete_lesson", args=[LESSONS[0]["slug"]])
        first = self.client.post(url)
        second = self.client.post(url)

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(LessonProgress.objects.filter(user=self.user).count(), 1)

    def test_learning_pages_require_sign_in(self):
        self.client.logout()

        response = self.client.get(reverse("dashboard"))
        playground = self.client.get(reverse("web_playground"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
        self.assertEqual(playground.status_code, 302)

    def test_pwa_manifest_and_service_worker_are_available(self):
        manifest_path = find("manifest.webmanifest")
        worker = self.client.get(reverse("service_worker"))

        with open(manifest_path, encoding="utf-8") as manifest_file:
            manifest = json.load(manifest_file)
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["start_url"], "/")
        self.assertEqual(
            {icon["sizes"] for icon in manifest["icons"]},
            {"192x192", "512x512"},
        )
        self.assertTrue(find("pwa/icon-192.png"))
        self.assertTrue(find("pwa/icon-512.png"))
        self.assertTrue(find("pwa/apple-touch-icon.png"))
        self.assertEqual(worker.status_code, 200)
        self.assertEqual(worker["Service-Worker-Allowed"], "/")
        self.assertContains(worker, "offline.html")

    def test_base_navigation_has_an_accessible_compact_menu(self):
        self.client.logout()
        response = self.client.get(reverse("home"))

        self.assertContains(response, 'aria-controls="site-navigation"')
        self.assertContains(response, 'aria-label="Open navigation"')
        self.assertContains(response, 'id="site-navigation"')

    def test_homepage_offers_install_and_browser_instructions(self):
        self.client.logout()
        response = self.client.get(reverse("home"))

        self.assertContains(response, "Install app")
        self.assertContains(response, 'data-install-dialog')
        self.assertContains(response, 'rel="apple-touch-icon"')
        self.assertContains(response, "Add to Home Screen")

    def test_dashboard_and_lesson_render_for_signed_in_learner(self):
        dashboard = self.client.get(reverse("dashboard"))
        lesson = self.client.get(reverse("lesson", args=[LESSONS[0]["slug"]]))

        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, LESSONS[0]["title"])
        self.assertContains(dashboard, f"0 / {len(LESSONS)}")
        self.assertContains(dashboard, "Object-Oriented Python")
        self.assertContains(dashboard, reverse("course", args=["java"]))
        self.assertEqual(lesson.status_code, 200)
        self.assertContains(lesson, "Your Python tutor")
        self.assertContains(lesson, "Your lesson notes")
        self.assertContains(lesson, "Submit quiz")

    def test_homepage_lists_java_and_current_curriculum_size(self):
        self.client.logout()

        response = self.client.get(reverse("home"))

        self.assertContains(response, "Java: Beginner to Advanced OOP")
        self.assertContains(response, f">{len(LESSONS)}<")
        self.assertContains(response, "4 paths")

    def test_browser_playground_has_starter_project_and_is_sandboxed(self):
        response = self.client.get(reverse("web_playground"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Browser playground")
        self.assertContains(response, "Try the button")
        self.assertContains(response, 'sandbox="allow-scripts"')
        self.assertNotContains(response, "allow-same-origin")
        self.assertContains(response, "Preview network access is blocked")

    def test_dashboard_search_filters_lessons_and_learning_paths(self):
        response = self.client.get(reverse("dashboard"), {"q": "variables"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Variables and data types")
        self.assertNotContains(response, "JavaScript project: interactive checklist")

    def test_activity_calendar_and_lesson_sequence_render(self):
        lesson = LESSONS[1]

        dashboard = self.client.get(reverse("dashboard"))
        detail = self.client.get(reverse("lesson", args=[lesson["slug"]]))

        self.assertContains(dashboard, "Last 12 weeks")
        self.assertContains(detail, f"Lesson 2 of {len(LESSONS)}")
        self.assertContains(detail, reverse("lesson", args=[LESSONS[0]["slug"]]))
        self.assertContains(detail, reverse("lesson", args=[LESSONS[2]["slug"]]))
        self.assertContains(detail, "Lesson checklist")

    def test_completing_lessons_awards_achievement_and_xp(self):
        self.client.post(reverse("complete_lesson", args=[LESSONS[0]["slug"]]))

        self.assertTrue(
            EarnedAchievement.objects.filter(
                user=self.user,
                achievement_code="first-steps",
            ).exists()
        )
        self.assertContains(self.client.get(reverse("profile")), "10")

    def test_study_planner_is_user_scoped_and_validates_sessions(self):
        today = timezone.localdate()
        self.assertEqual(self.client.get(reverse("study_planner")).status_code, 200)
        response = self.client.post(
            reverse("study_planner"),
            {
                "title": "Practice loops",
                "planned_for": today.isoformat(),
                "target_minutes": "25",
            },
        )
        self.assertRedirects(response, reverse("study_planner"))
        item = StudyPlanItem.objects.get(user=self.user, title="Practice loops")
        self.assertEqual(item.target_minutes, 25)

        self.client.post(
            reverse("study_planner"),
            {"action": "complete", "item_id": str(item.pk)},
        )
        item.refresh_from_db()
        self.assertTrue(item.is_completed)

        next_week = today + timedelta(days=8)
        self.client.post(
            reverse("study_planner"),
            {
                "title": "Too far ahead",
                "planned_for": next_week.isoformat(),
                "target_minutes": "20",
            },
        )
        self.assertFalse(
            StudyPlanItem.objects.filter(user=self.user, title="Too far ahead").exists()
        )

        other_user = User.objects.create_user(username="planner-other", password="safe-test-password")
        self.client.force_login(other_user)
        denied = self.client.post(
            reverse("study_planner"),
            {"action": "delete", "item_id": str(item.pk)},
        )
        self.assertEqual(denied.status_code, 404)
        self.assertTrue(StudyPlanItem.objects.filter(pk=item.pk).exists())

    def test_project_milestones_are_saved_and_award_project_badge(self):
        project = PROJECTS[0]
        self.assertEqual(self.client.get(reverse("projects")).status_code, 200)
        for milestone in project["milestones"]:
            response = self.client.post(
                reverse(
                    "toggle_project_milestone",
                    args=[project["slug"], milestone["slug"]],
                )
            )
            self.assertEqual(response.status_code, 302)

        progress = ProjectProgress.objects.get(user=self.user, project_slug=project["slug"])
        self.assertEqual(len(progress.completed_milestones), 3)
        self.assertTrue(
            EarnedAchievement.objects.filter(
                user=self.user,
                achievement_code="project-builder",
            ).exists()
        )
        self.assertEqual(
            self.client.get(reverse("project_detail", args=[project["slug"]])).status_code,
            200,
        )

    def test_offline_pack_downloads_only_known_learning_paths(self):
        response = self.client.get(
            reverse("offline_download"),
            {"track": "Getting started"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertContains(response, "Variables and data types")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        invalid = self.client.get(reverse("offline_download"), {"track": "not-a-path"})
        self.assertEqual(invalid.status_code, 404)

    def test_public_profiles_are_opt_in_and_do_not_expose_private_fields(self):
        profile = LearnerProfile.objects.get_or_create(user=self.user)[0]
        profile.display_name = "Public learner"
        profile.public_profile = True
        profile.save()
        self.user.email = "learner-private@example.test"
        self.user.save(update_fields=["email"])
        LessonProgress.objects.create(user=self.user, lesson_slug=LESSONS[0]["slug"])

        response = self.client.get(
            reverse("public_learner_profile", args=[profile.public_id])
        )
        board = self.client.get(reverse("leaderboard"))

        self.assertContains(response, "Public learner")
        self.assertContains(response, "10")
        self.assertNotContains(response, self.user.email)
        self.assertContains(board, "Public learner")

        profile.public_profile = False
        profile.save(update_fields=["public_profile"])
        self.assertEqual(
            self.client.get(reverse("public_learner_profile", args=[profile.public_id])).status_code,
            404,
        )
        self.assertNotContains(self.client.get(reverse("leaderboard")), "Public learner")

    def test_profile_can_manage_public_sharing_and_in_app_reminders(self):
        response = self.client.post(
            reverse("profile"),
            {
                "display_name": "A learner",
                "daily_goal": "2",
                "daily_reminders": "on",
                "public_profile": "on",
            },
        )
        self.assertRedirects(response, reverse("profile"))
        profile = LearnerProfile.objects.get(user=self.user)
        self.assertTrue(profile.daily_reminders)
        self.assertTrue(profile.public_profile)
        self.assertContains(self.client.get(reverse("profile")), str(profile.public_id))

        self.client.post(
            reverse("profile"),
            {"display_name": "A learner", "daily_goal": "2"},
        )
        profile.refresh_from_db()
        self.assertFalse(profile.daily_reminders)
        self.assertFalse(profile.public_profile)

    def test_bookmarks_are_user_scoped_and_can_be_removed(self):
        lesson_slug = LESSONS[0]["slug"]
        self.client.post(reverse("toggle_bookmark", args=[lesson_slug]))
        self.assertTrue(
            LessonBookmark.objects.filter(user=self.user, lesson_slug=lesson_slug).exists()
        )
        self.assertContains(self.client.get(reverse("bookmarks")), LESSONS[0]["title"])

        other_user = User.objects.create_user(username="another", password="safe-test-password")
        self.client.force_login(other_user)
        self.assertNotContains(self.client.get(reverse("bookmarks")), LESSONS[0]["title"])

        self.client.force_login(self.user)
        self.client.post(reverse("toggle_bookmark", args=[lesson_slug]))
        self.assertFalse(
            LessonBookmark.objects.filter(user=self.user, lesson_slug=lesson_slug).exists()
        )

    def test_lesson_notes_are_saved_per_user(self):
        lesson_slug = LESSONS[0]["slug"]

        response = self.client.post(
            reverse("save_note", args=[lesson_slug]),
            {"content": "Remember to check the interpreter version."},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            LessonNote.objects.get(user=self.user, lesson_slug=lesson_slug).content,
            "Remember to check the interpreter version.",
        )
        self.assertContains(self.client.get(reverse("lesson", args=[lesson_slug])), "Remember to check")

    def test_lesson_quick_check_saves_private_answer_and_confidence(self):
        lesson = LESSONS[0]
        response = self.client.post(
            reverse("save_lesson_quick_check", args=[lesson["slug"]]),
            {
                "answer": "The interpreter executes the source file.",
                "confidence": "getting_there",
            },
        )

        self.assertEqual(response.status_code, 302)
        quick_check = LessonQuickCheck.objects.get(
            user=self.user, lesson_slug=lesson["slug"]
        )
        self.assertEqual(quick_check.answer, "The interpreter executes the source file.")
        self.assertEqual(quick_check.confidence, "getting_there")
        self.assertContains(
            self.client.get(reverse("lesson", args=[lesson["slug"]])),
            lesson["quiz"],
        )
        self.assertContains(
            self.client.get(reverse("lesson", args=[lesson["slug"]])),
            "The interpreter executes the source file.",
        )

        self.client.post(
            reverse("save_lesson_quick_check", args=[lesson["slug"]]),
            {"answer": "Updated answer", "confidence": "confident"},
        )
        quick_check.refresh_from_db()
        self.assertEqual(quick_check.answer, "Updated answer")
        self.assertEqual(
            LessonQuickCheck.objects.filter(
                user=self.user, lesson_slug=lesson["slug"]
            ).count(),
            1,
        )

        other_user = User.objects.create_user(
            username="quick-check-reader",
            password="safe-test-password",
        )
        self.client.force_login(other_user)
        self.assertNotContains(
            self.client.get(reverse("lesson", args=[lesson["slug"]])),
            "Updated answer",
        )

    def test_lesson_quick_check_rejects_empty_or_invalid_submission(self):
        lesson_slug = LESSONS[0]["slug"]
        for data in (
            {"answer": " ", "confidence": "confident"},
            {"answer": "An answer", "confidence": "invalid"},
            {"answer": "x" * 2001, "confidence": "confident"},
        ):
            response = self.client.post(
                reverse("save_lesson_quick_check", args=[lesson_slug]),
                data,
            )
            self.assertEqual(response.status_code, 302)

        self.assertFalse(LessonQuickCheck.objects.filter(user=self.user).exists())

    def test_quiz_scores_are_saved_and_invalid_answers_are_rejected(self):
        lesson = LESSONS[0]
        questions = quiz_for_track(lesson["track"])
        answers = {f"answer_{index}": question["answer"] for index, question in enumerate(questions)}

        response = self.client.post(reverse("submit_quiz", args=[lesson["slug"]]), answers)

        self.assertEqual(response.status_code, 302)
        attempt = QuizAttempt.objects.get(user=self.user, lesson_slug=lesson["slug"])
        self.assertEqual((attempt.score, attempt.total), (len(questions), len(questions)))
        self.assertContains(self.client.get(reverse("profile")), f"{len(questions)} / {len(questions)}")

        wrong_answers = {
            f"answer_{index}": (question["answer"] + 1) % len(question["choices"])
            for index, question in enumerate(questions)
        }
        self.client.post(reverse("submit_quiz", args=[lesson["slug"]]), wrong_answers)
        self.assertEqual(
            QuizAttempt.objects.filter(user=self.user, score=0).count(),
            1,
        )

        invalid = self.client.post(
            reverse("submit_quiz", args=[lesson["slug"]]),
            {"answer_0": "99"},
        )
        self.assertEqual(invalid.status_code, 302)
        self.assertEqual(QuizAttempt.objects.filter(user=self.user).count(), 2)

    def test_passing_final_assessment_and_completing_lessons_issues_verifiable_pdf(self):
        course = Course.objects.get(slug="object-oriented-python")
        lesson_slugs = list(
            CourseLesson.objects.filter(module__course=course)
            .order_by("sort_order", "id")
            .values_list("slug", flat=True)
        )
        LessonProgress.objects.bulk_create(
            [
                LessonProgress(user=self.user, lesson_slug=slug)
                for slug in lesson_slugs[:-1]
            ]
        )
        questions = list(course.assessment_questions.all())
        answers = {
            f"answer_{index}": question.correct_choice
            for index, question in enumerate(questions)
        }

        response = self.client.post(
            reverse("submit_course_assessment", args=[course.slug]),
            answers,
        )

        self.assertRedirects(response, reverse("course", args=[course.slug]))
        attempt = CourseAssessmentAttempt.objects.get(user=self.user, course=course)
        self.assertTrue(attempt.passed)
        self.assertFalse(Certificate.objects.filter(user=self.user, course=course).exists())
        self.client.post(reverse("complete_lesson", args=[lesson_slugs[-1]]))
        certificate = Certificate.objects.get(user=self.user, course=course)
        self.assertContains(self.client.get(reverse("certificates")), course.title)
        verify_url = reverse("verify_certificate", args=[certificate.certificate_id])
        self.assertContains(self.client.get(verify_url), "Certificate verified")
        pdf = self.client.get(
            reverse("download_certificate", args=[certificate.certificate_id])
        )
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertTrue(pdf.content.startswith(b"%PDF"))

        other_user = User.objects.create_user(username="certificate-other", password="safe-test-password")
        self.client.force_login(other_user)
        self.assertEqual(
            self.client.get(
                reverse("download_certificate", args=[certificate.certificate_id])
            ).status_code,
            404,
        )

    def test_failed_course_assessment_does_not_issue_certificate(self):
        course = Course.objects.get(slug="object-oriented-python")
        questions = list(course.assessment_questions.all())
        answers = {
            f"answer_{index}": (question.correct_choice + 1) % len(question.choices)
            for index, question in enumerate(questions)
        }

        self.client.post(
            reverse("submit_course_assessment", args=[course.slug]),
            answers,
        )

        self.assertFalse(
            CourseAssessmentAttempt.objects.get(user=self.user, course=course).passed
        )
        self.assertFalse(Certificate.objects.filter(user=self.user, course=course).exists())

    def test_assignment_submissions_are_saved_per_learner(self):
        assignment = CourseAssignment.objects.get(slug="oop-library-project")
        response = self.client.post(
            reverse(
                "submit_assignment",
                args=[assignment.course.slug, assignment.slug],
            ),
            {"content": "I modeled books and used a library class to organize them."},
        )
        self.assertRedirects(response, reverse("course", args=[assignment.course.slug]))
        submission = AssignmentSubmission.objects.get(
            assignment=assignment,
            user=self.user,
        )
        self.assertIn("library class", submission.content)

        instructor = User.objects.create_user(
            username="course-instructor",
            password="safe-test-password",
        )
        assignment.course.instructor = instructor
        assignment.course.save(update_fields=["instructor"])
        self.client.force_login(instructor)
        self.assertContains(
            self.client.get(reverse("instructor_assignments")),
            assignment.title,
        )
        self.client.post(
            reverse("instructor_assignments"),
            {
                "submission_id": str(submission.pk),
                "score": "90",
                "feedback": "Clear explanation and thoughtful design.",
            },
        )
        submission.refresh_from_db()
        self.assertEqual(submission.status, AssignmentSubmission.Status.REVIEWED)
        self.assertEqual(submission.score, 90)

        other_user = User.objects.create_user(username="assignment-other", password="safe-test-password")
        self.client.force_login(other_user)
        self.assertEqual(
            self.client.get(reverse("instructor_assignments")).status_code,
            404,
        )
        response = self.client.get(reverse("course", args=[assignment.course.slug]))
        self.assertNotContains(response, submission.content)

    def test_community_posts_and_replies_are_saved(self):
        body = (
            "I am learning modules and packages. How do you decide what belongs in each file? "
            "I want to keep related behavior together without making files too large. "
            "I am also wondering how you name a package and when you split one into subpackages. "
            "Please share an example that helped you organize a growing project."
        )
        response = self.client.post(
            reverse("community"),
            {
                "title": "How do you organize a Python project?",
                "body": body,
            },
        )
        post = DiscussionPost.objects.get(author=self.user)
        self.assertRedirects(response, reverse("discussion_detail", args=[post.pk]))
        community_response = self.client.get(reverse("community"))
        self.assertContains(community_response, post.title)
        self.assertContains(community_response, body)
        self.client.post(
            reverse("discussion_detail", args=[post.pk]),
            {"body": "I keep each module focused on one related responsibility."},
        )
        self.assertEqual(post.replies.count(), 1)
        self.assertContains(
            self.client.get(reverse("discussion_detail", args=[post.pk])),
            "focused on one related responsibility",
        )

    def test_study_group_capacity_and_membership_are_enforced(self):
        self.client.post(
            reverse("study_groups"),
            {
                "name": "Python practice circle",
                "description": "A small group for practicing Python together each week.",
                "max_members": "2",
            },
        )
        group = StudyGroup.objects.get(name="Python practice circle")
        self.assertContains(self.client.get(reverse("study_groups")), group.name)
        self.assertTrue(
            StudyGroupMembership.objects.filter(
                group=group,
                user=self.user,
                role=StudyGroupMembership.Role.ORGANIZER,
            ).exists()
        )

        other_user = User.objects.create_user(username="group-member", password="safe-test-password")
        self.client.force_login(other_user)
        self.client.post(
            reverse("toggle_study_group_membership", args=[group.slug])
        )
        self.assertEqual(group.memberships.count(), 2)

        third_user = User.objects.create_user(username="group-full", password="safe-test-password")
        self.client.force_login(third_user)
        self.client.post(
            reverse("toggle_study_group_membership", args=[group.slug])
        )
        self.assertEqual(group.memberships.count(), 2)

    def test_career_responses_are_private_and_free_plan_is_selectable(self):
        prompt = CareerPrompt.objects.filter(
            category=CareerPrompt.Category.INTERVIEW,
        ).first()
        self.client.post(
            reverse("save_career_response", args=[prompt.pk]),
            {
                "answer": "I built a small application that helped me practice data modeling.",
                "self_rating": "4",
                "reflection": "I will explain the tradeoffs more clearly next time.",
            },
        )
        saved = CareerPracticeResponse.objects.get(user=self.user, prompt=prompt)
        self.assertEqual(saved.self_rating, 4)
        self.assertContains(self.client.get(reverse("career_center")), prompt.title)

        self.assertContains(self.client.get(reverse("subscription_plans")), "Premium")
        self.client.post(
            reverse("subscription_plans"),
            {"plan": "free"},
        )
        self.assertEqual(
            UserSubscription.objects.get(user=self.user).plan.code,
            "free",
        )
        self.client.post(
            reverse("subscription_plans"),
            {"plan": "premium"},
        )
        self.assertEqual(
            UserSubscription.objects.get(user=self.user).plan.code,
            "free",
        )

        other_user = User.objects.create_user(username="career-other", password="safe-test-password")
        self.client.force_login(other_user)
        response = self.client.get(reverse("career_center"))
        self.assertNotContains(response, saved.answer)

    def test_staff_dashboard_is_restricted_and_renders_platform_totals(self):
        self.assertEqual(self.client.get(reverse("admin_dashboard")).status_code, 404)
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.assertContains(self.client.get(reverse("admin_dashboard")), "Platform administration")

    def test_daily_goal_profile_and_streak_use_saved_completions(self):
        lesson_slug = LESSONS[0]["slug"]
        self.client.post(reverse("complete_lesson", args=[lesson_slug]))
        self.client.post(reverse("complete_lesson", args=[lesson_slug]))

        activity = DailyActivity.objects.get(user=self.user)
        self.assertEqual(activity.lessons_completed, 1)
        dashboard = self.client.get(reverse("dashboard"))
        self.assertContains(dashboard, "Today: 1 / 1 lessons")
        self.assertContains(dashboard, "1 day current streak")

        response = self.client.post(
            reverse("profile"),
            {"display_name": "Python Learner", "daily_goal": "3"},
        )
        self.assertEqual(response.status_code, 302)
        learner_profile = LearnerProfile.objects.get(user=self.user)
        self.assertEqual(learner_profile.display_name, "Python Learner")
        self.assertEqual(learner_profile.daily_goal, 3)

    @patch("tutor.views.timezone.localdate", return_value=date(2025, 1, 10))
    def test_streak_counts_consecutive_days_and_expires_after_a_gap(self, mock_localdate):
        DailyActivity.objects.create(
            user=self.user, activity_date=date(2025, 1, 8), lessons_completed=1
        )
        DailyActivity.objects.create(
            user=self.user, activity_date=date(2025, 1, 9), lessons_completed=1
        )

        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "2 days current streak")

        DailyActivity.objects.filter(user=self.user, activity_date=date(2025, 1, 8)).delete()
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "1 day current streak")

    def test_signup_creates_and_signs_in_a_learner(self):
        self.client.logout()
        response = self.client.post(
            reverse("signup"),
            {
                "username": "new-learner",
                "email": "new-learner@example.test",
                "password1": "a-very-safe-password-384!",
                "password2": "a-very-safe-password-384!",
            },
        )

        self.assertRedirects(response, reverse("dashboard"))
        self.assertTrue(
            User.objects.filter(username="new-learner").exists()
        )
        self.assertTrue(User.objects.get(username="new-learner").is_active)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_password_reset_email_route_is_removed(self):
        response = self.client.get("/accounts/password-reset/")

        self.assertEqual(response.status_code, 404)

    def test_two_accounts_can_share_username_and_log_in_by_email(self):
        self.client.logout()
        first_password = "First-safe-password-384!"
        second_password = "Second-safe-password-384!"
        signup_url = reverse("signup")

        first_response = self.client.post(
            signup_url,
            {
                "username": "developer",
                "email": "user1@example.test",
                "password1": first_password,
                "password2": first_password,
            },
        )
        self.assertRedirects(first_response, reverse("dashboard"))
        first_user = User.objects.get(email="user1@example.test")

        self.client.logout()
        second_response = self.client.post(
            signup_url,
            {
                "username": "developer",
                "email": "user2@example.test",
                "password1": second_password,
                "password2": second_password,
            },
        )
        self.assertRedirects(second_response, reverse("dashboard"))
        second_user = User.objects.get(email="user2@example.test")
        self.assertNotEqual(first_user.pk, second_user.pk)

        self.client.logout()
        login_url = reverse("login")
        self.assertRedirects(
            self.client.post(
                login_url,
                {"username": "user1@example.test", "password": first_password},
            ),
            reverse("dashboard"),
        )
        first_user.set_password("Changed-first-password-384!")
        first_user.save(update_fields=["password"])

        self.client.logout()
        self.assertRedirects(
            self.client.post(
                login_url,
                {"username": "user2@example.test", "password": second_password},
            ),
            reverse("dashboard"),
        )
        second_user.refresh_from_db()
        self.assertTrue(second_user.check_password(second_password))

    def test_signup_rejects_case_insensitive_duplicate_email(self):
        User.objects.create_user(
            username="existing",
            email="learner@example.test",
            password="Existing-safe-password-384!",
        )
        self.client.logout()

        response = self.client.post(
            reverse("signup"),
            {
                "username": "another-name",
                "email": "LEARNER@example.test",
                "password1": "Another-safe-password-384!",
                "password2": "Another-safe-password-384!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this email address already exists.")
        self.assertEqual(User.objects.filter(email__iexact="learner@example.test").count(), 1)

    def test_curriculum_spans_all_tracks_and_keeps_slugs_unique(self):
        slugs = [lesson["slug"] for lesson in LESSONS]
        tracks = get_tracks()
        oop_lessons = next(
            track["lessons"]
            for track in tracks
            if track["title"] == "Object-oriented Python"
        )

        self.assertEqual(len(LESSONS), 142)
        self.assertEqual(len(slugs), len(set(slugs)))
        self.assertEqual(len(tracks), 13)
        self.assertEqual(len(oop_lessons), 10)
        self.assertTrue(all(lesson["exercise"] for lesson in LESSONS))

    def test_database_lesson_teaches_postgresql_with_environment_credentials(self):
        lesson = CourseLesson.objects.get(slug="postgresql-and-databases")
        self.assertEqual(lesson.title, "PostgreSQL and databases")
        self.assertIn('os.environ["DATABASE_URL"]', lesson.example)
        self.assertIn("VALUES (%s)", lesson.example)
        self.assertFalse(CourseLesson.objects.filter(slug="sqlite-and-databases").exists())

        response = self.client.get(reverse("lesson", args=[lesson.slug]))
        self.assertContains(response, "psycopg")
        self.assertNotContains(response, "sqlite3")

    def test_javascript_and_html_css_courses_cover_beginner_to_advanced_topics(self):
        tracks = {track["title"]: track["lessons"] for track in get_tracks()}

        self.assertEqual(len(tracks["JavaScript"]), 30)
        self.assertEqual(len(tracks["HTML and CSS"]), 30)
        self.assertTrue(all(lesson["language"] == "JavaScript" for lesson in tracks["JavaScript"]))
        self.assertTrue(all(lesson["language"] == "HTML and CSS" for lesson in tracks["HTML and CSS"]))
        javascript_titles = {lesson["title"] for lesson in tracks["JavaScript"]}
        html_titles = {lesson["title"] for lesson in tracks["HTML and CSS"]}
        self.assertIn("Closures and function factories", javascript_titles)
        self.assertIn("Fetch, HTTP status, and request cancellation", javascript_titles)
        self.assertIn("The cascade, specificity, and inheritance", html_titles)
        self.assertIn("Container queries and logical properties", html_titles)

    def test_java_course_covers_oop_from_beginner_to_advanced_with_runnable_examples(self):
        java_lessons = [
            lesson for lesson in LESSONS if lesson["track"] == "Java"
        ]
        levels = {lesson["level"] for lesson in java_lessons}

        self.assertEqual(len(java_lessons), 36)
        self.assertEqual(levels, {"Start here", "Beginner", "Intermediate", "Advanced"})
        self.assertTrue(
            all("public static void main" in lesson["example"] for lesson in java_lessons)
        )
        self.assertTrue(
            all(lesson["language"] == "Java" and lesson["exercise"] for lesson in java_lessons)
        )

    def test_new_course_pages_render_their_language_specific_lessons(self):
        javascript = self.client.get(reverse("course", args=["javascript"]))
        html_css = self.client.get(reverse("course", args=["html-css"]))
        java = self.client.get(reverse("course", args=["java"]))

        self.assertEqual(javascript.status_code, 200)
        self.assertContains(javascript, "JavaScript and the browser")
        self.assertContains(javascript, "JavaScript project: interactive checklist")
        self.assertContains(javascript, "30 LESSONS")
        self.assertEqual(html_css.status_code, 200)
        self.assertContains(html_css, "What HTML and CSS do")
        self.assertContains(html_css, "Accessibility and portfolio page project")
        self.assertContains(html_css, "30 LESSONS")
        self.assertEqual(java.status_code, 200)
        self.assertContains(java, "Java: Beginner to Advanced OOP")
        self.assertContains(java, "Capstone: design an object-oriented library")
        self.assertContains(java, "36 LESSONS")

    def test_java_lessons_show_the_java_runner_and_reject_other_runner_languages(self):
        lesson = next(item for item in LESSONS if item["slug"] == "java-first-program")

        response = self.client.get(reverse("lesson", args=[lesson["slug"]]))
        unsupported = self.client.post(
            reverse("run_code"),
            data=json.dumps(
                {
                    "code": "print('not supported')",
                    "language": "JavaScript",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Java code")
        self.assertContains(response, "public class Main")
        self.assertEqual(unsupported.status_code, 400)

    def test_non_python_lesson_uses_matching_tutor_and_hides_python_runner(self):
        lesson = next(item for item in LESSONS if item["slug"] == "javascript-getting-started")

        response = self.client.get(reverse("lesson", args=[lesson["slug"]]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your JavaScript tutor")
        self.assertNotContains(response, "Practice in the sandbox")

    def test_oop_course_page_shows_a_complete_learning_path(self):
        response = self.client.get(reverse("oop_course"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Object-Oriented Python")
        self.assertContains(response, "Polymorphism and duck typing")
        self.assertContains(response, "OOP project: a small library")
        self.assertContains(response, "0 / 10")

    def test_resources_page_includes_verified_video_and_written_resources(self):
        response = self.client.get(reverse("resources"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Corey Schafer")
        self.assertContains(response, "freeCodeCamp.org")
        self.assertContains(response, "ArjanCodes")
        self.assertContains(response, "MDN: JavaScript Guide")
        self.assertContains(response, "MDN: Learn web development")
        self.assertContains(response, "Python Classes")
        self.assertContains(response, "Real Python: Object-Oriented Programming")
        self.assertContains(response, 'rel="noopener noreferrer"')
        self.assertGreaterEqual(
            sum(len(group["resources"]) for group in RESOURCE_GROUPS),
            10,
        )

    @override_settings(
        AI_API_KEY="test-key",
        AI_API_BASE_URL="https://provider.test/v1",
        AI_MODEL="test-model",
        AI_API_TIMEOUT=45,
    )
    @patch("tutor.services.urlopen")
    def test_ai_tutor_uses_lesson_context_and_chat_history(self, mock_urlopen):
        mock_urlopen.return_value = BytesIO(
            json.dumps(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [{"text": "A helpful explanation."}]
                            }
                        }
                    ]
                }
            ).encode()
        )
        history = [
            {"role": "user", "content": "What is a variable?"},
            {"role": "assistant", "content": "A named place to store a value."},
        ]

        reply = get_ai_reply("Explain it again", LESSONS[0], history)

        self.assertEqual(reply, "A helpful explanation.")
        request = mock_urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(
            request.full_url,
            "https://provider.test/v1/models/test-model:generateContent",
        )
        self.assertEqual(
            payload["contents"][0],
            {"role": "user", "parts": [{"text": history[0]["content"]}]},
        )
        self.assertEqual(
            payload["contents"][1],
            {"role": "model", "parts": [{"text": history[1]["content"]}]},
        )
        self.assertEqual(request.get_header("X-goog-api-key"), "test-key")
        self.assertIsNone(request.get_header("Authorization"))
        self.assertEqual(mock_urlopen.call_args.kwargs["timeout"], 45)
        self.assertIn(
            LESSONS[0]["title"],
            payload["systemInstruction"]["parts"][0]["text"],
        )
        self.assertEqual(payload["generationConfig"]["maxOutputTokens"], 700)

    @override_settings(
        AI_API_KEY="test-key",
        AI_API_BASE_URL="https://provider.test/v1",
        AI_MODEL="test-model",
    )
    @patch("tutor.services.urlopen")
    def test_ai_tutor_uses_the_current_course_language(self, mock_urlopen):
        mock_urlopen.return_value = BytesIO(
            json.dumps(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [{"text": "Use a const binding."}]
                            }
                        }
                    ]
                }
            ).encode()
        )
        javascript_lesson = next(
            lesson for lesson in LESSONS if lesson["slug"] == "javascript-values-and-variables"
        )

        get_ai_reply("How do I declare a constant?", javascript_lesson, [])

        payload = json.loads(mock_urlopen.call_args.args[0].data)
        self.assertIn(
            "Course language: JavaScript",
            payload["systemInstruction"]["parts"][0]["text"],
        )

    @override_settings(
        AI_API_KEY="test-secret",
        AI_API_BASE_URL="https://provider.test/v1",
        AI_MODEL="unavailable-model",
    )
    @patch("tutor.services.urlopen")
    def test_ai_provider_errors_explain_failure_without_leaking_key(self, mock_urlopen):
        body = json.dumps(
            {"error": {"message": "Model unavailable for this API key."}}
        ).encode()
        mock_urlopen.side_effect = HTTPError(
            "https://provider.test/v1/models/unavailable-model:generateContent",
            404,
            "Not Found",
            {},
            BytesIO(body),
        )

        with self.assertRaisesRegex(TutorServiceError, "Model unavailable") as raised:
            get_ai_reply("Help me", LESSONS[0], [])

        self.assertNotIn("test-secret", str(raised.exception))

    @override_settings(
        AI_API_KEY="test-key",
        AI_API_BASE_URL="https://provider.test/v1",
        AI_MODEL="test-model",
    )
    @patch("tutor.services.urlopen")
    def test_ai_tutor_handles_non_json_provider_response(self, mock_urlopen):
        mock_urlopen.return_value = BytesIO(b"<html>upstream error</html>")

        with self.assertRaisesRegex(TutorServiceError, "invalid response"):
            get_ai_reply("Help me", LESSONS[0], [])

    @override_settings(
        AI_API_KEY="test-key",
        AI_API_BASE_URL=(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-flash-latest:generateContent"
        ),
        AI_MODEL="gemini-flash-latest",
    )
    @patch("tutor.services.urlopen")
    def test_ai_tutor_uses_a_full_gemini_generate_content_url(self, mock_urlopen):
        mock_urlopen.return_value = BytesIO(
            json.dumps(
                {
                    "candidates": [
                        {"content": {"parts": [{"text": "Gemini is ready."}]}}
                    ]
                }
            ).encode()
        )

        reply = get_ai_reply("Say hello", LESSONS[0], [])

        self.assertEqual(reply, "Gemini is ready.")
        self.assertEqual(
            mock_urlopen.call_args.args[0].full_url,
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-flash-latest:generateContent",
        )

    @override_settings(
        AI_API_KEY="test-key",
        AI_API_BASE_URL="https://provider.test/v1beta/openai",
        AI_MODEL="test-model",
    )
    @patch("tutor.services.urlopen")
    def test_ai_tutor_migrates_legacy_openai_base_path(self, mock_urlopen):
        mock_urlopen.return_value = BytesIO(
            json.dumps(
                {
                    "candidates": [
                        {"content": {"parts": [{"text": "Gemini is ready."}]}}
                    ]
                }
            ).encode()
        )

        get_ai_reply("Say hello", LESSONS[0], [])

        self.assertEqual(
            mock_urlopen.call_args.args[0].full_url,
            "https://provider.test/v1beta/models/test-model:generateContent",
        )

    @patch("tutor.views.get_ai_reply", return_value="Try using a for loop.")
    def test_chat_saves_history_per_user_and_lesson(self, mock_get_ai_reply):
        response = self.client.post(
            reverse("chat"),
            data=json.dumps(
                {"message": "How do I repeat this?", "lesson": LESSONS[0]["slug"]}
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(TutorMessage.objects.filter(user=self.user).count(), 2)
        self.assertEqual(mock_get_ai_reply.call_args.args[2], [])

        self.client.post(
            reverse("chat"),
            data=json.dumps(
                {"message": "And what about while?", "lesson": LESSONS[0]["slug"]}
            ),
            content_type="application/json",
        )
        history = mock_get_ai_reply.call_args.args[2]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[1]["role"], "assistant")

    @patch(
        "tutor.views.get_ai_reply",
        side_effect=TutorServiceError("Gemini returned an unavailable response."),
    )
    def test_chat_reports_gemini_errors_as_json(self, mock_get_ai_reply):
        response = self.client.post(
            reverse("chat"),
            data=json.dumps(
                {"message": "Explain this topic", "lesson": LESSONS[0]["slug"]}
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(
            response.json(),
            {"error": "Gemini returned an unavailable response."},
        )
        mock_get_ai_reply.assert_called_once()

    @patch("tutor.views.run_python_code", return_value={
        "stdout": "Hello\n",
        "stderr": "",
        "status": "Accepted",
    })
    def test_code_runner_endpoint_sends_code_to_sandbox(self, mock_run_python_code):
        response = self.client.post(
            reverse("run_code"),
            data=json.dumps({"code": 'print("Hello")', "stdin": ""}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stdout"], "Hello\n")
        mock_run_python_code.assert_called_once_with('print("Hello")', "")

    @patch(
        "tutor.views.run_python_code",
        return_value={"stdout": "Java is ready!\n", "stderr": "", "status": "Accepted"},
    )
    def test_java_code_runner_uses_configured_java_language(self, mock_run_python_code):
        response = self.client.post(
            reverse("run_code"),
            data=json.dumps(
                {
                    "code": 'public class Main { public static void main(String[] args) { System.out.println("Java is ready!"); } }',
                    "language": "Java",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stdout"], "Java is ready!\n")
        mock_run_python_code.assert_called_once_with(
            'public class Main { public static void main(String[] args) { System.out.println("Java is ready!"); } }',
            "",
            language_id=settings.CODE_RUNNER_JAVA_LANGUAGE_ID,
        )

    def test_code_runner_endpoint_rejects_empty_code(self):
        response = self.client.post(
            reverse("run_code"),
            data=json.dumps({"code": "  "}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    @override_settings(
        CODE_RUNNER_URL="https://runner.test",
        CODE_RUNNER_API_KEY="test-runner-key",
        CODE_RUNNER_LANGUAGE_ID=123,
    )
    @patch("tutor.services.urlopen")
    def test_sandbox_request_has_resource_limits(self, mock_urlopen):
        mock_urlopen.return_value = BytesIO(
            json.dumps(
                {
                    "stdout": "2\n",
                    "stderr": None,
                    "status": {"description": "Accepted"},
                }
            ).encode()
        )

        result = run_python_code("print(1 + 1)", "input")

        self.assertEqual(result["stdout"], "2\n")
        request = mock_urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(request.full_url, "https://runner.test/submissions?base64_encoded=false&wait=true")
        self.assertEqual(payload["language_id"], 123)
        self.assertEqual(payload["cpu_time_limit"], 2)
        self.assertEqual(payload["wall_time_limit"], 5)
        self.assertEqual(payload["memory_limit"], 128000)
        self.assertEqual(payload["stdin"], "input")
        self.assertEqual(request.headers["X-auth-token"], "test-runner-key")


class AdminOversightTests(TestCase):
    def test_successful_signup_is_written_to_application_logs(self):
        with self.assertLogs("tutor.views", level="INFO") as account_logs:
            response = self.client.post(
                reverse("signup"),
                {
                    "username": "audited-learner",
                    "email": "audited-learner@example.test",
                    "password1": "Audited-learner-password-384!",
                    "password2": "Audited-learner-password-384!",
                },
            )

        self.assertRedirects(response, reverse("dashboard"))
        self.assertIn("Learner account created (user_id=", account_logs.output[0])

    def test_superuser_can_review_registered_user_accounts(self):
        admin_user = User.objects.create_superuser(
            username="site-owner",
            email="owner@example.test",
            password="Admin-review-password-384!",
        )
        learner = User.objects.create_user(
            username="registered-learner",
            email="learner@example.test",
            password="Learner-review-password-384!",
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse("admin:auth_user_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, learner.username)
        self.assertContains(response, learner.email)

    def test_bootstrap_command_creates_admin_once_without_resetting_password(self):
        credentials = {
            "DJANGO_SUPERUSER_USERNAME": "bootstrap-owner",
            "DJANGO_SUPERUSER_EMAIL": "bootstrap-owner@example.test",
            "DJANGO_SUPERUSER_PASSWORD": "Bootstrap-only-password-384!",
        }
        with patch.dict("os.environ", credentials):
            call_command("bootstrap_admin", verbosity=0)
            admin_user = User.objects.get(username=credentials["DJANGO_SUPERUSER_USERNAME"])
            original_password_hash = admin_user.password

            with patch.dict(
                "os.environ",
                {"DJANGO_SUPERUSER_PASSWORD": ""},
            ):
                call_command("bootstrap_admin", verbosity=0)

        admin_user.refresh_from_db()
        self.assertTrue(admin_user.is_superuser)
        self.assertEqual(admin_user.password, original_password_hash)
        self.assertTrue(
            admin_user.check_password(credentials["DJANGO_SUPERUSER_PASSWORD"])
        )

    def test_bootstrap_command_rejects_partial_credentials(self):
        credentials = {
            "DJANGO_SUPERUSER_USERNAME": "partial-owner",
            "DJANGO_SUPERUSER_EMAIL": "",
            "DJANGO_SUPERUSER_PASSWORD": "",
        }
        with patch.dict("os.environ", credentials):
            with self.assertRaises(CommandError):
                call_command("bootstrap_admin", verbosity=0)


class RequestAuditMiddlewareTests(TestCase):
    def test_api_request_log_includes_user_and_safe_route_without_query_or_body(self):
        user = User.objects.create_user(
            username="audit-learner",
            email="audit-learner@example.test",
            password="Audit-learner-password-384!",
        )
        path = reverse("chat")
        request = RequestFactory().post(
            f"{path}?token=private-query-token",
            data="private-request-body",
            content_type="text/plain",
        )
        request.user = user
        middleware = RequestAuditMiddleware(
            lambda _request: HttpResponse(status=202)
        )

        with self.assertLogs("tutor.access", level="INFO") as request_logs:
            response = middleware(request)

        event = json.loads(request_logs.records[0].getMessage())
        self.assertEqual(response.status_code, 202)
        self.assertEqual(event["event"], "http_request")
        self.assertEqual(event["method"], "POST")
        self.assertEqual(event["route"], resolve(path).route)
        self.assertEqual(event["status"], 202)
        self.assertEqual(event["user"]["username"], user.username)
        self.assertEqual(event["user"]["email"], user.email)
        self.assertNotIn("private-query-token", request_logs.records[0].getMessage())
        self.assertNotIn("private-request-body", request_logs.records[0].getMessage())
