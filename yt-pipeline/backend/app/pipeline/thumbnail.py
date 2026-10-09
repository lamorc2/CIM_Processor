from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..models import AppSettings, Job, ThumbnailPreviewRequest
from ..paths import job_dir


def _font(size: int, font_path: str = "") -> ImageFont.ImageFont:
    candidates = []
    if font_path:
        candidates.append(font_path)
    candidates.extend(
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ]
    )
    for c in candidates:
        p = Path(c)
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    cur = words[0]
    for w in words[1:]:
        trial = f"{cur} {w}"
        if draw.textlength(trial, font=font) <= max_width:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def render_thumbnail(
    *,
    headline: str,
    subheadline: str = "",
    text_color: str = "#FFFFFF",
    accent_color: str = "#FF3B30",
    source_image_path: str = "",
    font_path: str = "",
    out_path: Path | None = None,
) -> bytes:
    width, height = 1280, 720
    if source_image_path and Path(source_image_path).exists():
        img = Image.open(source_image_path).convert("RGB")
        img = img.resize((width, height), Image.Resampling.LANCZOS)
    else:
        # Atmospheric gradient background (not flat)
        img = Image.new("RGB", (width, height), "#0b1220")
        draw_bg = ImageDraw.Draw(img)
        for y in range(height):
            ratio = y / height
            r = int(11 + ratio * 40)
            g = int(18 + ratio * 20)
            b = int(32 + ratio * 10)
            draw_bg.line([(0, y), (width, y)], fill=(r, g, b))
        # Accent slash
        try:
            ar, ag, ab = (
                int(accent_color[1:3], 16) // 3,
                int(accent_color[3:5], 16) // 4,
                int(accent_color[5:7], 16) // 4,
            )
        except Exception:
            ar, ag, ab = 40, 20, 20
        draw_bg.polygon(
            [(width * 0.55, 0), (width, 0), (width, height), (width * 0.35, height)],
            fill=(ar, ag, ab),
        )

    draw = ImageDraw.Draw(img)
    # Dark bottom gradient panel for text legibility
    for y in range(height // 2, height):
        alpha = int(180 * ((y - height / 2) / (height / 2)))
        overlay = Image.new("RGBA", (width, 1), (0, 0, 0, alpha))
        img.paste(overlay, (0, y), overlay)

    draw = ImageDraw.Draw(img)
    # Accent bar
    draw.rectangle([48, 120, 72, 360], fill=accent_color)

    title_font = _font(72, font_path)
    sub_font = _font(36, font_path)
    lines = _wrap(draw, headline.upper() if headline else "UNTITLED", title_font, width - 160)
    y = 140
    for line in lines[:3]:
        draw.text((96, y), line, font=title_font, fill=text_color, stroke_width=2, stroke_fill="#000000")
        y += 82
    if subheadline:
        sub_lines = _wrap(draw, subheadline, sub_font, width - 160)
        y += 8
        for line in sub_lines[:2]:
            draw.text((96, y), line, font=sub_font, fill="#E8E8E8", stroke_width=1, stroke_fill="#000000")
            y += 44

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, format="JPEG", quality=92)
        return out_path.read_bytes()

    from io import BytesIO

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def run_thumbnail_stage(settings: AppSettings, job: Job) -> Job:
    thumb = job.inputs.thumbnail
    out = job_dir(settings.workspace_dir, job.id) / "stages" / "04_thumbnail" / "thumb.jpg"

    source = thumb.source_image_path
    if thumb.mode == "upload" and source and Path(source).exists():
        # If upload with no headline overlay requested, still allow overlay if headline set
        pass

    headline = thumb.headline or job.inputs.title
    render_thumbnail(
        headline=headline,
        subheadline=thumb.subheadline,
        text_color=thumb.text_color or settings.thumbnail.default_text_color,
        accent_color=thumb.accent_color or settings.thumbnail.default_accent_color,
        source_image_path=source,
        font_path=settings.thumbnail.font_path,
        out_path=out,
    )
    job.outputs.thumbnail_path = str(out)
    return job


def preview_thumbnail(settings: AppSettings, req: ThumbnailPreviewRequest) -> bytes:
    return render_thumbnail(
        headline=req.headline,
        subheadline=req.subheadline,
        text_color=req.text_color,
        accent_color=req.accent_color,
        source_image_path=req.source_image_path,
        font_path=settings.thumbnail.font_path,
    )
