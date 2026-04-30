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
    """Delete a video submission. Media files are handled by post_delete signal in models.py"""
    submission = get_object_or_404(VideoSubmission, id=submission_id, teacher=request.user)
    
    if request.method == 'POST':
        # Database record deletion will trigger post_delete signal
        submission.delete()
        messages.success(request, 'Video dan seluruh data medianya berhasil dihapus.')
        return redirect('teacher-dashboard')
    
    # If GET request, show confirmation page
    return render(request, 'teacher/confirm_delete.html', {'submission': submission})


@role_required([UserProfile.ROLE_PRINCIPAL])
def principal_dashboard(request):
    from django.utils import timezone
    from datetime import timedelta
    import json
    
    submissions = VideoSubmission.objects.select_related('teacher', 'teacher__profile').all()
    summary = submissions.aggregate(
        total=Count('id'),
        completed=Count('id', filter=Q(status=VideoSubmission.STATUS_COMPLETED)),
    )

    completed_count = submissions.filter(status=VideoSubmission.STATUS_COMPLETED).count()
    processing_count = submissions.filter(status=VideoSubmission.STATUS_PROCESSING).count()
    failed_count = submissions.filter(status=VideoSubmission.STATUS_FAILED).count()
    pending_count = submissions.filter(status=VideoSubmission.STATUS_PENDING).count()

    # Analytics per Mata Pelajaran dengan ekspresi dominan
    subject_stats = (
        submissions.values('subject')
        .annotate(
            total=Count('id'),
            completed=Count('id', filter=Q(status=VideoSubmission.STATUS_COMPLETED)),
            processing=Count('id', filter=Q(status=VideoSubmission.STATUS_PROCESSING)),
            failed=Count('id', filter=Q(status=VideoSubmission.STATUS_FAILED)),
        )
        .order_by('-total')
    )
    
    # Hitung ekspresi dominan untuk masing-masing subject
    for stat in subject_stats:
        stat['success_rate'] = (stat['completed'] / stat['total'] * 100) if stat['total'] > 0 else 0
        
        # Get expressions for this subject
        subject_submissions = submissions.filter(
            subject=stat['subject'],
            status=VideoSubmission.STATUS_COMPLETED
        )
        
        expression_freq = {}
        for submission in subject_submissions:
            try:
                breakdown = json.loads(submission.expression_breakdown)
                for expr, count in breakdown.items():
                    expression_freq[expr] = expression_freq.get(expr, 0) + count
            except:
                pass
        
        # Top 3 expressions for this subject
        stat['expressions'] = sorted(expression_freq.items(), key=lambda x: x[1], reverse=True)[:3]

    # Weekly breakdown (last 7 days)
    today = timezone.now().date()
    week_ago = today - timedelta(days=6)
    
    weekly_data = []
    for i in range(7):
        date = week_ago + timedelta(days=i)
        count = submissions.filter(
            status=VideoSubmission.STATUS_COMPLETED,
            created_at__date=date
        ).count()
        day_name = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu'][date.weekday()]
        weekly_data.append({
            'date': date,
            'day_name': day_name,
            'count': count
        })

    # Monthly breakdown (last 6 months)
    six_months_ago = today - timedelta(days=180)
    monthly_data = []
    for i in range(6):
        month_start = six_months_ago + timedelta(days=30*i)
        month_end = month_start + timedelta(days=29)
        count = submissions.filter(
            status=VideoSubmission.STATUS_COMPLETED,
            created_at__date__gte=month_start,
            created_at__date__lte=month_end
        ).count()
        monthly_data.append({
            'month': month_start.strftime('%b'),
            'count': count
        })

    # Teacher Performance (top 5 teachers)
    teacher_stats = (
        submissions.values('teacher__profile__full_name', 'teacher_id')
        .annotate(
            total=Count('id'),
            completed=Count('id', filter=Q(status=VideoSubmission.STATUS_COMPLETED)),
            failed=Count('id', filter=Q(status=VideoSubmission.STATUS_FAILED)),
        )
        .order_by('-total')[:5]
    )
    
    for stat in teacher_stats:
        stat['success_rate'] = (stat['completed'] / stat['total'] * 100) if stat['total'] > 0 else 0
        stat['full_name'] = stat['teacher__profile__full_name'] or 'Unknown'

    # Day of week analysis (activity pattern)
    day_analysis = (
        submissions.filter(status=VideoSubmission.STATUS_COMPLETED)
        .values('day')
        .annotate(total=Count('id'))
        .order_by('-total')
    )

    # Expression frequency (aggregate from all completed submissions)
    expression_freq = {}
    for submission in submissions.filter(status=VideoSubmission.STATUS_COMPLETED):
        try:
            breakdown = json.loads(submission.expression_breakdown)
            for expr, count in breakdown.items():
                expression_freq[expr] = expression_freq.get(expr, 0) + count
        except:
            pass
    
    # Top 5 expressions
    top_expressions = sorted(expression_freq.items(), key=lambda x: x[1], reverse=True)[:5]

    context = {
        'submissions': submissions[:20],
        'summary': summary,
        'completed_count': completed_count,
        'processing_count': processing_count,
        'failed_count': failed_count,
        'pending_count': pending_count,
        'subject_stats': subject_stats,
        'weekly_data': weekly_data,
        'monthly_data': monthly_data,
        'teacher_stats': teacher_stats,
        'day_analysis': day_analysis,
        'top_expressions': top_expressions,
    }
    return render(request, 'principal/dashboard.html', context)


@role_required([UserProfile.ROLE_PRINCIPAL])
def principal_submission_detail(request, submission_id):
    submission = get_object_or_404(VideoSubmission, id=submission_id)
    return render(request, 'principal/submission_detail.html', {'submission': submission})


@login_required
@role_required([UserProfile.ROLE_PRINCIPAL])
def submissions_by_date(request):
    """API endpoint untuk filter submissions berdasarkan date range"""
    from datetime import datetime
    
    date_from_str = request.GET.get('date_from')
    date_to_str = request.GET.get('date_to')
    
    if not date_from_str or not date_to_str:
        return JsonResponse({'error': 'date_from dan date_to harus disediakan'}, status=400)
    
    try:
        date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Format tanggal tidak valid'}, status=400)
    
    # Filter submissions berdasarkan date range
    submissions = VideoSubmission.objects.filter(
        created_at__date__gte=date_from,
        created_at__date__lte=date_to
    ).select_related('teacher', 'teacher__profile').order_by('-created_at')
    
    # Format data untuk response
    data = {
        'submissions': [
            {
                'id': sub.id,
                'teacher_name': sub.teacher.profile.full_name if hasattr(sub.teacher, 'profile') else 'Unknown',
                'subject': sub.get_subject_display() or sub.subject,
                'class_name': sub.class_name,
                'status': sub.status,
                'status_display': sub.get_status_display(),
                'expression': sub.predicted_label or '-',
                'created_at': sub.created_at.isoformat(),
            }
            for sub in submissions
        ]
    }
    
    return JsonResponse(data)


def home(request):
    if request.user.is_authenticated:
        return redirect('role-redirect')
    return redirect('login')


def about(request):
    return HttpResponseForbidden('Halaman about dinonaktifkan untuk sistem ini.')


@role_required([UserProfile.ROLE_PRINCIPAL])
def model_validation(request):
    import json
    from .services import _check_ground_truth_from_dataset, _extract_video_id

    submissions = VideoSubmission.objects.filter(status=VideoSubmission.STATUS_COMPLETED).order_by('-created_at')
    
    total_submissions = submissions.count()

    # Process submissions for display
    processed_submissions = []
    for sub in submissions:
        video_id = _extract_video_id(sub.original_video.name)

        if not sub.ground_truth_label or sub.ground_truth_breakdown in ("", "{}"):
            gt_label, is_correct, gt_breakdown = _check_ground_truth_from_dataset(
                sub.original_video.name,
                sub.predicted_label or ""
            )
            if gt_label:
                sub.ground_truth_label = gt_label
                sub.ground_truth_breakdown = json.dumps(gt_breakdown)
                sub.is_correct = is_correct
                sub.save(update_fields=['ground_truth_label', 'ground_truth_breakdown', 'is_correct'])

        # Load breakdowns
        model_breakdown = {}
        gt_breakdown = {}
        try:
            model_breakdown = json.loads(sub.expression_breakdown)
            gt_breakdown = json.loads(sub.ground_truth_breakdown)
        except:
            pass
            
        # Get duration logic (placeholder or from actual metadata if available)
        # Using a random dummy duration for Bab 4 simulation if not in model
        duration = f"{sub.total_faces // 30} menit" if sub.total_faces else "-"
        
        # Calculate percentages for distributions
        model_total = sum(model_breakdown.values()) if model_breakdown else 0
        gt_total = sum(gt_breakdown.values()) if gt_breakdown else 0
        
        clean_prediction = (sub.predicted_label or "").replace(' (dominan)', '').strip()
        
        distributions = []
        all_labels = set(list(model_breakdown.keys()) + list(gt_breakdown.keys()))
        for label in sorted(all_labels):
            model_val = model_breakdown.get(label, 0)
            gt_val = gt_breakdown.get(label, 0)
            
            model_pct = (model_val / model_total * 100) if model_total > 0 else 0
            gt_pct = (gt_val / gt_total * 100) if gt_total > 0 else 0
            
            distributions.append({
                'label': label,
                'model_count': model_val,
                'gt_count': gt_val,
                'model_pct': round(model_pct, 1),
                'gt_pct': round(gt_pct, 1),
                'is_match': (label == sub.ground_truth_label and label == clean_prediction)
            })
            
        # Calculate Similarity based on distribution difference
        total_diff = sum([abs(d['model_pct'] - d['gt_pct']) for d in distributions])
        avg_mae = total_diff / len(distributions) if distributions else 0
        similarity = max(0, 100 - avg_mae)

        processed_submissions.append({
            'obj': sub,
            'video_id': video_id,
            'duration': duration,
            'model_total': model_total,
            'gt_total': gt_total,
            'distributions': distributions,
            'similarity': round(similarity, 2)
        })

    total_valid = sum(1 for item in processed_submissions if item['obj'].is_correct is True)
    accuracy = (total_valid / total_submissions * 100) if total_submissions > 0 else 0
    avg_similarity = sum([s['similarity'] for s in processed_submissions]) / total_submissions if total_submissions > 0 else 0
        
    return render(request, 'principal/validation.html', {
        'submissions': processed_submissions,
        'total_submissions': total_submissions,
        'total_valid': total_valid,
        'accuracy': round(accuracy, 2),
        'avg_similarity': round(avg_similarity, 2)
    })
