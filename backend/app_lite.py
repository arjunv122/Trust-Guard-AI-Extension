"""
Simple Flask API for TrustGuard AI without heavy ML dependencies  
Use this version for testing the frontend integration
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
CORS(app, origins=['http://localhost:8000', 'http://127.0.0.1:8000'], supports_credentials=True)

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        'service': 'TrustGuard AI Analysis API (Lite Version)',
        'version': '1.0.0-lite',
        'status': 'running'
    }), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'TrustGuard AI'
    }), 200

@app.route('/api/analysis/health', methods=['GET'])
def analysis_health():
    return jsonify({
        'success': True,
        'service': 'Analysis Service',
        'models': {
            'model_loaded': True,
            'mode': 'mock'
        }
    }), 200

@app.route('/api/analysis/models/status', methods=['GET'])
def models_status():
    return jsonify({
        'success': True,
        'models': {
            'model_loaded': True,
            'bertscore_available': False,
            'nli_available': False,
            'sentence_transformer_available': False,
            'openai_available': False,
            'mode': 'mock'
        },
        'available_services': {
            'hallucination_detection': True,
            'fact_checking': False,
            'sentiment_analysis': False,
            'bias_detection': False
        }
    }), 200

@app.route('/api/analysis/hallucination', methods=['POST'])
def detect_hallucination():
    try:
        data = request.get_json()
        text = data.get('text', '')
        
        if len(text) < 50:
            return jsonify({
                'success': False,
                'error': 'Text must be at least 50 characters'
            }), 400
        
        # Mock analysis - calculate based on text characteristics
        sentences = [s.strip() for s in text.replace('!', '.').replace('?', '.').split('.') if s.strip()]
        word_count = len(text.split())
        
        # Simple heuristic: longer sentences with more words = higher trust
        trust_score = min(95, 60 + (word_count // 10))
        confidence = trust_score / 100.0
        
        risk = 'low' if trust_score > 75 else ('medium' if trust_score > 50 else 'high')
        
        return jsonify({
            'success': True,
            'text_length': len(text),
            'sentence_count': len(sentences),
            'sentences': sentences[:5],  # First 5 sentences
            'scores': {
                'mock': {
                    'average_score': confidence,
                    'sentence_scores': [0.8] * len(sentences)
                }
            },
            'hallucination_analysis': {
                'overall_risk': risk,
                'confidence': confidence,
                'flagged_sentences': [],
                'recommendations': [
                    f'{risk.capitalize()} hallucination risk detected (mock analysis).',
                    'Note: This is a mock response. Install ML models for real analysis.'
                ]
            },
            'trust_score': trust_score
        }), 200
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analysis/text', methods=['POST'])
def analyze_text():
    try:
        data = request.get_json()
        text = data.get('text', '')
        analysis_types = data.get('analysis_types', ['hallucination'])
        
        if len(text) < 50:
            return jsonify({
                'success': False,
                'error': 'Text must be at least 50 characters'
            }), 400
        
        # Calculate mock trust score
        word_count = len(text.split())
        trust_score = min(92, 65 + (word_count // 8))
        
        return jsonify({
            'success': True,
            'text_length': len(text),
            'analysis_types': analysis_types,
            'analyses': {
                'hallucination': {
                    'success': True,
                    'trust_score': trust_score,
                    'hallucination_analysis': {
                        'overall_risk': 'low',
                        'confidence': trust_score / 100.0,
                        'recommendations': [
                            'Mock analysis complete.',
                            'Install ML models for detailed analysis.'
                        ]
                    }
                }
            },
            'overall_trust_score': trust_score,
            'note': 'This is a mock response for testing. Install full dependencies for real analysis.'
        }), 200
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = 5001
    logger.info(f"Starting TrustGuard AI Lite Server on port {port}")
    logger.info("This is a lightweight version for testing")
    logger.info("Server ready!")
    logger.info("=" * 60)
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=True
    )
