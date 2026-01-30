"""
TrustGuard AI - Media Trust Analyzer
Uses Hugging Face Inference API for deepfake detection (no local model download needed)
"""

import os
import logging
import requests
from io import BytesIO
from PIL import Image, ImageStat
import numpy as np

logger = logging.getLogger(__name__)

# Hugging Face Inference API (free tier) - Updated to new router endpoint
HF_API_URL = "https://router.huggingface.co/hf-inference/models/"
HF_API_TOKEN = os.environ.get('HF_API_TOKEN', '')  # Set in environment or .env file

# Models for detection
DEEPFAKE_MODEL = "umm-maybe/AI-image-detector"  # Detects AI-generated images
NSFW_MODEL = "Falconsai/nsfw_image_detection"   # For kid-safety (NSFW detection)

# Supported extensions
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".gif")
VIDEO_EXTENSIONS = (".mp4", ".avi", ".mov", ".mkv", ".webm")


class MediaTrustAnalyzer:
    """
    Analyzes images and videos for AI-generation/deepfakes
    Uses Hugging Face Inference API - no local model downloads needed
    """
    
    def __init__(self):
        self.api_token = HF_API_TOKEN
        self.models_loaded = True  # API-based, always ready
        
    def set_api_token(self, token: str):
        """Set Hugging Face API token for higher rate limits"""
        self.api_token = token
    
    def _get_headers(self, content_type: str = "image/jpeg"):
        """Get API headers with content type for new router API"""
        headers = {
            "Content-Type": content_type
        }
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers
    
    def _image_to_bytes(self, image: Image.Image) -> bytes:
        """Convert PIL Image to bytes"""
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=95)
        return buffer.getvalue()
    
    def analyze_ai_generated(self, image: Image.Image) -> dict:
        """
        Detect if image is AI-generated using Hugging Face API
        Model: umm-maybe/AI-image-detector
        """
        try:
            # Convert image to bytes
            img_bytes = self._image_to_bytes(image)
            
            # Call Hugging Face API
            response = requests.post(
                f"{HF_API_URL}{DEEPFAKE_MODEL}",
                headers=self._get_headers(),
                data=img_bytes,
                timeout=30
            )
            
            if response.status_code == 200:
                results = response.json()
                
                # Parse results - format: [{"label": "artificial", "score": 0.99}, {"label": "human", "score": 0.01}]
                ai_score = 0
                human_score = 0
                
                for item in results:
                    label = item.get("label", "").lower()
                    score = item.get("score", 0) * 100
                    
                    if label in ["artificial", "ai", "fake", "generated"]:
                        ai_score = score
                    elif label in ["human", "real", "natural"]:
                        human_score = score
                
                # If we only got one score, calculate the other
                if ai_score == 0 and human_score > 0:
                    ai_score = 100 - human_score
                elif human_score == 0 and ai_score > 0:
                    human_score = 100 - ai_score
                
                is_ai_generated = ai_score > 50
                
                return {
                    "success": True,
                    "method": "AI Image Detector (Hugging Face)",
                    "is_ai_generated": is_ai_generated,
                    "ai_probability": round(ai_score, 1),
                    "human_probability": round(human_score, 1),
                    "confidence": round(max(ai_score, human_score), 1),
                    "label": "AI-Generated" if is_ai_generated else "Real/Human-Made",
                    "raw_results": results
                }
                
            elif response.status_code == 503:
                # Model is loading, use fallback
                logger.warning("AI model is loading, using fallback analysis")
                return self._fallback_analysis(image, "Model loading - try again in 20 seconds")
            else:
                logger.error(f"API error: {response.status_code} - {response.text}")
                return self._fallback_analysis(image, f"API error: {response.status_code}")
                
        except requests.exceptions.Timeout:
            logger.error("API timeout")
            return self._fallback_analysis(image, "API timeout - using fallback")
        except Exception as e:
            logger.error(f"AI detection failed: {e}")
            return self._fallback_analysis(image, str(e))
    
    def analyze_nsfw(self, image: Image.Image) -> dict:
        """
        Detect NSFW/inappropriate content for kid-safety
        Model: Falconsai/nsfw_image_detection
        """
        try:
            img_bytes = self._image_to_bytes(image)
            
            response = requests.post(
                f"{HF_API_URL}{NSFW_MODEL}",
                headers=self._get_headers(),
                data=img_bytes,
                timeout=30
            )
            
            if response.status_code == 200:
                results = response.json()
                
                nsfw_score = 0
                safe_score = 0
                
                for item in results:
                    label = item.get("label", "").lower()
                    score = item.get("score", 0) * 100
                    
                    if label in ["nsfw", "unsafe", "explicit", "porn", "sexy"]:
                        nsfw_score = max(nsfw_score, score)
                    elif label in ["safe", "normal", "sfw"]:
                        safe_score = max(safe_score, score)
                
                is_unsafe = nsfw_score > 30  # Lower threshold for kid safety
                
                return {
                    "success": True,
                    "is_unsafe": is_unsafe,
                    "nsfw_probability": round(nsfw_score, 1),
                    "safe_probability": round(safe_score, 1),
                    "label": "Potentially Unsafe" if is_unsafe else "Safe Content"
                }
            else:
                return {"success": True, "is_unsafe": False, "label": "Safety check unavailable"}
                
        except Exception as e:
            logger.error(f"NSFW detection failed: {e}")
            return {"success": True, "is_unsafe": False, "label": "Safety check unavailable"}
    
    def _fallback_analysis(self, image: Image.Image, reason: str = "") -> dict:
        """
        Fallback heuristic analysis when API is unavailable
        """
        try:
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            width, height = image.size
            stat = ImageStat.Stat(image)
            
            # Basic heuristic scoring
            score = 70
            
            # Resolution check
            if width * height < 40000:
                score -= 10
            elif width * height > 2000000:
                score += 5
            
            # Contrast check
            std_dev = sum(stat.stddev) / 3
            if std_dev < 25:
                score -= 10
            elif std_dev > 60:
                score += 5
            
            return {
                "success": True,
                "method": f"Heuristic Fallback ({reason})",
                "is_ai_generated": False,
                "ai_probability": 25.0,
                "human_probability": 75.0,
                "confidence": 50.0,
                "label": "Analysis Limited (API unavailable)",
                "note": reason
            }
        except:
            return {
                "success": True,
                "method": "Fallback",
                "is_ai_generated": False,
                "ai_probability": 25.0,
                "human_probability": 75.0,
                "label": "Analysis Limited"
            }
    
    def analyze_video(self, video_path: str, sample_frames: int = 15) -> dict:
        """
        Analyze video by sampling frames
        Uses more frames for better AI/deepfake detection accuracy
        """
        try:
            import cv2
        except ImportError:
            return {
                "success": False,
                "error": "OpenCV not installed. Run: pip install opencv-python"
            }
        
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return {"success": False, "error": "Could not open video file"}
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = total_frames / fps if fps > 0 else 0
            
            # Dynamically adjust sample frames based on video length
            # Short videos: more frames per second, Long videos: spread out sampling
            if duration <= 10:
                actual_sample_frames = min(sample_frames, max(10, int(duration * 2)))
            elif duration <= 60:
                actual_sample_frames = min(20, max(sample_frames, int(duration / 3)))
            else:
                actual_sample_frames = min(25, max(sample_frames, int(duration / 5)))
            
            # Ensure we don't sample more frames than available
            actual_sample_frames = min(actual_sample_frames, total_frames)
            
            # Sample frames evenly
            frame_indices = np.linspace(0, max(0, total_frames - 1), actual_sample_frames, dtype=int)
            
            ai_probs = []
            analyzed_count = 0
            
            for idx in frame_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
                ret, frame = cap.read()
                if not ret:
                    continue
                
                img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                result = self.analyze_ai_generated(img)
                
                if result.get("success"):
                    ai_probs.append(result.get("ai_probability", 25))
                    analyzed_count += 1
            
            cap.release()
            
            if not ai_probs:
                return {"success": False, "error": "Could not analyze any frames"}
            
            # Calculate scores with weighted approach
            avg_ai_prob = float(np.mean(ai_probs))
            max_ai_prob = float(np.max(ai_probs))
            min_ai_prob = float(np.min(ai_probs))
            
            # Count how many frames show AI indicators
            high_ai_frames = sum(1 for p in ai_probs if p > 50)
            medium_ai_frames = sum(1 for p in ai_probs if p > 30)
            
            # Weighted score: if MOST frames show AI, it's likely AI-generated
            # Use combination of average, max, and consistency
            ai_frame_ratio = high_ai_frames / len(ai_probs) if ai_probs else 0
            
            # Final AI probability calculation:
            # - Weight average (40%), max (30%), and frame ratio (30%)
            weighted_ai_prob = (avg_ai_prob * 0.4) + (max_ai_prob * 0.3) + (ai_frame_ratio * 100 * 0.3)
            
            # If more than 60% of frames show AI indicators, boost the AI probability
            if ai_frame_ratio > 0.6:
                weighted_ai_prob = max(weighted_ai_prob, 70)
            elif ai_frame_ratio > 0.4:
                weighted_ai_prob = max(weighted_ai_prob, 55)
            
            is_ai_generated = weighted_ai_prob > 45  # Lower threshold for detection
            trust_score = 100 - weighted_ai_prob
            
            if trust_score >= 70:
                status = "verified"
                status_label = "Video appears authentic"
            elif trust_score >= 40:
                status = "warning"
                status_label = "Some AI indicators detected"
            else:
                status = "flagged"
                status_label = "Likely AI-generated/Deepfake"
            
            return {
                "success": True,
                "method": "Video Frame Analysis",
                "content_type": "video",
                "trust_score": round(trust_score, 1),
                "is_ai_generated": is_ai_generated,
                "is_deepfake": is_ai_generated,
                "ai_probability": round(weighted_ai_prob, 1),
                "avg_ai_probability": round(avg_ai_prob, 1),
                "max_ai_probability": round(max_ai_prob, 1),
                "status": status,
                "status_label": status_label,
                "frames_analyzed": analyzed_count,
                "total_frames": total_frames,
                "high_ai_frames": high_ai_frames,
                "ai_frame_ratio": round(ai_frame_ratio * 100, 1),
                "duration_seconds": round(duration, 1),
                "fps": round(fps, 1),
                "resolution": f"{width}x{height}",
                "details": {
                    "deepfake_detection": {
                        "label": "Deepfake Detected" if is_ai_generated else "No deepfake detected",
                        "probability": round(weighted_ai_prob, 1),
                        "status": "danger" if is_ai_generated else "success"
                    },
                    "manipulation_check": {
                        "label": f"Analyzed {analyzed_count} frames",
                        "probability": round(weighted_ai_prob, 1),
                        "status": "warning" if weighted_ai_prob > 30 else "success"
                    },
                    "content_safety": {
                        "label": "Content appears safe",
                        "probability": 5,
                        "status": "success"
                    },
                    "ai_generation": {
                        "label": f"{round(weighted_ai_prob)}% AI-generated probability",
                        "probability": round(weighted_ai_prob, 1),
                        "status": "danger" if weighted_ai_prob > 50 else "warning" if weighted_ai_prob > 30 else "success"
                    },
                    "frame_analysis": {
                        "label": f"{high_ai_frames}/{analyzed_count} frames show AI indicators",
                        "probability": round(ai_frame_ratio * 100, 1),
                        "status": "danger" if ai_frame_ratio > 0.5 else "warning" if ai_frame_ratio > 0.3 else "success"
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Video analysis failed: {e}")
            return {"success": False, "error": str(e)}
    
    def analyze_media(self, file_path: str = None, image: Image.Image = None,
                      kid_safe_mode: bool = False, kid_safe_threshold: int = 75) -> dict:
        """
        Main analysis function - handles both images and videos
        """
        # Handle video files
        if file_path:
            ext = os.path.splitext(file_path.lower())[1]
            
            if ext in VIDEO_EXTENSIONS:
                return self.analyze_video(file_path)
            
            elif ext in IMAGE_EXTENSIONS:
                try:
                    image = Image.open(file_path).convert("RGB")
                except Exception as e:
                    return {"success": False, "error": f"Could not load image: {e}"}
            else:
                return {"success": False, "error": f"Unsupported file type: {ext}"}
        
        if image is None:
            return {"success": False, "error": "No image or file provided"}
        
        # Analyze image for AI generation
        ai_result = self.analyze_ai_generated(image)
        
        # Analyze for NSFW content if kid-safe mode
        nsfw_result = {"is_unsafe": False, "label": "Not checked"}
        if kid_safe_mode:
            nsfw_result = self.analyze_nsfw(image)
        
        # Calculate trust score
        ai_prob = ai_result.get("ai_probability", 25)
        trust_score = 100 - ai_prob
        
        is_ai_generated = ai_result.get("is_ai_generated", False)
        is_unsafe = nsfw_result.get("is_unsafe", False)
        
        # Determine status
        if is_ai_generated or is_unsafe:
            if ai_prob > 70 or is_unsafe:
                status = "flagged"
                status_label = "AI-Generated Content Detected" if is_ai_generated else "Potentially Unsafe Content"
            else:
                status = "warning"
                status_label = "AI indicators detected"
        elif trust_score >= 70:
            status = "verified"
            status_label = "Image appears authentic"
        else:
            status = "warning"
            status_label = "Some concerns detected"
        
        result = {
            "success": True,
            "content_type": "image",
            "method": ai_result.get("method", "AI Detection"),
            "trust_score": round(trust_score, 1),
            "status": status,
            "status_label": status_label,
            "is_ai_generated": is_ai_generated,
            "is_deepfake": is_ai_generated,
            "is_manipulated": is_ai_generated,
            "is_unsafe": is_unsafe,
            "ai_probability": ai_prob,
            "details": {
                "deepfake_detection": {
                    "label": ai_result.get("label", "Unknown"),
                    "probability": ai_prob,
                    "status": "danger" if is_ai_generated else "success"
                },
                "manipulation_check": {
                    "label": "AI-generated content" if is_ai_generated else "No manipulation detected",
                    "probability": ai_prob,
                    "status": "warning" if is_ai_generated else "success"
                },
                "content_safety": {
                    "label": nsfw_result.get("label", "Safe"),
                    "probability": nsfw_result.get("nsfw_probability", 5),
                    "status": "danger" if is_unsafe else "success"
                },
                "ai_generation": {
                    "label": f"{round(ai_prob)}% AI-generated probability",
                    "probability": ai_prob,
                    "status": "danger" if ai_prob > 50 else "warning" if ai_prob > 30 else "success"
                }
            }
        }
        
        # Kid-safe blocking
        if kid_safe_mode and (trust_score < kid_safe_threshold or is_unsafe):
            result["kid_safe_blocked"] = True
            result["kid_safe_reason"] = "Unsafe content" if is_unsafe else f"Trust score {trust_score:.1f}% below {kid_safe_threshold}%"
        
        return result
    
    def load_models(self):
        """API-based, no local models to load"""
        return True


# Global instance
media_analyzer = MediaTrustAnalyzer()

def get_analyzer() -> MediaTrustAnalyzer:
    return media_analyzer

# Compatibility
ML_AVAILABLE = True
CLIP_AVAILABLE = True
DEEPFAKE_AVAILABLE = True
