# api/customers/models.py

from pyexpat import model
from django.db import models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError

# Create your models here.

class customer(models.Model):
    """カスタマーモデル（最上位)"""

    # 識別情報
    customer_code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='カスタマーコード',
        help_text='例: CS001'
    )

    # 企業情報
    company_name = models.CharField(
        max_length=200,
        unique=True,
        verbose_name='企業名',
        help_text='例: 株式会社ABC'
    )

    # 基本情報
    website = models.URLField(
        blank=True,
        null=True,
        verbose_name='ウェブサイト',
    )

    notes  = models.TextField(
        blank=True,
        null=True,
        verbose_name='備考'
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name='有効',
        help_text='取引中顧客かどうか'
    )

    #　タイムスタンプ
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='作成日時'
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新日時',
    )

    class Meta:
        verbose_name = 'カスタマー'
        verbose_name_plural = 'カスタマー一覧'
        ordering = ['company_name']
        db_table = 'customers'

    def __str__(self):
        return self.company_name
