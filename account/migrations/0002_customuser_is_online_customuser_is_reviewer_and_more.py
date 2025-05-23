# Generated by Django 5.1.7 on 2025-04-08 05:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="is_online",
            field=models.BooleanField(
                default=False, help_text="Indicates if the user is currently online"
            ),
        ),
        migrations.AddField(
            model_name="customuser",
            name="is_reviewer",
            field=models.BooleanField(
                default=False, help_text="Designates whether this user can review tasks"
            ),
        ),
        migrations.AddField(
            model_name="customuser",
            name="last_activity",
            field=models.DateTimeField(
                auto_now=True, help_text="Last time the user was active"
            ),
        ),
    ]
