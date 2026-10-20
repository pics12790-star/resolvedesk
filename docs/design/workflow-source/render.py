"""Run the installed demo renderer with FFmpeg 9 and readable caption boxes."""
import importlib.util
from pathlib import Path
import subprocess

skill = Path.home() / ".codex/skills/web-product-demo-video/scripts/render_video.py"
spec = importlib.util.spec_from_file_location("demo_renderer", skill)
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)
original_ass = renderer.write_ass
original_run = subprocess.run

def caption_boxes(path, storyboard):
    result = original_ass(path, storyboard)
    if result:
        text = path.read_text(encoding="utf-8-sig")
        # BorderStyle 3 needs a nonzero outline to draw a readable box.
        path.write_text(text.replace(",3,0,0,2,40,40,", ",3,8,0,2,40,40,"), encoding="utf-8-sig")
    return result

def compatible_run(command, **kwargs):
    command = ["-/filter_complex" if arg == "-filter_complex_script" else arg for arg in command]
    return original_run(command, **kwargs)

renderer.write_ass = caption_boxes
subprocess.run = compatible_run
raise SystemExit(renderer.main())
