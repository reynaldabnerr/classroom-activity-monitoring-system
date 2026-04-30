import os
import django
import json
from pathlib import Path

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from main.models import VideoSubmission
from main.services import _check_ground_truth_from_dataset

def sync_validation():
    submissions = VideoSubmission.objects.all()
    print(f"Syncing {submissions.count()} submissions...")
    
    for sub in submissions:
        video_filename = os.path.basename(sub.original_video.name)
        predicted_label = sub.predicted_label or ""
        
        print(f"Processing: {video_filename} (ID: {sub.id})")
        
        # Run the validation logic
        gt_label, is_correct, gt_breakdown = _check_ground_truth_from_dataset(video_filename, predicted_label)
        
        if gt_label:
            sub.ground_truth_label = gt_label
            sub.ground_truth_breakdown = json.dumps(gt_breakdown)
            sub.is_correct = is_correct
            sub.save(update_fields=['ground_truth_label', 'ground_truth_breakdown', 'is_correct'])
            print(f"  ✅ Updated: GT={gt_label}, Correct={is_correct}")
        else:
            print(f"  ❌ No GT found for {video_filename}")

if __name__ == "__main__":
    sync_validation()
