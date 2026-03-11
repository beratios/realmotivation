# 🎬 RealMotivation — YouTube Shorts Automation

Auto-generates and uploads **3 motivational YouTube Shorts per day** using:
- **Claude AI** — Script writing & story selection
- **Pexels API** — Free stock video footage
- **Google TTS** — Natural English voiceover
- **MoviePy + FFmpeg** — 9:16 video compositing
- **YouTube Data API** — Automatic upload
- **GitHub Actions** — Daily scheduling (Toronto / ET time)

---

## 📅 Upload Schedule (Toronto / Eastern Time)

| Slot | Time ET | Time UTC |
|------|---------|----------|
| Video 1 | 8:00 AM | 1:00 PM |
| Video 2 | 6:00 PM | 11:00 PM |
| Video 3 | 8:00 PM | 1:00 AM next day |

---

## 🚀 Setup Guide

### 1. Clone & Push to GitHub
```bash
git clone https://github.com/YOUR_USERNAME/realmotivation
cd realmotivation
git add .
git commit -m "Initial setup"
git push origin main
```

### 2. Get API Keys

#### Pexels API (Free)
1. Go to https://www.pexels.com/api/
2. Sign up → Get API key instantly
3. Free tier: 200 requests/hour ✅

#### Anthropic API
1. Go to https://console.anthropic.com
2. Create API key
3. ~$0.01–0.05 per video generation

#### YouTube Data API + OAuth
1. Go to https://console.cloud.google.com
2. Create a new project → "RealMotivation"
3. Enable **YouTube Data API v3**
4. Create **OAuth 2.0 credentials** (Desktop app type)
5. Download client_secret.json
6. Run the auth helper:
```bash
pip install google-auth-oauthlib
python scripts/setup_youtube_auth.py
```
7. Copy the refresh token it gives you

### 3. Add GitHub Secrets
Go to your repo → Settings → Secrets and variables → Actions

Add these secrets:
```
PEXELS_API_KEY         = your_pexels_key
ANTHROPIC_API_KEY      = sk-ant-...
YOUTUBE_CLIENT_ID      = your_client_id.apps.googleusercontent.com
YOUTUBE_CLIENT_SECRET  = your_client_secret
YOUTUBE_REFRESH_TOKEN  = 1//0e... (from step 2)
```

### 4. Enable GitHub Actions
- Go to your repo → Actions tab
- Click "Enable Actions" if prompted
- The workflow will run automatically on schedule

### 5. Test Manually
Go to Actions → "Daily YouTube Shorts Generator" → "Run workflow"

---

## 📁 Project Structure
```
realmotivation/
├── .github/
│   └── workflows/
│       └── daily_shorts.yml     # GitHub Actions schedule
├── content/
│   └── stories.json             # 50+ story bank (expandable to 500+)
├── scripts/
│   ├── generate_video.py        # Main pipeline
│   ├── generate_single.py       # Single slot runner
│   └── setup_youtube_auth.py   # One-time OAuth setup
├── requirements.txt
└── README.md
```

---

## 🎥 Content Types

| Type | Description |
|------|-------------|
| `founder_story` | Zuckerberg, Musk, Bezos origin stories |
| `motivation_quote` | Compound effect, 1% rule, discipline |
| `historical` | Lincoln, Gandhi, Einstein, Marie Curie |
| `rules_of_success` | Pareto, 10,000 hours, 5AM club |

---

## ➕ Adding More Stories
Edit `content/stories.json` and add entries following this format:
```json
{
  "id": 51,
  "type": "founder_story",
  "title": "Your Story Title",
  "hook": "Shocking opening line",
  "story": "The narrative (2-4 sentences)",
  "lesson": "The takeaway",
  "quote": "Famous quote related to theme",
  "tags": ["tag1", "tag2"],
  "pexels_query": "search terms for background video"
}
```

---

## 💰 Cost Estimate (per month)
| Service | Cost |
|---------|------|
| Pexels API | Free |
| Google TTS | Free (1M chars/month) |
| Claude AI (~90 scripts) | ~$2–5 |
| GitHub Actions | Free |
| **Total** | **~$2–5/month** |
