import io
import logging
from typing import Dict, List, Tuple
import httpx
from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)


class ImprovedMediaTrustEngine:
    """Enhanced AI image detection - fixed numpy serialization"""
    
    def __init__(self):
        self.min_image_size = 100
        self.analysis_size = 256
    
    async def analyze(self, images: List[str], videos: List[str]) -> Dict:
        """Analyze images and videos"""
        if not images and not videos:
            return {
                "score": None,
                "applicable": False,
                "reason": "No media to analyze",
                "details": None
            }
        
        image_results = []
        ai_images = 0
        
        for img_url in images[:15]:
            result = await self._analyze_image_url(img_url)
            image_results.append(result)
            if result.get('is_ai_generated'):
                ai_images += 1
        
        video_results = []
        for vid_url in videos[:5]:
            result = self._analyze_video(vid_url)
            video_results.append(result)
        
        score = self._calculate_score(image_results, video_results)
        
        return {
            "score": int(score),  # Ensure int
            "applicable": True,
            "details": {
                "images": {
                    "total": len(images),
                    "analyzed": len(image_results),
                    "ai_generated_count": int(ai_images),
                    "results": image_results,
                    "message": self._get_image_message(ai_images, len(image_results))
                },
                "videos": {
                    "total": len(videos),
                    "analyzed": len(video_results),
                    "results": video_results,
                    "message": f"{len(video_results)} video(s) analyzed"
                }
            }
        }
    
    async def _analyze_image_url(self, url: str) -> Dict:
        """Analyze image from URL"""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                image_data = response.content
            
            return await self.analyze_single_image_enhanced(image_data, url)
            
        except Exception as e:
            logger.error(f"Error analyzing image {url}: {e}")
            return {
                "url": url,
                "is_ai_generated": False,
                "confidence": 0.0,
                "error": str(e)
            }
    
    async def analyze_single_image_enhanced(self, image_data: bytes, url: str = None) -> Dict:
        """Enhanced single image analysis with numpy fix"""
        try:
            image = Image.open(io.BytesIO(image_data))
            original_size = image.size
            
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            if image.width < self.min_image_size or image.height < self.min_image_size:
                return {
                    "url": url,
                    "is_ai_generated": False,
                    "confidence": 0.0,
                    "note": "Image too small for analysis",
                    "size": list(original_size)  # Convert tuple to list
                }
            
            image_resized = image.resize((self.analysis_size, self.analysis_size))
            img_array = np.array(image_resized) / 255.0
            
            # Run detection methods
            detections = {
                "texture": self._texture_analysis(img_array),
                "color": self._color_analysis(img_array),
                "edge": self._edge_analysis(img_array),
                "noise": self._noise_analysis(img_array),
                "symmetry": self._symmetry_analysis(img_array),
            }
            
            is_ai, confidence, indicators = self._aggregate_detections(detections)
            
            return {
                "url": url,
                "is_ai_generated": bool(is_ai),  # Convert numpy.bool to Python bool
                "confidence": float(confidence),  # Convert to Python float
                "indicators": indicators,
                "size": list(original_size),  # Convert tuple to list
                "format": str(image.format) if image.format else "unknown"
            }
            
        except Exception as e:
            logger.error(f"Image analysis error: {e}")
            return {
                "url": url,
                "is_ai_generated": False,
                "confidence": 0.0,
                "error": str(e)
            }
    
    def _texture_analysis(self, img_array: np.ndarray) -> Dict:
        """Analyze texture patterns"""
        gray = np.mean(img_array, axis=2)
        
        window_size = 16
        variances = []
        
        for i in range(0, gray.shape[0] - window_size, window_size):
            for j in range(0, gray.shape[1] - window_size, window_size):
                window = gray[i:i+window_size, j:j+window_size]
                variances.append(float(np.var(window)))
        
        if not variances:
            return {"suspicious": False, "confidence": 0.0}
        
        variance_of_variances = float(np.var(variances))
        mean_variance = float(np.mean(variances))
        
        is_suspicious = variance_of_variances < 0.001 and mean_variance < 0.01
        confidence = 0.3 if is_suspicious else 0.0
        
        return {
            "suspicious": bool(is_suspicious),
            "confidence": float(confidence),
            "indicator": "uniform_texture" if is_suspicious else None
        }
    
    def _color_analysis(self, img_array: np.ndarray) -> Dict:
        """Analyze color distribution"""
        r, g, b = img_array[:,:,0], img_array[:,:,1], img_array[:,:,2]
        
        rg_corr = float(np.corrcoef(r.flatten(), g.flatten())[0, 1])
        gb_corr = float(np.corrcoef(g.flatten(), b.flatten())[0, 1])
        rb_corr = float(np.corrcoef(r.flatten(), b.flatten())[0, 1])
        
        # Handle NaN
        if np.isnan(rg_corr): rg_corr = 0.0
        if np.isnan(gb_corr): gb_corr = 0.0
        if np.isnan(rb_corr): rb_corr = 0.0
        
        avg_corr = (abs(rg_corr) + abs(gb_corr) + abs(rb_corr)) / 3
        
        is_suspicious = avg_corr > 0.95
        confidence = 0.25 if is_suspicious else 0.0
        
        return {
            "suspicious": bool(is_suspicious),
            "confidence": float(confidence),
            "indicator": "high_color_correlation" if is_suspicious else None
        }
    
    def _edge_analysis(self, img_array: np.ndarray) -> Dict:
        """Analyze edge coherence"""
        gray = np.mean(img_array, axis=2)
        
        edges_h = np.abs(np.diff(gray, axis=0))
        edges_v = np.abs(np.diff(gray, axis=1))
        
        edge_mean = float((np.mean(edges_h) + np.mean(edges_v)) / 2)
        edge_variance = float((np.var(edges_h) + np.var(edges_v)) / 2)
        
        is_suspicious = edge_mean < 0.02 and edge_variance < 0.001
        confidence = 0.2 if is_suspicious else 0.0
        
        return {
            "suspicious": bool(is_suspicious),
            "confidence": float(confidence),
            "indicator": "smooth_edges" if is_suspicious else None
        }
    
    def _noise_analysis(self, img_array: np.ndarray) -> Dict:
        """Analyze noise patterns"""
        gray = np.mean(img_array, axis=2)
        
        # Simple high-pass filter
        padded = np.pad(gray, 1, mode='reflect')
        local_mean = np.zeros_like(gray)
        
        for i in range(gray.shape[0]):
            for j in range(gray.shape[1]):
                local_mean[i, j] = np.mean(padded[i:i+3, j:j+3])
        
        noise = gray - local_mean
        noise_std = float(np.std(noise))
        
        is_suspicious = noise_std < 0.005 or noise_std > 0.1
        confidence = 0.15 if is_suspicious else 0.0
        
        return {
            "suspicious": bool(is_suspicious),
            "confidence": float(confidence),
            "indicator": "unusual_noise" if is_suspicious else None
        }
    
    def _symmetry_analysis(self, img_array: np.ndarray) -> Dict:
        """Check for unnatural symmetry"""
        mid = img_array.shape[1] // 2
        left = img_array[:, :mid, :]
        right = np.flip(img_array[:, mid:mid+left.shape[1], :], axis=1)
        
        if left.shape != right.shape:
            return {"suspicious": False, "confidence": 0.0}
        
        diff = np.abs(left - right)
        symmetry_score = float(1 - np.mean(diff))
        
        is_suspicious = symmetry_score > 0.9
        confidence = 0.2 if is_suspicious else 0.0
        
        return {
            "suspicious": bool(is_suspicious),
            "confidence": float(confidence),
            "indicator": "unnatural_symmetry" if is_suspicious else None
        }
    
    def _aggregate_detections(self, detections: Dict) -> Tuple[bool, float, List[str]]:
        """Aggregate detection results"""
        total_confidence = 0.0
        suspicious_count = 0
        indicators = []
        
        for method, result in detections.items():
            if result.get('suspicious'):
                suspicious_count += 1
                total_confidence += result.get('confidence', 0)
                if result.get('indicator'):
                    indicators.append(result['indicator'])
        
        confidence = min(total_confidence, 0.95)
        is_ai = suspicious_count >= 3 or (suspicious_count >= 2 and confidence > 0.4)
        
        return bool(is_ai), float(round(confidence, 2)), indicators
    
    def _get_image_message(self, ai_count: int, total: int) -> str:
        if ai_count > 0:
            return f"🤖 {ai_count} AI-generated image(s) detected out of {total}"
        elif total > 0:
            return f"✓ All {total} image(s) appear authentic"
        return "No images analyzed"
    
    def _analyze_video(self, url: str) -> Dict:
        """Video analysis placeholder"""
        is_youtube = 'youtube.com' in url or 'youtu.be' in url
        is_vimeo = 'vimeo.com' in url
        
        return {
            "url": url,
            "is_ai_generated": False,
            "confidence": 0.5,
            "platform": "youtube" if is_youtube else "vimeo" if is_vimeo else "unknown",
            "note": "Video frame analysis not implemented"
        }
    
    async def analyze_multiple_images(self, urls: List[str]) -> List[Dict]:
        """Analyze multiple images"""
        results = []
        for url in urls[:20]:
            result = await self._analyze_image_url(url)
            results.append(result)
        return results
    
    def _calculate_score(self, image_results: List[Dict], video_results: List[Dict]) -> int:
        """Calculate media trust score"""
        if not image_results and not video_results:
            return 100
        
        score = 100
        
        for result in image_results:
            if result.get('is_ai_generated'):
                confidence = result.get('confidence', 0.5)
                if confidence > 0.7:
                    score -= 30
                elif confidence > 0.5:
                    score -= 20
                else:
                    score -= 12
        
        for result in video_results:
            if result.get('is_ai_generated'):
                score -= 25
        
        return max(0, min(100, int(score)))