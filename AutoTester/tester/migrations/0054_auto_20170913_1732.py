# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-09-13 22:32
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tester', '0053_auto_20170913_1700'),
    ]

    operations = [
        migrations.AlterField(
            model_name='testdefinition',
            name='testName',
            field=models.CharField(default='New Test', max_length=40, unique=True),
        ),
    ]
