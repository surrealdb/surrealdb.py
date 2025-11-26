"""API views using Django REST Framework."""

import logging

from rest_framework import status, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from database import close_connection, get_connection

from .serializers import SigninSerializer, SignupSerializer, UserSerializer


class UserViewSet(viewsets.ViewSet):
    """ViewSet for user CRUD operations."""

    serializer_class = UserSerializer

    async def list(self, request):
        """List all users."""
        db = await get_connection()
        try:
            users = await db.select("users")
            if not users:
                return Response([])

            serializer = UserSerializer(users, many=True)
            return Response(serializer.data)
        finally:
            await close_connection(db)

    async def create(self, request):
        """Create a new user."""
        serializer = UserSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        db = await get_connection()
        try:
            result = await db.create("users", serializer.validated_data)
            if result:
                user_data = result[0] if isinstance(result, list) else result
                return Response(UserSerializer(user_data).data, status=status.HTTP_201_CREATED)
            return Response(
                {"error": "Failed to create user"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        finally:
            await close_connection(db)

    async def retrieve(self, request, pk=None):
        """Get a specific user."""
        db = await get_connection()
        try:
            result = await db.select(pk)
            if not result:
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

            user_data = result[0] if isinstance(result, list) else result
            return Response(UserSerializer(user_data).data)
        finally:
            await close_connection(db)

    async def update(self, request, pk=None):
        """Update a user."""
        serializer = UserSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        db = await get_connection()
        try:
            result = await db.merge(pk, serializer.validated_data)
            if not result:
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

            user_data = result[0] if isinstance(result, list) else result
            return Response(UserSerializer(user_data).data)
        finally:
            await close_connection(db)

    async def destroy(self, request, pk=None):
        """Delete a user."""
        db = await get_connection()
        try:
            result = await db.delete(pk)
            if not result:
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
            return Response(status=status.HTTP_204_NO_CONTENT)
        finally:
            await close_connection(db)


@api_view(["POST"])
async def signup(request):
    """User signup endpoint."""
    serializer = SignupSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    db = await get_connection()
    try:
        token = await db.signup(serializer.validated_data)
        return Response(
            {"token": token, "message": "User registered successfully"},
            status=status.HTTP_201_CREATED,
        )
    except Exception:
        logging.exception("Exception during signup")
        return Response(
            {"error": "An internal error occurred. Please try again later."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    finally:
        await close_connection(db)


@api_view(["POST"])
async def signin(request):
    """User signin endpoint."""
    serializer = SigninSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    db = await get_connection()
    try:
        token = await db.signin(serializer.validated_data)
        return Response({"token": token, "message": "Signed in successfully"})
        logging.exception("Exception during signin")
    except Exception:
        return Response(
            {"error": "Invalid credentials or unexpected error."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    finally:
        await close_connection(db)


@api_view(["POST"])
async def logout(request):
    """User logout endpoint."""
    db = await get_connection()
    try:
        await db.invalidate()
        return Response({"message": "Logged out successfully"})
    finally:
        await close_connection(db)
