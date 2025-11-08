from rest_framework import generics, status, views, permissions
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from django.utils import timezone

from .models import User
from .serializers import (
    UserSerializer, UserCreateSerializer, UserUpdateSerializer, 
    ChangePasswordSerializer, LoginSerializer
)


class LoginView(views.APIView):
    """統一ログインビュー"""
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = self.serializer_class(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        # 最終ログイン時刻を更新
        user.last_login = timezone.now()
        user.last_login_at = user.last_login
        user.save(update_fields=['last_login', 'last_login_at'])

        # JWTトークンを生成
        refresh = RefreshToken.for_user(user)

        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data,
        }, status=status.HTTP_200_OK)


class LogoutView(views.APIView):
    """ログアウトビュー"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()

            return Response(
                {"message": "ログアウトしました"}, 
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": "ログアウトに失敗しました"}, 
                status=status.HTTP_400_BAD_REQUEST
            )


class IsAdminUser(permissions.BasePermission):
    """管理権限の確認"""

    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.is_administrator
        )


class UserListCreateView(generics.ListCreateAPIView):
    """ユーザー一覧取得・作成ビュー"""
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return UserCreateSerializer
        return UserSerializer

    def perform_create(self, serializer):
        serializer.save()


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """ユーザー詳細取得・更新・削除ビュー"""
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return UserUpdateSerializer
        return UserSerializer

    def get_object(self):
        """自分のプロフィール又は管理者の場合は他のユーザー"""
        pk = self.kwargs.get('pk')

        if pk == 'me':
            return self.request.user

        # 管理者の場合は他のユーザーにアクセス可能
        if self.request.user.is_administrator:
            return super().get_object()
        
        # 管理者以外は他のユーザーの情報にアクセスできない
        if str(self.request.user.pk) != str(pk):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("他のユーザーの情報にアクセスする権限がありません")
        
        return self.request.user

    def destroy(self, request, *args, **kwargs):
        """ユーザーの削除"""
        if not request.user.is_administrator:
            return Response(
                {"error": "削除権限がありません"}, 
                status=status.HTTP_403_FORBIDDEN
            )

        instance = self.get_object()
        if instance == request.user:
            return Response(
                {"error": "自分自身は削除できません"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(views.APIView):
    """現在のユーザー情報取得ビュー"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChangePasswordView(generics.UpdateAPIView):
    """パスワード変更ビュー"""
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = self.get_object()
        user.set_password(serializer.validated_data['new_password'])
        user.save()

        return Response(
            {"message": "パスワードを変更しました"}, 
            status=status.HTTP_200_OK
        )


class CheckAuthView(views.APIView):
    """認証状態確認ビュー"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "is_authenticated": True,
            'is_admin': request.user.is_administrator,
            "user": UserSerializer(request.user).data
        }, status=status.HTTP_200_OK)