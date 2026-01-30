"""
Simplified Hallucination Detection without heavy dependencies
Uses sentence-transformers only for basic consistency checking
"""

import os
from typing import Dict, List
import logging
from sentence_transformers import SentenceTransformer
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimplifiedHallucinationDetector:
    """Simplified hallucination detection using semantic similarity"""
    
    def __init__(self):
        self.model_loaded = False
        self.sentence_model = None
        self._load_models()
    
    def _load_models(self):
        """Load sentence transformer model"""
        try:
            logger.info("Loading sentence transformer model...")
            self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
            self.model_loaded = True
            logger.info("✓ Model loaded successfully")
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            self.model_loaded = False
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Simple sentence splitting"""
        sentences = []
        for sent in text.replace('!', '.').replace('?', '.').split('.'):
            sent = sent.strip()
            if sent and len(sent) > 10:
                sentences.append(sent)
        return sentences
    
    def detect_hallucination(self, text: str, method: str = 'simple', num_samples: int = 3) -> Dict:
        """
        Detect hallucinations using semantic similarity
        """
        if not self.model_loaded:
            return {'error': 'Model not loaded', 'success': False}
        
        try:
            sentences = self._split_into_sentences(text)
            
            if len(sentences) < 2:
                return {
                    'success': True,
                    'text_length': len(text),
                    'sentence_count': len(sentences),
                    'trust_score': 75,
                    'hallucination_analysis': {
                        'overall_risk': 'low',
                        'confidence': 0.75,
                        'flagged_sentences': [],
                        'recommendations': ['Text too short for detailed analysis']
                    }
                }
            
            # Encode all sentences
            embeddings = self.sentence_model.encode(sentences)
            
            # Calculate pairwise similarities
            similarities = []
            for i in range(len(embeddings)):
                for j in range(i+1, len(embeddings)):
                    sim = np.dot(embeddings[i], embeddings[j]) / (
                        np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[j])
                    )
                    similarities.append(float(sim))
            
            avg_similarity = np.mean(similarities) if similarities else 0.5
            min_similarity = np.min(similarities) if similarities else 0.5
            
            # Calculate sentence-level scores (compare each to average)
            avg_embedding = np.mean(embeddings, axis=0)
            sentence_scores = []
            for emb in embeddings:
                score = np.dot(emb, avg_embedding) / (
                    np.linalg.norm(emb) * np.linalg.norm(avg_embedding)
                )
                sentence_scores.append(float(score))
            
            # Analyze risk
            risk_level = 'low' if avg_similarity > 0.7 else ('medium' if avg_similarity > 0.4 else 'high')
            
            flagged_sentences = []
            for idx, score in enumerate(sentence_scores):
                if score < 0.6:
                    flagged_sentences.append({
                        'index': idx,
                        'score': score,
                        'risk': 'high' if score < 0.4 else 'medium'
                    })
            
            # Calculate trust score
            trust_score = int(min(100, max(0, avg_similarity * 100)))
            
            return {
                'success': True,
                'text_length': len(text),
                'sentence_count': len(sentences),
                'sentences': sentences,
                'scores': {
                    'semantic_similarity': {
                        'sentence_scores': sentence_scores,
                        'average_score': float(avg_similarity),
                        'min_score': float(min_similarity)
                    }
                },
                'hallucination_analysis': {
                    'overall_risk': risk_level,
                    'confidence': float(avg_similarity),
                    'flagged_sentences': flagged_sentences,
                    'recommendations': self._get_recommendations(risk_level, len(flagged_sentences))
                },
                'trust_score': trust_score
            }
            
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            return {'error': str(e), 'success': False}
    
    def _get_recommendations(self, risk_level: str, flagged_count: int) -> List[str]:
        """Generate recommendations"""
        recs = []
        if risk_level == 'high':
            recs.append("High inconsistency detected. Verify claims against reliable sources.")
        elif risk_level == 'medium':
            recs.append("Medium inconsistency. Consider fact-checking key claims.")
        else:
            recs.append("Low inconsistency. Content appears coherent.")
        
        if flagged_count > 0:
            recs.append(f"{flagged_count} sentence(s) flagged for verification.")
        
        return recs
    
    def get_model_status(self) -> Dict:
        """Get model status"""
        return {
            'model_loaded': self.model_loaded,
            'bertscore_available': False,
            'nli_available': False,
            'sentence_transformer_available': self.sentence_model is not None,
            'openai_available': False
        }


_detector_instance = None

def get_hallucination_detector():
    """Get singleton instance"""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = SimplifiedHallucinationDetector()
    return _detector_instance
