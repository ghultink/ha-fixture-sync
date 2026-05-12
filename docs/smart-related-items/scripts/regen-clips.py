#!/usr/bin/env python3
"""Regenerate the 12 demo clips with neutral, non-customer-name footer text.

Builds a 75s 1280x720 MP4 per clip: animated radial gradient background +
a PNG overlay with the title, description, and footer ("CC0 · synthetic
demo content · Blue Billywig smart-related-items demo · topic: <neutral>").

Uses PIL for text rendering (ffmpeg here lacks libfreetype/drawtext).
"""
import subprocess
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
OUT_DIR = Path("/tmp/regen-clips")
OUT_DIR.mkdir(exist_ok=True)

W, H = 1280, 720

# Per-topic gradient palette (center → edge) tuned for the topic mood.
PALETTES = {
    "recipes":     ("#FFB347", "#5C2A00"),
    "real estate": ("#5FA8D3", "#0F2A44"),
    "parenting":   ("#FFB4A2", "#5A1D3A"),
    "gaming":      ("#B388EB", "#2A0E5A"),
}

CLIPS = [
    ("7281312", "Quick Microwave Pasta",       "A 3-minute weeknight dinner — water, pasta, microwave, done.",            "recipes"),
    ("7281315", "5-Minute Veggie Frittata",    "Eggs, leftover veg, a microwave-safe mug. Breakfast, sorted.",            "recipes"),
    ("7281317", "One-Pot Lentil Curry",        "Aromatics, lentils, coconut milk — one pan, twenty minutes.",             "recipes"),
    ("7281318", "Open House Tips",             "What to spot, what to ignore, and what the agent isn't telling you.",     "real estate"),
    ("7281319", "First-Time Buyer Guide",      "Mortgage, deposit, paperwork — the basics, in 90 seconds.",               "real estate"),
    ("7281320", "Mortgage Basics",             "Fixed vs. variable, how much you can really afford, in plain English.",   "real estate"),
    ("7281321", "Bedtime Routine Hacks",       "Three small tweaks that work better than yelling.",                       "parenting"),
    ("7281322", "Toddler Tantrums 101",        "Why they happen, and the calm response that defuses most of them.",       "parenting"),
    ("7281323", "Healthy Snacks for Kids",     "Five quick snacks even a picky eater will eat.",                          "parenting"),
    ("7281324", "Best RPGs of 2025",           "The five role-playing games actually worth your weekend.",                "gaming"),
    ("7281325", "Building a Gaming Setup",     "A budget desk-and-monitor combo that runs everything indie.",             "gaming"),
    ("7281327", "Indie Games You Missed",      "Twelve under-the-radar releases worth installing tonight.",               "gaming"),
]


def wrap(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        bbox = font.getbbox(trial)
        if bbox[2] - bbox[0] <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def shadow_text(draw, xy, text, font, fill, shadow_alpha=160):
    sx, sy = xy
    draw.text((sx + 2, sy + 2), text, font=font, fill=(0, 0, 0, shadow_alpha))
    draw.text((sx, sy), text, font=font, fill=fill)


def make_overlay_png(title: str, desc: str, topic: str, dest: Path) -> None:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    title_font = ImageFont.truetype(FONT_PATH, 64)
    desc_font  = ImageFont.truetype(FONT_PATH, 28)
    foot_font  = ImageFont.truetype(FONT_PATH, 18)

    # Title — wrap to width 1100
    title_lines = wrap(title, title_font, 1100)
    desc_lines = wrap(desc, desc_font, 1000)
    foot_text  = f"CC0 · synthetic demo content · Blue Billywig smart-related-items demo · topic: {topic}"

    # Vertical positioning: title centered around mid; description right below.
    line_h_title = title_font.getbbox("Ag")[3] - title_font.getbbox("Ag")[1] + 10
    line_h_desc  = desc_font.getbbox("Ag")[3] - desc_font.getbbox("Ag")[1] + 6
    total_h = len(title_lines) * line_h_title + 18 + len(desc_lines) * line_h_desc
    y = (H - total_h) // 2 - 30

    # Soft translucent backdrop behind title block for legibility
    pad = 28
    block_w = max(
        max((title_font.getbbox(l)[2] - title_font.getbbox(l)[0]) for l in title_lines),
        max((desc_font.getbbox(l)[2] - desc_font.getbbox(l)[0])  for l in desc_lines),
    )
    block_x = (W - block_w) // 2
    block_h = total_h
    draw.rounded_rectangle(
        [block_x - pad, y - pad, block_x + block_w + pad, y + block_h + pad - 8],
        radius=18, fill=(0, 0, 0, 70)
    )

    # Title
    for line in title_lines:
        bbox = title_font.getbbox(line)
        x = (W - (bbox[2] - bbox[0])) // 2
        shadow_text(draw, (x, y), line, title_font, (255, 255, 255, 255))
        y += line_h_title
    y += 18

    # Description
    for line in desc_lines:
        bbox = desc_font.getbbox(line)
        x = (W - (bbox[2] - bbox[0])) // 2
        shadow_text(draw, (x, y), line, desc_font, (255, 255, 255, 240))
        y += line_h_desc

    # Footer (small) at bottom-center
    fbbox = foot_font.getbbox(foot_text)
    fw = fbbox[2] - fbbox[0]
    fx = (W - fw) // 2
    fy = H - 44
    shadow_text(draw, (fx, fy), foot_text, foot_font, (255, 255, 255, 210))

    img.save(dest, "PNG")


def render_clip(mid: str, title: str, desc: str, topic: str) -> Path:
    overlay = OUT_DIR / f"{mid}-overlay.png"
    make_overlay_png(title, desc, topic, overlay)

    c0, c1 = PALETTES[topic]
    src = (f"gradients=size={W}x{H}:type=radial:rate=30:"
           f"c0={c0}:c1={c1}:speed=0.0015:duration=75")
    out = OUT_DIR / f"{mid}.mp4"

    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "warning", "-y",
        "-f", "lavfi", "-i", src,
        "-loop", "1", "-i", str(overlay),
        "-filter_complex", "[0:v][1:v] overlay=0:0:format=auto [v]",
        "-map", "[v]",
        "-t", "75",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "medium", "-crf", "23",
        "-movflags", "+faststart",
        str(out),
    ]
    print(f"  rendering {mid} ({topic}) -> {out.name}")
    subprocess.run(cmd, check=True)
    return out


def main():
    print(f"Rendering {len(CLIPS)} clips to {OUT_DIR}/ ...")
    for clip in CLIPS:
        render_clip(*clip)
    print("\nDone. Files:")
    for f in sorted(OUT_DIR.glob("*.mp4")):
        sz = f.stat().st_size / 1024 / 1024
        print(f"  {f.name:>14}  {sz:6.2f} MB")


if __name__ == "__main__":
    main()
