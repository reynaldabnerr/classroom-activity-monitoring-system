from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LogoutView
from django.db.models import Avg, Count, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import FormView
import shutil
from pathlib import Path

from .decorators import role_required
from .forms import LoginForm, VideoSubmissionForm
from .models import UserProfile, VideoSubmission
from .services import process_submission


class UserLoginView(FormView):
    template_name = 'auth/login.html'
    form_class = LoginForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('role-redirect')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        login(self.request, form.get_user())
        return redirect('role-redirect')


class UserLogoutView(LogoutView):
    next_page = 'login'


@login_required
def role_redirect(request):
    try:
        profile = request.user.profile
    except Exception:
        profile = None
    if not profile:
        messages.error(request, 'Akun Anda belum memiliki role. Hubungi admin.')
        logout(request)
        return redirect('login')

    if profile.role == UserProfile.ROLE_TEACHER:
        return redirect('teacher-dashboard')
    if profile.role == UserProfile.ROLE_PRINCIPAL:
        return redirect('principal-dashboard')
    return redirect('login')


@role_required([UserProfile.ROLE_TEACHER])
def teacher_dashboard(request):
    submissions = VideoSubmission.objects.filter(teacher=request.user)
    context = {
        'submissions': submissions,
        'total_uploads': submissions.count(),
        'total_completed': submissions.filter(status=VideoSubmission.STATUS_COMPLETED).count(),
        'total_processing': submissions.filter(status=VideoSubmission.STATUS_PROCESSING).count(),
    }
    return render(request, 'teacher/dashboard.html', context)


@role_required([UserProfile.ROLE_TEACHER])
def upload_video(request):
    if request.method == 'POST':
        form = VideoSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            submission = form.save(commit=False)
            submission.teacher = request.user
            submission.status = VideoSubmission.STATUS_PENDING
            submission.save()

            process_submission(submission)
            
            # Check if it's AJAX request (fetch)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.POST.get('ajax'):
                return JsonResponse({
                    'success': True,
                    'submission_id': submission.id,
                    'status_url': f'/guru/api/submission/{submission.id}/status/',
                })
            else:
                # Regular form submission - redirect
                return redirect('teacher-processing', submission_id=submission.id)
        else:
            # Form errors
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.POST.get('ajax'):
                return JsonResponse({
                    'success': False,
                    'errors': form.errors,
                })
    else:
        form = VideoSubmissionForm()

    return render(request, 'teacher/upload.html', {'form': form})


@role_required([UserProfile.ROLE_TEACHER])
def teacher_submission_detail(request, submission_id):
    submission = get_object_or_404(VideoSubmission, id=submission_id, teacher=request.user)
    return render(request, 'teacher/submission_detail.html', {'submission': submission})


@role_required([UserProfile.ROLE_TEACHER])
def teacher_processing(request, submission_id):
    """Show processing status page"""
    submission = get_object_or_404(VideoSubmission, id=submission_id, teacher=request.user)
    return render(request, 'teacher/processing.html', {'submission': submission})


@role_required([UserProfile.ROLE_TEACHER])
def submission_processing_status(request, submission_id):
    """Return current processing status as JSON"""
    submission = get_object_or_404(VideoSubmission, id=submission_id, teacher=request.user)
    
    # Map status to progress percentage
    status_map = {
        VideoSubmission.STATUS_PENDING: 10,      # 10% - waiting to start
        VideoSubmission.STATUS_PROCESSING: 50,   # 50% - currently processing
        VideoSubmission.STATUS_COMPLETED: 100,   # 100% - done
        VideoSubmission.STATUS_FAILED: 0,        # 0% - failed
    }
    
    progress = status_map.get(submission.status, 0)
    is_done = submission.status in [VideoSubmission.STATUS_COMPLETED, VideoSubmission.STATUS_FAILED]
    
    return JsonResponse({
        'status': submission.status,
        'progress': progress,
        'status_display': submission.get_status_display(),
        'is_done': is_done,
        'total_faces': submission.total_faces,
        'predicted_label': submission.predicted_label,
        'model_score': submission.model_score,
        'process_log': submission.process_log[-500:] if submission.process_log else '',  # Last 500 chars
    })


@role_required([UserProfile.ROLE_TEACHER])
def delete_submission(request, submission_id):
    """Delete a video submission and its associated files"""
    submission = get_object_or_404(VideoSubmission, id=submission_id, teacher=request.user)
    
    if request.method == 'POST':
        # Delete original video file
        if submission.original_video:
            try:
                submission.original_video.delete()
            except Exception as e:
                print(f"Error deleting video file: {e}")
        
        # Delete preprocessed directory
        if submission.preprocessed_dir:
            try:
                preproc_path = Path(submission.preprocessed_dir)
                if preproc_path.exists():
                    shutil.rmtree(preproc_path)
                    print(f"Deleted preprocessed directory: {preproc_path}")
            except Exception as e:
                print(f"Error deleting preprocessed directory: {e}")
        
        # Delete database record
        submission_id = submission.id
        submission.delete()
        messages.success(request, 'Video berhasil dihapus.')
        return redirect('teacher-dashboard')
    
    # If GET request, show confirmation page
    return render(request, 'teacher/confirm_delete.html', {'submission': submission})


@role_required([UserProfile.ROLE_PRINCIPAL])
def principal_dashboard(request):
    from django.utils import timezone
    from datetime import timedelta
    
    submissions = VideoSubmission.objects.select_related('teacher').all()
    summary = submissions.aggregate(
        total=Count('id'),
        completed=Count('id', filter=Q(status=VideoSubmission.STATUS_COMPLETED)),
    )

    completed_count = submissions.filter(status=VideoSubmission.STATUS_COMPLETED).count()
    processing_count = submissions.filter(status=VideoSubmission.STATUS_PROCESSING).count()
    failed_count = submissions.filter(status=VideoSubmission.STATUS_FAILED).count()

    # Analytics per Mata Pelajaran
    subject_stats = (
        submissions.filter(status=VideoSubmission.STATUS_COMPLETED)
        .values('subject')
        .annotate(
            total=Count('id'),
            avg_faces=Count('total_faces'),
        )
        .order_by('-total')
    )

    # Weekly breakdown (last 7 days)
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    weekly_data = (
        submissions.filter(
            status=VideoSubmission.STATUS_COMPLETED,
            created_at__date__gte=week_ago,
            created_at__date__lte=today
        )
        .extra(select={'date': 'DATE(created_at)'})
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )

    context = {
        'submissions': submissions[:20],
        'summary': summary,
        'completed_count': completed_count,
        'processing_count': processing_count,
        'failed_count': failed_count,
        'subject_stats': subject_stats,
        'weekly_data': weekly_data,
    }
    return render(request, 'principal/dashboard.html', context)


@role_required([UserProfile.ROLE_PRINCIPAL])
def principal_submission_detail(request, submission_id):
    submission = get_object_or_404(VideoSubmission, id=submission_id)
    return render(request, 'principal/submission_detail.html', {'submission': submission})


def home(request):
    if request.user.is_authenticated:
        return redirect('role-redirect')
    return redirect('login')


def about(request):
    return HttpResponseForbidden('Halaman about dinonaktifkan untuk sistem ini.')

