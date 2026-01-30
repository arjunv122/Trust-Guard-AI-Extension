import re
from typing import Dict
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import logging

logger = logging.getLogger(__name__)


class ContentAnalyzer:
    """Analyzes input content to determine what's present"""
    
    async def analyze(self, request) -> Dict:
        """Analyze content and determine what's present"""
        result = {
            "has_text": False,
            "has_media": False,
            "text": None,
            "images": [],
            "videos": [],
            "url": None
        }
        
        if request.content_type == "text":
            # Plain text analysis
            if request.text and len(request.text.strip()) > 10:
                result["has_text"] = True
                result["text"] = request.text.strip()
            
        elif request.content_type == "url":
            # Fetch and analyze URL
            content = await self._fetch_url_content(request.url)
            result.update(content)
            
        elif request.content_type == "page":
            # Full page scan data from extension
            page_data = request.page_data or {}
            
            text = page_data.get('text', '')
            if text and len(text.strip()) > 10:
                result["has_text"] = True
                result["text"] = text.strip()[:10000]  # Limit text
            
            images = page_data.get('images', [])
            videos = page_data.get('videos', [])
            
            result["images"] = images[:20]  # Limit to 20 images
            result["videos"] = videos[:10]  # Limit to 10 videos
            result["has_media"] = len(images) > 0 or len(videos) > 0
            result["url"] = page_data.get('url')
            
        return result
    
    async def _fetch_url_content(self, url: str) -> Dict:
        """Fetch content from URL"""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script/style
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            
            # Extract text
            text = soup.get_text(separator=' ', strip=True)
            
            # Extract images
            images = []
            for img in soup.find_all('img', src=True):
                src = img['src']
                if not src.startswith('http'):
                    src = urljoin(url, src)
                if src.startswith('http'):
                    images.append(src)
            
            # Extract videos
            videos = []
            for video in soup.find_all('video', src=True):
                src = video.get('src', '')
                if src and not src.startswith('http'):
                    src = urljoin(url, src)
                if src and src.startswith('http'):
                    videos.append(src)
            
            # Check iframes for YouTube/Vimeo
            for iframe in soup.find_all('iframe', src=True):
                src = iframe['src']
                if 'youtube.com' in src or 'vimeo.com' in src:
                    videos.append(src)
            
            return {
                "has_text": len(text) > 50,
                "has_media": len(images) > 0 or len(videos) > 0,
                "text": text[:10000],
                "images": images[:20],
                "videos": videos[:10],
                "url": url
            }
            
        except Exception as e:
            logger.error(f"Error fetching URL {url}: {e}")
            return {
                "has_text": False,
                "has_media": False,
                "text": None,
                "images": [],
                "videos": [],
                "url": url
            }