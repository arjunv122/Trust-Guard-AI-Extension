# TrustGuard AI 🛡️

AI-powered content verification platform for detecting hallucinations, deepfakes, and phishing URLs. TrustGuard AI provides both a web interface and browser extension for comprehensive content analysis.

## Features

- **🔍 Hallucination Detection** - Detect AI-generated misinformation using SelfCheckGPT
- **📹 Deepfake Detection** - Analyze images and videos for AI manipulation
- **🔗 URL Phishing Scanner** - Check URLs for phishing and malicious patterns
- **🧩 Browser Extension** - Quick analysis directly from any webpage
- **📊 Analysis Dashboard** - View detailed reports and analysis history
- **🔐 Trust Scoring** - Comprehensive trust assessment algorithm

---

## Project Structure

```
trustgaurd-ai/
├── backend/              # Flask/FastAPI backend server
│   ├── app.py           # Main application
│   ├── server.py        # Server configuration
│   ├── services/        # AI detection services
│   └── routes/          # API routes
├── extension/           # Browser extension
│   ├── popup/           # Extension popup UI
│   ├── content/         # Content script
│   ├── background/      # Background scripts
│   └── backend/         # Extension-specific backend
├── index.html           # Main dashboard
├── upload-file.html     # File upload interface
├── scan-url.html        # URL scanning interface
└── analyze-text.html    # Text analysis interface
```

## Quick Setup

### 1. Clone the Repository
```bash
git clone https://github.com/arjunv122/Trust-Guard-AI-Extension.git
cd trustgaurd-ai
```

### 2. Create Virtual Environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Mac/Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 4. Configure API Keys
Create a `.env` file in the `backend/` folder:
```env
GROQ_API_KEY=your-groq-api-key-here
HF_API_TOKEN=your-huggingface-token-here
```

Get your API keys:
- **Groq**: https://console.groq.com/keys
- **Hugging Face**: https://huggingface.co/settings/tokens

### 5. Start the Servers

**Terminal 1 - Backend Server:**
```bash
cd backend
python server.py
```
Backend runs on: http://localhost:5001

**Terminal 2 - Frontend Server:**
```bash
cd trustgaurd-ai
python -m http.server 8080
```
Frontend runs on: http://localhost:8080

---

## Windows Commands (Copy-Paste Ready)

```powershell
# Step 1: Clone and setup
git clone https://github.com/arjunv122/Trust-Guard-AI-Extension.git
cd trustgaurd-ai

# Step 2: Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Step 3: Install dependencies
cd backend
pip install -r requirements.txt

# Step 4: Create .env file (edit with your API keys)
echo "GROQ_API_KEY=your-key-here" > .env
echo "HF_API_TOKEN=your-hf-token-here" >> .env

# Step 5: Start backend (Terminal 1)
python server.py

# Step 6: Start frontend (NEW Terminal 2)
cd ..
python -m http.server 8080
```

---

## Usage

### Dashboard
Open http://localhost:8080 in your browser

| Feature | URL |
|---------|-----|
| Home | http://localhost:8080/index.html |
| Text Analysis | http://localhost:8080/analyze-text.html |
| Media Analysis | http://localhost:8080/analyze-media.html |
| URL Scanner | http://localhost:8080/scan-url.html |

### Browser Extension
1. Go to `chrome://extensions/` (or `edge://extensions/`)
2. Enable **Developer mode** (top right toggle)
3. Click **Load unpacked**
4. Select the `extension/` folder
5. Click the TrustGuard icon in toolbar to use

---

## Requirements

Key Python packages (see `backend/requirements.txt`):

```
flask==3.0.0
flask-cors==4.0.0
python-dotenv==1.0.0
transformers==4.36.0
torch==2.1.2
Pillow==10.1.0
requests==2.31.0
spacy==3.7.2
nltk==3.8.1
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/analyze` | POST | Text hallucination analysis |
| `/api/analyze/fact-verification` | POST | Fact checking |
| `/api/analyze/media` | POST | Deepfake detection |
| `/api/analyze/url` | POST | URL phishing scan |
| `/health` | GET | Server health check |

---

## Project Structure

```
trustgaurd-ai/
├── backend/
│   ├── server.py              # Flask API server
│   ├── media_analyzer.py      # Deepfake detection
│   ├── url_phishing_detector.py
│   ├── requirements.txt
│   └── .env                   # API keys (create this)
├── extension/
│   ├── manifest.json
│   ├── popup/
│   ├── background/
│   └── content/
├── index.html                 # Dashboard home
├── analyze-text.html          # Text analysis
├── analyze-media.html         # Media analysis
├── scan-url.html              # URL scanner
└── report.html                # Detailed report view
```

---

## Troubleshooting

**Server won't start?**
```bash
# Make sure venv is activated
.venv\Scripts\Activate.ps1
cd backend
python server.py
```

**Extension not connecting?**
- Check backend is running on port 5001
- Check for CORS errors in browser console

**Analysis failing?**
- Verify API keys are set in `backend/.env`
- Check terminal for error messages

---

## Technology Stack

**Backend:**
- Flask/FastAPI
- Python 3.8+
- Transformers (Hugging Face)
- PyTorch
- Groq API

**Frontend:**
- HTML5 / CSS3
- Vanilla JavaScript
- Responsive Design

**Browser Extension:**
- Manifest V3
- Content Scripts
- Background Service Workers
- Popup UI

---

## API Keys Required

Get your free API keys from:
1. **Groq API** - https://console.groq.com/keys (Fast LLM API)
2. **Hugging Face** - https://huggingface.co/settings/tokens (Model access)

---

## Features Details

### Hallucination Detection
Uses SelfCheckGPT to verify if AI-generated content contains factual inconsistencies.

### Deepfake Detection
Analyzes images and videos to detect signs of AI manipulation or synthetic media.

### URL Phishing Scanner
Checks URLs against phishing databases and analyzes malicious patterns.

### Trust Scoring Algorithm
Comprehensive scoring based on:
- Content consistency
- Source reputation
- Media authenticity
- URL safety patterns

---

## Contributing

Contributions are welcome! Please feel free to submit pull requests.

---

## License

MIT License

---

**Version**: 2.0  
**Repository**: https://github.com/arjunv122/Trust-Guard-AI-Extension  
**Last Updated**: April 28, 2026
