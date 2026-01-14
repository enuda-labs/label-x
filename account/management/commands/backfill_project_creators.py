from django.core.management.base import BaseCommand
from account.models import Project, ProjectMember
from account.choices import ProjectMemberRole


class Command(BaseCommand):
    help = 'Add project creators as ProjectMembers with OWNER role for existing projects'

    def handle(self, *args, **options):
        projects = Project.objects.filter(created_by__isnull=False)
        created_count = 0
        skipped_count = 0

        for project in projects:
            # Check if creator is already a member
            if ProjectMember.objects.filter(project=project, user=project.created_by).exists():
                self.stdout.write(
                    self.style.WARNING(f'Project "{project.name}": Creator already a member, skipping...')
                )
                skipped_count += 1
                continue

            # Create ProjectMember entry for creator
            ProjectMember.objects.create(
                project=project,
                user=project.created_by,
                role=ProjectMemberRole.OWNER
            )
            self.stdout.write(
                self.style.SUCCESS(f'Project "{project.name}": Added creator "{project.created_by.username}" as OWNER')
            )
            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(f'\n✅ Successfully added {created_count} project creator(s) as members')
        )
        if skipped_count > 0:
            self.stdout.write(
                self.style.WARNING(f'⚠️  Skipped {skipped_count} project(s) (creators already members)')
            )

