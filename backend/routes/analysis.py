"""
Analysis Routes
Handles text analysis, hallucination detection, and fact-checking
"""

from flask import Blueprint, request, jsonify
from services.hallucination_detector_simple import get_hallucination_detector
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create blueprint
analysis_bp = Blueprint('analysis', __name__, url_prefix='/api/analysis')


@analysis_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    detector = get_hallucination_detector()
    status = detector.get_model_status()
    
    return jsonify({
        'success': True,
        'service': 'Analysis Service',
        'models': status
    }), 200


@analysis_bp.route('/hallucination', methods=['POST'])
def detect_hallucination():
    """
    Detect hallucinations in text content
    
    Request body:
    {
        "text": "Text to analyze",
        "method": "bertscore" | "nli" | "both" (optional, default: "bertscore"),
        "num_samples": 3 (optional, default: 3)
    }
    """
    try:
        # Get request data
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: text'
            }), 400
        
        text = data['text'].strip()
        
        if len(text) < 50:
            return jsonify({
                'success': False,
                'error': 'Text must be at least 50 characters long'
            }), 400
        
        method = data.get('method', 'bertscore')
        num_samples = data.get('num_samples', 3)
        
        # Validate method
        if method not in ['bertscore', 'nli', 'both']:
            return jsonify({
                'success': False,
                'error': 'Invalid method. Must be one of: bertscore, nli, both'
            }), 400
        
        # Get detector and analyze
        logger.info(f"Analyzing text ({len(text)} chars) with method: {method}")
        detector = get_hallucination_detector()
        
        result = detector.detect_hallucination(
            text=text,
            method=method,
            num_samples=num_samples
        )
        
        if not result.get('success', False):
            return jsonify(result), 500
        
        # Calculate trust score based on hallucination risk
        hallucination_analysis = result.get('hallucination_analysis', {})
        risk_level = hallucination_analysis.get('overall_risk', 'unknown')
        
        # Convert risk to trust score (0-100)
        trust_score = 0
        if risk_level == 'low':
            trust_score = 85 + (hallucination_analysis.get('confidence', 0.7) - 0.7) * 50
        elif risk_level == 'medium':
            trust_score = 50 + (hallucination_analysis.get('confidence', 0.5) - 0.4) * 100
        elif risk_level == 'high':
            trust_score = 20 + hallucination_analysis.get('confidence', 0.3) * 50
        
        result['trust_score'] = min(100, max(0, int(trust_score)))
        
        logger.info(f"✓ Analysis complete. Trust score: {result['trust_score']}")
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error in hallucination detection: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@analysis_bp.route('/text', methods=['POST'])
def analyze_text():
    """
    Complete text analysis including hallucination detection
    
    Request body:
    {
        "text": "Text to analyze",
        "analysis_types": ["factcheck", "hallucination", "sentiment", "bias"]
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: text'
            }), 400
        
        text = data['text'].strip()
        analysis_types = data.get('analysis_types', ['hallucination'])
        
        if len(text) < 50:
            return jsonify({
                'success': False,
                'error': 'Text must be at least 50 characters long'
            }), 400
        
        results = {
            'success': True,
            'text_length': len(text),
            'analysis_types': analysis_types,
            'analyses': {}
        }
        
        # Hallucination detection
        if 'hallucination' in analysis_types:
            logger.info("Running hallucination detection...")
            detector = get_hallucination_detector()
            hallucination_result = detector.detect_hallucination(
                text=text,
                method='bertscore'  # Use fast method for initial analysis
            )
            results['analyses']['hallucination'] = hallucination_result
        
        # Fact-checking (placeholder - to be implemented)
        if 'factcheck' in analysis_types:
            logger.info("Fact-checking requested (not yet implemented)")
            results['analyses']['factcheck'] = {
                'status': 'not_implemented',
                'message': 'Fact-checking service coming soon'
            }
        
        # Sentiment analysis (placeholder)
        if 'sentiment' in analysis_types:
            logger.info("Sentiment analysis requested (not yet implemented)")
            results['analyses']['sentiment'] = {
                'status': 'not_implemented',
                'message': 'Sentiment analysis service coming soon'
            }
        
        # Bias detection (placeholder)
        if 'bias' in analysis_types:
            logger.info("Bias detection requested (not yet implemented)")
            results['analyses']['bias'] = {
                'status': 'not_implemented',
                'message': 'Bias detection service coming soon'
            }
        
        # Calculate overall trust score
        if 'hallucination' in results['analyses'] and results['analyses']['hallucination'].get('success'):
            hallucination_data = results['analyses']['hallucination']
            results['overall_trust_score'] = hallucination_data.get('trust_score', 50)
        else:
            results['overall_trust_score'] = 50
        
        return jsonify(results), 200
        
    except Exception as e:
        logger.error(f"Error in text analysis: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@analysis_bp.route('/models/status', methods=['GET'])
def get_models_status():
    """Get the status of all loaded AI models"""
    try:
        detector = get_hallucination_detector()
        status = detector.get_model_status()
        
        return jsonify({
            'success': True,
            'models': status,
            'available_services': {
                'hallucination_detection': status['model_loaded'],
                'fact_checking': False,  # To be implemented
                'sentiment_analysis': False,  # To be implemented
                'bias_detection': False  # To be implemented
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
