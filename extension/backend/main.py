import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
# Add backend directory to Python path
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import logging

from services.content_analyzer import ContentAnalyzer
# CHANGED: Import improved engines instead of original ones
from services.content_analyzer import ContentAnalyzer
from services.information_trust import ImprovedInformationTrustEngine
from services.media_trust import ImprovedMediaTrustEngine
from utils.scoring import calculate_overall_score
from utils.validators import validate_analysis_request

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="TrustGuard AI API", version="2.0.0")

# CORS - Allow all for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize engines
content_analyzer = ContentAnalyzer()
# CHANGED: Use improved engines
info_engine = ImprovedInformationTrustEngine()
media_engine = ImprovedMediaTrustEngine()


# Request Models
class AnalyzeRequest(BaseModel):
    content_type: str  # "text", "url", "page"
    text: Optional[str] = None
    url: Optional[str] = None
    page_data: Optional[dict] = None


class ImageAnalyzeRequest(BaseModel):
    image_urls: List[str]


@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "TrustGuard AI API",
        "version": "2.0.0",
        "endpoints": {
            "analyze": "/api/analyze",
            "analyze_images": "/api/analyze-images"
        }
    }


@app.post("/api/analyze")
async def analyze_content(request: AnalyzeRequest):
    """Main analysis endpoint"""
    try:
        # Validate request
        validate_analysis_request(
            request.content_type,
            request.text,
            request.url,
            request.page_data
        )
        
        logger.info(f"Analysis request: type={request.content_type}")
        
        # Step 1: Analyze content structure
        content_analysis = await content_analyzer.analyze(request)
        
        logger.info(f"Content: has_text={content_analysis['has_text']}, has_media={content_analysis['has_media']}")
        
        # Step 2: Run applicable analyses
        results = {}
        applicable_pillars = []
        
        # Information Trust - only if text exists
        if content_analysis['has_text']:
            logger.info("Running Information Trust analysis...")
            results['information_trust'] = await info_engine.analyze(
                text=content_analysis['text'],
                url=request.url
            )
            applicable_pillars.append("information_trust")
        else:
            results['information_trust'] = {
                "score": None,
                "applicable": False,
                "reason": "No text content to analyze",
                "details": None
            }
        
        # Media Trust - only if images/videos exist
        if content_analysis['has_media']:
            logger.info("Running Media Trust analysis...")
            results['media_trust'] = await media_engine.analyze(
                images=content_analysis['images'],
                videos=content_analysis['videos']
            )
            applicable_pillars.append("media_trust")
        else:
            results['media_trust'] = {
                "score": None,
                "applicable": False,
                "reason": "No images or videos to analyze",
                "details": None
            }
        
        # Step 3: Calculate overall score
        overall = calculate_overall_score(results, applicable_pillars)
        
        response = {
            "overall_score": overall['score'],
            "verdict": overall['verdict'],
            "confidence": overall['confidence'],
            "pillars": results,
            "applicable_pillars": applicable_pillars,
            "findings": overall['findings'],
            "ai_content_detected": overall.get('ai_content_detected', False),
            "suspicious_segments": overall.get('suspicious_segments', [])
        }
        
        logger.info(f"Analysis complete: {overall['score']}/100 - {overall['verdict']}")
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Analysis error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze-images")
async def analyze_images(request: ImageAnalyzeRequest):
    """Analyze multiple images for AI/deepfake detection"""
    try:
        # CHANGED: Use the improved method name
        results = await media_engine.analyze(request.image_urls, [])
        return {
            "success": True,
            "results": results.get('details', {}).get('images', {}).get('results', [])
        }
    except Exception as e:
        logger.error(f"Image analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze-image")
async def analyze_single_image(file: UploadFile = File(...)):
    """Analyze uploaded image"""
    try:
        image_data = await file.read()
        # CHANGED: Use the improved method name
        result = await media_engine.analyze_single_image_enhanced(image_data)
        return result
    except Exception as e:
        logger.error(f"Image analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Run server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)