from rest_framework import serializers

from accounts.models import Role

from .models import Project


class ProjectSerializer(serializers.ModelSerializer):
	class Meta:
		model = Project
		fields = (
			"id", "slug", "name", "description", "owner",
			"status", "metadata", "created_at", "updated_at",
		)
		read_only_fields = ("id", "slug", "owner", "status", "created_at", "updated_at")


class ProjectWriteSerializer(serializers.Serializer):
	name = serializers.CharField(max_length=120)
	description = serializers.CharField(required=False, allow_blank=True, default="")
	metadata = serializers.JSONField(required=False, default=dict)


class ProjectPatchSerializer(serializers.Serializer):
	name = serializers.CharField(max_length=120, required=False)
	description = serializers.CharField(required=False, allow_blank=True)
	metadata = serializers.JSONField(required=False)


class MembershipWriteSerializer(serializers.Serializer):
	user_id = serializers.IntegerField()
	role = serializers.ChoiceField(choices=Role.choices)


class MembershipReadSerializer(serializers.Serializer):
	user_id = serializers.IntegerField(source="user_id")
	username = serializers.CharField(source="user.username")
	email = serializers.EmailField(source="user.email")
	role = serializers.CharField()


class DocumentSerializer(serializers.Serializer):
	data = serializers.JSONField()
