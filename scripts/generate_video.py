#!/usr/bin/env python3
"""
RealMotivation - YouTube Shorts Auto Generator
Generates 3 motivational short videos per day using:
- Claude AI for script selection/generation
- Pexels for stock video footage
- Google TTS for narration
- Whisper (OpenAI) for word-level subtitle timing
- MoviePy for video editing
- YouTube API for upload
"""

import os
import json
import random
import requests
import subprocess
import tempfile
import time
import logging
import textwrap
from datetime import datetime
from pathlib import Path
from gtts import gTTS
from moviepy.editor import (
    VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip,
    concatenate_videoclips, ColorClip
)
from moviepy.video.fx.all import resize
import anthropic
import whisper

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ─── CONFIG ────────────────────────────────────────────────────────────────────
PEXELS_API_KEY      = os.environ["PEXELS_API_KEY"]
YOUTUBE_CLIENT_ID   = os.environ["YOUTUBE_CLIENT_ID"]
YOUTUBE_CLIENT_SECRET = os.environ["YOUTUBE_CLIENT_SECRET"]
YOUTUBE_REFRESH_TOKEN = os.environ["YOUTUBE_REFRESH_TOKEN"]
ANTHROPIC_API_KEY   = os.environ["ANTHROPIC_API_KEY"]

STORIES_FILE        = Path(__file__).parent.parent / "content" / "stories.json"
OUTPUT_DIR          = Path("/tmp/realmotivation")
OUTPUT_DIR.mkdir(exist_ok=True)

SHORT_WIDTH         = 1080
SHORT_HEIGHT        = 1920
FPS                 = 30
MAX_DURATION        = 58   # seconds (YouTube Shorts limit is 60)
MIN_DURATION        = 30

FONT_PATH           = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
TITLE_FONT_SIZE     = 72
BODY_FONT_SIZE      = 52
QUOTE_FONT_SIZE     = 58

# Hashtags per content type
HASHTAG_MAP = {
    "founder_story":   "#success #entrepreneur #motivation #startup #mindset #shorts",
    "motivation_quote": "#motivation #mindset #success #inspiration #shorts #quotes",
    "historical":      "#history #success #motivation #inspire #legend #shorts",
    "rules_of_success": "#success #rules #mindset #hustle #growth #shorts",
}

# ─── STORY LOADER ──────────────────────────────────────────────────────────────
def load_stories():
    with open(STORIES_FILE) as f:
        return json.load(f)

def pick_stories(n=3, used_ids=None):
    """Pick n unique stories not recently used."""
    stories = load_stories()
    used_ids = used_ids or []
    available = [s for s in stories if s["id"] not in used_ids]
    if len(available) < n:
        available = stories  # reset if exhausted
    return random.sample(available, n)

# ─── SCRIPT GENERATOR (Claude AI) ──────────────────────────────────────────────
def generate_script(story: dict) -> dict:
    """Use Claude to generate an engaging YouTube Shorts script from a story."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    prompt = f"""You are a viral YouTube Shorts scriptwriter specializing in motivation and success stories.

Story data:
{json.dumps(story, indent=2)}

Write a YouTube Shorts script (max 55 seconds when spoken at normal pace ~150 words/min, so max 130 words).

Return ONLY a JSON object with these keys:
{{
  "hook": "First 3 seconds - shocking/intriguing one-liner to stop scrolling",
  "narration": "The full voiceover script (max 130 words, punchy, emotional)",
  "on_screen_texts": ["line 1", "line 2", "line 3", "line 4", "line 5"],
  "title": "YouTube video title (max 60 chars, include emoji)",
  "description": "YouTube description (2-3 sentences + hashtags)",
  "end_card_text": "Powerful final 3-word phrase shown at end"
}}

Rules:
- Hook must be shocking or counterintuitive
- Use short punchy sentences
- Build emotion through the narration
- On-screen texts appear one by one over the video
- End with the quote from the story
- Description must end with relevant hashtags"""

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    raw = message.content[0].text.strip()
    # Clean JSON if wrapped in backticks
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    
    return json.loads(raw.strip())

# ─── PEXELS VIDEO FETCHER ───────────────────────────────────────────────────────
def fetch_pexels_video(query: str, min_duration: int = 15, max_duration: int = 60) -> str:
    """Fetch and download a vertical video from Pexels."""
    headers = {"Authorization": PEXELS_API_KEY}
    
    # Try portrait orientation first
    for orientation in ["portrait", "landscape"]:
        params = {
            "query": query,
            "orientation": orientation,
            "size": "medium",
            "per_page": 15,
        }
        resp = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        
        videos = data.get("videos", [])
        for video in videos:
            if min_duration <= video["duration"] <= max_duration:
                # Find best quality file
                files = sorted(video["video_files"], key=lambda x: x.get("width", 0), reverse=True)
                for vf in files:
                    if vf.get("width") and vf["width"] >= 720:
                        url = vf["link"]
                        out_path = OUTPUT_DIR / f"pexels_{video['id']}.mp4"
                        if not out_path.exists():
                            logger.info(f"Downloading Pexels video: {url[:60]}...")
                            r = requests.get(url, stream=True, timeout=30)
                            with open(out_path, "wb") as f:
                                for chunk in r.iter_content(chunk_size=8192):
                                    f.write(chunk)
                        return str(out_path)
    
    raise RuntimeError(f"No suitable Pexels video found for query: {query}")

# ─── TTS GENERATOR ─────────────────────────────────────────────────────────────
def generate_tts(text: str, output_path: str) -> str:
    """Generate speech using Google TTS."""
    tts = gTTS(text=text, lang='en', slow=False, tld='com')
    tts.save(output_path)
    logger.info(f"TTS saved to {output_path}")
    return output_path

# ─── WHISPER SUBTITLE GENERATOR ────────────────────────────────────────────────
_whisper_model = None

def get_whisper_model():
    """Lazy-load Whisper model (loads once, reused across videos)."""
    global _whisper_model
    if _whisper_model is None:
        logger.info("Loading Whisper 'base' model...")
        _whisper_model = whisper.load_model("base")
    return _whisper_model

def transcribe_audio(audio_path: str) -> list:
    """
    Transcribe audio and return word-level timestamps.
    Returns list of: {"word": str, "start": float, "end": float}
    """
    logger.info("Transcribing audio with Whisper...")
    model = get_whisper_model()
    result = model.transcribe(
        audio_path,
        word_timestamps=True,
        language="en",
        fp16=False,
    )
    
    words = []
    for segment in result.get("segments", []):
        for w in segment.get("words", []):
            words.append({
                "word": w["word"].strip(),
                "start": w["start"],
                "end": w["end"],
            })
    
    logger.info(f"Transcribed {len(words)} words")
    return words

def group_words_into_chunks(words: list, max_words: int = 4) -> list:
    """
    Group individual words into subtitle chunks (3-4 words each).
    Returns list of: {"text": str, "start": float, "end": float}
    """
    chunks = []
    i = 0
    while i < len(words):
        chunk_words = words[i:i + max_words]
        chunk_text = " ".join(w["word"] for w in chunk_words).strip()
        chunks.append({
            "text": chunk_text.upper(),
            "start": chunk_words[0]["start"],
            "end": chunk_words[-1]["end"],
        })
        i += max_words
    return chunks

# ─── VIDEO COMPOSER ─────────────────────────────────────────────────────────────
def add_text_overlay(clip, text: str, y_pos: float, font_size: int = 52,
                     color: str = "white", stroke_color: str = "black",
                     stroke_width: int = 3, start: float = 0, duration: float = None):
    """Add text overlay to a clip."""
    duration = duration or clip.duration
    
    txt = TextClip(
        text,
        fontsize=font_size,
        color=color,
        font=FONT_PATH if Path(FONT_PATH).exists() else "DejaVu-Sans-Bold",
        stroke_color=stroke_color,
        stroke_width=stroke_width,
        method="caption",
        size=(SHORT_WIDTH - 100, None),
        align="center",
    ).set_start(start).set_duration(duration).set_position(("center", y_pos))
    
    return txt

def make_subtitle_clips(chunks: list, video_duration: float) -> list:
    """
    Create karaoke-style subtitle TextClips from Whisper chunks.
    Each chunk appears exactly when spoken, centered at bottom third.
    Active chunk = yellow highlight. Background = semi-transparent dark pill.
    """
    subtitle_clips = []
    font = FONT_PATH if Path(FONT_PATH).exists() else "DejaVu-Sans-Bold"
    
    # Subtitle zone: bottom third of screen
    SUBTITLE_Y = int(SHORT_HEIGHT * 0.72)
    SUBTITLE_FONT_SIZE = 68
    
    for chunk in chunks:
        start  = chunk["start"]
        dur    = max(chunk["end"] - chunk["start"], 0.15)
        text   = chunk["text"]
        
        # Skip empty chunks
        if not text.strip():
            continue
        
        # ── Dark background pill ──────────────────────────────────────────────
        # We approximate width by text length; MoviePy will clip properly
        bg = ColorClip(
            size=(SHORT_WIDTH - 60, 105),
            color=[0, 0, 0]
        ).set_opacity(0.55).set_start(start).set_duration(dur)
        bg = bg.set_position(("center", SUBTITLE_Y - 10))
        subtitle_clips.append(bg)
        
        # ── Active subtitle word (yellow, bold) ───────────────────────────────
        txt_clip = TextClip(
            text,
            fontsize=SUBTITLE_FONT_SIZE,
            color="yellow",
            font=font,
            stroke_color="black",
            stroke_width=3,
            method="caption",
            size=(SHORT_WIDTH - 80, None),
            align="center",
        ).set_start(start).set_duration(dur).set_position(("center", SUBTITLE_Y))
        
        subtitle_clips.append(txt_clip)
    
    return subtitle_clips

def compose_short(story: dict, script: dict, video_path: str, audio_path: str) -> str:
    """Compose the final YouTube Short video with live karaoke-style subtitles."""
    logger.info("Composing video...")
    
    # ── 1. Transcribe audio → word timestamps ─────────────────────────────────
    words  = transcribe_audio(audio_path)
    chunks = group_words_into_chunks(words, max_words=4)
    
    # ── 2. Load audio ─────────────────────────────────────────────────────────
    audio = AudioFileClip(audio_path)
    target_duration = min(audio.duration + 2, MAX_DURATION)
    
    # ── 3. Load & crop video to 9:16 ──────────────────────────────────────────
    raw_clip = VideoFileClip(video_path)
    
    if raw_clip.duration < target_duration:
        loops = int(target_duration / raw_clip.duration) + 1
        raw_clip = concatenate_videoclips([raw_clip] * loops)
    
    video_clip = raw_clip.subclip(0, target_duration)
    
    vid_w, vid_h = video_clip.size
    target_ratio = SHORT_WIDTH / SHORT_HEIGHT
    current_ratio = vid_w / vid_h
    
    if current_ratio > target_ratio:
        new_w = int(vid_h * target_ratio)
        x_center = vid_w // 2
        video_clip = video_clip.crop(x1=x_center - new_w//2, x2=x_center + new_w//2)
    else:
        new_h = int(vid_w / target_ratio)
        y_center = vid_h // 2
        video_clip = video_clip.crop(y1=y_center - new_h//2, y2=y_center + new_h//2)
    
    video_clip = video_clip.resize((SHORT_WIDTH, SHORT_HEIGHT))
    
    # ── 4. Dark overlay ───────────────────────────────────────────────────────
    dark_overlay = ColorClip(
        size=(SHORT_WIDTH, SHORT_HEIGHT),
        color=[0, 0, 0]
    ).set_opacity(0.40).set_duration(target_duration)
    
    layers = [video_clip, dark_overlay]
    
    # ── 5. Hook text (first 3.5 sec, top, yellow) ─────────────────────────────
    hook_txt = add_text_overlay(
        video_clip, script["hook"].upper(),
        y_pos=180, font_size=TITLE_FONT_SIZE,
        color="yellow", start=0, duration=3.5
    )
    layers.append(hook_txt)
    
    # ── 6. LIVE SUBTITLES (Whisper word timestamps, karaoke style) ────────────
    subtitle_clips = make_subtitle_clips(chunks, target_duration)
    layers.extend(subtitle_clips)
    
    # ── 7. End card (last 2 seconds) ──────────────────────────────────────────
    end_start = audio.duration - 0.3
    end_dur   = target_duration - end_start

    if end_dur > 0.5:
        # Final quote
        quote_clip = add_text_overlay(
            video_clip,
            f'"{story["quote"]}"',
            y_pos=int(SHORT_HEIGHT * 0.38),
            font_size=QUOTE_FONT_SIZE,
            color="yellow",
            start=end_start, duration=end_dur
        )
        layers.append(quote_clip)

        # Follow CTA
        cta = add_text_overlay(
            video_clip,
            script.get("end_card_text", "FOLLOW FOR MORE 🔥"),
            y_pos=int(SHORT_HEIGHT * 0.88),
            font_size=56,
            color="white",
            start=end_start, duration=end_dur
        )
        layers.append(cta)
    
    # ── 8. Watermark (always visible, top-right) ───────────────────────────────
    watermark = add_text_overlay(
        video_clip, "@RealMotivation",
        y_pos=70, font_size=36,
        color="white", stroke_width=2,
        start=0, duration=target_duration
    )
    layers.append(watermark)
    
    # ── 9. Compose & export ───────────────────────────────────────────────────
    final = CompositeVideoClip(layers, size=(SHORT_WIDTH, SHORT_HEIGHT))
    final = final.set_audio(audio.set_duration(target_duration))
    
    output_path = str(OUTPUT_DIR / f"short_{story['id']}_{int(time.time())}.mp4")
    
    final.write_videofile(
        output_path,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="fast",
        threads=4,
        logger=None
    )
    
    logger.info(f"Video saved: {output_path}")
    return output_path

# ─── YOUTUBE UPLOADER ───────────────────────────────────────────────────────────
def get_youtube_access_token() -> str:
    """Exchange refresh token for access token."""
    resp = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": YOUTUBE_CLIENT_ID,
        "client_secret": YOUTUBE_CLIENT_SECRET,
        "refresh_token": YOUTUBE_REFRESH_TOKEN,
        "grant_type": "refresh_token",
    })
    resp.raise_for_status()
    return resp.json()["access_token"]

def upload_to_youtube(video_path: str, title: str, description: str, tags: list) -> str:
    """Upload video to YouTube as a Short."""
    access_token = get_youtube_access_token()
    
    # Step 1: Initialize upload
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Upload-Content-Type": "video/mp4",
        "X-Upload-Content-Length": str(os.path.getsize(video_path)),
    }
    
    metadata = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags[:20],
            "categoryId": "26",  # Howto & Style
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        }
    }
    
    init_resp = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos"
        "?uploadType=resumable&part=snippet,status",
        headers=headers,
        json=metadata
    )
    init_resp.raise_for_status()
    upload_url = init_resp.headers["Location"]
    
    # Step 2: Upload the file
    with open(video_path, "rb") as f:
        upload_resp = requests.put(
            upload_url,
            data=f,
            headers={"Content-Type": "video/mp4"}
        )
    upload_resp.raise_for_status()
    
    video_id = upload_resp.json().get("id", "unknown")
    logger.info(f"Uploaded to YouTube: https://youtube.com/shorts/{video_id}")
    return video_id

# ─── MAIN PIPELINE ─────────────────────────────────────────────────────────────
def process_story(story: dict) -> dict:
    """Full pipeline for one story → YouTube Short."""
    logger.info(f"Processing story #{story['id']}: {story['title']}")
    
    # 1. Generate script with Claude
    logger.info("Generating script with Claude...")
    script = generate_script(story)
    
    # 2. Generate TTS audio
    audio_path = str(OUTPUT_DIR / f"audio_{story['id']}.mp3")
    generate_tts(script["narration"], audio_path)
    
    # 3. Fetch Pexels video
    logger.info(f"Fetching Pexels video for: {story['pexels_query']}")
    video_path = fetch_pexels_video(story["pexels_query"])
    
    # 4. Compose video
    final_video_path = compose_short(story, script, video_path, audio_path)
    
    # 5. Upload to YouTube
    hashtags = HASHTAG_MAP.get(story["type"], "#motivation #success #shorts")
    description = script["description"] + f"\n\n{hashtags}"
    
    video_id = upload_to_youtube(
        final_video_path,
        title=script["title"],
        description=description,
        tags=story.get("tags", []) + ["motivation", "success", "shorts", "inspire"]
    )
    
    return {
        "story_id": story["id"],
        "title": script["title"],
        "youtube_id": video_id,
        "video_path": final_video_path,
        "timestamp": datetime.utcnow().isoformat(),
    }

def run_daily_batch():
    """Generate and upload 3 shorts for today."""
    logger.info("=" * 60)
    logger.info("RealMotivation Daily Batch Started")
    logger.info(f"Time: {datetime.utcnow().isoformat()}")
    logger.info("=" * 60)
    
    # Load used IDs to avoid repetition
    used_file = OUTPUT_DIR / "used_ids.json"
    used_ids = json.loads(used_file.read_text()) if used_file.exists() else []
    
    # Pick 3 stories
    stories = pick_stories(n=3, used_ids=used_ids)
    
    results = []
    for i, story in enumerate(stories):
        logger.info(f"\n{'─'*40}\nProcessing video {i+1}/3\n{'─'*40}")
        try:
            result = process_story(story)
            results.append(result)
            used_ids.append(story["id"])
            logger.info(f"✅ Video {i+1} done: {result['title']}")
        except Exception as e:
            logger.error(f"❌ Video {i+1} failed: {e}", exc_info=True)
    
    # Save used IDs
    used_file.write_text(json.dumps(used_ids[-300:]))  # keep last 300
    
    # Save daily log
    log_file = OUTPUT_DIR / f"log_{datetime.utcnow().strftime('%Y%m%d')}.json"
    log_file.write_text(json.dumps(results, indent=2))
    
    logger.info(f"\n{'='*60}\nBatch complete. {len(results)}/3 videos uploaded.\n{'='*60}")
    return results

if __name__ == "__main__":
    run_daily_batch()
