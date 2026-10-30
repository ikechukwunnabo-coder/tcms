from django.contrib import admin

from .models import Learner, LearnerContact, LearnerDocument


class LearnerContactInline(admin.TabularInline):
    model = LearnerContact
    extra = 0


class LearnerDocumentInline(admin.TabularInline):
    model = LearnerDocument
    extra = 0


@admin.register(Learner)
class LearnerAdmin(admin.ModelAdmin):
    list_display = ("badge_no", "surname", "first_name", "company", "active")
    list_filter = ("active", "company")
    search_fields = ("badge_no", "surname", "first_name")
    inlines = (LearnerContactInline, LearnerDocumentInline)
