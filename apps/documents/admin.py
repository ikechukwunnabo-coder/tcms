from django.contrib import admin

from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "owner_type", "owner_id", "generated_at")
    list_filter = ("kind",)
    search_fields = ("object_key", "sha256")
