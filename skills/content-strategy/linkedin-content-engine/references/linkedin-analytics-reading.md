# Reading LinkedIn Analytics from Screenshots

When Greg shares a LinkedIn analytics screenshot and standard tools (vision_analyze, browser_vision) can't read it from a local file path, use this fallback OCR pipeline.

## When to Use This

- Greg sends a screenshot from his Mac (`~/.hermes/image_cache/img_*.jpg`) that vision_analyze can't process
- The image contains numbers/metrics that need extraction
- You need precise counts (impressions, likes, comments, reposts) to run the Post-Mortem Protocol

## OCR Pipeline

### Step 1: Install dependencies (one-time)

```bash
pip3 install pytesseract
brew install tesseract
```

### Step 2: Extract text

```python
from PIL import Image
import pytesseract

img = Image.open('/path/to/screenshot.jpg')
text = pytesseract.image_to_string(img)
print(text)
```

### Step 3: Improve accuracy if needed

If the text is noisy, try these refinements in order of effectiveness:

**A. Scale up before OCR (most effective for blurry images)**
```python
big = img.resize((img.width * 3, img.height * 3), Image.LANCZOS)
gray = big.convert('L')
text = pytesseract.image_to_string(gray, config='--psm 6')
```

**B. Grayscale + contrast boost**
```python
from PIL import ImageEnhance, ImageFilter
gray = img.convert('L')
enhancer = ImageEnhance.Contrast(gray)
gray = enhancer.enhance(2.0)
gray = gray.filter(ImageFilter.SHARPEN)
text = pytesseract.image_to_string(gray)
```

**C. Binarization (threshold to pure black & white) — aggressive, for clean UIs**
```python
# After scaling and grayscale:
gray = gray.point(lambda x: 0 if x < 128 else 255)
```

**D. Cropping to specific zones**
```python
# Top 40% usually has the metric numbers
top = img.crop((0, 0, img.width, int(img.height * 0.4)))
# Bottom half usually has the impression count + "View analytics" link
bottom = img.crop((0, int(img.height * 0.5), img.width, img.height))
```

**E. Combined pipeline (recommended for small/cropped analytics cards)**
```python
from PIL import Image, ImageEnhance, ImageFilter
img = Image.open('/path/to/screenshot.jpg')
big = img.resize((img.width * 3, img.height * 3), Image.LANCZOS)
gray = big.convert('L')
gray = ImageEnhance.Contrast(gray).enhance(2.5)
gray = gray.filter(ImageFilter.SHARPEN)
# Try different PSM modes
for psm in [4, 6, 7, 11]:
    t = pytesseract.image_to_string(gray, config=f'--psm {psm}')
    print(f'PSM {psm}: {t.strip()}')
```
- `--psm 4` = assume a single column of text of variable sizes
- `--psm 6` = assume a uniform block of text
- `--psm 7` = treat as a single line of text (use on small crops)
- `--psm 11` = sparse text, arbitrary order
- `--psm 12` = sparse text with OSD
- Try multiple PSM modes if first pass is noisy — the top metric bar often reads better with `--psm 7` while the bottom "impressions" line reads better with `--psm 6`

**F. For very small images (<500px height):** Skip crop-and-OCR on individual zones. Scale up 3-4x, apply full image OCR with `--psm 4`, then parse the larger numbers programmatically.

### Step 4: Interpret the output

Common LinkedIn analytics screenshot elements that appear:

| OCR Text | What It Maps To |
|----------|----------------|
| `2,089 impressions` | Total post views |
| `Akash Dasgupta and 22 others` | ~23 people interacted (liked + commented + reposted) |
| `6 comments` | Number of comments |
| `3 reposts` | Number of reposts/shares |
| `Reactions` or a number nearby | Total reactions (likes + love + celebrate, etc.) |
| `+15` (near reactions) | Reactions gained in a time window |

### Calculating Engagement Rate

```python
# Extract numbers from text
import re
nums = re.findall(r'[\d,]+', ocr_text)
# impressions is typically the largest number
# engagement = reactions + comments + reposts
# rate = (engagement / impressions) * 100
```

## Benchmarks for Interpretation

See the Post-Mortem Protocol in SKILL.md for full benchmarks, but in brief:

- **<0.5%** = Below average
- **0.5-1%** = Average
- **1-3%** = Good
- **3-5%** = Excellent

## Cold-Start Recovery Pattern

When a post shows **early low numbers** (<200 impressions, 0 engagement) that later climb (2K+ impressions, 15+ reactions, 6+ comments):

- This is NOT a flop — it's a **recovered cold start**
- The algorithm showed it to a small sample first; a later viewer engaged, which opened the taps
- Apply the `Fork C: Recovered Cold Start` verdict from the Post-Mortem Protocol
- Reframe for Greg: the post found its legs, this is growth not failure

## Pitfalls

- OCR may misread numbers — cross-check against what Greg tells you
- LinkedIn's UI changes regularly; element positions may shift
- If OCR returns zero results, try upscaling the image first: `img = img.resize((img.width*2, img.height*2), Image.LANCZOS)`
- Don't run OCR on images with heavy shadows, reflections, or dark-mode UIs — ask Greg for a cleaner screenshot
