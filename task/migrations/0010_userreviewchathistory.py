# Generated by Django 5.1.7 on 2025-04-20 19:15

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('task', '0009_alter_task_review_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserReviewChatHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ai_output', models.JSONField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('human_confidence_score', models.FloatField()),
                ('human_justification', models.TextField()),
                ('human_classification', models.CharField(choices=[('Safe', 'Safe'), ('Mildly Offensive', 'Mildly Offensive'), ('Highly Offensive', 'Highly Offensive')], max_length=25)),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='task.task')),
            ],
        ),
    ]
