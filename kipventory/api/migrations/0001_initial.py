# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-03-25 22:04
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
            name='BulkImport',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data', models.FileField(upload_to='')),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('administrator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='CartItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(default=0)),
                ('request_type', models.CharField(choices=[('loan', 'Loan'), ('disbursement', 'Disbursement')], default='disbursement', max_length=15)),
                ('due_date', models.DateTimeField(blank=True, default=None, null=True)),
            ],
            options={
                'ordering': ('item__name',),
            },
        ),
        migrations.CreateModel(
            name='CustomField',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('private', models.BooleanField(default=False)),
                ('field_type', models.CharField(choices=[('Single', 'Single-line text'), ('Multi', 'Multi-line text'), ('Int', 'Integer'), ('Float', 'Float')], default='Single', max_length=10)),
            ],
            options={
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='CustomValue',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('Single', models.CharField(blank=True, default='', max_length=100)),
                ('Multi', models.TextField(blank=True, default='', max_length=500)),
                ('Int', models.IntegerField(blank=True, default=0)),
                ('Float', models.FloatField(blank=True, default=0.0)),
                ('field', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='values', to='api.CustomField', to_field='name')),
            ],
            options={
                'ordering': ('field__name',),
            },
        ),
        migrations.CreateModel(
            name='Disbursement',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('quantity', models.PositiveIntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name='Item',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('quantity', models.PositiveIntegerField(default=0)),
                ('model_no', models.CharField(blank=True, default='', max_length=100)),
                ('description', models.TextField(blank=True, default='', max_length=500)),
            ],
            options={
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='Loan',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_loaned', models.DateTimeField(auto_now_add=True)),
                ('quantity_loaned', models.PositiveIntegerField(default=0)),
                ('quantity_returned', models.PositiveIntegerField(default=0)),
                ('date_returned', models.DateTimeField(blank=True, null=True)),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.Item')),
            ],
            options={
                'ordering': ('id',),
            },
        ),
        migrations.CreateModel(
            name='LoanGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ],
        ),
        migrations.CreateModel(
            name='Log',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(blank=True, null=True)),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('message', models.CharField(blank=True, max_length=500, null=True)),
                ('default_item', models.CharField(blank=True, max_length=100, null=True)),
                ('default_initiating_user', models.CharField(blank=True, max_length=100, null=True)),
                ('default_affected_user', models.CharField(blank=True, max_length=100, null=True)),
                ('category', models.CharField(choices=[('Item Modification', 'Item Modification'), ('Item Creation', 'Item Creation'), ('Item Deletion', 'Item Deletion'), ('Request Item Creation', 'Request Item Creation'), ('Request Item Approval: Loan', 'Request Item Approval: Loan'), ('Request Item Approval: Disburse', 'Request Item Approval: Disburse'), ('Request Item Denial', 'Request Item Denial'), ('User Creation', 'User Creation'), ('Transaction Creation', 'Transaction Creation')], max_length=50)),
                ('affected_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='affected_user', to=settings.AUTH_USER_MODEL)),
                ('initiating_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='initiating_user', to=settings.AUTH_USER_MODEL)),
                ('item', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='api.Item')),
            ],
        ),
        migrations.CreateModel(
            name='NewUserRequest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('username', models.CharField(max_length=150, unique=True)),
                ('first_name', models.CharField(max_length=30)),
                ('last_name', models.CharField(max_length=30)),
                ('email', models.CharField(max_length=150, unique=True)),
                ('comment', models.CharField(blank=True, max_length=300)),
            ],
        ),
        migrations.CreateModel(
            name='Request',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_open', models.DateTimeField(auto_now_add=True)),
                ('open_comment', models.TextField(blank=True, default='', max_length=500)),
                ('date_closed', models.DateTimeField(blank=True, null=True)),
                ('closed_comment', models.TextField(blank=True, max_length=500)),
                ('status', models.CharField(choices=[('O', 'Outstanding'), ('A', 'Approved'), ('D', 'Denied')], default='O', max_length=15)),
                ('administrator', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='requests_administrated', to=settings.AUTH_USER_MODEL)),
                ('requester', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='requests', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('date_open',),
            },
        ),
        migrations.CreateModel(
            name='RequestedItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(default=0)),
                ('request_type', models.CharField(choices=[('loan', 'Loan'), ('disbursement', 'Disbursement')], default='loan', max_length=15)),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.Item')),
                ('request', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='requested_items', to='api.Request')),
            ],
            options={
                'ordering': ('item__name',),
            },
        ),
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
            ],
            options={
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='Transaction',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(choices=[('Acquisition', 'Acquisition'), ('Loss', 'Loss')], max_length=20)),
                ('quantity', models.PositiveIntegerField()),
                ('comment', models.CharField(blank=True, max_length=100, null=True)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('administrator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.Item')),
            ],
        ),
        migrations.AddField(
            model_name='log',
            name='request',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='api.Request'),
        ),
        migrations.AddField(
            model_name='loangroup',
            name='request',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='loan_group', to='api.Request'),
        ),
        migrations.AddField(
            model_name='loan',
            name='loan_group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='loans', to='api.LoanGroup'),
        ),
        migrations.AddField(
            model_name='loan',
            name='request',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='loaned_items', to='api.Request'),
        ),
        migrations.AddField(
            model_name='item',
            name='tags',
            field=models.ManyToManyField(blank=True, to='api.Tag'),
        ),
        migrations.AddField(
            model_name='disbursement',
            name='item',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.Item'),
        ),
        migrations.AddField(
            model_name='disbursement',
            name='request',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='disbursed_items', to='api.Request'),
        ),
        migrations.AddField(
            model_name='customvalue',
            name='item',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='values', to='api.Item'),
        ),
        migrations.AddField(
            model_name='cartitem',
            name='item',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.Item'),
        ),
        migrations.AddField(
            model_name='cartitem',
            name='owner',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cart_items', to=settings.AUTH_USER_MODEL),
        ),
    ]
