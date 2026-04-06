from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from main.models import UserProfile


class Command(BaseCommand):
    help = 'Create default teacher and principal accounts.'

    def handle(self, *args, **options):
        teacher, _ = User.objects.get_or_create(username='guru1', defaults={'email': 'guru1@example.com'})
        teacher.set_password('guru12345')
        teacher.save()
        UserProfile.objects.update_or_create(
            user=teacher,
            defaults={'role': UserProfile.ROLE_TEACHER, 'full_name': 'Guru Demo'},
        )

        principal, _ = User.objects.get_or_create(
            username='kepsek1', defaults={'email': 'kepsek1@example.com'}
        )
        principal.set_password('kepsek12345')
        principal.save()
        UserProfile.objects.update_or_create(
            user=principal,
            defaults={'role': UserProfile.ROLE_PRINCIPAL, 'full_name': 'Kepala Sekolah Demo'},
        )

        self.stdout.write(self.style.SUCCESS('Default users created/updated.'))
        self.stdout.write('Teacher  : guru1 / guru12345')
        self.stdout.write('Principal: kepsek1 / kepsek12345')
