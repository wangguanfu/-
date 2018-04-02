# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
        ('orders', '0002_auto_20171017_1057'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderinfo',
            name='address',
            field=models.ForeignKey(verbose_name='收获地址', default=1, to='users.Address'),
            preserve_default=False,
        ),
    ]
