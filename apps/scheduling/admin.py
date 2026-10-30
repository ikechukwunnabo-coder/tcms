from django.contrib import admin

from .models import CourseSession, Enrolment, Instructor, SessionInstructor, Venue


class SessionInstructorInline(admin.TabularInline):
    model = SessionInstructor
    extra = 0


@admin.register(CourseSession)
class CourseSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "course",
        "venue",
        "start_date",
        "end_date",
        "capacity",
        "seats_taken",
        "reserve_pct",
        "status",
    )
    list_filter = ("status", "venue")
    inlines = (SessionInstructorInline,)


@admin.register(Enrolment)
class EnrolmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "learner",
        "requested_session",
        "session",
        "state",
        "status",
        "booking_ref",
    )
    list_filter = ("state", "status")
    search_fields = ("booking_ref",)


admin.site.register(Venue)
admin.site.register(Instructor)
