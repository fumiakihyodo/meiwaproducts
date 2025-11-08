# api/purchases/views.py

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.db.models import Count, Q, Prefetch
import logging

from api.purchases.models import Part, PriceHistory
from api.purchases.serializers import (
    PartListSerializer,
    PartDetailSerializer,
    PartCreateUpdateSerializer,
    PriceHistoryListSerializer,
    PriceHistoryDetailSerializer,
    PriceHistoryCreateUpdateSerializer,
)

logger = logging.getLogger(__name__)


class IsAdminUser(permissions.BasePermission):
    """管理者権限の確認"""

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_administrator
        )


# ==================== Part Views ====================

class PartListCreateView(generics.ListCreateAPIView):
    """部品一覧取得・作成ビュー"""
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """クエリセットを取得"""
        queryset = Part.objects.select_related(
            'product',
            'supplier_branch__supplier',
            'created_by'
        ).annotate(
            price_history_count=Count('price_histories')
        )
        
        # フィルタリング
        product_id = self.request.query_params.get('product', None)
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        
        supplier_id = self.request.query_params.get('supplier', None)
        if supplier_id:
            queryset = queryset.filter(supplier_branch__supplier_id=supplier_id)
        
        branch_id = self.request.query_params.get('branch', None)
        if branch_id:
            queryset = queryset.filter(supplier_branch_id=branch_id)
        
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(part_number__icontains=search) |
                Q(part_name__icontains=search) |
                Q(product__product_number__icontains=search) |
                Q(product__product_name__icontains=search) |
                Q(supplier_branch__supplier__company_name__icontains=search)
            )
        
        return queryset.order_by('part_number')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PartCreateUpdateSerializer
        return PartListSerializer

    def create(self, request, *args, **kwargs):
        """部品作成（デバッグログ付き）"""
        logger.info(f"[Part Create] User: {request.user}")
        logger.info(f"[Part Create] Data: {request.data}")
        
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            # created_byはHiddenFieldで自動設定される
            self.perform_create(serializer)
            
            headers = self.get_success_headers(serializer.data)
            logger.info(f"[Part Create] Success: Part ID {serializer.data.get('id')}")
            
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
            
        except Exception as e:
            logger.error(f"[Part Create] Error: {str(e)}")
            logger.error(f"[Part Create] Error type: {type(e).__name__}")
            if hasattr(e, 'detail'):
                logger.error(f"[Part Create] Error detail: {e.detail}")
            raise

    def perform_create(self, serializer):
        """部品作成時に作成者を設定（冗長だがフォールバック）"""
        # HiddenFieldで既に設定されているが、念のため
        serializer.save()


class PartDetailView(generics.RetrieveUpdateDestroyAPIView):
    """部品詳細取得・更新・削除ビュー"""
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'pk'

    def get_queryset(self):
        """クエリセットを取得"""
        # 価格履歴を最適化して取得
        price_histories_prefetch = Prefetch(
            'price_histories',
            queryset=PriceHistory.objects.select_related('created_by').order_by('-start_date', '-created_at')
        )
        
        return Part.objects.select_related(
            'product',
            'supplier_branch__supplier',
            'created_by'
        ).prefetch_related(
            price_histories_prefetch
        ).annotate(
            price_history_count=Count('price_histories')
        )

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return PartCreateUpdateSerializer
        return PartDetailSerializer

    def destroy(self, request, *args, **kwargs):
        """部品の削除（管理者のみ）"""
        if not request.user.is_administrator:
            return Response(
                {"error": "削除権限がありません"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        instance = self.get_object()
        
        # 価格履歴が存在するかチェック
        if instance.price_histories.exists():
            return Response(
                {"error": "価格履歴が存在するため削除できません。無効化を検討してください。"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==================== PriceHistory Views ====================

class PriceHistoryListCreateView(generics.ListCreateAPIView):
    """価格履歴一覧取得・作成ビュー"""
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """クエリセットを取得"""
        queryset = PriceHistory.objects.select_related(
            'part__product',
            'part__supplier_branch__supplier',
            'created_by'
        )
        
        # フィルタリング
        part_id = self.request.query_params.get('part', None)
        if part_id:
            queryset = queryset.filter(part_id=part_id)
        
        product_id = self.request.query_params.get('product', None)
        if product_id:
            queryset = queryset.filter(part__product_id=product_id)
        
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # 有効期間フィルタ
        status_filter = self.request.query_params.get('status', None)
        if status_filter == 'current':
            # 現在有効な価格のみ
            from django.utils import timezone
            today = timezone.now().date()
            queryset = queryset.filter(
                is_active=True,
                start_date__lte=today
            ).filter(
                Q(end_date__isnull=True) | Q(end_date__gte=today)
            )
        elif status_filter == 'future':
            # 将来の価格のみ
            from django.utils import timezone
            today = timezone.now().date()
            queryset = queryset.filter(start_date__gt=today)
        elif status_filter == 'expired':
            # 期限切れのみ
            from django.utils import timezone
            today = timezone.now().date()
            queryset = queryset.filter(
                end_date__isnull=False,
                end_date__lt=today
            )
        
        return queryset.order_by('-start_date', '-created_at')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PriceHistoryCreateUpdateSerializer
        return PriceHistoryListSerializer

    def create(self, request, *args, **kwargs):
        """価格履歴作成（デバッグログ付き）"""
        logger.info(f"[PriceHistory Create] User: {request.user}")
        logger.info(f"[PriceHistory Create] Data: {request.data}")
        logger.info(f"[PriceHistory Create] Files: {request.FILES}")
        
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            # created_byはHiddenFieldで自動設定される
            self.perform_create(serializer)
            
            headers = self.get_success_headers(serializer.data)
            logger.info(f"[PriceHistory Create] Success: PriceHistory ID {serializer.data.get('id')}")
            
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
            
        except Exception as e:
            logger.error(f"[PriceHistory Create] Error: {str(e)}")
            logger.error(f"[PriceHistory Create] Error type: {type(e).__name__}")
            if hasattr(e, 'detail'):
                logger.error(f"[PriceHistory Create] Error detail: {e.detail}")
            raise

    def perform_create(self, serializer):
        """価格履歴作成時に作成者を設定（冗長だがフォールバック）"""
        # HiddenFieldで既に設定されているが、念のため
        serializer.save()


class PriceHistoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """価格履歴詳細取得・更新・削除ビュー"""
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'pk'

    def get_queryset(self):
        """クエリセットを取得"""
        return PriceHistory.objects.select_related(
            'part__product',
            'part__supplier_branch__supplier',
            'created_by'
        )

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return PriceHistoryCreateUpdateSerializer
        return PriceHistoryDetailSerializer

    def destroy(self, request, *args, **kwargs):
        """価格履歴の削除（管理者のみ）"""
        if not request.user.is_administrator:
            return Response(
                {"error": "削除権限がありません"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        self.perform_destroy(self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)