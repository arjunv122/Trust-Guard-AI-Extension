"""
TrustGuard AI - Flask Application
Main application entry point for the analysis backend
"""

from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Configure CORS
CORS(app, origins=['http://localhost:8000', 'http://127.0.0.1:8000'], supports_credentials=True)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max file size


# Import and register blueprints
try:
    from routes.analysis import analysis_bp
    app.register_blueprint(analysis_bp)
    logger.info("✓ Analysis routes registered")
except Exception as e:
    logger.error(f"Error registering analysis routes: {str(e)}")


# Root endpoint
@app.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return jsonify({
        'service': 'TrustGuard AI Analysis API',
        'version': '1.0.0',
        'status': 'running',
        'endpoints': {
            'health': '/api/analysis/health',
            'hallucination_detection': '/api/analysis/hallucination',
            'text_analysis': '/api/analysis/text',
            'models_status': '/api/analysis/models/status'
        }
    }), 200


# Health check
@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'TrustGuard AI'
    }), 200


# Error handlers
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500


if __name__ == '__main__':
    # Run the Flask app
    port = int(os.getenv('PORT', 5001))
    debug = os.getenv('FLASK_ENV', 'development') == 'development'
    
    logger.info(f"Starting TrustGuard AI Analysis Service on port {port}")
    logger.info("AI models will be loaded on first analysis request")
    logger.info("=" * 60)
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )
