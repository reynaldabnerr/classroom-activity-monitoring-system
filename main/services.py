import subprocess
import sys
import json
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from .models import VideoSubmission
from .model_inference import SimpleEfficientNetInference


def _run_preprocessing(video_path, output_dir):
    script_path = settings.BASE_DIR / 'extract_face_single_video.py'
    command = [
        sys.executable,
        str(script_path),
        '--input-video',
        str(video_path),
        '--output-dir',
        str(output_dir),
        '--target-size',
        '224',
        '--min-faces',
        '200',
    ]

    result = subprocess.run(command, capture_output=True, text=True)
    return result.returncode == 0, (result.stdout or '') + '\n' + (result.stderr or '')


def _run_dummy_model_on_preprocessed(preprocessed_dir):
    """Run inference menggunakan model EfficientNet B2 yang sesungguhnya."""
    model_path = settings.BASE_DIR / 'efficientnet_b2_final.pth'
    
    # Default breakdown if model not found
    default_breakdown = {'Happy': 0, 'Sad': 0, 'Angry': 0, 'Surprised': 0, 'Neutral': 0, 'Tired': 0}
    
    if not model_path.exists():
        print(f"WARNING: Model file not found at {model_path}, menggunakan fallback scoring")
        files = sorted(Path(preprocessed_dir).glob('face_*.jpg'))
        total_faces = len(files)
        if total_faces == 0:
            return 0, 0.0, 'Tidak terdeteksi', default_breakdown
        score = min(100.0, (total_faces / 200.0) * 100.0)
        if score >= 80:
            label = 'Kehadiran Tinggi'
        elif score >= 50:
            label = 'Kehadiran Sedang'
        else:
            label = 'Kehadiran Rendah'
        return total_faces, score, label, default_breakdown

    try:
        model = SimpleEfficientNetInference(str(model_path), device='cpu')
        total_faces, confidence, label, breakdown = model.predict_on_faces(preprocessed_dir)
        # confidence is already 0-100, no need to scale
        return total_faces, confidence, label, breakdown
    except Exception as e:
        print(f"Model inference error: {e}")
        files = sorted(Path(preprocessed_dir).glob('face_*.jpg'))
        total_faces = len(files)
        return total_faces, 0.0, f'Gagal inference: {str(e)[:40]}', default_breakdown


def process_submission(submission: VideoSubmission):
    submission.status = VideoSubmission.STATUS_PROCESSING
    submission.save(update_fields=['status'])

    out_dir = settings.MEDIA_ROOT / 'videos' / 'preprocessed' / f'submission_{submission.id}'
    out_dir.mkdir(parents=True, exist_ok=True)

    ok, logs = _run_preprocessing(submission.original_video.path, out_dir)
    submission.process_log = logs.strip()

    if not ok:
        submission.status = VideoSubmission.STATUS_FAILED
        submission.processed_at = timezone.now()
        submission.preprocessed_dir = str(out_dir)
        submission.save(update_fields=['status', 'processed_at', 'preprocessed_dir', 'process_log'])
        return

    total_faces, score, label, breakdown = _run_dummy_model_on_preprocessed(out_dir)
    submission.status = VideoSubmission.STATUS_COMPLETED
    submission.total_faces = total_faces
    submission.model_score = score
    submission.predicted_label = label
    submission.expression_breakdown = json.dumps(breakdown)
    submission.processed_at = timezone.now()
    submission.preprocessed_dir = str(out_dir)
    submission.save(
        update_fields=[
            'status',
            'total_faces',
            'model_score',
            'predicted_label',
            'expression_breakdown',
            'processed_at',
            'preprocessed_dir',
            'process_log',
        ]
    )
