# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-09-06 21:20
from __future__ import unicode_literals

import datetime
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tester', '0023_auto_20170906_0936'),
    ]

    operations = [
        migrations.CreateModel(
            name='JobExternal',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('jobStatus', models.CharField(default='Queued', max_length=20)),
                ('timeStamp', models.DateTimeField(default=datetime.datetime.now)),
                ('jobToRun', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tester.TestSequenceExternal')),
            ],
            options={
                'ordering': ['timeStamp'],
            },
        ),
        migrations.AlterField(
            model_name='carouselslotexternal',
            name='reagentInserted',
            field=models.DateTimeField(default=datetime.datetime.now),
        ),
    ]
