from django.contrib import admin

from .models import Notification, NotificationTemplate


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ("code", "channel", "subject")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "template_code", "recipient", "channel", "status", "sent_at")
    list_filter = ("status", "channel")
    search_fields = ("recipient", "template_code")
