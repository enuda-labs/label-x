# Generated by Django 5.1.7 on 2025-05-22 02:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0010_userapikey'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='description',
            field=models.TextField(blank=True, null=True),
        ),
    ]
