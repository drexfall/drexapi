from django.contrib import admin

from .models import Outbox, Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
	list_display = ("name", "slug", "owner", "status", "created_at")
	list_filter = ("status",)
	search_fields = ("name", "slug")
	readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Outbox)
class OutboxAdmin(admin.ModelAdmin):
	list_display = ("event_type", "aggregate_id", "status", "attempts", "created_at", "processed_at")
	list_filter = ("status", "event_type")
	search_fields = ("aggregate_id",)
	readonly_fields = ("id", "event_type", "aggregate_id", "payload", "created_at", "processed_at")
