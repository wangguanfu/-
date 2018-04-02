# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='OrderGoods',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('create_time', models.DateTimeField(verbose_name='创建时间', auto_now_add=True)),
                ('update_time', models.DateTimeField(verbose_name='更新时间', auto_now=True)),
                ('count', models.IntegerField(verbose_name='数量', default=1)),
                ('price', models.DecimalField(verbose_name='单价', max_digits=10, decimal_places=2)),
                ('comment', models.TextField(verbose_name='评价信息', default='')),
            ],
            options={
                'db_table': 'df_order_goods',
            },
        ),
        migrations.CreateModel(
            name='OrderInfo',
            fields=[
                ('create_time', models.DateTimeField(verbose_name='创建时间', auto_now_add=True)),
                ('update_time', models.DateTimeField(verbose_name='更新时间', auto_now=True)),
                ('order_id', models.CharField(verbose_name='订单号', primary_key=True, max_length=64, serialize=False)),
                ('total_count', models.IntegerField(verbose_name='商品总数', default=1)),
                ('total_amount', models.DecimalField(verbose_name='商品总金额', max_digits=10, decimal_places=2)),
                ('trans_cost', models.DecimalField(verbose_name='运费', max_digits=10, decimal_places=2)),
                ('pay_method', models.SmallIntegerField(verbose_name='支付方式', default=1, choices=[(1, '货到付款'), (2, '支付宝')])),
                ('status', models.SmallIntegerField(verbose_name='订单状态', default=1, choices=[(1, '待支付'), (2, '待发货'), (3, '待收货'), (4, '待评价'), (5, '已完成')])),
                ('trade_id', models.CharField(verbose_name='支付编号', max_length=100, unique=True, blank=True, null=True)),
            ],
            options={
                'db_table': 'df_order_info',
            },
        ),
    ]
