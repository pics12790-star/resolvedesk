"""Build the editing inputs from visually checked ranges of the real Luna recording."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def write(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

# Source times are video timestamps, not API latency measurements.
scenes = [
    ("inbox", 0, 6, "A damaged-order ticket, ready for investigation"),
    ("investigation", 22, 28.3, "Luna investigates the order and checks store evidence"),
    ("policies", 28.3, 41.5, "Inspect cited policies and the underlying order evidence"),
    ("approval", 41.5, 50.3, "Review the proposal. A person approves the replacement"),
    ("receipt", 56.8, 62.2, "The replacement is executed and its receipt verified"),
    ("audit", 62.2, 66.5, "Inspect the audit trail, model calls, and execution metrics"),
    ("evaluations", 67.5, 73.2, "Saved evaluations: 90 synthetic cases from an earlier run"),
    ("resolved", 74, 77.5, "Resolved with evidence, human approval, and a verified receipt"),
]
write("demo.config.json", {
    "version": 1, "project_name": "ResolveDesk live Luna workflow",
    "start_url": "http://127.0.0.1:8000",
    "video": {"width": 1600, "height": 1000, "fps": 60, "duration_limit": 65,
              "opening_hold_seconds": 1, "audio": False},
    "captions": {"enabled": True, "font_name": "Arial", "font_size": 32,
                 "bottom_margin": 16, "raised_margin": 150},
    "recording": {"output_video": "../workflow-luna.webm"},
    "editing": {"pre_roll_seconds": 0, "post_roll_seconds": 0, "default_transition": "cut"},
})
write("feature-inventory.json", {
    "version": 1,
    "service": {"name": "ResolveDesk", "audience": "Portfolio reviewers and interviewers",
                "video_goal": "Demonstrate a real Luna investigation through approved execution"},
    "features": [{"id": name, "order": i, "title": name.title(), "purpose": caption,
                  "caption": caption, "required": True, "priority": 100,
                  "estimated_seconds": round(end - start, 3),
                  "start_marker": name + "-start", "end_marker": name + "-end", "focus": None}
                 for i, (name, start, end, caption) in enumerate(scenes, 1)],
})
write("recording-markers.json", {
    "version": 1, "video": "../workflow-luna.webm", "timebase": "source-video-seconds",
    "markers": [{"name": name + suffix, "seconds": time}
                for name, start, end, _ in scenes
                for suffix, time in [("-start", start), ("-end", end)]],
})
write("recording-plan.json", {
    "version": 1, "recorder": "../record-workflow.cjs",
    "notes": "Custom recorder waits for actual API completion and validates the live model metrics and receipt.",
    "actions": [
        {"type": "goto", "url": "http://127.0.0.1:8000"},
        {"type": "wait_for", "selector": "button:has-text('Start investigation')"},
        {"type": "click", "selector": "button:has-text('Start investigation')"},
        {"type": "wait_for", "selector": "button:has-text('Approve replacement')", "timeout_ms": 120000},
        {"type": "click", "selector": ".policy-citations details:nth-child(1) summary"},
        {"type": "click", "selector": ".policy-citations details:nth-child(2) summary"},
        {"type": "click", "selector": ".timeline li:has-text('get order') summary"},
        {"type": "click", "selector": ".timeline li:has-text('get order') summary"},
        {"type": "click", "selector": "button:has-text('Approve replacement')"},
        {"type": "wait_for", "selector": ".receipt", "timeout_ms": 60000},
        {"type": "click", "selector": "nav button:has-text('Evaluations')"},
        {"type": "wait_for", "selector": ".eval-stats"},
        {"type": "click", "selector": "nav button:has-text('Inbox')"},
    ],
})

# A portable subtitle companion for platforms that support separate captions.
def srt_time(seconds):
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

cursor = 1.0
subtitles = []
for i, (_, start, end, caption) in enumerate(scenes, 1):
    duration = end - start
    subtitles.append(f"{i}\n{srt_time(cursor)} --> {srt_time(cursor + duration)}\n{caption}\n")
    cursor += duration
(ROOT / "captions.srt").write_text("\n".join(subtitles), encoding="utf-8")
print(f"Prepared {len(scenes)} verified scenes, {cursor:.1f} seconds")
