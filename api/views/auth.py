# Login User
from django.contrib.auth.password_validation import validate_password
from rest_framework import generics, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.validators import UniqueValidator
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from core.models import User, Portal


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):

	@classmethod
	def get_token(cls, user):
		token = super().get_token(user)

		token['username'] = user.username
		token['email'] = user.email

		return token


class RegisterSerializer(serializers.ModelSerializer):
	password = serializers.CharField(
		write_only=True, required=True, validators=[validate_password])
	password2 = serializers.CharField(write_only=True, required=True)
	email = serializers.EmailField(
		required=True,
		validators=[UniqueValidator(queryset=User.objects.all())]
	)

	class Meta:
		model = User
		fields = ('username', 'email', 'password', 'password2', 'portal')

	def validate(self, attrs):
		if attrs['password'] != attrs['password2']:
			raise serializers.ValidationError(
				{"password": "Password fields didn't match."})

		return attrs

	def create(self, validated_data):
		user = User.objects.create(
			username=validated_data['username'],
			email=validated_data['email'],
			portal=validated_data['portal']
		)

		user.set_password(validated_data['password'])
		user.save()

		return user


class PortalSerializer(serializers.ModelSerializer):
	class Meta:
		model = Portal
		fields = '__all__'


class ProfileSerializer(serializers.ModelSerializer):
	portal = PortalSerializer(many=True, read_only=True)

	class Meta:
		model = User
		fields = 'username,email,portal'.split(",")


class MyTokenObtainPairView(TokenObtainPairView):
	serializer_class = MyTokenObtainPairSerializer


# Register User
class RegisterView(generics.CreateAPIView):
	queryset = User.objects.all()
	permission_classes = (AllowAny,)
	serializer_class = RegisterSerializer


# api/profile  and api/profile/update
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_profile(request):
	user = request.user
	serializer = ProfileSerializer(user, many=False)
	return Response(serializer.data)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_profile(request):
	user = request.user
	serializer = ProfileSerializer(user, data=request.data, partial=True)
	if serializer.is_valid():
		serializer.save()
	return Response(serializer.data)
