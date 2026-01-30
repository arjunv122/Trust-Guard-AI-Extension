from typing import Dict, List


def calculate_overall_score(results: Dict, applicable_pillars: List[str]) -> Dict:
    """Calculate overall trust score"""
    
    if not applicable_pillars:
        return {
            "score": 0,
            "verdict": "INSUFFICIENT DATA",
            "confidence": 0,
            "findings": [{"type": "error", "message": "No content to analyze"}],
            "ai_content_detected": False,
            "suspicious_segments": []
        }
    
    scores = []
    weights = []
    ai_detected = False
    suspicious_segments = []
    
    # Information Trust
    if "information_trust" in applicable_pillars:
        info = results.get('information_trust', {})
        if info.get('score') is not None:
            scores.append(info['score'])
            weights.append(0.6)
            
            # Check for AI content
            details = info.get('details', {})
            ai_detection = details.get('ai_detection', {})
            if ai_detection.get('is_ai_generated'):
                ai_detected = True
            
            # Get suspicious segments
            segments = details.get('suspicious_segments', [])
            suspicious_segments.extend(segments)
    
    # Media Trust
    if "media_trust" in applicable_pillars:
        media = results.get('media_trust', {})
        if media.get('score') is not None:
            scores.append(media['score'])
            weights.append(0.4)
            
            # Check for AI images
            details = media.get('details', {})
            images = details.get('images', {})
            if images.get('ai_generated_count', 0) > 0:
                ai_detected = True
    
    # Calculate weighted average
    if not scores:
        return {
            "score": 0,
            "verdict": "INSUFFICIENT DATA",
            "confidence": 0,
            "findings": [{"type": "error", "message": "Could not calculate scores"}],
            "ai_content_detected": ai_detected,
            "suspicious_segments": suspicious_segments
        }
    
    total_weight = sum(weights)
    weights = [w / total_weight for w in weights]
    overall_score = round(sum(s * w for s, w in zip(scores, weights)))
    
    # Determine verdict
    if overall_score >= 80:
        verdict = "HIGH TRUST"
    elif overall_score >= 60:
        verdict = "MODERATE TRUST"
    elif overall_score >= 40:
        verdict = "LOW TRUST"
    else:
        verdict = "VERY LOW TRUST"
    
    # Generate findings
    findings = _generate_findings(results, applicable_pillars)
    
    return {
        "score": overall_score,
        "verdict": verdict,
        "confidence": round(len(scores) / 2, 2),
        "findings": findings,
        "ai_content_detected": ai_detected,
        "suspicious_segments": suspicious_segments
    }


def _generate_findings(results: Dict, applicable_pillars: List[str]) -> List[Dict]:
    """Generate user-friendly findings"""
    findings = []
    
    # Information Trust findings
    if "information_trust" in applicable_pillars:
        info = results.get('information_trust', {})
        details = info.get('details') or {}
        
        # AI Detection finding
        ai_det = details.get('ai_detection', {})
        if ai_det.get('is_ai_generated'):
            findings.append({
                "type": "warning",
                "pillar": "information_trust",
                "message": f"AI-generated content detected (confidence: {ai_det.get('confidence', 0):.0%})"
            })
        else:
            findings.append({
                "type": "success",
                "pillar": "information_trust",
                "message": "Content appears to be human-written"
            })
        
        # Fact check finding
        fact = details.get('fact_check', {})
        if fact.get('total_claims', 0) > 0:
            if fact.get('verification_rate', 0) > 0.7:
                findings.append({
                    "type": "success",
                    "pillar": "information_trust",
                    "message": f"Claims verified: {fact.get('message', '')}"
                })
            else:
                findings.append({
                    "type": "warning",
                    "pillar": "information_trust",
                    "message": f"Some claims unverified: {fact.get('message', '')}"
                })
    
    # Media Trust findings
    if "media_trust" in applicable_pillars:
        media = results.get('media_trust', {})
        details = media.get('details') or {}
        
        images = details.get('images', {})
        ai_count = images.get('ai_generated_count', 0)
        
        if ai_count > 0:
            findings.append({
                "type": "error",
                "pillar": "media_trust",
                "message": f"{ai_count} AI-generated image(s) detected"
            })
        elif images.get('analyzed', 0) > 0:
            findings.append({
                "type": "success",
                "pillar": "media_trust",
                "message": "All images appear authentic"
            })
    
    return findings