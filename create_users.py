#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from main.models import UserProfile

# Create teacher user
teacher_user, created = User.objects.get_or_create(username='guru')
if created:
    teacher_user.set_password('guru123')
    teacher_user.save()
    print("✅ User 'guru' created")
else:
    print("⚠️ User 'guru' already exists")

# Create teacher profile
teacher_profile, created = UserProfile.objects.get_or_create(user=teacher_user)
if created:
    teacher_profile.role = 'teacher'
    teacher_profile.full_name = 'Guru'
    teacher_profile.save()
    print("✅ Profile teacher created")
else:
    print("⚠️ Teacher profile already exists")

# Create principal user
principal_user, created = User.objects.get_or_create(username='kepsek')
if created:
    principal_user.set_password('kepsek123')
    principal_user.save()
    print("✅ User 'kepsek' created")
else:
    print("⚠️ User 'kepsek' already exists")

# Create principal profile
principal_profile, created = UserProfile.objects.get_or_create(user=principal_user)
if created:
    principal_profile.role = 'principal'
    principal_profile.full_name = 'Kepala Sekolah'
    principal_profile.save()
    print("✅ Profile principal created")
else:
    print("⚠️ Principal profile already exists")

print("\n✅ Setup lengkap!")
print(f"Teacher: guru / guru123")
print(f"Principal: kepsek / kepsek123")
