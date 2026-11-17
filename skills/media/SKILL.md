---
name: media
description: "Media creation and consumption — video, audio, GIFs, music, and YouTube. Covers ComfyUI, Manim, Spotify, and content extraction."
category: creative
trigger: media creation, video generation, audio, GIFs, music generation
---

# Media Skills

Complete guide to media creation and consumption.

## Overview

This skill consolidates:
1. **Video** — Manim animations
2. **Image** — ComfyUI image generation
3. **Audio** — Music generation, Spotify
4. **GIFs** — Search and creation
5. **YouTube** — Content extraction

---

## 1. Video (Manim)

### Install

```bash
pip install manim
```

### Create

```python
from manim import *

class SquareToCircle(Scene):
    def construct(self):
        square = Square()
        self.play(Create(square))
        self.play(Transform(square, Circle()))
        self.play(FadeOut(square))
```

### Render

```bash
manim -pql video.py SquareToCircle
```

---

## 2. Image (ComfyUI)

### Workflow

Use ComfyUI for image generation:
1. Load workflow JSON
2. Run prompt
3. Download output

---

## 3. Audio

### Spotify

```bash
spotify play
spotify pause
spotify next
spotify search "song name"
```

### Music Generation

Use Suno/AudioCraft for AI music.

---

## 4. GIFs

### Search

```bash
gif-search "funny cat"
```

---

## 5. YouTube

### Transcripts

Extract transcripts from YouTube videos.

---

## References

- `references/` — Workflows