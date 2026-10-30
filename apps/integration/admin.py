from django.contrib import admin

from .models import ExternalRef, OutboxEvent, SeedMarker, WebhookDelivery


@admin.register(OutboxEvent)
class OutboxEventAdmin(admin.ModelAdmin):
    list_display = ("id", "topic", "status", "attempts", "created_at", "processed_at")
    list_filter = ("status", "topic")


admin.site.register(WebhookDelivery)
admin.site.register(ExternalRef)
admin.site.register(SeedMarker)
