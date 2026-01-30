// TrustGuard AI - Content Script (Green Theme)
// Integrated with TrustGuard Dashboard Flask Backend
(function() {
  'use strict';

  if (window.__trustguardLoaded) return;
  window.__trustguardLoaded = true;

  const API = 'http://localhost:5001';
  const DASHBOARD_URL = 'http://localhost:8080';
  let currentBtn = null;
  let currentPanel = null;
  let selectedText = '';
  let lastMousePos = { x: 0, y: 0 };

  // Inject styles with green theme
  const style = document.createElement('style');
  style.id = 'trustguard-styles';
  style.textContent = `
    @keyframes tg-spin { to { transform: rotate(360deg); } }
    @keyframes tg-fade { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }
    
    #tg-btn {
      position: absolute !important;
      z-index: 2147483647 !important;
      display: inline-flex !important;
      align-items: center !important;
      gap: 8px !important;
      padding: 10px 18px !important;
      background: #00d26a !important;
      color: #000000 !important;
      border: none !important;
      border-radius: 8px !important;
      font-size: 13px !important;
      font-weight: 600 !important;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
      cursor: pointer !important;
      box-shadow: 0 4px 20px rgba(0, 210, 106, 0.4) !important;
      animation: tg-fade 0.2s ease !important;
      user-select: none !important;
    }
    
    #tg-btn:hover {
      background: #00ff88 !important;
      transform: translateY(-2px) !important;
      box-shadow: 0 6px 25px rgba(0, 210, 106, 0.5) !important;
    }
    
    #tg-btn * { pointer-events: none !important; }
    
    #tg-panel {
      position: fixed !important;
      z-index: 2147483647 !important;
      background: #0a0a0a !important;
      border-radius: 16px !important;
      box-shadow: 0 20px 60px rgba(0,0,0,0.5) !important;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
      overflow: hidden !important;
      animation: tg-fade 0.25s ease !important;
      border: 1px solid #2a2a2a !important;
    }
  `;
  document.head.appendChild(style);

  // Track mouse position
  document.addEventListener('mousemove', (e) => {
    lastMousePos = { x: e.pageX, y: e.pageY };
  }, true);

  // Selection handler
  function handleSelection() {
    removeBtn();
    
    const selection = window.getSelection();
    let text = selection.toString().trim();
    
    if (!text) {
      const active = document.activeElement;
      if (active && (active.tagName === 'TEXTAREA' || active.tagName === 'INPUT')) {
        text = active.value.substring(active.selectionStart, active.selectionEnd).trim();
      }
    }
    
    if (text.length >= 30) {
      selectedText = text.substring(0, 10000);
      
      let pos = { x: lastMousePos.x, y: lastMousePos.y + 10 };
      
      try {
        if (selection.rangeCount > 0) {
          const range = selection.getRangeAt(0);
          const rect = range.getBoundingClientRect();
          if (rect.width > 0) {
            pos = { x: rect.left + window.scrollX, y: rect.bottom + window.scrollY + 8 };
          }
        }
      } catch (e) {}
      
      createBtn(pos.x, pos.y);
    }
  }

  let debounceTimer = null;
  document.addEventListener('mouseup', (e) => {
    if (e.target.closest('#tg-btn, #tg-panel')) return;
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(handleSelection, 100);
  }, true);

  document.addEventListener('click', (e) => {
    const btn = e.target.closest('#tg-btn');
    if (btn) {
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();
      analyzeText();
      return false;
    }
    if (!e.target.closest('#tg-panel')) {
      removeBtn();
    }
  }, true);

  document.addEventListener('mousedown', (e) => {
    const btn = e.target.closest('#tg-btn');
    if (btn) {
      e.preventDefault();
      e.stopPropagation();
    }
  }, true);

  function removeBtn() {
    if (currentBtn && currentBtn.parentNode) {
      currentBtn.parentNode.removeChild(currentBtn);
    }
    currentBtn = null;
  }

  function removePanel() {
    if (currentPanel && currentPanel.parentNode) {
      currentPanel.parentNode.removeChild(currentPanel);
    }
    currentPanel = null;
  }

  function createBtn(x, y) {
    removeBtn();
    
    currentBtn = document.createElement('div');
    currentBtn.id = 'tg-btn';
    currentBtn.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
        <path d="M9 12l2 2 4-4"/>
      </svg>
      <span>Check Trust</span>
    `;
    
    const maxX = window.innerWidth - 140;
    currentBtn.style.left = Math.max(10, Math.min(x, maxX)) + 'px';
    currentBtn.style.top = y + 'px';
    
    document.body.appendChild(currentBtn);
    setTimeout(() => { if (currentBtn) removeBtn(); }, 12000);
  }

  async function analyzeText() {
    if (!selectedText || !currentBtn) return;
    
    const btnX = parseInt(currentBtn.style.left);
    const btnY = parseInt(currentBtn.style.top);
    
    currentBtn.innerHTML = `
      <div style="width:14px;height:14px;border:2px solid rgba(0,0,0,0.2);border-top-color:#000;border-radius:50%;animation:tg-spin 0.6s linear infinite;"></div>
      <span>Analyzing...</span>
    `;
    currentBtn.style.pointerEvents = 'none';
    
    try {
      const response = await fetch(`${API}/api/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content_type: 'text', text: selectedText })
      });
      
      if (!response.ok) throw new Error(`Server error: ${response.status}`);
      
      const result = await response.json();
      removeBtn();
      showPanel(result, btnX, btnY);
    } catch (err) {
      console.error('TrustGuard:', err);
      removeBtn();
      showError(err.message, btnX, btnY);
    }
  }

  function showPanel(result, x, y) {
    removePanel();
    
    const score = result.overall_score || 0;
    const verdict = result.verdict || 'UNKNOWN';
    const aiDetected = result.ai_content_detected;
    const findings = result.findings || [];
    const reportId = result.report_id || null;
    
    // Green theme colors based on score
    let scoreColor, scoreBgColor, ringColor;
    if (score >= 70) {
      scoreColor = '#00d26a';
      scoreBgColor = 'rgba(0, 210, 106, 0.1)';
      ringColor = '#00d26a';
    } else if (score >= 40) {
      scoreColor = '#ffa502';
      scoreBgColor = 'rgba(255, 165, 2, 0.1)';
      ringColor = '#ffa502';
    } else {
      scoreColor = '#ff4757';
      scoreBgColor = 'rgba(255, 71, 87, 0.1)';
      ringColor = '#ff4757';
    }

    const findingsHtml = findings.slice(0, 5).map(f => {
      const icons = { success: '✓', warning: '⚠', error: '✗', info: 'ℹ' };
      const colors = { success: '#00d26a', warning: '#ffa502', error: '#ff4757', info: '#6495ed' };
      const bgColors = { 
        success: 'rgba(0, 210, 106, 0.1)', 
        warning: 'rgba(255, 165, 2, 0.1)', 
        error: 'rgba(255, 71, 87, 0.1)', 
        info: 'rgba(100, 149, 237, 0.1)' 
      };
      return `<div style="display:flex;align-items:flex-start;gap:10px;padding:10px 12px;background:${bgColors[f.type] || bgColors.info};border-radius:8px;color:${colors[f.type] || colors.info};font-size:12px;margin-bottom:8px;">
        <span style="font-weight:bold;">${icons[f.type] || 'ℹ'}</span>
        <span style="flex:1;line-height:1.4;">${f.message}</span>
      </div>`;
    }).join('');

    currentPanel = document.createElement('div');
    currentPanel.id = 'tg-panel';
    
    const panelWidth = 340;
    const panelX = Math.max(20, Math.min(x - window.scrollX, window.innerWidth - panelWidth - 20));
    const panelY = Math.max(20, Math.min(y - window.scrollY, window.innerHeight - 450));
    
    currentPanel.style.left = panelX + 'px';
    currentPanel.style.top = panelY + 'px';
    currentPanel.style.width = panelWidth + 'px';

    currentPanel.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;padding:16px 20px;background:#141414;border-bottom:1px solid #2a2a2a;">
        <div style="display:flex;align-items:center;gap:10px;">
          <svg width="24" height="24" viewBox="0 0 40 40" fill="none">
            <path d="M20 4L34 10V20C34 28 20 36 20 36S6 28 6 20V10L20 4Z" fill="#00d26a"/>
            <path d="M14 20L18 24L26 16" stroke="#000" stroke-width="2.5" stroke-linecap="round" fill="none"/>
          </svg>
          <span style="font-weight:600;font-size:15px;color:#fff;">TrustGuard</span>
        </div>
        <button id="tg-close" style="background:none;border:none;color:#666;font-size:24px;cursor:pointer;line-height:1;padding:0;">&times;</button>
      </div>
      
      <div style="padding:24px;text-align:center;">
        <div style="display:inline-block;background:${scoreBgColor};padding:20px 32px;border-radius:16px;margin-bottom:16px;border:1px solid ${scoreColor}22;">
          <div style="font-size:52px;font-weight:700;color:${scoreColor};line-height:1;">${score}</div>
          <div style="font-size:11px;color:#666;text-transform:uppercase;margin-top:6px;letter-spacing:1px;">Trust Score</div>
        </div>
        
        <div style="font-size:14px;font-weight:700;color:${scoreColor};margin-bottom:16px;text-transform:uppercase;letter-spacing:0.5px;">${verdict}</div>
        
        ${aiDetected ? `
          <div style="display:flex;align-items:center;justify-content:center;gap:8px;background:rgba(255,165,2,0.1);color:#ffa502;padding:12px 16px;border-radius:10px;font-size:13px;font-weight:600;margin-bottom:16px;border:1px solid rgba(255,165,2,0.2);">
            <span>🤖</span>
            <span>AI-generated content detected</span>
          </div>
        ` : ''}
        
        ${findings.length > 0 ? `
          <div style="text-align:left;border-top:1px solid #2a2a2a;padding-top:16px;margin-top:8px;">
            <div style="font-size:11px;font-weight:600;color:#666;margin-bottom:12px;text-transform:uppercase;letter-spacing:0.5px;">Key Findings</div>
            ${findingsHtml}
          </div>
        ` : ''}
        
        ${reportId ? `
          <div style="margin-top:16px;padding-top:16px;border-top:1px solid #2a2a2a;">
            <a href="${DASHBOARD_URL}/report.html?id=${reportId}" target="_blank" id="tg-view-report" style="display:inline-flex;align-items:center;gap:8px;padding:12px 20px;background:#00d26a;color:#000;font-weight:600;font-size:13px;text-decoration:none;border-radius:8px;cursor:pointer;">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                <polyline points="15 3 21 3 21 9"/>
                <line x1="10" y1="14" x2="21" y2="3"/>
              </svg>
              <span>View Full Report</span>
            </a>
          </div>
        ` : ''}
      </div>
    `;

    document.body.appendChild(currentPanel);
    
    const closeBtn = currentPanel.querySelector('#tg-close');
    if (closeBtn) {
      closeBtn.onclick = (e) => { e.stopPropagation(); removePanel(); };
      closeBtn.onmouseenter = () => { closeBtn.style.color = '#fff'; };
      closeBtn.onmouseleave = () => { closeBtn.style.color = '#666'; };
    }
    
    setTimeout(removePanel, 60000);
  }

  function showError(message, x, y) {
    removePanel();
    
    currentPanel = document.createElement('div');
    currentPanel.id = 'tg-panel';
    
    currentPanel.style.left = Math.max(20, Math.min(x, window.innerWidth - 300)) + 'px';
    currentPanel.style.top = Math.max(20, y - window.scrollY) + 'px';
    currentPanel.style.width = '300px';

    currentPanel.innerHTML = `
      <div style="padding:16px 20px;background:#1a0a0a;border-bottom:1px solid #3a2020;display:flex;justify-content:space-between;align-items:center;">
        <span style="font-weight:600;color:#ff4757;">⚠️ Connection Error</span>
        <button id="tg-close" style="background:none;border:none;color:#666;font-size:20px;cursor:pointer;">&times;</button>
      </div>
      <div style="padding:20px;text-align:center;background:#0a0a0a;">
        <div style="font-size:13px;color:#888;margin-bottom:14px;">${message}</div>
        <div style="font-size:12px;color:#666;background:#141414;padding:12px;border-radius:8px;border:1px solid #2a2a2a;">
          Start the backend server:<br>
          <code style="color:#00d26a;font-weight:600;">python main.py</code>
        </div>
      </div>
    `;

    document.body.appendChild(currentPanel);
    const closeBtn = currentPanel.querySelector('#tg-close');
    if (closeBtn) closeBtn.onclick = removePanel;
    setTimeout(removePanel, 8000);
  }

  console.log('✅ TrustGuard AI loaded on:', window.location.hostname);
})();