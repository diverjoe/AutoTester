# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-09-13 22:00
from __future__ import unicode_literals

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tester', '0052_auto_20170912_1248'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='testschedule',
            options={'ordering': ['testToSchedule']},
        ),
        migrations.AlterField(
            model_name='testdefinition',
            name='agitateMixtureSecs',
            field=models.IntegerField(default=0, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(1000)]),
        ),
        migrations.AlterField(
            model_name='testdefinition',
            name='delayBeforeReadingSecs',
            field=models.IntegerField(default=0, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(1000)]),
        ),
        migrations.AlterField(
            model_name='testdefinition',
            name='reagent1AgitateSecs',
            field=models.IntegerField(default=0, null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(1000)]),
        ),
        migrations.AlterField(
            model_name='testdefinition',
            name='reagent1DropCount',
            field=models.IntegerField(default=0, null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(50)]),
        ),
        migrations.AlterField(
            model_name='testdefinition',
            name='reagent2AgitateSecs',
            field=models.IntegerField(default=0, null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(1000)]),
        ),
        migrations.AlterField(
            model_name='testdefinition',
            name='reagent2DropCount',
            field=models.IntegerField(default=0, null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(50)]),
        ),
        migrations.AlterField(
            model_name='testdefinition',
            name='reagent3AgitateSecs',
            field=models.IntegerField(default=0, null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(1000)]),
        ),
        migrations.AlterField(
            model_name='testdefinition',
            name='reagent3DropCount',
            field=models.IntegerField(default=0, null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(50)]),
        ),
        migrations.AlterField(
            model_name='testdefinition',
            name='waterVolInML',
            field=models.FloatField(default=5.0, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(12)]),
        ),
    ]
