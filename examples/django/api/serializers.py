"""DRF serializers for API."""

from rest_framework import serializers


class UserSerializer(serializers.Serializer):
    """Serializer for User data."""

    id = serializers.CharField(read_only=True)
    name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    age = serializers.IntegerField(required=False, allow_null=True)


class SignupSerializer(serializers.Serializer):
    """Serializer for user signup."""

    namespace = serializers.CharField()
    database = serializers.CharField()
    access = serializers.CharField()
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)


class SigninSerializer(serializers.Serializer):
    """Serializer for user signin."""

    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
