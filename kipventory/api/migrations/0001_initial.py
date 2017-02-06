# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-02-05 22:48
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CartItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.IntegerField(default=1)),
            ],
        ),
        migrations.CreateModel(
            name='Item',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('photo_src', models.ImageField(upload_to='items')),
                ('location', models.CharField(max_length=100)),
                ('model', models.CharField(max_length=100)),
                ('quantity', models.IntegerField(default=0)),
                ('description', models.TextField(max_length=500)),
            ],
        ),
        migrations.CreateModel(
            name='Request',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.IntegerField()),
                ('date_open', models.DateTimeField(blank=True)),
                ('open_reason', models.TextField(blank=True, max_length=500)),
                ('date_closed', models.DateTimeField(blank=True, null=True)),
                ('closed_comment', models.TextField(blank=True, max_length=500, null=True)),
                ('status', models.CharField(choices=[('O', 'Outstanding'), ('A', 'Approved'), ('D', 'Denied')], default='O', max_length=10)),
                ('administrator', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='requests_administrated', to=settings.AUTH_USER_MODEL)),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.Item')),
                ('requester', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
            ],
        ),
        migrations.AddField(
            model_name='item',
            name='tags',
            field=models.ManyToManyField(blank=True, to='api.Tag'),
        ),
        migrations.AddField(
            model_name='cartitem',
            name='item',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.Item'),
        ),
        migrations.AddField(
            model_name='cartitem',
            name='owner',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
    ]
