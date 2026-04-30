import torch
import torch.nn as nn
from pathlib import Path
import numpy as np
from PIL import Image


class SimpleEfficientNetInference:
    """Wrapper untuk EfficientNet B2 model untuk inferensi pada face crops."""

    def __init__(self, model_path: str, device: str = 'cpu'):
        self.device = device
        self.model = self._load_model(model_path)
        self.model.to(device)
        self.model.eval()

    def _load_model(self, model_path: str):
        """Load model dari .pth file."""
        try:
            checkpoint = torch.load(model_path, map_location='cpu')
            
            # EfficientNet B2 dengan classifier 6-class
            from torchvision import models
            from torch.nn import Sequential, Linear, Dropout, ReLU
            
            model = models.efficientnet_b2(pretrained=False)
            
            # Build classifier sesuai checkpoint:
            # classifier.1 = Linear(1408, 768)
            # classifier.4 = Linear(768, 6) 
            num_features = model.classifier[1].in_features  # 1408
            
            model.classifier = Sequential(
                model.classifier[0],      # Dropout(p=0.3, inplace=True)
                Linear(num_features, 768),  # Linear(1408, 768)
                ReLU(inplace=True),       # activation
                Dropout(p=0.3, inplace=True),  # classifier.2 placeholder (Dropout)
                Linear(768, 6),           # Linear(768, 6) - 6 class output
            )
            
            model.load_state_dict(checkpoint)
            # Convert model to float32 for inference compatibility
            model = model.float()
            return model
        except Exception as e:
            print(f"Error loading model: {e}")
            raise

    def predict_on_faces(self, face_dir: str) -> tuple:
        """
        Prediksi pada semua face crops di folder.
        Classifier menghasilkan 6 classes untuk expression recognition:
        0=Angry, 1=Happy, 2=Neutral, 3=Sad, 4=Surprised, 5=Tired
        
        Return: (total_faces, avg_confidence, predicted_label, expression_breakdown)
        expression_breakdown = {'Angry': count, 'Happy': count, ...}
        """
        face_dir = Path(face_dir)
        face_files = sorted(face_dir.glob('face_*.jpg'))
        
        if not face_files:
            return 0, 0.0, 'Tidak ada face', {}

        predictions = []
        error_count = 0
        
        # Expression class mapping (MUST match training: angry, happy, neutral, sad, surprised, tired)
        expression_map = {
            0: 'Angry',
            1: 'Happy',
            2: 'Neutral',
            3: 'Sad',
            4: 'Surprised',
            5: 'Tired'
        }
        
        with torch.no_grad():
            for i, face_file in enumerate(face_files):  # Process ALL faces
                try:
                    img = Image.open(face_file).convert('RGB')
                    img_tensor = self._preprocess(img)
                    img_tensor = img_tensor.to(self.device)
                    img_tensor = img_tensor.float()
                    
                    output = self.model(img_tensor)
                    probs = torch.softmax(output, dim=1)
                    conf, pred_class = torch.max(probs, dim=1)
                    
                    predictions.append({
                        'confidence': conf.item(),
                        'class': pred_class.item(),
                        'expression': expression_map.get(pred_class.item(), 'Unknown')
                    })
                except Exception as e:
                    error_count += 1
                    print(f"[Model Inference] Error on face {i} ({face_file.name}): {type(e).__name__}: {str(e)[:60]}")
                    continue

        if not predictions:
            return len(face_files), 0.0, f'Model failed on all faces ({error_count} errors)', {}

        # Calculate breakdown from ALL predictions (no confidence filter)
        breakdown = {expr: 0 for expr in expression_map.values()}
        for pred in predictions:
            breakdown[pred['expression']] += 1

        avg_confidence = np.mean([p['confidence'] for p in predictions])
        pred_classes = [p['class'] for p in predictions]
        most_common_class = max(set(pred_classes), key=pred_classes.count)
        
        # Determine overall label based on most common expression
        most_common_expression = expression_map.get(most_common_class, 'Unknown')
        label = f'{most_common_expression} (dominan)'
        
        # Ensure score is 0-100 (cap if exceeds)
        score = min(avg_confidence * 100.0, 100.0)
        score = max(score, 0.0)
        score = round(score, 2)
        
        return len(face_files), score, label, breakdown

    def _preprocess(self, img: Image.Image) -> torch.Tensor:
        """Preprocess image untuk model efficientnet."""
        img = img.resize((224, 224))
        img_array = np.array(img).astype(np.float32)
        img_array = img_array / 255.0
        
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        img_array = (img_array - mean) / std
        
        tensor = torch.from_numpy(img_array).permute(2, 0, 1).unsqueeze(0)
        # Ensure tensor is float32 to match model weights
        tensor = tensor.float()
        return tensor
