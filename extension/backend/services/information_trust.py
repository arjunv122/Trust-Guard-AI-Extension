import re
from typing import Dict, List, Optional
import httpx
import logging
import math
import os

logger = logging.getLogger(__name__)


class ImprovedInformationTrustEngine:
    """
    AI Content Detection using Sapling AI API
    NO HuggingFace models - they are broken
    """
    
    def __init__(self):
        # Get Sapling API key from environment
        self.sapling_api_key = os.getenv("SAPLING_API_KEY", "")
        
        if self.sapling_api_key:
            logger.info("✅ Sapling AI API key loaded successfully")
        else:
            logger.warning("⚠️ SAPLING_API_KEY not found in environment!")
            logger.warning("⚠️ Add it to backend/.env file: SAPLING_API_KEY=your_key_here")
        
        # Fallback patterns (used only if Sapling fails)
        self.ai_patterns = [
            (r"\bas an AI\b", 0.95),
            (r"\bI'?m an AI\b", 0.95),
            (r"\blanguage model\b", 0.85),
            (r"\bI was trained\b", 0.80),
            (r"\bIt'?s worth noting\b", 0.40),
            (r"\bI hope this helps\b", 0.45),
            (r"\bI cannot provide\b", 0.55),
            (r"\bLet me know if\b", 0.40),
            (r"\bI'd be happy to\b", 0.45),
            (r"\bGreat question\b", 0.40),
            (r"\bCertainly[!.,]", 0.35),
            (r"\b(?:delve|tapestry|multifaceted)\b", 0.25),
            (r"\b(?:Furthermore|Moreover|Additionally)\b", 0.20),
            (r"\b(?:comprehensive|facilitate|utilize)\b", 0.18),
        ]
    
    async def analyze(self, text: str, url: Optional[str] = None) -> Dict:
        """Main analysis - uses Sapling AI"""
        
        if not text or len(text.strip()) < 30:
            return {
                "score": None,
                "applicable": False,
                "reason": f"Text too short ({len(text.strip()) if text else 0} chars)",
                "details": None
            }
        
        text = text.strip()
        ai_detection = None
        
        # ════════════════════════════════════════════════════════
        # TRY SAPLING AI (Primary Detection)
        # ════════════════════════════════════════════════════════
        if self.sapling_api_key:
            ai_detection = await self._sapling_detect(text)
        else:
            logger.warning("Sapling API key not configured!")
        
        # ════════════════════════════════════════════════════════
        # FALLBACK TO STATISTICAL + PATTERN (if Sapling fails)
        # ════════════════════════════════════════════════════════
        if not ai_detection:
            logger.warning("Using fallback detection (Sapling unavailable)")
            ai_detection = self._fallback_detection(text)
        
        # Source credibility
        source = self._check_source(url) if url else {"score": 5, "credibility": "unknown"}
        
        # Calculate final score
        score = self._calculate_score(ai_detection, source)
        
        # Find suspicious segments
        suspicious = self._find_suspicious_segments(text)
        
        logger.info(f"✅ Analysis: {score}/100 - AI: {ai_detection['ai_probability']:.1%} via {ai_detection['method']}")
        
        return {
            "score": int(score),
            "applicable": True,
            "details": {
                "ai_detection": {
                    "is_ai_generated": bool(ai_detection["is_ai"]),
                    "confidence": float(ai_detection["confidence"]),
                    "ai_probability": float(ai_detection["ai_probability"]),
                    "human_probability": float(ai_detection["human_probability"]),
                    "method": str(ai_detection["method"]),
                    "message": str(ai_detection["message"])
                },
                "fact_check": {
                    "total_claims": 0,
                    "verified_claims": 0,
                    "verification_rate": 1.0,
                    "status": "not_checked",
                    "message": "Fact verification not available"
                },
                "sources": source,
                "suspicious_segments": suspicious
            }
        }
    
    async def _sapling_detect(self, text: str) -> Optional[Dict]:
        """
        Sapling AI Detection API
        Docs: https://sapling.ai/docs/api/ai-content-detection
        """
        
        try:
            logger.info("🔍 Calling Sapling AI API...")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.sapling.ai/api/v1/aidetect",
                    headers={"Content-Type": "application/json"},
                    json={
                        "key": self.sapling_api_key,
                        "text": text[:50000]
                    }
                )
                
                logger.info(f"Sapling API response status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Sapling returns score 0-1 (1 = AI generated)
                    ai_prob = float(data.get("score", 0))
                    
                    logger.info(f"🎯 Sapling AI result: {ai_prob:.1%} AI probability")
                    
                    return self._format_result(ai_prob, "Sapling AI")
                
                elif response.status_code == 401:
                    logger.error("❌ Sapling AI: Invalid API key!")
                    logger.error("Check your SAPLING_API_KEY in .env file")
                elif response.status_code == 402:
                    logger.error("❌ Sapling AI: Out of credits!")
                elif response.status_code == 429:
                    logger.error("❌ Sapling AI: Rate limited - too many requests")
                else:
                    logger.error(f"❌ Sapling AI error: {response.status_code}")
                    logger.error(f"Response: {response.text[:200]}")
                
        except httpx.TimeoutException:
            logger.error("❌ Sapling AI: Request timed out (30s)")
        except Exception as e:
            logger.error(f"❌ Sapling AI exception: {type(e).__name__}: {e}")
        
        return None
    
    def _fallback_detection(self, text: str) -> Dict:
        """Enhanced fallback when Sapling is unavailable"""
        
        logger.info("Using pattern + statistical fallback")
        
        text_lower = text.lower()
        
        # ─────────────────────────────────────────────────────
        # 1. PATTERN MATCHING (40% weight)
        # ─────────────────────────────────────────────────────
        pattern_score = 0.0
        matched = 0
        
        for pattern, weight in self.ai_patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            if matches:
                pattern_score += weight * min(len(matches), 2)
                matched += 1
        
        pattern_score = min(pattern_score, 0.90)
        
        # ─────────────────────────────────────────────────────
        # 2. SENTENCE UNIFORMITY (30% weight)
        # ─────────────────────────────────────────────────────
        sentences = [s.strip() for s in re.split(r'[.!?]+', text) if len(s.strip()) > 10]
        uniformity_score = 0.0
        
        if len(sentences) >= 4:
            lengths = [len(s.split()) for s in sentences]
            avg = sum(lengths) / len(lengths)
            
            if avg > 0:
                variance = sum((l - avg) ** 2 for l in lengths) / len(lengths)
                cv = math.sqrt(variance) / avg
                
                if cv < 0.18:
                    uniformity_score = 0.45
                elif cv < 0.25:
                    uniformity_score = 0.35
                elif cv < 0.35:
                    uniformity_score = 0.25
                elif cv < 0.45:
                    uniformity_score = 0.15
        
        # ─────────────────────────────────────────────────────
        # 3. FORMAL LANGUAGE (20% weight)
        # ─────────────────────────────────────────────────────
        formal_words = len(re.findall(
            r'\b(?:utilize|implement|facilitate|comprehensive|furthermore|moreover|additionally|consequently|nevertheless|subsequently|accordingly|respectively)\b',
            text_lower
        ))
        total_words = len(re.findall(r'\b\w+\b', text))
        formal_score = min((formal_words / max(total_words, 1)) * 30, 0.35)
        
        # ─────────────────────────────────────────────────────
        # 4. STRUCTURE PATTERNS (10% weight)
        # ─────────────────────────────────────────────────────
        list_items = len(re.findall(r'(?:^|\n)\s*[-•*]\s', text))
        numbered = len(re.findall(r'(?:^|\n)\s*\d+[.)]\s', text))
        colons = len(re.findall(r':\s*\n', text))
        structure_score = min((list_items + numbered + colons) * 0.05, 0.25)
        
        # ─────────────────────────────────────────────────────
        # COMBINE SCORES
        # ─────────────────────────────────────────────────────
        ai_score = (
            pattern_score * 0.40 +
            uniformity_score * 0.30 +
            formal_score * 0.20 +
            structure_score * 0.10
        )
        
        # Boost if multiple indicators present
        if matched >= 3 and uniformity_score > 0.2:
            ai_score = min(ai_score * 1.2, 0.90)
        
        ai_score = min(max(ai_score, 0), 0.90)
        
        method = f"Fallback ({matched} patterns)"
        return self._format_result(ai_score, method)
    
    def _format_result(self, ai_probability: float, method: str) -> Dict:
        """Format the detection result"""
        
        ai_probability = float(max(0, min(1, ai_probability)))
        human_probability = 1.0 - ai_probability
        
        is_ai = ai_probability > 0.50
        confidence = abs(ai_probability - 0.5) * 2
        
        # Generate message based on probability
        if is_ai:
            if ai_probability > 0.90:
                message = f"🤖 Definitely AI-generated ({ai_probability:.0%})"
            elif ai_probability > 0.80:
                message = f"🤖 Very likely AI-generated ({ai_probability:.0%})"
            elif ai_probability > 0.70:
                message = f"🤖 Likely AI-generated ({ai_probability:.0%})"
            elif ai_probability > 0.60:
                message = f"⚠️ Probably AI-generated ({ai_probability:.0%})"
            else:
                message = f"⚠️ Possibly AI-generated ({ai_probability:.0%})"
        else:
            if human_probability > 0.90:
                message = "✅ Definitely human-written"
            elif human_probability > 0.80:
                message = "✅ Very likely human-written"
            elif human_probability > 0.70:
                message = "✅ Likely human-written"
            else:
                message = "✅ Probably human-written"
        
        return {
            "is_ai": is_ai,
            "confidence": round(confidence, 3),
            "ai_probability": round(ai_probability, 4),
            "human_probability": round(human_probability, 4),
            "method": method,
            "message": message
        }
    
    def _check_source(self, url: str) -> Dict:
        """Check source credibility"""
        if not url:
            return {"score": 5, "credibility": "unknown"}
        
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.lower().replace("www.", "")
        except:
            return {"score": 5, "credibility": "unknown"}
        
        high_trust = [".gov", ".edu", "reuters.com", "apnews.com", "bbc.com", "nature.com"]
        low_trust = ["blogspot.com", "wordpress.com", "medium.com", "reddit.com"]
        
        for d in high_trust:
            if d in domain:
                return {"score": 9, "credibility": "high", "domain": domain}
        
        for d in low_trust:
            if d in domain:
                return {"score": 3, "credibility": "low", "domain": domain}
        
        return {"score": 5, "credibility": "unknown", "domain": domain}
    
    def _find_suspicious_segments(self, text: str) -> List[Dict]:
        """Find AI-like segments for highlighting"""
        segments = []
        
        patterns = [
            (r"as an AI\b", "high"),
            (r"I'?m an AI\b", "high"),
            (r"language model", "high"),
            (r"it'?s worth noting", "medium"),
            (r"I hope this helps", "medium"),
            (r"Let me know if", "medium"),
        ]
        
        for pattern, severity in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                segments.append({
                    "text": text[max(0, match.start()-30):min(len(text), match.end()+30)],
                    "match": match.group(),
                    "severity": severity
                })
        
        return segments[:10]
    
    def _calculate_score(self, ai_detection: Dict, source: Dict) -> int:
        """Calculate trust score"""
        score = 100
        
        if ai_detection.get("is_ai"):
            ai_prob = ai_detection.get("ai_probability", 0.5)
            
            if ai_prob > 0.95:
                score -= 75
            elif ai_prob > 0.90:
                score -= 65
            elif ai_prob > 0.80:
                score -= 55
            elif ai_prob > 0.70:
                score -= 45
            elif ai_prob > 0.60:
                score -= 35
            elif ai_prob > 0.50:
                score -= 25
        
        # Source adjustment
        src = source.get("score", 5)
        if src >= 8:
            score += 5
        elif src <= 3:
            score -= 10
        
        return max(0, min(100, int(score)))