from django.contrib import admin

from .models import UserProfile, VideoSubmission


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
	list_display = ('full_name', 'user', 'role')
	list_filter = ('role',)
	search_fields = ('full_name', 'user__username')


@admin.register(VideoSubmission)
class VideoSubmissionAdmin(admin.ModelAdmin):
	list_display = ('id', 'teacher', 'subject', 'class_name', 'status', 'model_score', 'created_at')
	list_filter = ('status', 'subject', 'day')
	search_fields = ('subject', 'class_name', 'teacher__username')
