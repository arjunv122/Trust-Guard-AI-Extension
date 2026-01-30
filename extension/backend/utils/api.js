// API configuration
const API_BASE_URL = 'http://localhost:8000/api';

// Analyze content
export async function analyzeContent(content) {
  try {
    const response = await fetch(`${API_BASE_URL}/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        content,
        pillars: ['information', 'media', 'bias']
      })
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('API call failed:', error);
    throw error;
  }
}

// Get analysis history
export async function getHistory() {
  try {
    const response = await fetch(`${API_BASE_URL}/history`);
    return await response.json();
  } catch (error) {
    console.error('Failed to fetch history:', error);
    throw error;
  }
}

// Save analysis
export async function saveAnalysis(analysis) {
  try {
    await chrome.storage.local.get(['analysisHistory'], (result) => {
      const history = result.analysisHistory || [];
      history.unshift({
        ...analysis,
        timestamp: Date.now()
      });
      
      // Keep only last 50 analyses
      if (history.length > 50) {
        history.pop();
      }
      
      chrome.storage.local.set({ analysisHistory: history });
    });
  } catch (error) {
    console.error('Failed to save analysis:', error);
  }
}