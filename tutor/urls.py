from django.urls import path

from . import views


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("courses/object-oriented-python/", views.object_oriented_course, name="oop_course"),
    path("courses/<slug:slug>/", views.course_detail, name="course"),
    path("courses/<slug:slug>/assessment/", views.submit_course_assessment, name="submit_course_assessment"),
    path(
        "courses/<slug:course_slug>/assignments/<slug:assignment_slug>/submit/",
        views.submit_assignment,
        name="submit_assignment",
    ),
    path("resources/", views.resources, name="resources"),
    path("playground/", views.web_playground, name="web_playground"),
    path("planner/", views.study_planner, name="study_planner"),
    path("projects/", views.projects, name="projects"),
    path("projects/<slug:slug>/", views.project_detail, name="project_detail"),
    path(
        "projects/<slug:slug>/milestones/<slug:milestone_slug>/toggle/",
        views.toggle_project_milestone,
        name="toggle_project_milestone",
    ),
    path("offline-download/", views.offline_download, name="offline_download"),
    path("leaderboard/", views.leaderboard, name="leaderboard"),
    path("community/", views.community, name="community"),
    path("community/<int:post_id>/", views.discussion_detail, name="discussion_detail"),
    path("study-groups/", views.study_groups, name="study_groups"),
    path(
        "study-groups/<slug:slug>/membership/",
        views.toggle_study_group_membership,
        name="toggle_study_group_membership",
    ),
    path("career/", views.career_center, name="career_center"),
    path(
        "career/prompts/<int:prompt_id>/respond/",
        views.save_career_response,
        name="save_career_response",
    ),
    path("certificates/", views.certificates, name="certificates"),
    path(
        "certificates/verify/<uuid:certificate_id>/",
        views.verify_certificate,
        name="verify_certificate",
    ),
    path(
        "certificates/<uuid:certificate_id>/download/",
        views.download_certificate,
        name="download_certificate",
    ),
    path("plans/", views.subscription_plans, name="subscription_plans"),
    path("staff-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("instructor/assignments/", views.instructor_assignments, name="instructor_assignments"),
    path("learners/<uuid:public_id>/", views.public_learner_profile, name="public_learner_profile"),
    path("lesson/<slug:slug>/", views.lesson_detail, name="lesson"),
    path("lesson/<slug:slug>/complete/", views.complete_lesson, name="complete_lesson"),
    path("lesson/<slug:slug>/bookmark/", views.toggle_bookmark, name="toggle_bookmark"),
    path("lesson/<slug:slug>/notes/", views.save_note, name="save_note"),
    path("lesson/<slug:slug>/quiz/", views.submit_quiz, name="submit_quiz"),
    path("bookmarks/", views.bookmarks, name="bookmarks"),
    path("profile/", views.profile, name="profile"),
    path("chat/", views.chat, name="chat"),
    path("run-code/", views.run_code, name="run_code"),
]
