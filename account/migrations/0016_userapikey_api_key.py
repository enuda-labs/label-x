# Generated by Django 5.1.7 on 2025-06-05 03:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0015_alter_userapikey_key_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='userapikey',
            name='api_key',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
