import httpx
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class AIDetector:
    """Uses Hugging Face models for AI content detection"""
    
    def __init__(self):
        # Free AI detection models on Hugging Face
        self.models = {
            "roberta": "roberta-base-openai-detector",  # OpenAI's GPT detector
            "radar": "TrustSafeAI/RADAR-Vicuna-7B",     # Academic detector
            "hello": "Hello-SimpleAI/chatgpt-detector-roberta"  # ChatGPT detector
        }
        self.api_url = "https://api-inference.huggingface.co/models"
        self.hf_token = None  # Optional: Add your HF token for higher rate limits
    
    async def detect_ai_content(self, text: str) -> Dict:
        """
        Detect if text is AI-generated using multiple models
        Returns confidence score and detection result
        """
        if len(text) < 50:
            return {
                "is_ai": False,
                "confidence": 0.0,
                "method": "too_short",
                "message": "Text too short for reliable detection"
            }
        
        # Truncate for API limits
        text = text[:2000]
        
        results = []
        
        # Try OpenAI's RoBERTa detector (most reliable)
        roberta_result = await self._query_roberta_detector(text)
        if roberta_result:
            results.append(roberta_result)
        
        # Try ChatGPT detector
        chatgpt_result = await self._query_chatgpt_detector(text)
        if chatgpt_result:
            results.append(chatgpt_result)
        
        # Aggregate results
        if not results:
            # Fallback to heuristics
            return await self._heuristic_detection(text)
        
        # Average the confidences
        ai_confidences = [r['ai_probability'] for r in results]
        avg_confidence = sum(ai_confidences) / len(ai_confidences)
        
        is_ai = avg_confidence > 0.7
        
        return {
            "is_ai": is_ai,
            "confidence": round(avg_confidence, 3),
            "method": "ml_ensemble",
            "models_used": len(results),
            "message": self._get_message(is_ai, avg_confidence),
            "details": results
        }
    
    async def _query_roberta_detector(self, text: str) -> Optional[Dict]:
        """Query OpenAI's RoBERTa-based GPT detector"""
        try:
            headers = {}
            if self.hf_token:
                headers["Authorization"] = f"Bearer {self.hf_token}"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.api_url}/openai-community/roberta-base-openai-detector",
                    headers=headers,
                    json={"inputs": text}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    # Result format: [[{"label": "Real", "score": 0.7}, {"label": "Fake", "score": 0.3}]]
                    if isinstance(result, list) and len(result) > 0:
                        scores = {item['label']: item['score'] for item in result[0]}
                        ai_prob = scores.get('Fake', 0)  # "Fake" = AI-generated
                        return {
                            "model": "roberta-openai-detector",
                            "ai_probability": ai_prob,
                            "human_probability": scores.get('Real', 0)
                        }
        except Exception as e:
            logger.debug(f"RoBERTa detector error: {e}")
        
        return None
    
    async def _query_chatgpt_detector(self, text: str) -> Optional[Dict]:
        """Query ChatGPT-specific detector"""
        try:
            headers = {}
            if self.hf_token:
                headers["Authorization"] = f"Bearer {self.hf_token}"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.api_url}/Hello-SimpleAI/chatgpt-detector-roberta",
                    headers=headers,
                    json={"inputs": text}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if isinstance(result, list) and len(result) > 0:
                        scores = {item['label']: item['score'] for item in result[0]}
                        # Labels: "ChatGPT" or "Human"
                        ai_prob = scores.get('ChatGPT', scores.get('LABEL_1', 0))
                        return {
                            "model": "chatgpt-detector",
                            "ai_probability": ai_prob,
                            "human_probability": scores.get('Human', scores.get('LABEL_0', 0))
                        }
        except Exception as e:
            logger.debug(f"ChatGPT detector error: {e}")
        
        return None
    
    async def _heuristic_detection(self, text: str) -> Dict:
        """Fallback to pattern-based detection"""
        import re
        
        ai_patterns = [
            (r"as an AI( language model)?", 0.9),
            (r"I'?m (just )?an AI", 0.9),
            (r"I was trained", 0.8),
            (r"my training data", 0.8),
            (r"I don'?t have (personal )?(opinions|feelings)", 0.7),
            (r"it'?s (important|worth) (to note|noting)", 0.3),
            (r"\b(delve|tapestry|multifaceted|synergy)\b", 0.2),
        ]
        
        text_lower = text.lower()
        confidence = 0.0
        matches = []
        
        for pattern, weight in ai_patterns:
            if re.search(pattern, text_lower):
                confidence += weight
                matches.append(pattern)
        
        confidence = min(confidence, 1.0)
        is_ai = confidence > 0.5
        
        return {
            "is_ai": is_ai,
            "confidence": round(confidence, 3),
            "method": "heuristic",
            "patterns_matched": len(matches),
            "message": self._get_message(is_ai, confidence)
        }
    
    def _get_message(self, is_ai: bool, confidence: float) -> str:
        if confidence > 0.85:
            return "High confidence: AI-generated content" if is_ai else "High confidence: Human-written"
        elif confidence > 0.6:
            return "Likely AI-generated" if is_ai else "Likely human-written"
        elif confidence > 0.4:
            return "Uncertain - may contain AI elements"
        else:
            return "Content appears to be human-written"