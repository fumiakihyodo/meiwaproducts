from django.contrib import admin
from api.products.models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """製品管理画面"""
    
    list_display = [
        'product_number', 'product_name', 'status',
        'parts_count', 'created_by', 'created_at', 'updated_at'
    ]
    
    list_filter = ['status', 'created_at', 'updated_at']
    
    search_fields = [
        'product_number', 'product_name', 'description'
    ]
    
    readonly_fields = ['created_at', 'updated_at', 'parts_count']
    
    fieldsets = (
        ('基本情報', {
            'fields': ('product_number', 'product_name', 'description')
        }),
        ('ステータス', {
            'fields': ('status',)
        }),
        ('作成情報', {
            'fields': ('created_by', 'created_at', 'updated_at', 'parts_count'),
            'classes': ('collapse',)
        }),
    )
    
    def parts_count(self, obj):
        """紐づく部品数"""
        return obj.parts.filter(is_active=True).count()
    parts_count.short_description = '部品数'
    
    def save_model(self, request, obj, form, change):
        """保存時に作成者を設定"""
        if not change:  # 新規作成時のみ
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
