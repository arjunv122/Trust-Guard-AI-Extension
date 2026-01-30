// TrustGuard AI - Popup Script
// Integrated with TrustGuard Dashboard Flask Backend
const API_URL = 'http://localhost:5001';
const DASHBOARD_URL = 'http://localhost:8080';

// State
let currentAnalysis = null;
let suspiciousSegments = [];
let currentReportId = null;

// Initialize
document.addEventListener('DOMContentLoaded', init);

function init() {
  // Get DOM elements
  const btnAnalyze = document.getElementById('btn-analyze');
  const btnScanPage = document.getElementById('btn-scan-page');
  const btnNew = document.getElementById('btn-new');
  const btnHighlight = document.getElementById('btn-highlight');
  const btnViewReport = document.getElementById('btn-view-report');
  const inputText = document.getElementById('input-text');

  // Event listeners
  btnAnalyze.addEventListener('click', handleAnalyze);
  btnScanPage.addEventListener('click', handleScanPage);
  btnNew.addEventListener('click', resetToInitial);
  btnHighlight.addEventListener('click', handleHighlight);
  btnViewReport.addEventListener('click', handleViewReport);

  // Check for pending analysis
  chrome.storage.local.get(['pendingAnalysis', 'analysisType'], (data) => {
    if (data.pendingAnalysis) {
      inputText.value = data.pendingAnalysis;
      chrome.storage.local.remove(['pendingAnalysis', 'analysisType']);
      
      if (data.analysisType === 'image') {
        // Handle image analysis
        analyzeImages([data.pendingAnalysis]);
      } else {
        handleAnalyze();
      }
    }
  });
}

// Handle analyze button click
async function handleAnalyze() {
  const inputText = document.getElementById('input-text');
  const content = inputText.value.trim();

  if (!content) {
    alert('Please enter text or URL to analyze');
    return;
  }

  // Determine content type
  const isURL = /^https?:\/\/.+/i.test(content);
  const contentType = isURL ? 'url' : 'text';

  await runAnalysis({
    content_type: contentType,
    [contentType]: content
  });
}

// Handle scan page button
async function handleScanPage() {
  showState('loading');
  updateLoading('Extracting page content...');

  try {
    // Get current tab
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    // Execute content extraction
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        const url = window.location.href;
        const title = document.title;

        // Clone body and remove unwanted elements
        const bodyClone = document.body.cloneNode(true);
        const remove = bodyClone.querySelectorAll('script, style, noscript, iframe, nav, footer');
        remove.forEach(el => el.remove());

        const text = bodyClone.innerText.substring(0, 15000);

        // Get images
        const images = Array.from(document.querySelectorAll('img'))
          .filter(img => img.width > 50 && img.height > 50)
          .map(img => img.src)
          .filter(src => src && src.startsWith('http'))
          .slice(0, 20);

        // Get videos
        const videos = Array.from(document.querySelectorAll('video, iframe'))
          .map(el => el.src)
          .filter(src => src && src.startsWith('http'))
          .slice(0, 10);

        return { url, title, text, images, videos };
      }
    });

    const pageData = results[0].result;

    if (!pageData || (!pageData.text && pageData.images.length === 0)) {
      alert('Could not extract content from this page');
      resetToInitial();
      return;
    }

    await runAnalysis({
      content_type: 'page',
      page_data: pageData
    });

  } catch (error) {
    console.error('Scan error:', error);
    alert('Error scanning page: ' + error.message);
    resetToInitial();
  }
}

// Run analysis
async function runAnalysis(requestBody) {
  showState('loading');
  updateLoading('Connecting to server...');
  animateProgress(0);

  try {
    updateLoading('Analyzing content...');
    animateProgress(30);

    const response = await fetch(`${API_URL}/api/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody)
    });

    animateProgress(70);

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Server error: ${response.status}`);
    }

    const analysis = await response.json();
    console.log('Analysis result:', analysis);

    animateProgress(100);
    
    currentAnalysis = analysis;
    suspiciousSegments = analysis.suspicious_segments || [];

    setTimeout(() => displayResults(analysis), 300);

  } catch (error) {
    console.error('Analysis error:', error);
    alert('Analysis failed: ' + error.message);
    resetToInitial();
  }
}

// Analyze images separately
async function analyzeImages(imageUrls) {
  showState('loading');
  updateLoading('Analyzing images...');

  try {
    const response = await fetch(`${API_URL}/api/analyze-images`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_urls: imageUrls })
    });

    if (!response.ok) throw new Error('Image analysis failed');

    const result = await response.json();
    console.log('Image analysis:', result);

    // Convert to standard format
    const analysis = {
      overall_score: result.results.some(r => r.is_ai_generated) ? 40 : 85,
      verdict: result.results.some(r => r.is_ai_generated) ? 'LOW TRUST' : 'HIGH TRUST',
      confidence: 0.5,
      pillars: {
        information_trust: { score: null, applicable: false, reason: 'No text to analyze' },
        media_trust: {
          score: result.results.some(r => r.is_ai_generated) ? 30 : 90,
          applicable: true,
          details: {
            images: {
              total: imageUrls.length,
              analyzed: result.results.length,
              ai_generated_count: result.results.filter(r => r.is_ai_generated).length,
              results: result.results,
              message: result.results.some(r => r.is_ai_generated) 
                ? 'AI-generated image detected' 
                : 'Images appear authentic'
            },
            videos: { total: 0, analyzed: 0, results: [] }
          }
        }
      },
      applicable_pillars: ['media_trust'],
      findings: result.results.some(r => r.is_ai_generated)
        ? [{ type: 'error', pillar: 'media_trust', message: 'AI-generated image detected' }]
        : [{ type: 'success', pillar: 'media_trust', message: 'Images appear authentic' }],
      ai_content_detected: result.results.some(r => r.is_ai_generated)
    };

    currentAnalysis = analysis;
    displayResults(analysis);

  } catch (error) {
    console.error('Image analysis error:', error);
    alert('Image analysis failed: ' + error.message);
    resetToInitial();
  }
}

// Display results
function displayResults(analysis) {
  showState('results');

  const score = analysis.overall_score || 0;
  const applicable = analysis.applicable_pillars || [];

  // Store report ID for View Full Report button
  currentReportId = analysis.report_id || null;

  // Animate score
  animateScore(score);

  // Update verdict
  const verdictEl = document.getElementById('verdict');
  verdictEl.textContent = analysis.verdict;
  verdictEl.className = 'verdict ' + (score >= 70 ? 'high' : score >= 40 ? 'moderate' : 'low');

  // Show AI alert if detected
  const aiAlert = document.getElementById('ai-alert');
  if (analysis.ai_content_detected) {
    aiAlert.style.display = 'flex';
    document.getElementById('ai-alert-text').textContent = 'AI-generated content detected!';
  } else {
    aiAlert.style.display = 'none';
  }

  // Show analysis notice
  const notice = document.getElementById('analysis-notice');
  const noticeText = document.getElementById('notice-text');
  
  if (applicable.length === 1) {
    notice.style.display = 'block';
    const name = applicable[0] === 'information_trust' ? 'Text' : 'Media';
    noticeText.textContent = `Only ${name} analysis was applicable for this content`;
  } else if (applicable.length === 0) {
    notice.style.display = 'block';
    noticeText.textContent = 'No analyzable content found';
  } else {
    notice.style.display = 'none';
  }

  // Update Information Trust pillar
  updateInfoPillar(analysis.pillars, applicable);

  // Update Media Trust pillar
  updateMediaPillar(analysis.pillars, applicable);

  // Update findings
  updateFindings(analysis.findings);

  // Show highlight button if we have suspicious segments
  const btnHighlight = document.getElementById('btn-highlight');
  if (suspiciousSegments.length > 0) {
    btnHighlight.style.display = 'flex';
  } else {
    btnHighlight.style.display = 'none';
  }

  // Show View Full Report button if we have a report ID
  const btnViewReport = document.getElementById('btn-view-report');
  if (currentReportId) {
    btnViewReport.style.display = 'flex';
  } else {
    btnViewReport.style.display = 'none';
  }
}

// Update Information Trust pillar
function updateInfoPillar(pillars, applicable) {
  const card = document.getElementById('pillar-info');
  const scoreEl = document.getElementById('info-score');
  const detailsEl = document.getElementById('info-details');

  const isApplicable = applicable.includes('information_trust');
  const data = pillars?.information_trust;

  if (isApplicable && data?.score !== null) {
    card.classList.remove('not-applicable');
    scoreEl.textContent = `${data.score}/100`;
    scoreEl.classList.remove('na');

    const details = data.details || {};
    const aiDet = details.ai_detection || {};
    const fact = details.fact_check || {};
    const sources = details.sources || {};

    detailsEl.innerHTML = `
      <div class="detail-item">
        <span class="detail-icon">${aiDet.is_ai_generated ? '🤖' : '✓'}</span>
        <span class="detail-text">${aiDet.message || 'AI detection complete'}</span>
      </div>
      <div class="detail-item">
        <span class="detail-icon">${fact.status === 'verified' ? '✓' : '⚠️'}</span>
        <span class="detail-text">${fact.message || 'Fact check complete'}</span>
      </div>
      <div class="detail-item">
        <span class="detail-icon">🔗</span>
        <span class="detail-text">${sources.count || 0} source(s) - ${sources.credibility || 'unknown'} credibility</span>
      </div>
    `;
  } else {
    card.classList.add('not-applicable');
    scoreEl.textContent = 'N/A';
    scoreEl.classList.add('na');
    detailsEl.innerHTML = `
      <div class="na-message">
        <span>📄</span>
        <span>${data?.reason || 'No text content to analyze'}</span>
      </div>
    `;
  }
}

// Update Media Trust pillar
function updateMediaPillar(pillars, applicable) {
  const card = document.getElementById('pillar-media');
  const scoreEl = document.getElementById('media-score');
  const detailsEl = document.getElementById('media-details');

  const isApplicable = applicable.includes('media_trust');
  const data = pillars?.media_trust;

  if (isApplicable && data?.score !== null) {
    card.classList.remove('not-applicable');
    scoreEl.textContent = `${data.score}/100`;
    scoreEl.classList.remove('na');

    const details = data.details || {};
    const images = details.images || {};
    const videos = details.videos || {};

    const aiCount = images.ai_generated_count || 0;

    detailsEl.innerHTML = `
      <div class="detail-item">
        <span class="detail-icon">${aiCount > 0 ? '🤖' : '✓'}</span>
        <span class="detail-text">${images.message || `${images.analyzed || 0} image(s) analyzed`}</span>
      </div>
      <div class="detail-item">
        <span class="detail-icon">🎬</span>
        <span class="detail-text">${videos.message || `${videos.analyzed || 0} video(s) analyzed`}</span>
      </div>
    `;
  } else {
    card.classList.add('not-applicable');
    scoreEl.textContent = 'N/A';
    scoreEl.classList.add('na');
    detailsEl.innerHTML = `
      <div class="na-message">
        <span>🖼️</span>
        <span>${data?.reason || 'No images or videos to analyze'}</span>
      </div>
    `;
  }
}

// Update findings
function updateFindings(findings) {
  const section = document.getElementById('findings-section');
  const list = document.getElementById('findings-list');

  if (!findings || findings.length === 0) {
    section.style.display = 'none';
    return;
  }

  section.style.display = 'block';
  list.innerHTML = '';

  findings.forEach(finding => {
    const item = document.createElement('div');
    item.className = `finding-item ${finding.type || 'info'}`;

    const icons = { success: '✓', warning: '⚠️', error: '✗', info: 'ℹ️' };
    const icon = icons[finding.type] || 'ℹ️';

    item.innerHTML = `
      <span class="finding-icon">${icon}</span>
      <span>${finding.message}</span>
    `;

    list.appendChild(item);
  });
}

// Handle highlight button
async function handleHighlight() {
  if (suspiciousSegments.length === 0) return;

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    await chrome.tabs.sendMessage(tab.id, {
      action: 'highlight',
      segments: suspiciousSegments
    });

    // Visual feedback
    const btn = document.getElementById('btn-highlight');
    btn.textContent = '✓ Highlighted!';
    setTimeout(() => {
      btn.innerHTML = '<span>Highlight on Page</span>';
    }, 2000);

  } catch (error) {
    console.error('Highlight error:', error);
  }
}

// Animate score
function animateScore(targetScore) {
  const scoreEl = document.getElementById('score-value');
  const ring = document.getElementById('score-ring');

  const circumference = 283; // 2 * PI * 45
  const offset = circumference - (targetScore / 100) * circumference;

  // Color based on score
  const color = targetScore >= 70 ? '#4CAF50' : targetScore >= 40 ? '#FF9800' : '#F44336';
  ring.style.stroke = color;

  // Animate
  let current = 0;
  const increment = targetScore / 40;

  const interval = setInterval(() => {
    current += increment;
    if (current >= targetScore) {
      current = targetScore;
      clearInterval(interval);
    }

    scoreEl.textContent = Math.round(current);
    const currentOffset = circumference - (current / 100) * circumference;
    ring.style.strokeDashoffset = currentOffset;
  }, 25);
}

// Animate progress bar
function animateProgress(target) {
  const progress = document.getElementById('progress');
  progress.style.width = `${target}%`;
}

// Update loading message
function updateLoading(message) {
  document.getElementById('loading-text').textContent = message;
}

// Show state
function showState(state) {
  document.getElementById('initial-state').style.display = state === 'initial' ? 'block' : 'none';
  document.getElementById('loading-state').style.display = state === 'loading' ? 'block' : 'none';
  document.getElementById('results-state').style.display = state === 'results' ? 'block' : 'none';
}

// Reset to initial
function resetToInitial() {
  showState('initial');
  document.getElementById('input-text').value = '';
  document.getElementById('progress').style.width = '0%';
  currentAnalysis = null;
  suspiciousSegments = [];
  currentReportId = null;
}

// Handle View Full Report button click
function handleViewReport() {
  if (currentReportId) {
    // Open the dashboard report page with the report ID
    const reportUrl = `${DASHBOARD_URL}/report.html?id=${currentReportId}`;
    chrome.tabs.create({ url: reportUrl });
  } else if (currentAnalysis) {
    // If no report ID, open the general analysis page
    chrome.tabs.create({ url: `${DASHBOARD_URL}/analyze-text.html` });
  }
}