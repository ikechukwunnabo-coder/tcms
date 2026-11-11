from django.contrib import admin

from .models import DailyMedicalCheck, TrainingInstructor, TrainingItem, TrainingRecord


class TrainingItemInline(admin.TabularInline):
    model = TrainingItem
    extra = 0


class TrainingInstructorInline(admin.TabularInline):
    model = TrainingInstructor
    extra = 0


class DailyMedicalCheckInline(admin.TabularInline):
    model = DailyMedicalCheck
    extra = 0


@admin.register(TrainingRecord)
class TrainingRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "learner", "course", "start_date", "end_date", "status")
    list_filter = ("status", "course")
    search_fields = ("learner__badge_no", "learner__surname")
    inlines = (TrainingItemInline, TrainingInstructorInline, DailyMedicalCheckInline)
