# Generated manually to update TaskCluster reviewers field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('task', '0022_alter_task_task_type_alter_taskcluster_task_type'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='taskcluster',
            name='assigned_to',
        ),
        migrations.AddField(
            model_name='taskcluster',
            name='assigned_reviewers',
            field=models.ManyToManyField(
                blank=True,
                help_text='Users assigned to review the tasks in this cluster',
                related_name='assigned_clusters',
                to='account.customuser'
            ),
        ),
    ]
