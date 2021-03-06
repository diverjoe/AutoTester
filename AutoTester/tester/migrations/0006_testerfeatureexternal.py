# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-09-03 14:46
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tester', '0005_auto_20170903_0929'),
    ]

    operations = [
        migrations.CreateModel(
            name='TesterFeatureExternal',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('featureName', models.CharField(default='dummy Feature', max_length=40)),
                ('featureDescription', models.CharField(default='description of Feature', max_length=200)),
                ('ulClipRowOffset', models.FloatField(default=-50)),
                ('ulClipColOffset', models.FloatField(default=-50)),
                ('lrClipRowOffset', models.FloatField(default=50)),
                ('lrClipColOffset', models.FloatField(default=50)),
                ('learnedWithReferenceDistance', models.FloatField(default=95)),
                ('usesRow', models.BooleanField(default=False)),
                ('centerImage', models.BooleanField(default=False)),
                ('useDlib', models.BooleanField(default=False)),
                ('trainingURL', models.CharField(default='http://robogardens.com', max_length=1000)),
                ('roiSideLength', models.IntegerField(default=65)),
                ('cParmValue', models.IntegerField(default=8)),
                ('upSampling', models.IntegerField(default=0)),
                ('positionCoefficientA', models.FloatField(default=1)),
                ('positionCoefficientB', models.FloatField(default=0)),
            ],
        ),
    ]
