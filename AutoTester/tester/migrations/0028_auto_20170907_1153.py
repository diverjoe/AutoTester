# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-09-07 16:53
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tester', '0027_auto_20170907_1153'),
    ]

    operations = [
        migrations.AlterField(
            model_name='testsequenceexternal',
            name='hoursToRun',
            field=models.ManyToManyField(to='tester.HourChoices'),
        ),
    ]