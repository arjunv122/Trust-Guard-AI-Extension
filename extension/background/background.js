// TrustGuard Background Script
// Integrated with TrustGuard Dashboard Flask Backend
const API_URL = 'http://localhost:5001';
const DASHBOARD_URL = 'http://localhost:8080';

// Create context menu on install
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'trustguard-check',
    title: '🛡️ Check Trust with TrustGuard AI',
    contexts: ['selection']
  });
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === 'trustguard-check' && info.selectionText) {
    // Analyze directly from background
    analyzeText(info.selectionText, tab.id);
  }
});

// Listen for messages from content script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'analyze') {
    // Make API call from background script (bypasses content blockers)
    analyzeFromBackground(request.text)
      .then(result => sendResponse({ success: true, data: result }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    
    return true; // Keep channel open for async response
  }
  
  if (request.action === 'checkAPI') {
    fetch(`${API_URL}/`)
      .then(r => r.ok ? sendResponse({ online: true }) : sendResponse({ online: false }))
      .catch(() => sendResponse({ online: false }));
    
    return true;
  }
});

async function analyzeFromBackground(text) {
  const response = await fetch(`${API_URL}/api/analyze`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      content_type: 'text',
      text: text
    })
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return await response.json();
}

async function analyzeText(text, tabId) {
  try {
    const result = await analyzeFromBackground(text);
    
    // Send result to content script to display
    chrome.tabs.sendMessage(tabId, {
      action: 'showResult',
      result: result
    });
  } catch (error) {
    chrome.tabs.sendMessage(tabId, {
      action: 'showError',
      error: error.message
    });
  }
}