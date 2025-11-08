# api/products/views.py

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.db.models import Count, Q

from api.products.models import Product
from api.products.serializers import (
    ProductListSerializer,
    ProductDetailSerializer,
    ProductCreateUpdateSerializer
)


class IsAdminUser(permissions.BasePermission):
    """管理者権限の確認"""

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_administrator
        )


class ProductListCreateView(generics.ListCreateAPIView):
    """製品一覧取得・作成ビュー"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """クエリセットを取得（部品数も含む）"""
        queryset = Product.objects.annotate(
            parts_count=Count('parts', filter=Q(parts__is_active=True))
        ).select_related('created_by')
        
        # フィルタリング
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(product_number__icontains=search) |
                Q(product_name__icontains=search) |
                Q(description__icontains=search)
            )
        
        return queryset.order_by('-created_at')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ProductCreateUpdateSerializer
        return ProductListSerializer

    def perform_create(self, serializer):
        """製品作成時に作成者を設定"""
        serializer.save(created_by=self.request.user)


class ProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    """製品詳細取得・更新・削除ビュー"""
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'pk'

    def get_queryset(self):
        """クエリセットを取得"""
        return Product.objects.annotate(
            parts_count=Count('parts', filter=Q(parts__is_active=True))
        ).select_related('created_by').prefetch_related('parts__supplier_branch__supplier')

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ProductCreateUpdateSerializer
        return ProductDetailSerializer

    def destroy(self, request, *args, **kwargs):
        """製品の削除（管理者のみ）"""
        if not request.user.is_administrator:
            return Response(
                {"error": "削除権限がありません"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        instance = self.get_object()
        
        # 紐づく部品が存在するかチェック
        if instance.parts.filter(is_active=True).exists():
            return Response(
                {"error": "有効な部品が紐づいているため削除できません"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
