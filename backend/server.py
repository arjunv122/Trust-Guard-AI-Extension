"""
TrustGuard AI - Hallucination Detection API
Uses lightweight NLP techniques and LLM-based SelfCheckGPT approach
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import re
import logging
from collections import Counter
import math
import os
import json
from datetime import datetime
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
CORS(app, origins=['*'], supports_credentials=True)

# ============================================
# History Storage System
# ============================================

HISTORY_FILE = os.path.join(os.path.dirname(__file__), 'analysis_history.json')

def load_history():
    """Load analysis history from JSON file"""
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading history: {e}")
    return []

def save_history(history):
    """Save analysis history to JSON file"""
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error saving history: {e}")
        return False

def add_to_history(entry):
    """Add a new entry to history"""
    history = load_history()
    entry['id'] = str(uuid.uuid4())
    entry['timestamp'] = datetime.now().isoformat()
    entry['date'] = datetime.now().strftime('%b %d, %Y')
    entry['time'] = datetime.now().strftime('%H:%M')
    history.insert(0, entry)  # Add to beginning (newest first)
    
    # Keep only last 500 entries
    history = history[:500]
    save_history(history)
    return entry

def get_history_stats():
    """Calculate history statistics"""
    history = load_history()
    total = len(history)
    verified = sum(1 for h in history if h.get('trust_score', 0) >= 80)
    warnings = sum(1 for h in history if 50 <= h.get('trust_score', 0) < 80)
    flagged = sum(1 for h in history if h.get('trust_score', 0) < 50)
    
    return {
        'total': total,
        'verified': verified,
        'warnings': warnings,
        'flagged': flagged
    }

# ============================================
# LLM-Based SelfCheckGPT Hallucination Detector
# ============================================

class LLMHallucinationDetector:
    """
    SelfCheckGPT-inspired hallucination detection using LLM API
    Generates multiple verification samples and checks consistency
    """
    
    def __init__(self):
        self.api_key = os.environ.get('GROQ_API_KEY', '')
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama-3.1-8b-instant"  # Fast and free
        self.name = "TrustGuard LLM Hallucination Detector"
    
    def set_api_key(self, key):
        """Set the API key"""
        self.api_key = key
    
    def is_configured(self):
        """Check if API key is configured"""
        return bool(self.api_key)
    
    def _call_llm(self, messages, temperature=0.7):
        """Call the Groq LLM API"""
        try:
            import urllib.request
            import urllib.error
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = json.dumps({
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 1024
            }).encode('utf-8')
            
            req = urllib.request.Request(self.api_url, data=data, headers=headers, method='POST')
            
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result['choices'][0]['message']['content']
                
        except urllib.error.HTTPError as e:
            logger.error(f"LLM API HTTP Error: {e.code} - {e.reason}")
            return None
        except Exception as e:
            logger.error(f"LLM API Error: {str(e)}")
            return None
    
    def _split_into_claims(self, text):
        """Split text into individual claims/sentences"""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip() and len(s.strip()) > 15]
    
    def _verify_claim(self, claim):
        """
        Verify a single claim using LLM
        Returns verification result with confidence
        """
        prompt = f"""Analyze the following claim for potential hallucination or factual accuracy.

CLAIM: "{claim}"

Respond in this exact JSON format:
{{
    "is_verifiable": true/false,
    "confidence": 0.0-1.0,
    "likely_accurate": true/false,
    "reasoning": "brief explanation",
    "red_flags": ["list", "of", "concerns"],
    "simple_explanation": "Explain in 1-2 simple sentences what the problem is, written for someone with no technical background. Use everyday language.",
    "suggestion": "how to verify this in plain language"
}}

Be critical. Look for:
- Specific claims without sources
- Statistics without attribution
- Absolute statements ("always", "never", "all")
- Vague attributions ("studies show", "experts say")
- Potentially outdated information
- Claims that seem too specific or too confident"""

        messages = [
            {"role": "system", "content": "You are a fact-checking assistant that identifies potential hallucinations and unverified claims. Be skeptical and thorough. Always respond with valid JSON. When explaining issues, write like you're explaining to a friend who doesn't know technical terms - be simple and clear."},
            {"role": "user", "content": prompt}
        ]
        
        response = self._call_llm(messages, temperature=0.3)
        
        if not response:
            return {
                "claim": claim,
                "is_verifiable": True,
                "confidence": 0.5,
                "likely_accurate": None,
                "reasoning": "Could not verify - LLM unavailable",
                "red_flags": ["Verification failed"],
                "suggestion": "Manual verification required"
            }
        
        try:
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                result = json.loads(json_match.group())
                result["claim"] = claim
                return result
        except json.JSONDecodeError:
            pass
        
        return {
            "claim": claim,
            "is_verifiable": True,
            "confidence": 0.5,
            "likely_accurate": None,
            "reasoning": "Could not parse verification result",
            "red_flags": ["Parse error"],
            "suggestion": "Manual verification required"
        }
    
    def _generate_consistency_check(self, text):
        """
        SelfCheckGPT approach: Ask LLM to rephrase and check for consistency
        """
        prompt = f"""I will give you a piece of text. Your task is to:
1. Identify the key factual claims in the text
2. For each claim, assess if it seems consistent and well-supported
3. Flag any claims that seem potentially hallucinated, made up, or unsupported

TEXT:
"{text}"

Respond in this exact JSON format:
{{
    "overall_assessment": "reliable/questionable/unreliable",
    "confidence_score": 0.0-1.0,
    "key_claims": [
        {{
            "claim": "the specific claim",
            "assessment": "supported/unsupported/uncertain",
            "concern": "why it might be problematic (or null if fine)",
            "simple_explanation": "Explain simply why this is flagged, like explaining to a non-technical person. What should they be careful about?"
        }}
    ],
    "hallucination_indicators": ["list of red flags found"],
    "simple_indicators": ["same red flags but explained in simple everyday language for regular people"],
    "summary": "brief overall assessment",
    "simple_summary": "Explain what you found in 2-3 simple sentences. Pretend you're explaining to your grandmother. Avoid jargon."
}}"""

        messages = [
            {"role": "system", "content": "You are an expert at detecting AI hallucinations and factual inaccuracies. Analyze texts critically and identify unsupported or potentially false claims. Always respond with valid JSON. When explaining, use simple everyday language that anyone can understand - no technical terms."},
            {"role": "user", "content": prompt}
        ]
        
        response = self._call_llm(messages, temperature=0.2)
        
        if not response:
            return None
        
        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
        
        return None
    
    def detect_hallucination(self, text):
        """
        Main hallucination detection using LLM-based SelfCheckGPT approach
        """
        if not text or len(text.strip()) < 30:
            return {
                'success': False,
                'error': 'Text must be at least 30 characters long'
            }
        
        if not self.is_configured():
            return {
                'success': False,
                'error': 'LLM API key not configured. Please set GROQ_API_KEY or use /api/config endpoint.',
                'needs_api_key': True
            }
        
        # Split into claims
        claims = self._split_into_claims(text)
        
        if not claims:
            return {
                'success': False,
                'error': 'Could not extract claims from text'
            }
        
        # Run consistency check on full text
        consistency_result = self._generate_consistency_check(text)
        
        # Verify individual claims (limit to first 5 for speed)
        claim_verifications = []
        for claim in claims[:5]:
            verification = self._verify_claim(claim)
            claim_verifications.append(verification)
        
        # Calculate scores
        if consistency_result:
            base_score = consistency_result.get('confidence_score', 0.7) * 100
            assessment = consistency_result.get('overall_assessment', 'questionable')
            
            # Adjust based on key claims
            key_claims = consistency_result.get('key_claims', [])
            unsupported_count = sum(1 for c in key_claims if c.get('assessment') == 'unsupported')
            uncertain_count = sum(1 for c in key_claims if c.get('assessment') == 'uncertain')
            
            base_score -= unsupported_count * 15
            base_score -= uncertain_count * 5
        else:
            # Fallback to claim verification scores
            confidences = [v.get('confidence', 0.5) for v in claim_verifications]
            base_score = (sum(confidences) / len(confidences)) * 100 if confidences else 50
            assessment = 'questionable'
        
        # Adjust based on individual claim verifications
        for v in claim_verifications:
            if v.get('likely_accurate') == False:
                base_score -= 10
            elif v.get('likely_accurate') == True:
                base_score += 2
            if v.get('red_flags'):
                base_score -= len(v['red_flags']) * 3
        
        trust_score = max(0, min(100, int(base_score)))
        
        # Determine risk level
        if trust_score >= 80:
            risk_level = 'low'
            risk_description = 'Text appears reliable with minimal hallucination indicators.'
        elif trust_score >= 60:
            risk_level = 'medium'
            risk_description = 'Some claims may need verification. Potential hallucination detected.'
        else:
            risk_level = 'high'
            risk_description = 'Multiple potential hallucinations or unsupported claims detected.'
        
        # Collect all red flags
        all_red_flags = []
        if consistency_result:
            all_red_flags.extend(consistency_result.get('hallucination_indicators', []))
        for v in claim_verifications:
            all_red_flags.extend(v.get('red_flags', []))
        
        # Generate recommendations
        recommendations = []
        if unsupported_count > 0 if consistency_result else False:
            recommendations.append(f"{unsupported_count} claim(s) appear unsupported - verify with reliable sources.")
        if all_red_flags:
            recommendations.append("Review flagged concerns and cross-reference claims.")
        if any(v.get('likely_accurate') == False for v in claim_verifications):
            recommendations.append("Some claims may be inaccurate - fact-check before using.")
        if not recommendations:
            recommendations.append("Text analysis complete. Claims appear generally consistent.")
        
        return {
            'success': True,
            'method': 'llm_selfcheck',
            'trust_score': trust_score,
            'sentence_count': len(claims),
            'word_count': len(text.split()),
            'character_count': len(text),
            'analysis': {
                'overall_risk': risk_level,
                'risk_description': risk_description,
                'simple_summary': consistency_result.get('simple_summary', '') if consistency_result else self._generate_simple_summary(risk_level, trust_score),
                'confidence': trust_score / 100.0,
                'llm_assessment': consistency_result.get('overall_assessment', 'unknown') if consistency_result else 'unknown',
                'flagged_count': len(all_red_flags),
                'total_issues': len(all_red_flags),
                'summary': consistency_result.get('summary', '') if consistency_result else ''
            },
            'claim_verifications': claim_verifications,
            'consistency_check': consistency_result,
            'flagged_sentences': [
                {
                    'sentence': v['claim'],
                    'score': int(v.get('confidence', 0.5) * 100),
                    'issues': v.get('red_flags', []),
                    'simple_explanation': v.get('simple_explanation', self._simplify_issues(v.get('red_flags', []))),
                    'suggestion': v.get('suggestion', ''),
                    'has_issues': bool(v.get('red_flags'))
                }
                for v in claim_verifications if v.get('red_flags')
            ],
            'simple_findings': consistency_result.get('simple_indicators', []) if consistency_result else [],
            'key_findings': [
                {
                    'claim': kc.get('claim', ''),
                    'status': kc.get('assessment', 'uncertain'),
                    'concern': kc.get('concern', ''),
                    'simple_explanation': kc.get('simple_explanation', '')
                }
                for kc in (consistency_result.get('key_claims', []) if consistency_result else [])
            ],
            'recommendations': recommendations,
            'metrics': {
                'hallucination_score': trust_score,
                'ai_detection': max(0, 100 - trust_score) if trust_score < 80 else (100 - trust_score) * 2,
                'consistency': int(consistency_result.get('confidence_score', 0.7) * 100) if consistency_result else 70,
                'factual_claims': len(claims)
            }
        }
    
    def _generate_simple_summary(self, risk_level, score):
        """Generate a simple layman summary based on risk level"""
        if risk_level == 'low':
            return "This text looks trustworthy! The information appears to be accurate and consistent."
        elif risk_level == 'medium':
            return "This text has some parts that might not be accurate. You should double-check the facts before trusting it completely."
        else:
            return "Be careful with this text! Several statements seem questionable or may not be true. We recommend verifying the information from other sources."
    
    def _simplify_issues(self, red_flags):
        """Convert technical red flags to simple explanations"""
        if not red_flags:
            return ""
        
        simple_map = {
            'vague': "This statement is too general and doesn't give specific details",
            'unverified': "We couldn't confirm if this is true",
            'source': "No reliable source was mentioned to back this up",
            'absolute': "Using words like 'always' or 'never' is rarely accurate",
            'statistic': "Numbers and percentages should be checked with official sources",
            'expert': "Saying 'experts say' without naming them is a red flag",
            'study': "Claims about studies should include who did the research",
            'outdated': "This information might be old and no longer accurate"
        }
        
        explanations = []
        for flag in red_flags[:3]:  # Limit to 3
            flag_lower = flag.lower()
            for key, simple in simple_map.items():
                if key in flag_lower:
                    explanations.append(simple)
                    break
            else:
                # Default simple explanation
                explanations.append(f"This part needs verification: {flag}")
        
        return " | ".join(explanations) if explanations else "This statement should be fact-checked before trusting it."


# Initialize LLM detector
llm_detector = LLMHallucinationDetector()

# ============================================
# Heuristic Hallucination Detection Logic (Fallback)
# ============================================

class HallucinationDetector:
    """Lightweight hallucination detector using text analysis heuristics"""
    
    # Words that often indicate uncertain or potentially hallucinated content
    UNCERTAINTY_MARKERS = [
        'reportedly', 'allegedly', 'supposedly', 'claimed', 'rumored',
        'unconfirmed', 'possibly', 'might', 'could be', 'may have',
        'some say', 'it is said', 'according to sources', 'believed to'
    ]
    
    # Words that indicate strong claims that need verification
    STRONG_CLAIM_MARKERS = [
        'always', 'never', 'all', 'none', 'every', 'no one', 'everyone',
        'definitely', 'certainly', 'absolutely', 'undoubtedly', 'proven',
        'scientifically proven', 'studies show', 'research proves', 'experts say'
    ]
    
    # Patterns that might indicate AI-generated content
    AI_PATTERNS = [
        r'\b(it\'s important to note|it\'s worth noting|it should be noted)\b',
        r'\b(in conclusion|to summarize|in summary)\b',
        r'\b(as an ai|as a language model|i cannot)\b',
        r'\b(delve into|dive into|explore the|unpack)\b',
        r'\b(firstly|secondly|thirdly|lastly)\b',
        r'\b(comprehensive|robust|leverage|utilize)\b'
    ]
    
    # Factual claim patterns
    FACTUAL_PATTERNS = [
        r'\b\d{4}\b',  # Years
        r'\b\d+%\b',   # Percentages  
        r'\b\d+\s*(million|billion|trillion)\b',  # Large numbers
        r'\b(study|research|survey|poll)\s+(shows?|found|revealed|indicates?)\b',
        r'\b(according to|based on|as per)\b'
    ]
    
    def __init__(self):
        self.name = "TrustGuard Hallucination Detector"
    
    def split_sentences(self, text):
        """Split text into sentences"""
        # Simple sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
    
    def analyze_sentence(self, sentence):
        """Analyze a single sentence for hallucination indicators"""
        sentence_lower = sentence.lower()
        issues = []
        score = 100  # Start with perfect score
        
        # Check for uncertainty markers
        for marker in self.UNCERTAINTY_MARKERS:
            if marker in sentence_lower:
                issues.append(f"Contains uncertainty marker: '{marker}'")
                score -= 10
        
        # Check for strong claims
        for marker in self.STRONG_CLAIM_MARKERS:
            if marker in sentence_lower:
                issues.append(f"Contains strong claim: '{marker}'")
                score -= 8
        
        # Check for AI patterns
        for pattern in self.AI_PATTERNS:
            if re.search(pattern, sentence_lower):
                issues.append("Contains common AI-generated phrase pattern")
                score -= 12
                break
        
        # Check for factual claims that need verification
        factual_claims = []
        for pattern in self.FACTUAL_PATTERNS:
            matches = re.findall(pattern, sentence_lower)
            if matches:
                factual_claims.extend(matches if isinstance(matches[0], str) else [m[0] for m in matches])
        
        if factual_claims:
            issues.append(f"Contains {len(factual_claims)} factual claim(s) requiring verification")
            score -= 5 * len(factual_claims)
        
        # Very short sentences with claims are suspicious
        if len(sentence.split()) < 8 and any(marker in sentence_lower for marker in self.STRONG_CLAIM_MARKERS):
            issues.append("Short sentence with strong claim")
            score -= 10
        
        return {
            'sentence': sentence,
            'score': max(0, min(100, score)),
            'issues': issues,
            'has_issues': len(issues) > 0
        }
    
    def calculate_consistency_score(self, sentences):
        """Check internal consistency of the text"""
        if len(sentences) < 2:
            return 100
        
        # Extract key terms from each sentence
        all_terms = []
        for sent in sentences:
            words = re.findall(r'\b[a-zA-Z]{4,}\b', sent.lower())
            all_terms.extend(words)
        
        # Check term frequency - inconsistent texts repeat terms less
        term_counts = Counter(all_terms)
        if len(term_counts) == 0:
            return 80
        
        # Higher repetition of key terms = more consistent
        most_common = term_counts.most_common(10)
        avg_frequency = sum(count for _, count in most_common) / len(most_common) if most_common else 1
        
        consistency = min(100, 60 + (avg_frequency * 8))
        return int(consistency)
    
    def detect_hallucination(self, text):
        """Main detection method"""
        if not text or len(text.strip()) < 50:
            return {
                'success': False,
                'error': 'Text must be at least 50 characters long'
            }
        
        # Split into sentences
        sentences = self.split_sentences(text)
        
        if len(sentences) == 0:
            return {
                'success': False,
                'error': 'Could not extract valid sentences from text'
            }
        
        # Analyze each sentence
        sentence_analyses = [self.analyze_sentence(s) for s in sentences]
        
        # Calculate overall scores
        sentence_scores = [a['score'] for a in sentence_analyses]
        avg_sentence_score = sum(sentence_scores) / len(sentence_scores)
        
        # Consistency score
        consistency_score = self.calculate_consistency_score(sentences)
        
        # Overall trust score (weighted average)
        trust_score = int((avg_sentence_score * 0.7) + (consistency_score * 0.3))
        
        # Determine risk level
        if trust_score >= 80:
            risk_level = 'low'
            risk_description = 'The text appears to be generally reliable with minimal hallucination indicators.'
        elif trust_score >= 60:
            risk_level = 'medium'
            risk_description = 'The text contains some patterns that may indicate potential hallucinations or unverified claims.'
        else:
            risk_level = 'high'
            risk_description = 'The text shows multiple indicators of potential hallucination or unreliable content.'
        
        # Collect all issues
        flagged_sentences = [a for a in sentence_analyses if a['has_issues']]
        all_issues = []
        for a in flagged_sentences:
            all_issues.extend(a['issues'])
        
        # Generate recommendations
        recommendations = []
        if any('uncertainty' in issue.lower() for issue in all_issues):
            recommendations.append('Verify claims marked with uncertainty markers through reliable sources.')
        if any('strong claim' in issue.lower() for issue in all_issues):
            recommendations.append('Strong absolute claims should be fact-checked independently.')
        if any('ai-generated' in issue.lower() for issue in all_issues):
            recommendations.append('Text shows patterns common in AI-generated content.')
        if any('factual claim' in issue.lower() for issue in all_issues):
            recommendations.append('Verify specific facts, dates, and statistics from primary sources.')
        if not recommendations:
            recommendations.append('Text analysis complete. No major concerns detected.')
        
        return {
            'success': True,
            'trust_score': trust_score,
            'sentence_count': len(sentences),
            'word_count': len(text.split()),
            'character_count': len(text),
            'analysis': {
                'overall_risk': risk_level,
                'risk_description': risk_description,
                'confidence': trust_score / 100.0,
                'avg_sentence_score': round(avg_sentence_score, 1),
                'consistency_score': consistency_score,
                'flagged_count': len(flagged_sentences),
                'total_issues': len(all_issues)
            },
            'sentence_breakdown': sentence_analyses[:10],  # First 10 sentences
            'flagged_sentences': flagged_sentences[:5],    # Top 5 flagged
            'recommendations': recommendations,
            'metrics': {
                'hallucination_score': round(avg_sentence_score, 1),
                'ai_detection': round(100 - avg_sentence_score + 20, 1) if avg_sentence_score < 80 else round((100 - avg_sentence_score) * 2, 1),
                'consistency': consistency_score,
                'factual_claims': sum(1 for a in sentence_analyses if any('factual' in i.lower() for i in a['issues']))
            }
        }


# Initialize detector
detector = HallucinationDetector()


# ============================================
# Fact Verification Logic
# ============================================

class FactVerifier:
    """
    Fact Verification System
    Analyzes text for factual claims and verifies them against known patterns
    """
    
    # Known factual patterns to identify claims
    CLAIM_PATTERNS = {
        'dates': r'\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}|\d{4})\b',
        'statistics': r'\b(\d+(?:\.\d+)?(?:\s*%|\s+percent))\b',
        'numbers': r'\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(million|billion|trillion|thousand|hundred)?\b',
        'scientific': r'\b(study|research|experiment|trial|survey|poll|analysis)\s+(shows?|found|revealed|indicates?|proves?|demonstrated?)\b',
        'quotes': r'"([^"]+)"',
        'attributions': r'\b(according to|based on|as per|as stated by|reported by|cited by)\s+([A-Z][a-zA-Z\s]+)',
        'organizations': r'\b(University|Institute|Organization|Association|Foundation|Center|Agency|Department)\s+of\s+[A-Z][a-zA-Z\s]+',
        'named_entities': r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b',  # Proper nouns
    }
    
    # Common false/misleading claim indicators
    MISLEADING_INDICATORS = [
        'studies show', 'research proves', 'scientists confirm',
        'experts agree', 'everyone knows', 'it is well known',
        'undisputed fact', 'proven fact', 'common knowledge'
    ]
    
    # Verifiable claim starters
    VERIFIABLE_STARTERS = [
        'in', 'on', 'during', 'since', 'before', 'after',
        'according to', 'based on', 'as reported by'
    ]
    
    # Known facts database with sources (in production would use external APIs)
    KNOWN_FACTS = {
        # World capitals
        'france': {
            'capital': 'paris',
            'source': 'CIA World Factbook',
            'source_url': 'https://www.cia.gov/the-world-factbook/countries/france/'
        },
        'germany': {
            'capital': 'berlin',
            'source': 'CIA World Factbook',
            'source_url': 'https://www.cia.gov/the-world-factbook/countries/germany/'
        },
        'japan': {
            'capital': 'tokyo',
            'source': 'CIA World Factbook',
            'source_url': 'https://www.cia.gov/the-world-factbook/countries/japan/'
        },
        'usa': {
            'capital': 'washington',
            'source': 'CIA World Factbook',
            'source_url': 'https://www.cia.gov/the-world-factbook/countries/united-states/'
        },
        'united states': {
            'capital': 'washington',
            'source': 'CIA World Factbook',
            'source_url': 'https://www.cia.gov/the-world-factbook/countries/united-states/'
        },
        'uk': {
            'capital': 'london',
            'source': 'CIA World Factbook',
            'source_url': 'https://www.cia.gov/the-world-factbook/countries/united-kingdom/'
        },
        'united kingdom': {
            'capital': 'london',
            'source': 'CIA World Factbook',
            'source_url': 'https://www.cia.gov/the-world-factbook/countries/united-kingdom/'
        },
        'india': {
            'capital': 'new delhi',
            'source': 'CIA World Factbook',
            'source_url': 'https://www.cia.gov/the-world-factbook/countries/india/'
        },
        'china': {
            'capital': 'beijing',
            'source': 'CIA World Factbook',
            'source_url': 'https://www.cia.gov/the-world-factbook/countries/china/'
        },
        'australia': {
            'capital': 'canberra',
            'source': 'CIA World Factbook',
            'source_url': 'https://www.cia.gov/the-world-factbook/countries/australia/'
        },
        'canada': {
            'capital': 'ottawa',
            'source': 'CIA World Factbook',
            'source_url': 'https://www.cia.gov/the-world-factbook/countries/canada/'
        },
        'brazil': {
            'capital': 'brasilia',
            'source': 'CIA World Factbook',
            'source_url': 'https://www.cia.gov/the-world-factbook/countries/brazil/'
        },
        'russia': {
            'capital': 'moscow',
            'source': 'CIA World Factbook',
            'source_url': 'https://www.cia.gov/the-world-factbook/countries/russia/'
        },
        'italy': {
            'capital': 'rome',
            'source': 'CIA World Factbook',
            'source_url': 'https://www.cia.gov/the-world-factbook/countries/italy/'
        },
        'spain': {
            'capital': 'madrid',
            'source': 'CIA World Factbook',
            'source_url': 'https://www.cia.gov/the-world-factbook/countries/spain/'
        },
        # Historical dates
        'world war 1': {
            'started': '1914',
            'ended': '1918',
            'source': 'History.com',
            'source_url': 'https://www.history.com/topics/world-war-i/world-war-i-history'
        },
        'world war 2': {
            'started': '1939',
            'ended': '1945',
            'source': 'National WWII Museum',
            'source_url': 'https://www.nationalww2museum.org/war/wwii-history'
        },
        'moon landing': {
            'year': '1969',
            'date': 'July 20, 1969',
            'source': 'NASA',
            'source_url': 'https://www.nasa.gov/mission_pages/apollo/apollo-11.html'
        },
        'apollo 11': {
            'year': '1969',
            'date': 'July 20, 1969',
            'source': 'NASA',
            'source_url': 'https://www.nasa.gov/mission_pages/apollo/apollo-11.html'
        },
        'internet': {
            'invented': '1983',
            'arpanet': '1969',
            'source': 'Computer History Museum',
            'source_url': 'https://www.computerhistory.org/internethistory/'
        },
        'declaration of independence': {
            'year': '1776',
            'date': 'July 4, 1776',
            'source': 'National Archives',
            'source_url': 'https://www.archives.gov/founding-docs/declaration'
        },
        'french revolution': {
            'started': '1789',
            'ended': '1799',
            'source': 'Britannica',
            'source_url': 'https://www.britannica.com/event/French-Revolution'
        },
        # Scientific facts
        'speed of light': {
            'value': '299792458',
            'unit': 'm/s',
            'source': 'NIST',
            'source_url': 'https://www.nist.gov/si-redefinition/meter'
        },
        'water boiling': {
            'celsius': '100',
            'fahrenheit': '212',
            'source': 'USGS',
            'source_url': 'https://www.usgs.gov/special-topics/water-science-school'
        },
        'earth': {
            'age': '4.5 billion years',
            'circumference': '40075 km',
            'source': 'NASA',
            'source_url': 'https://solarsystem.nasa.gov/planets/earth/overview/'
        },
        'sun': {
            'age': '4.6 billion years',
            'temperature': '5500 celsius',
            'source': 'NASA',
            'source_url': 'https://solarsystem.nasa.gov/solar-system/sun/overview/'
        },
        'mount everest': {
            'height': '8849',
            'unit': 'meters',
            'source': 'National Geographic',
            'source_url': 'https://www.nationalgeographic.com/environment/article/mount-everest'
        },
        # Population facts
        'world population': {
            'value': '8 billion',
            'year': '2024',
            'source': 'United Nations',
            'source_url': 'https://www.un.org/en/global-issues/population'
        },
    }
    
    def __init__(self):
        self.name = "TrustGuard Fact Verifier"
    
    def extract_claims(self, text):
        """Extract all potential factual claims from text"""
        claims = []
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        for idx, sentence in enumerate(sentences):
            sentence_claims = {
                'sentence': sentence,
                'sentence_index': idx,
                'claims': [],
                'verification_status': 'pending'
            }
            
            # Check for each pattern type
            for claim_type, pattern in self.CLAIM_PATTERNS.items():
                matches = re.findall(pattern, sentence, re.IGNORECASE)
                if matches:
                    for match in matches:
                        claim_text = match if isinstance(match, str) else match[0]
                        if len(claim_text) > 2:  # Filter out noise
                            sentence_claims['claims'].append({
                                'type': claim_type,
                                'text': claim_text,
                                'verifiable': True
                            })
            
            if sentence_claims['claims']:
                claims.append(sentence_claims)
        
        return claims
    
    def check_misleading_patterns(self, text):
        """Check for common misleading claim patterns"""
        text_lower = text.lower()
        found_patterns = []
        
        for pattern in self.MISLEADING_INDICATORS:
            if pattern in text_lower:
                found_patterns.append({
                    'pattern': pattern,
                    'warning': f"Vague attribution '{pattern}' - specific source needed",
                    'severity': 'medium'
                })
        
        return found_patterns
    
    def verify_against_knowledge(self, text):
        """Verify claims against known facts database with source links"""
        text_lower = text.lower()
        verifications = []
        
        # Check capital city claims
        capital_pattern = r'(?:capital of|capital city of)\s+(\w+(?:\s+\w+)?)\s+is\s+(\w+(?:\s+\w+)?)'
        capital_matches = re.findall(capital_pattern, text_lower)
        
        for country, claimed_capital in capital_matches:
            country = country.strip()
            claimed_capital = claimed_capital.strip()
            if country in self.KNOWN_FACTS:
                facts = self.KNOWN_FACTS[country]
                actual = facts.get('capital', '')
                if actual:
                    is_correct = actual.lower() == claimed_capital.lower()
                    verifications.append({
                        'claim': f"Capital of {country.title()} is {claimed_capital.title()}",
                        'claim_type': 'geography',
                        'verified': is_correct,
                        'correct_answer': actual.title() if not is_correct else None,
                        'confidence': 0.95 if is_correct else 0.1,
                        'source': facts.get('source', 'Unknown'),
                        'source_url': facts.get('source_url', None)
                    })
        
        # Check for specific topics mentioned in text
        for topic, facts in self.KNOWN_FACTS.items():
            if topic in text_lower:
                source = facts.get('source', 'Unknown')
                source_url = facts.get('source_url', None)
                
                # Check year/date claims
                for fact_key, fact_value in facts.items():
                    if fact_key in ['source', 'source_url']:
                        continue
                    if isinstance(fact_value, str) and (fact_value.isdigit() or 'billion' in fact_value.lower()):
                        if fact_value in text or fact_value.lower() in text_lower:
                            # Determine claim type
                            claim_type = 'historical' if fact_key in ['started', 'ended', 'year', 'date'] else 'scientific'
                            verifications.append({
                                'claim': f"{topic.title()} - {fact_key.replace('_', ' ').title()}: {fact_value}",
                                'claim_type': claim_type,
                                'verified': True,
                                'confidence': 0.9,
                                'source': source,
                                'source_url': source_url
                            })
        
        # Check for common incorrect claims
        incorrect_claims = self._check_incorrect_claims(text_lower)
        verifications.extend(incorrect_claims)
        
        return verifications
    
    def _check_incorrect_claims(self, text_lower):
        """Check for commonly incorrect claims"""
        incorrect = []
        
        # Check for wrong capitals
        wrong_capital_patterns = [
            (r'capital of australia is sydney', 'australia', 'sydney', 'canberra'),
            (r'capital of turkey is istanbul', 'turkey', 'istanbul', 'ankara'),
            (r'capital of brazil is rio', 'brazil', 'rio', 'brasilia'),
            (r'capital of india is mumbai', 'india', 'mumbai', 'new delhi'),
            (r'capital of usa is new york', 'usa', 'new york', 'washington'),
        ]
        
        for pattern, country, wrong, correct in wrong_capital_patterns:
            if re.search(pattern, text_lower):
                country_facts = self.KNOWN_FACTS.get(country, {})
                incorrect.append({
                    'claim': f"Capital of {country.title()} is {wrong.title()}",
                    'claim_type': 'geography',
                    'verified': False,
                    'correct_answer': correct.title(),
                    'confidence': 0.05,
                    'source': country_facts.get('source', 'CIA World Factbook'),
                    'source_url': country_facts.get('source_url', 'https://www.cia.gov/the-world-factbook/')
                })
        
        return incorrect
    
    def calculate_verification_score(self, claims, misleading_patterns, verifications):
        """Calculate overall fact verification score"""
        if not claims and not misleading_patterns:
            return {
                'score': 85,
                'status': 'limited_claims',
                'description': 'Text contains few verifiable factual claims'
            }
        
        total_claims = sum(len(c['claims']) for c in claims)
        verified_true = sum(1 for v in verifications if v.get('verified', False))
        verified_false = sum(1 for v in verifications if not v.get('verified', True))
        misleading_count = len(misleading_patterns)
        
        # Base score
        score = 75
        
        # Adjust based on verifications
        if verifications:
            verification_rate = verified_true / len(verifications)
            score += verification_rate * 20
            score -= verified_false * 15
        
        # Penalize misleading patterns
        score -= misleading_count * 8
        
        # Bonus for having verifiable claims
        if total_claims > 0:
            score += min(10, total_claims * 2)
        
        score = max(0, min(100, score))
        
        if score >= 80:
            status = 'high_confidence'
            description = 'Facts appear to be accurate and well-sourced'
        elif score >= 60:
            status = 'medium_confidence'
            description = 'Some claims need additional verification'
        else:
            status = 'low_confidence'
            description = 'Multiple unverified or potentially false claims detected'
        
        return {
            'score': int(score),
            'status': status,
            'description': description
        }
    
    def generate_recommendations(self, claims, misleading_patterns, verifications):
        """Generate fact-checking recommendations"""
        recommendations = []
        
        # Check for unverified claims
        unverified_types = set()
        for claim_group in claims:
            for claim in claim_group['claims']:
                unverified_types.add(claim['type'])
        
        if 'statistics' in unverified_types:
            recommendations.append({
                'type': 'statistics',
                'action': 'Verify statistics with primary sources',
                'priority': 'high'
            })
        
        if 'dates' in unverified_types:
            recommendations.append({
                'type': 'dates',
                'action': 'Cross-reference dates with reliable historical sources',
                'priority': 'medium'
            })
        
        if 'quotes' in unverified_types:
            recommendations.append({
                'type': 'quotes',
                'action': 'Verify quotes are accurately attributed',
                'priority': 'high'
            })
        
        if 'attributions' in unverified_types:
            recommendations.append({
                'type': 'attribution',
                'action': 'Confirm source attributions are correct',
                'priority': 'medium'
            })
        
        if misleading_patterns:
            recommendations.append({
                'type': 'sourcing',
                'action': 'Replace vague attributions with specific sources',
                'priority': 'high'
            })
        
        # Check for false verifications
        false_claims = [v for v in verifications if not v.get('verified', True)]
        if false_claims:
            recommendations.append({
                'type': 'correction',
                'action': f'Correct {len(false_claims)} factually inaccurate claim(s)',
                'priority': 'critical'
            })
        
        if not recommendations:
            recommendations.append({
                'type': 'general',
                'action': 'Continue to verify claims with authoritative sources',
                'priority': 'low'
            })
        
        return recommendations
    
    def verify_facts(self, text):
        """Main fact verification method"""
        if not text or len(text.strip()) < 30:
            return {
                'success': False,
                'error': 'Text must be at least 30 characters long'
            }
        
        # Extract claims
        claims = self.extract_claims(text)
        
        # Check for misleading patterns
        misleading_patterns = self.check_misleading_patterns(text)
        
        # Verify against knowledge base
        verifications = self.verify_against_knowledge(text)
        
        # Calculate score
        score_result = self.calculate_verification_score(claims, misleading_patterns, verifications)
        
        # Generate recommendations
        recommendations = self.generate_recommendations(claims, misleading_patterns, verifications)
        
        # Count claim types
        claim_type_counts = {}
        for claim_group in claims:
            for claim in claim_group['claims']:
                ctype = claim['type']
                claim_type_counts[ctype] = claim_type_counts.get(ctype, 0) + 1
        
        return {
            'success': True,
            'verification_score': score_result['score'],
            'trust_score': score_result['score'],  # Alias for frontend compatibility
            'status': score_result['status'],
            'description': score_result['description'],
            'analysis': {
                'overall_risk': 'low' if score_result['score'] >= 80 else ('medium' if score_result['score'] >= 60 else 'high'),
                'risk_description': score_result['description'],
                'total_claims': sum(len(c['claims']) for c in claims),
                'claim_types': claim_type_counts,
                'verified_count': len([v for v in verifications if v.get('verified', False)]),
                'unverified_count': len([v for v in verifications if not v.get('verified', True)]),
                'misleading_patterns_count': len(misleading_patterns)
            },
            'claims': claims[:10],  # First 10 claim groups
            'misleading_patterns': misleading_patterns,
            'verifications': verifications,
            'recommendations': recommendations,
            'metrics': {
                'fact_score': score_result['score'],
                'claim_density': round(sum(len(c['claims']) for c in claims) / max(1, len(text.split())) * 100, 1),
                'source_quality': 100 - (len(misleading_patterns) * 15),
                'verification_rate': round(len([v for v in verifications if v.get('verified', False)]) / max(1, len(verifications)) * 100, 1) if verifications else 0
            }
        }


# Initialize verifier
fact_verifier = FactVerifier()


# ============================================
# API Routes
# ============================================

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        'service': 'TrustGuard AI Analysis API',
        'version': '2.0.0',
        'status': 'running',
        'endpoints': {
            'health': '/health',
            'analyze': '/api/analyze',
            'hallucination': '/api/analyze/hallucination'
        }
    }), 200


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'TrustGuard AI Hallucination Detector',
        'llm_configured': llm_detector.is_configured(),
        'llm_model': llm_detector.model if llm_detector.is_configured() else None
    }), 200


@app.route('/api/config', methods=['POST'])
def configure_api():
    """Configure API keys for LLM-based detection"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
        
        api_key = data.get('groq_api_key', '')
        
        if api_key:
            llm_detector.set_api_key(api_key)
            logger.info("Groq API key configured successfully")
            return jsonify({
                'success': True,
                'message': 'API key configured successfully',
                'llm_enabled': True
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No API key provided'
            }), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration status"""
    return jsonify({
        'llm_configured': llm_detector.is_configured(),
        'llm_model': llm_detector.model,
        'heuristic_available': True,
        'fact_verification_available': True
    }), 200


@app.route('/api/analyze', methods=['POST'])
def analyze_text():
    """Main analysis endpoint - routes to appropriate analyzer based on options"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
        
        text = data.get('text', '')
        options = data.get('options', {})
        analysis_type = options.get('type', 'hallucination')
        use_llm = options.get('use_llm', True)  # Default to LLM if available
        
        # Route to appropriate analyzer
        if analysis_type == 'fact-verification':
            result = fact_verifier.verify_facts(text)
        elif analysis_type == 'hallucination' and use_llm and llm_detector.is_configured():
            # Use LLM-based SelfCheckGPT approach
            result = llm_detector.detect_hallucination(text)
        else:
            # Fallback to heuristic detection
            result = detector.detect_hallucination(text)
        
        if not result['success']:
            return jsonify(result), 400
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Analysis error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Analysis failed: {str(e)}'
        }), 500


@app.route('/api/analyze/hallucination', methods=['POST'])
def analyze_hallucination():
    """Dedicated hallucination detection endpoint - uses LLM if available"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
        
        text = data.get('text', '')
        use_llm = data.get('use_llm', True)
        
        # Try LLM first, fallback to heuristic
        if use_llm and llm_detector.is_configured():
            result = llm_detector.detect_hallucination(text)
        else:
            result = detector.detect_hallucination(text)
        
        if not result['success']:
            return jsonify(result), 400
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Hallucination detection error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Detection failed: {str(e)}'
        }), 500


@app.route('/api/analyze/quick', methods=['POST'])
def quick_analyze():
    """Quick analysis returning just score and risk level"""
    try:
        data = request.get_json()
        text = data.get('text', '')
        
        result = detector.detect_hallucination(text)
        
        if not result['success']:
            return jsonify(result), 400
        
        return jsonify({
            'success': True,
            'trust_score': result['trust_score'],
            'risk_level': result['analysis']['overall_risk'],
            'flagged_count': result['analysis']['flagged_count']
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analyze/fact-verification', methods=['POST'])
def analyze_fact_verification():
    """Dedicated fact verification endpoint"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
        
        text = data.get('text', '')
        
        result = fact_verifier.verify_facts(text)
        
        if not result['success']:
            return jsonify(result), 400
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Fact verification error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Verification failed: {str(e)}'
        }), 500


# ============================================
# Run Server
# ============================================

@app.route('/api/history', methods=['GET'])
def get_history():
    """Get analysis history"""
    try:
        history = load_history()
        stats = get_history_stats()
        
        # Apply filters if provided
        filter_type = request.args.get('type', 'all')
        search_query = request.args.get('search', '').lower()
        limit = int(request.args.get('limit', 50))
        
        # Filter by type
        if filter_type != 'all':
            history = [h for h in history if h.get('type', '') == filter_type]
        
        # Filter by search
        if search_query:
            history = [h for h in history if search_query in h.get('title', '').lower() or search_query in h.get('preview', '').lower()]
        
        return jsonify({
            'success': True,
            'history': history[:limit],
            'stats': stats,
            'total': len(history)
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/history', methods=['POST'])
def save_to_history():
    """Save an analysis result to history"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        entry = {
            'type': data.get('type', 'text'),
            'title': data.get('title', 'Untitled Analysis'),
            'preview': data.get('preview', ''),
            'trust_score': data.get('trust_score', 0),
            'method': data.get('method', 'heuristic'),
            'analysis_type': data.get('analysis_type', 'hallucination'),
            'word_count': data.get('word_count', 0),
            'issues_found': data.get('issues_found', 0),
            'risk_level': data.get('risk_level', 'unknown'),
            'full_result': data.get('full_result', {})
        }
        
        saved_entry = add_to_history(entry)
        
        return jsonify({
            'success': True,
            'message': 'Analysis saved to history',
            'entry': saved_entry
        }), 201
        
    except Exception as e:
        logger.error(f"Error saving to history: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/history/<entry_id>', methods=['DELETE'])
def delete_history_entry(entry_id):
    """Delete a specific history entry"""
    try:
        history = load_history()
        history = [h for h in history if h.get('id') != entry_id]
        save_history(history)
        
        return jsonify({
            'success': True,
            'message': 'Entry deleted'
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/history/clear', methods=['DELETE'])
def clear_history():
    """Clear all history"""
    try:
        save_history([])
        return jsonify({
            'success': True,
            'message': 'History cleared'
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/history/export', methods=['GET'])
def export_history():
    """Export history as JSON"""
    try:
        history = load_history()
        return jsonify({
            'success': True,
            'data': history,
            'exported_at': datetime.now().isoformat(),
            'total_entries': len(history)
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# Media Analysis Endpoints (Deepfake Detection)
# ============================================

# Import media analyzer
try:
    from media_analyzer import get_analyzer, MediaTrustAnalyzer
    MEDIA_ANALYZER_AVAILABLE = True
except ImportError:
    MEDIA_ANALYZER_AVAILABLE = False
    logger.warning("Media analyzer not available")


@app.route('/api/analyze/media', methods=['POST'])
def analyze_media():
    """
    Analyze uploaded media (image/video) for deepfakes and manipulation
    Accepts multipart form data with file upload
    """
    if not MEDIA_ANALYZER_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Media analyzer not available. Check server logs.'
        }), 500
    
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file uploaded. Use form field "file".'
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        # Get options
        kid_safe_mode = request.form.get('kid_safe_mode', 'false').lower() == 'true'
        kid_safe_threshold = int(request.form.get('kid_safe_threshold', 75))
        
        # Save file temporarily
        import tempfile
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, file.filename)
        file.save(temp_path)
        
        try:
            # Analyze the media
            analyzer = get_analyzer()
            result = analyzer.analyze_media(
                file_path=temp_path,
                kid_safe_mode=kid_safe_mode,
                kid_safe_threshold=kid_safe_threshold
            )
            
            # Add to history if successful
            if result.get('success'):
                history_entry = {
                    'title': file.filename,
                    'content_type': result.get('content_type', 'image'),
                    'analysis_type': 'Deepfake Detection',
                    'trust_score': result.get('trust_score', 50),
                    'issues_found': 1 if result.get('is_deepfake') or result.get('is_manipulated') else 0,
                    'method': 'AI Vision Model'
                }
                add_to_history(history_entry)
            
            return jsonify(result), 200
            
        finally:
            # Clean up temp file
            try:
                os.remove(temp_path)
                os.rmdir(temp_dir)
            except:
                pass
                
    except Exception as e:
        logger.error(f"Media analysis error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/analyze/media/status', methods=['GET'])
def media_analyzer_status():
    """Check if media analyzer and models are available"""
    status = {
        'media_analyzer_available': MEDIA_ANALYZER_AVAILABLE,
        'models_loaded': False,
        'clip_available': False,
        'deepfake_available': False
    }
    
    if MEDIA_ANALYZER_AVAILABLE:
        try:
            from media_analyzer import CLIP_AVAILABLE, DEEPFAKE_AVAILABLE, ML_AVAILABLE
            analyzer = get_analyzer()
            status['models_loaded'] = analyzer.models_loaded
            status['clip_available'] = CLIP_AVAILABLE
            status['deepfake_available'] = DEEPFAKE_AVAILABLE
            status['ml_available'] = ML_AVAILABLE
        except:
            pass
    
    return jsonify(status), 200


@app.route('/api/analyze/media/load-models', methods=['POST'])
def load_media_models():
    """Manually trigger model loading"""
    if not MEDIA_ANALYZER_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Media analyzer not available'
        }), 500
    
    try:
        analyzer = get_analyzer()
        success = analyzer.load_models()
        
        return jsonify({
            'success': success,
            'message': 'Models loaded successfully' if success else 'Failed to load some models',
            'models_loaded': analyzer.models_loaded
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# URL Phishing Detection Endpoint
# ============================================

@app.route('/api/analyze/url', methods=['POST'])
def analyze_url_endpoint():
    """Analyze URL for phishing indicators"""
    try:
        from url_phishing_detector import url_detector
        
        data = request.get_json()
        url = data.get('url', '')
        
        if not url:
            return jsonify({
                'success': False,
                'error': 'No URL provided'
            }), 400
        
        # Analyze the URL
        result = url_detector.analyze_url(url)
        
        if result.get('success'):
            # Save to history
            history_entry = {
                'type': 'url',
                'content': url[:100],
                'trust_score': result.get('trust_score', 0),
                'status': result.get('status', 'unknown'),
                'title': f"URL Scan: {result.get('domain', url)[:40]}"
            }
            add_to_history(history_entry)
        
        return jsonify(result), 200
        
    except ImportError as e:
        logger.error(f"Import error: {e}")
        return jsonify({
            'success': False,
            'error': 'URL phishing detector not available'
        }), 500
    except Exception as e:
        logger.error(f"URL analysis error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/analyze/url/batch', methods=['POST'])
def analyze_urls_batch():
    """Analyze multiple URLs at once"""
    try:
        from url_phishing_detector import url_detector
        
        data = request.get_json()
        urls = data.get('urls', [])
        
        if not urls:
            return jsonify({
                'success': False,
                'error': 'No URLs provided'
            }), 400
        
        results = []
        for url in urls[:10]:  # Limit to 10 URLs
            result = url_detector.analyze_url(url)
            results.append({
                'url': url,
                'trust_score': result.get('trust_score', 0),
                'risk_level': result.get('risk_level', 'unknown'),
                'status': result.get('status', 'unknown')
            })
        
        return jsonify({
            'success': True,
            'results': results,
            'count': len(results)
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    port = 5001
    logger.info("=" * 60)
    logger.info("TrustGuard AI - Hallucination Detection Server")
    logger.info("=" * 60)
    logger.info(f"Starting server on http://localhost:{port}")
    logger.info("Endpoints:")
    logger.info("  POST /api/analyze - Full text analysis")
    logger.info("  POST /api/analyze/hallucination - Hallucination detection")
    logger.info("  POST /api/analyze/quick - Quick score check")
    logger.info("  POST /api/analyze/media - Deepfake/media analysis")
    logger.info("  POST /api/analyze/url - URL phishing detection")
    logger.info("=" * 60)
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=True
    )
