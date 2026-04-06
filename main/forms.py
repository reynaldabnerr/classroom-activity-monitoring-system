from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from .models import VideoSubmission


def validate_video_file(file):
    """Validasi file video untuk menerima format .mp4, .avi, .mov, .mkv, .mts, .m2ts, .webm"""
    allowed_extensions = ['mp4', 'avi', 'mov', 'mkv', 'mts', 'm2ts', 'webm', 'flv', 'wmv', 'ts']
    file_extension = file.name.split('.')[-1].lower()
    
    if file_extension not in allowed_extensions:
        raise ValidationError(
            f'Format file tidak didukung. Gunakan salah satu: {", ".join(allowed_extensions)}'
        )


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label='Username',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Masukkan username'}),
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Masukkan password'}),
    )


class VideoSubmissionForm(forms.ModelForm):
    class Meta:
        model = VideoSubmission
        fields = [
            'subject',
            'class_name',
            'submission_date',
            'start_time',
            'end_time',
            'notes',
            'original_video',
        ]
        widgets = {
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contoh: Matematika'}),
            'class_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contoh: X IPA 1'}),
            'submission_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'min': '2024-01-01',
            }),
            'start_time': forms.TimeInput(attrs={
                'class': 'form-control', 
                'type': 'time',
                'step': '300',  # 5 minute intervals
            }),
            'end_time': forms.TimeInput(attrs={
                'class': 'form-control', 
                'type': 'time',
                'step': '300',  # 5 minute intervals
            }),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Catatan tambahan'}),
            'original_video': forms.ClearableFileInput(attrs={
                'class': 'form-control', 
                'accept': '.mp4, .avi, .mov, .mkv, .mts, .m2ts, .webm, .flv, .wmv, .ts'
            }),
        }

    def clean_original_video(self):
        """Validasi file video"""
        file = self.cleaned_data.get('original_video')
        if file:
            validate_video_file(file)
        return file

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        if start_time and end_time and end_time <= start_time:
            raise forms.ValidationError('Jam selesai harus lebih besar dari jam mulai.')
        return cleaned_data
