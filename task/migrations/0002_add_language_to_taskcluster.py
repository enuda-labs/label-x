# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('task', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='taskcluster',
            name='language',
            field=models.CharField(default='English', help_text='Language for subtitle annotation and transcription', max_length=50),
        ),
    ]
