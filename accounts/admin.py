from django.contrib import admin

from .models import AuditLog, Membership, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
	list_display = ("user", "external_id", "email_verified", "created_at")
	search_fields = ("external_id", "user__username", "user__email")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
	list_display = ("user", "project", "role", "created_at")
	list_filter = ("role",)
	search_fields = ("user__username", "project__name")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
	list_display = ("action", "actor", "target_type", "target_id", "created_at")
	list_filter = ("action", "target_type")
	search_fields = ("actor__username", "target_id")
	readonly_fields = ("id", "actor", "action", "target_type", "target_id", "metadata", "created_at")
