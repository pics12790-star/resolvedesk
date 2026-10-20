# ResolveDesk workflow recording

The [captioned MP4](../workflow-luna.mp4) shows a real `gpt-6-luna` run from damaged-item investigation to reviewer approval and verified replacement. The [original recording](../workflow-luna.webm) preserves the complete session, including model and tool waits. The public README uses a GIF preview because it renders inline on GitHub.

Recorded October 20, 2026 at 1600×1000. Final export: H.264, constant 60 fps, silent, about 54 seconds. The original browser capture is 25 fps. The model calls are live; the commerce store is simulated. The Evaluations page displays an earlier 90-case benchmark.

## Record again

Install the frontend dependencies first (`npm ci` from `apps/web`). The recorder uses that existing Playwright installation and installed Google Chrome.

From the repository root, start a fresh local store. The existing `.env` supplies the OpenAI key; credentials are never embedded in the recorder or video sources.

```powershell
$env:AGENT_MODE = 'luna'
$env:OPENAI_AGENT_MODEL = 'gpt-6-luna'
$env:DATABASE_URL = 'sqlite'
$env:RESOLVEDESK_RUNTIME = Join-Path (Get-Location) ('runtime/recording-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$env:QDRANT_URL = ''
$env:QDRANT_API_KEY = ''
$env:RAG_DISABLE_EMBEDDINGS = 'true'
$env:LANGSMITH_TRACING = 'false'
.venv/Scripts/python.exe -m uvicorn resolvedesk.api:app --host 127.0.0.1 --port 8000
```

In another terminal at the repository root:

```powershell
node docs/design/record-workflow.cjs
```

The recorder clicks actual UI controls, waits for real run completion, and checks for a live OpenAI result, a resolved run, a receipt, and browser errors. Diagnostic screenshots and the detailed local trace stay under ignored `runtime/readme-luna/capture/`. Keep that trace private: it contains internal run capabilities. A fresh store prevents an earlier replacement from blocking this recording through idempotency checks.

## Edit and export

The editing workflow uses [Web Product Demo Video](https://github.com/jh941213/web-demo-skills), installed as `web-product-demo-video`. `prepare.py` contains source-video ranges checked against the captured footage; update those ranges after a new recording because model latency changes. `recording-plan.json` documents verified actions; the customized executable recorder is [record-workflow.cjs](../record-workflow.cjs).

From the repository root, with Python, FFmpeg 9, and FFprobe available:

```powershell
$demoSkill = Join-Path $env:USERPROFILE '.codex/skills/web-product-demo-video/scripts'
python docs/design/workflow-source/prepare.py
python "$demoSkill/create_storyboard.py" --config docs/design/workflow-source/demo.config.json --inventory docs/design/workflow-source/feature-inventory.json --markers docs/design/workflow-source/recording-markers.json --output docs/design/workflow-source/storyboard.json
python "$demoSkill/validate_storyboard.py" docs/design/workflow-source/storyboard.json --require-media --require-markers
python docs/design/workflow-source/render.py docs/design/workflow-source/storyboard.json --output ../workflow-luna.mp4 --preset fast --crf 20
python "$demoSkill/validate_video.py" docs/design/workflow-luna.mp4 --storyboard docs/design/workflow-source/storyboard.json --report docs/design/workflow-source/validation.json --contact-sheet docs/design/workflow-source/contact-sheet.jpg
ffmpeg -y -i docs/design/workflow-luna.mp4 -filter_complex 'fps=6,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle' -loop 0 docs/design/demo.gif
```

`render.py` adapts the installed skill to FFmpeg 9's filter-file option and adds a readable caption background. `captions.srt` is also available separately. `validation.json` records the full decode check and media properties; `contact-sheet.jpg` supports visual review. Inspect the video and contact sheet after any edit.
