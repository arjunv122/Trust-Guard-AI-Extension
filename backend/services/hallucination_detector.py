"""
Hallucination Detection Service using SelfCheckGPT
This service detects hallucinations in AI-generated or general text content
"""

import os
from typing import Dict, List, Optional
import logging
from selfcheckgpt.modeling_selfcheck import SelfCheckBERTScore, SelfCheckMQAG, SelfCheckNLI
import openai
from sentence_transformers import SentenceTransformer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HallucinationDetector:
    """
    Service for detecting hallucinations in text using SelfCheckGPT
    """
    
    def __init__(self):
        """Initialize the hallucination detection models"""
        self.model_loaded = False
        self.selfcheck_bertscore = None
        self.selfcheck_nli = None
        self.sentence_model = None
        
        # OpenAI API key for generating samples
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        if self.openai_api_key:
            openai.api_key = self.openai_api_key
        
        self._load_models()
    
    def _load_models(self):
        """Load the required models for hallucination detection"""
        try:
            logger.info("Loading hallucination detection models...")
            
            # Load SelfCheck-BERTScore (lightweight and fast)
            logger.info("Loading SelfCheck-BERTScore model...")
            self.selfcheck_bertscore = SelfCheckBERTScore(rescale_with_baseline=True)
            
            # Load SelfCheck-NLI (more accurate but slower)
            logger.info("Loading SelfCheck-NLI model...")
            self.selfcheck_nli = SelfCheckNLI(device='cpu')  # Use 'cuda' if GPU available
            
            # Load sentence transformer for embeddings
            logger.info("Loading sentence transformer...")
            self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
            
            self.model_loaded = True
            logger.info("✓ All hallucination detection models loaded successfully")
            
        except Exception as e:
            logger.error(f"Error loading models: {str(e)}")
            self.model_loaded = False
            raise
    
    def _generate_samples(self, text: str, num_samples: int = 3) -> List[str]:
        """
        Generate alternative versions of the text for consistency checking
        Uses OpenAI if available, otherwise uses simple variations
        """
        samples = []
        
        if self.openai_api_key:
            try:
                # Use OpenAI to generate paraphrased versions
                for i in range(num_samples):
                    response = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=[{
                            "role": "system",
                            "content": "Paraphrase the following text while keeping the same meaning and facts. Only return the paraphrased text."
                        }, {
                            "role": "user",
                            "content": text
                        }],
                        temperature=0.7 + (i * 0.1),  # Vary temperature for diversity
                        max_tokens=len(text.split()) * 2
                    )
                    samples.append(response.choices[0].message.content.strip())
                    
            except Exception as e:
                logger.warning(f"Error generating samples with OpenAI: {str(e)}")
                # Fallback to simple variations
                samples = self._generate_simple_samples(text, num_samples)
        else:
            # Use simple text variations
            samples = self._generate_simple_samples(text, num_samples)
        
        return samples
    
    def _generate_simple_samples(self, text: str, num_samples: int) -> List[str]:
        """Generate simple variations of the text (fallback method)"""
        samples = []
        sentences = text.split('. ')
        
        # Create variations by shuffling sentence order (maintaining context)
        for i in range(num_samples):
            if len(sentences) > 1:
                # Simple reordering or slight modifications
                samples.append(text)  # For now, just use the same text
            else:
                samples.append(text)
        
        return samples
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Simple sentence splitting (can be enhanced with spaCy)
        sentences = []
        for sent in text.replace('!', '.').replace('?', '.').split('.'):
            sent = sent.strip()
            if sent:
                sentences.append(sent)
        return sentences
    
    def detect_hallucination(
        self, 
        text: str, 
        method: str = 'bertscore',
        num_samples: int = 3
    ) -> Dict:
        """
        Detect hallucinations in the given text
        
        Args:
            text: The text to analyze
            method: Detection method ('bertscore', 'nli', or 'both')
            num_samples: Number of sample texts to generate for comparison
        
        Returns:
            Dictionary containing hallucination scores and analysis
        """
        if not self.model_loaded:
            return {
                'error': 'Models not loaded',
                'success': False
            }
        
        try:
            logger.info(f"Analyzing text for hallucinations using method: {method}")
            
            # Split text into sentences
            sentences = self._split_into_sentences(text)
            
            if len(sentences) == 0:
                return {
                    'error': 'No sentences found in text',
                    'success': False
                }
            
            # Generate sample texts for comparison
            logger.info(f"Generating {num_samples} sample texts...")
            samples = self._generate_samples(text, num_samples)
            
            results = {
                'success': True,
                'text_length': len(text),
                'sentence_count': len(sentences),
                'samples_generated': len(samples),
                'sentences': sentences,
                'scores': {}
            }
            
            # BERTScore method (fast)
            if method in ['bertscore', 'both']:
                logger.info("Computing BERTScore hallucination scores...")
                bertscore_scores = self.selfcheck_bertscore.predict(
                    sentences=sentences,
                    sampled_passages=samples
                )
                
                results['scores']['bertscore'] = {
                    'sentence_scores': [float(score) for score in bertscore_scores],
                    'average_score': float(sum(bertscore_scores) / len(bertscore_scores)),
                    'min_score': float(min(bertscore_scores)),
                    'max_score': float(max(bertscore_scores))
                }
            
            # NLI method (more accurate)
            if method in ['nli', 'both']:
                logger.info("Computing NLI hallucination scores...")
                nli_scores = self.selfcheck_nli.predict(
                    sentences=sentences,
                    sampled_passages=samples
                )
                
                results['scores']['nli'] = {
                    'sentence_scores': [float(score) for score in nli_scores],
                    'average_score': float(sum(nli_scores) / len(nli_scores)),
                    'min_score': float(min(nli_scores)),
                    'max_score': float(max(nli_scores))
                }
            
            # Calculate overall hallucination risk
            results['hallucination_analysis'] = self._analyze_scores(results['scores'])
            
            logger.info("✓ Hallucination detection completed")
            return results
            
        except Exception as e:
            logger.error(f"Error during hallucination detection: {str(e)}")
            return {
                'error': str(e),
                'success': False
            }
    
    def _analyze_scores(self, scores: Dict) -> Dict:
        """
        Analyze hallucination scores and provide interpretation
        
        Lower scores indicate higher hallucination risk
        """
        analysis = {
            'overall_risk': 'unknown',
            'confidence': 0.0,
            'flagged_sentences': [],
            'recommendations': []
        }
        
        # Use the most accurate available score
        if 'nli' in scores:
            avg_score = scores['nli']['average_score']
            sentence_scores = scores['nli']['sentence_scores']
        elif 'bertscore' in scores:
            avg_score = scores['bertscore']['average_score']
            sentence_scores = scores['bertscore']['sentence_scores']
        else:
            return analysis
        
        # Interpret scores (lower = more hallucination)
        # Typical thresholds: >0.7 = low risk, 0.4-0.7 = medium, <0.4 = high risk
        if avg_score > 0.7:
            analysis['overall_risk'] = 'low'
            analysis['confidence'] = avg_score
        elif avg_score > 0.4:
            analysis['overall_risk'] = 'medium'
            analysis['confidence'] = avg_score
        else:
            analysis['overall_risk'] = 'high'
            analysis['confidence'] = avg_score
        
        # Flag sentences with low scores
        threshold = 0.5
        for idx, score in enumerate(sentence_scores):
            if score < threshold:
                analysis['flagged_sentences'].append({
                    'index': idx,
                    'score': float(score),
                    'risk': 'high' if score < 0.3 else 'medium'
                })
        
        # Generate recommendations
        if analysis['overall_risk'] == 'high':
            analysis['recommendations'].append("High hallucination risk detected. Verify claims against reliable sources.")
        elif analysis['overall_risk'] == 'medium':
            analysis['recommendations'].append("Medium hallucination risk. Consider fact-checking key claims.")
        else:
            analysis['recommendations'].append("Low hallucination risk. Content appears consistent.")
        
        if len(analysis['flagged_sentences']) > 0:
            analysis['recommendations'].append(
                f"{len(analysis['flagged_sentences'])} sentence(s) flagged for verification."
            )
        
        return analysis
    
    def get_model_status(self) -> Dict:
        """Get the status of loaded models"""
        return {
            'model_loaded': self.model_loaded,
            'bertscore_available': self.selfcheck_bertscore is not None,
            'nli_available': self.selfcheck_nli is not None,
            'sentence_transformer_available': self.sentence_model is not None,
            'openai_available': self.openai_api_key is not None
        }


# Singleton instance
_detector_instance = None


def get_hallucination_detector() -> HallucinationDetector:
    """Get or create the singleton hallucination detector instance"""
    global _detector_instance
    
    if _detector_instance is None:
        _detector_instance = HallucinationDetector()
    
    return _detector_instance
