#!/usr/bin/env python3
"""
Generate a single YouTube Short for a given slot (1, 2, or 3).
Uses a shared state file to track which stories have been used.
"""

import argparse
import json
import random
import sys
import logging
from pathlib import Path
from generate_video import load_stories, process_story

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

STATE_FILE = Path("/tmp/realmotivation/state.json")
STATE_FILE.parent.mkdir(exist_ok=True)

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"used_ids": [], "today_slots": {}}

def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))

def pick_story_for_slot(slot: int, state: dict) -> dict:
    """Pick a story not used today or recently."""
    stories = load_stories()
    used = set(state.get("used_ids", []))
    today_slots = state.get("today_slots", {})
    
    # Already picked for this slot today?
    slot_key = str(slot)
    if slot_key in today_slots:
        story_id = today_slots[slot_key]
        matches = [s for s in stories if s["id"] == story_id]
        if matches:
            return matches[0]
    
    # Pick a new one
    available = [s for s in stories if s["id"] not in used]
    if not available:
        logger.warning("All stories used — resetting pool")
        available = stories
        state["used_ids"] = []
    
    story = random.choice(available)
    today_slots[slot_key] = story["id"]
    state["today_slots"] = today_slots
    state["used_ids"] = list(used) + [story["id"]]
    save_state(state)
    return story

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", type=int, default=1, choices=[1, 2, 3])
    args = parser.parse_args()
    
    logger.info(f"🎬 Generating video for slot {args.slot}")
    
    state = load_state()
    story = pick_story_for_slot(args.slot, state)
    
    logger.info(f"Selected story: #{story['id']} - {story['title']}")
    
    result = process_story(story)
    
    logger.info(f"✅ Done! YouTube ID: {result['youtube_id']}")
    logger.info(f"   https://youtube.com/shorts/{result['youtube_id']}")

if __name__ == "__main__":
    main()
