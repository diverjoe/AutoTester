# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-09-22 10:48
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tester', '0068_testerprocessingparameters_defaultfisheyeexpansionfactor'),
    ]

    operations = [
        migrations.AddField(
            model_name='testerfeatureexternal',
            name='dlibPositionColOffset',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='testerfeatureexternal',
            name='dlibPositionRowOffset',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='testerfeatureexternal',
            name='dlibUseRowPosition',
            field=models.BooleanField(default=True),
        ),
    ]
