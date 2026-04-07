#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from main.models import UserProfile

# Create teacher 2 user
username = 'guru2'
password = 'guru2123'
full_name = 'Guru Muda'

teacher_user, created = User.objects.get_or_create(username=username)
if created:
    teacher_user.set_password(password)
    teacher_user.save()
    print(f"✅ User '{username}' created")
else:
    print(f"⚠️ User '{username}' already exists")
    # Update password if exists
    teacher_user.set_password(password)
    teacher_user.save()
    print(f"✅ Password updated for '{username}'")

# Create teacher profile
teacher_profile, created = UserProfile.objects.get_or_create(user=teacher_user)
if created:
    teacher_profile.role = 'teacher'
    teacher_profile.full_name = full_name
    teacher_profile.save()
    print(f"✅ Profile teacher created: {full_name}")
else:
    print(f"⚠️ Teacher profile already exists")
    # Update full name
    teacher_profile.full_name = full_name
    teacher_profile.save()
    print(f"✅ Full name updated: {full_name}")

print("\n✅ Setup lengkap!")
print(f"Teacher 2: {username} / {password}")
print(f"Nama: {full_name}")
