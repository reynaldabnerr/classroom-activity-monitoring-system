import argparse
import cv2
import os
import os.path as osp
import shutil
import sys
from pathlib import Path
from ultralytics import YOLO
from huggingface_hub import hf_hub_download

# Try to import mediapipe - if fails, we'll use fallback
try:
    import mediapipe as mp
    HAS_MEDIAPIPE = True
    MP_VERSION = mp.__version__
    # For mediapipe >= 0.10, we need different imports
    if hasattr(mp, 'solutions'):
        MEDIAPIPE_LEGACY = True
    else:
        MEDIAPIPE_LEGACY = False
except ImportError:
    HAS_MEDIAPIPE = False
    MEDIAPIPE_LEGACY = False

# ===============================
# 1. INPUT VIDEO & OUTPUT FOLDER
# ===============================
# Fallback default only for manual CLI run.
# In web flow, these are overridden by --input-video and --output-dir from main/services.py.
SINGLE_VIDEO = str(Path('media') / 'videos' / 'raw' / 'sample.mp4')
OUTPUT_DIR = str(Path('media') / 'videos' / 'preprocessed' / 'sample_submission')

TARGET_SIZE = 224
MIN_FACES = 200

# ===============================
# 2. LOAD MODELS
# ===============================
model_path = hf_hub_download(
    repo_id="arnabdhar/YOLOv8-Face-Detection",
    filename="model.pt"
)
model = YOLO(model_path)

# Initialize mediapipe if available and in legacy mode
mp_face = None
if HAS_MEDIAPIPE and MEDIAPIPE_LEGACY:
    mp_face = mp.solutions.face_mesh.FaceMesh(
        refine_landmarks=True,
        max_num_faces=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )
    print(f"MediaPipe {MP_VERSION} (legacy) loaded for face quality assessment")
elif HAS_MEDIAPIPE:
    print(f"MediaPipe {MP_VERSION} (new API) detected - using fallback face validation")

# ===============================
# 3. QUALITY HELPERS
# ===============================
def is_frontal_face_mediapipe(face_img, landmarks):
    """Check if face is frontal using mediapipe landmarks"""
    if not landmarks:
        return False
    
    nose = landmarks[1]
    left_eye = landmarks[33]
    right_eye = landmarks[263]

    dx = abs(left_eye.x - right_eye.x)
    dy = abs(left_eye.y - right_eye.y)

    if dy > dx * 0.25:
        return False
    if abs(nose.x - 0.5) > 0.15:
        return False
    return True


def is_frontal_face_fallback(face_img):
    """Fallback face validation using simple heuristics"""
    h, w = face_img.shape[:2]
    
    # Simple checks: face should be roughly centered and have reasonable aspect ratio
    # This is a basic fallback when mediapipe is not available
    if h < 20 or w < 20:
        return False
    
    aspect_ratio = w / h
    # Face aspect ratio should be between 0.7 and 1.4
    if aspect_ratio < 0.7 or aspect_ratio > 1.4:
        return False
    
    return True


def is_frontal_face(face_img, mp_landmarks=None):
    """Check if face is frontal - tries mediapipe first, falls back to simple heuristics"""
    if mp_face is not None and mp_landmarks is not None:
        return is_frontal_face_mediapipe(face_img, mp_landmarks)
    else:
        return is_frontal_face_fallback(face_img)


def blur_score(img):
    return cv2.Laplacian(img, cv2.CV_64F).var()


def center_score(w, box):
    x1, _, x2, _ = box
    cx = (x1 + x2) / 2
    return 1 - abs(cx - w / 2) / w


# ===============================
# 4. PROCESS VIDEO
# ===============================
def process_video(video_path, output_dir, target_size, min_faces):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)

    if not cap.isOpened():
        print(f"ERROR: Could not open video: {video_path}")
        return -1

    if fps is None or fps <= 1:
        fps = 25.0

    interval = max(int(fps), 1)  # ~1 frame / second
    frame_idx = 0
    saved = 0

    print(f"\nProcessing: {video_path}")
    print(f"Output: {output_dir}")
    print(f"FPS: {fps:.2f} | Interval: {interval}")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        h, w = frame.shape[:2]
        results = model(frame, verbose=False)
        boxes = results[0].boxes

        best_score = 0
        best_face = None

        if boxes is not None:
            for box in boxes:
                conf = float(box.conf)
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                x1 = max(0, x1); y1 = max(0, y1)
                x2 = min(w, x2); y2 = min(h, y2)

                face = frame[y1:y2, x1:x2]
                if face.size == 0:
                    continue

                clarity = blur_score(face)
                cent = center_score(w, (x1, y1, x2, y2))

                # Try to validate face with mediapipe if available
                mp_landmarks = None
                if mp_face is not None:
                    face_rgb = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)
                    res = mp_face.process(face_rgb)
                    if res.multi_face_landmarks:
                        mp_landmarks = res.multi_face_landmarks[0].landmark
                    else:
                        # No face detected by mediapipe, skip
                        continue
                
                # Check if face is frontal (uses mediapipe if available, else fallback)
                if not is_frontal_face(face, mp_landmarks):
                    continue

                score = conf * 4 + clarity * 0.003 + cent * 2
                if score > best_score:
                    best_score = score
                    best_face = face

        if frame_idx % interval == 0 and best_face is not None:
            out = cv2.resize(best_face, (target_size, target_size))
            cv2.imwrite(osp.join(output_dir, f"face_{saved}.jpg"), out)
            saved += 1

        frame_idx += 1

    cap.release()
    print(f"Saved {saved} faces")
    if saved < min_faces:
        print(f"WARNING: saved faces ({saved}) below MIN_FACES ({min_faces})")
    return saved


def parse_args():
    parser = argparse.ArgumentParser(description='Extract face crops from a single video.')
    parser.add_argument('--input-video', default=SINGLE_VIDEO, help='Path to input video file')
    parser.add_argument('--output-dir', default=OUTPUT_DIR, help='Directory for extracted faces')
    parser.add_argument('--target-size', type=int, default=TARGET_SIZE, help='Target face image size')
    parser.add_argument('--min-faces', type=int, default=MIN_FACES, help='Minimum expected face count')
    parser.add_argument('--keep-output', action='store_true', help='Do not clean old output directory')
    return parser.parse_args()


# ===============================
# 5. RUN (CLEAN OUTPUT)
# ===============================
if __name__ == "__main__":
    args = parse_args()

    if not args.keep_output and osp.isdir(args.output_dir):
        print(f"Removing old output: {args.output_dir}")
        shutil.rmtree(args.output_dir)

    os.makedirs(args.output_dir, exist_ok=True)
    count = process_video(args.input_video, args.output_dir, args.target_size, args.min_faces)

    print("\nSINGLE VIDEO PREPROCESSING DONE")
    sys.exit(0 if count >= 0 else 1)
