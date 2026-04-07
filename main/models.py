from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
	ROLE_TEACHER = 'teacher'
	ROLE_PRINCIPAL = 'principal'
	ROLE_CHOICES = [
		(ROLE_TEACHER, 'Guru'),
		(ROLE_PRINCIPAL, 'Kepala Sekolah'),
	]

	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
	role = models.CharField(max_length=20, choices=ROLE_CHOICES)
	full_name = models.CharField(max_length=150)

	def __str__(self):
		return f"{self.full_name} ({self.get_role_display()})"


class VideoSubmission(models.Model):
	STATUS_PENDING = 'pending'
	STATUS_PROCESSING = 'processing'
	STATUS_COMPLETED = 'completed'
	STATUS_FAILED = 'failed'
	STATUS_CHOICES = [
		(STATUS_PENDING, 'Menunggu'),
		(STATUS_PROCESSING, 'Diproses'),
		(STATUS_COMPLETED, 'Selesai'),
		(STATUS_FAILED, 'Gagal'),
	]

	SUBJECT_ENGLISH = 'english'
	SUBJECT_BAHASA = 'bahasa_indonesia'
	SUBJECT_SCIENCE = 'science'
	SUBJECT_MATH = 'math'
	SUBJECT_CHOICES = [
		(SUBJECT_ENGLISH, 'English'),
		(SUBJECT_BAHASA, 'Bahasa Indonesia'),
		(SUBJECT_SCIENCE, 'Science'),
		(SUBJECT_MATH, 'Math'),
	]

	teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='video_submissions')
	subject = models.CharField(max_length=50, choices=SUBJECT_CHOICES)
	class_name = models.CharField(max_length=100)
	submission_date = models.DateField(default=timezone.now, help_text="Tanggal pembelajaran")
	day = models.CharField(max_length=20, editable=False, default='Senin')  # Auto-generated dari tanggal
	start_time = models.TimeField()
	end_time = models.TimeField()
	notes = models.TextField(blank=True)
	original_video = models.FileField(upload_to='videos/raw/')
	preprocessed_dir = models.CharField(max_length=255, blank=True)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
	total_faces = models.PositiveIntegerField(default=0)
	model_score = models.FloatField(default=0.0)
	predicted_label = models.CharField(max_length=100, blank=True)
	# Expression breakdown: JSON format {'Happy': 15, 'Sad': 8, ...}
	expression_breakdown = models.TextField(default='{}')
	process_log = models.TextField(blank=True)
	processed_at = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']

	def save(self, *args, **kwargs):
		"""Auto-generate day name from submission_date"""
		if self.submission_date:
			day_names = {
				0: 'Senin',      # Monday
				1: 'Selasa',     # Tuesday
				2: 'Rabu',       # Wednesday
				3: 'Kamis',      # Thursday
				4: 'Jumat',      # Friday
				5: 'Sabtu',      # Saturday
				6: 'Minggu'      # Sunday
			}
			self.day = day_names.get(self.submission_date.weekday(), 'Senin')
		super().save(*args, **kwargs)

	def __str__(self):
		return f"{self.subject} - {self.class_name} ({self.get_status_display()})"
