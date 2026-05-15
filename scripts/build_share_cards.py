"""
Build 1200×1200 WeChat-friendly share cards for the portfolio.

Layout: 4×2 work-grid (7 project tiles + 'Bob · 王波 / PORTFOLIO' brand tile in
the bottom-right slot). The project page being shared gets its tile boosted
with its accent colour outline + glow; on the index card no tile is focal,
and the three "weak" tiles (PDS / Waycraft / DEjob) sit at low saturation
so the visually-strong logos (Artifax, Translay, Foresee, Notisa) carry the
card.

Usage:
  python scripts/build_share_cards.py            # build all 8 cards
  python scripts/build_share_cards.py <slug>     # build a single card
  python scripts/build_share_cards.py --index    # build index card only

Output:
  share/index.jpg, share/pds.jpg, ..., share/notisa.jpg  (JPG q=92, <250KB)

To add a new project: append an entry to PROJECTS and re-run.
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import os, sys, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
RASTER_DIR = os.path.join(HERE, ".logo_cache")  # cache rasterised SVGs here
SHARE_DIR  = os.path.join(ROOT, "share")
os.makedirs(SHARE_DIR, exist_ok=True)
os.makedirs(RASTER_DIR, exist_ok=True)

# ── Canvas
W, H = 1200, 1200
BG = (242, 242, 243)
INK = (29, 29, 31)
MUTE = (110, 110, 115)
HAIR = (210, 210, 215)
TILE_BG = (255, 255, 255)

# ── Layout
TILE = 220
GAP_X = 32
ROW_GAP = 60
LABEL_GAP = 18
ROWS, COLS = 2, 4

grid_w = COLS * TILE + (COLS - 1) * GAP_X
GRID_X = (W - grid_w) // 2
TOP_BAND = 200
GRID_Y = TOP_BAND

# ── Projects (single source of truth)
# Each entry maps a project to:
#   slot     – 1-based grid position
#   slug     – output JPG filename (share/{slug}.jpg) AND HTML page identifier
#   code     – 2-char tile label number
#   short    – ASCII label under the tile
#   logo     – /logos/<logo>.svg or .png
#   accent   – RGB tuple for the focus border / footer text
#   style    – "branded" (keeps colour on index card) or "weak" (desaturated on
#              index, full colour when focal)
#   html     – the HTML file to patch on this site
#   title    – og:title (≤25 CJK chars for WeChat truncation)
#   desc     – og:description (each subpage's hero h1 in ZH)
PROJECTS = [
    dict(slot=1, slug="pds",      code="01", short="PDS",      logo="pds",
         accent=(29, 29, 31), style="weak",
         html="product-design-studio.html",
         title="产品设计工作室｜王波 作品集",
         desc ="从人的意图，到工程的现实。"),
    dict(slot=2, slug="artifax",  code="02", short="ARTIFAX",  logo="artifax",
         accent=(194, 104, 44), style="branded",
         html="pixelforge-artifax.html",
         title="PixelForge/Artifax｜王波 作品集",
         desc ="一个会读你的座舱。"),
    dict(slot=3, slug="translay", code="03", short="TRANSLAY", logo="translay",
         accent=(54, 105, 213), style="branded",
         html="translay.html",
         title="Translay｜王波 作品集",
         desc ="翻译任何屏幕，不离开当下。"),
    dict(slot=4, slug="waycraft", code="04", short="WAYCRAFT", logo="waycraft",
         accent=(189, 156, 76), style="weak",
         html="waycraft.html",
         title="Waycraft｜王波 作品集",
         desc ="从一句话，到一个完整行程。"),
    dict(slot=5, slug="dejob",    code="05", short="DEJOB",    logo="dejob",
         accent=(178, 56, 47), style="weak",
         html="dejob.html",
         title="DEjob｜王波 作品集",
         desc ="您的德国职业，从这里开始。"),
    dict(slot=6, slug="foresee",  code="06", short="FORESEE",  logo="foresee",
         accent=(138, 101, 55), style="branded",
         html="foresee.html",
         title="境见｜王波 作品集",
         desc ="古道之卦，AI 推理。"),
    dict(slot=7, slug="notisa",   code="07", short="NOTISA",   logo="notisa",
         accent=(44, 95, 166), style="branded",
         html="notisa.html",
         title="Notisa｜王波 作品集",
         desc ="本地这件事，自动入历。"),
]

INDEX_META = dict(
    html="index.html",
    title="Bob Wang · 王波｜作品集",
    desc ="站在每一轮技术变革的交汇处。",
)

# ── Fonts
def load_font(paths, size):
    for p in paths:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size=size)
            except Exception: continue
    return ImageFont.load_default()

FONT_SANS_BOLD = ["/System/Library/Fonts/Helvetica.ttc",
                  "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]
FONT_SERIF_CJK = ["/System/Library/Fonts/Supplemental/Songti.ttc",
                  "/System/Library/Fonts/PingFang.ttc"]
FONT_MONO      = ["/System/Library/Fonts/SFNSMono.ttf",
                  "/System/Library/Fonts/Menlo.ttc",
                  "/System/Library/Fonts/Supplemental/Andale Mono.ttf"]

font_brand     = load_font(FONT_SANS_BOLD, 60)
font_brand_zh  = load_font(FONT_SERIF_CJK, 52)
font_brand_dot = load_font(FONT_SANS_BOLD, 40)
font_meta      = load_font(FONT_MONO, 13)
font_label     = load_font(FONT_MONO, 13)
font_eyebrow   = load_font(FONT_MONO, 22)

# ── Logo handling
def logo_path(name):
    cached = os.path.join(RASTER_DIR, f"{name}.png")
    if os.path.exists(cached):
        return cached
    svg = os.path.join(ROOT, "logos", f"{name}.svg")
    png = os.path.join(ROOT, "logos", f"{name}.png")
    if os.path.exists(svg):
        try:
            subprocess.run(
                ["rsvg-convert", "-h", "480", svg, "-o", cached],
                check=True, capture_output=True,
            )
            return cached
        except Exception:
            pass
    if os.path.exists(png):
        return png
    return None

def fit_logo(img, inner):
    lw, lh = img.size
    r = min(inner / lw, inner / lh)
    return img.resize((int(lw * r), int(lh * r)), Image.LANCZOS)

# ── Positions
def slot_xy(slot):
    i = slot - 1
    r, c = i // COLS, i % COLS
    return GRID_X + c * (TILE + GAP_X), GRID_Y + r * (TILE + ROW_GAP)

# ── Drawing helpers
_focus_in_card = False

def draw_tile(canvas, draw, project, highlight=False):
    x, y = slot_xy(project["slot"])
    accent = project["accent"]
    r = 22

    if highlight:
        halo = Image.new("RGBA", (TILE + 80, TILE + 80), (0, 0, 0, 0))
        ImageDraw.Draw(halo).rounded_rectangle(
            [40, 40, 40 + TILE, 40 + TILE], radius=r, fill=(*accent, 64)
        )
        halo = halo.filter(ImageFilter.GaussianBlur(radius=24))
        canvas.alpha_composite(halo, (x - 40, y - 40))

    border = accent if highlight else HAIR
    bw = 3 if highlight else 1
    draw.rounded_rectangle([x, y, x + TILE, y + TILE], radius=r,
                           fill=TILE_BG, outline=border, width=bw)

    if highlight:
        sat = 1.0
    elif _focus_in_card:
        sat = 0.05
    elif project.get("style") == "weak":
        sat = 0.15
    else:
        sat = 1.0

    lp = logo_path(project["logo"])
    if lp:
        logo = Image.open(lp).convert("RGBA")
        inner = TILE - 64
        logo = fit_logo(logo, inner)
        lw, lh = logo.size
        lx = x + (TILE - lw) // 2
        ly = y + (TILE - lh) // 2
        if sat < 1.0:
            rr, gg, bb, aa = logo.split()
            rgb = Image.merge("RGB", (rr, gg, bb))
            rgb = ImageEnhance.Color(rgb).enhance(sat)
            logo = Image.merge("RGBA", (*rgb.split(), aa))
        canvas.paste(logo, (lx, ly), logo)

    label = f"{project['code']}  {project['short']}"
    color = accent if highlight else MUTE
    tb = draw.textbbox((0, 0), label, font=font_label)
    tw = tb[2] - tb[0]
    draw.text((x + (TILE - tw) // 2, y + TILE + LABEL_GAP),
              label, font=font_label, fill=color)

def render_tight(text, font, color):
    pad = 24
    w = int(font.getlength(text)) + pad * 2 if hasattr(font, "getlength") else 600
    h = int(font.size * 2) + pad * 2
    tmp = Image.new("RGBA", (max(w, 80), max(h, 80)), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((pad, pad), text, font=font, fill=color)
    bb = tmp.getbbox()
    return tmp.crop(bb) if bb else tmp

def draw_brand_tile(canvas):
    x, y = slot_xy(8)
    bob_img  = render_tight("Bob",       font_brand,     INK)
    sep_img  = render_tight("·",         font_brand_dot, MUTE)
    zh_img   = render_tight("王波",       font_brand_zh,  INK)
    meta_img = render_tight("PORTFOLIO", font_meta,      MUTE)

    bob_w, bob_h   = bob_img.size
    sep_w, sep_h   = sep_img.size
    zh_w,  zh_h    = zh_img.size
    meta_w, meta_h = meta_img.size

    row_h   = max(bob_h, zh_h)
    total_h = row_h + 14 + meta_h
    start_y = y + (TILE - total_h) // 2

    gap = 14
    row_w = bob_w + gap + sep_w + gap + zh_w
    cx = x + TILE // 2
    bx = cx - row_w // 2

    canvas.alpha_composite(bob_img, (bx, start_y))
    sep_x = bx + bob_w + gap
    canvas.alpha_composite(sep_img, (sep_x, start_y + (row_h - sep_h) // 2))
    zh_x = sep_x + sep_w + gap
    canvas.alpha_composite(zh_img, (zh_x, start_y))
    canvas.alpha_composite(meta_img, (cx - meta_w // 2, start_y + row_h + 14))

def build(highlight_slug, out_path):
    global _focus_in_card
    _focus_in_card = highlight_slug is not None

    canvas = Image.new("RGBA", (W, H), BG + (255,))
    draw = ImageDraw.Draw(canvas)

    for p in PROJECTS:
        draw_tile(canvas, draw, p, highlight=(highlight_slug == p["slug"]))
    draw_brand_tile(canvas)

    # Top eyebrow + hairline
    eyebrow = "SELECTED WORK"
    eb = draw.textbbox((0, 0), eyebrow, font=font_eyebrow)
    ew = eb[2] - eb[0]
    eyebrow_y = 88
    draw.text(((W - ew) // 2, eyebrow_y), eyebrow, font=font_eyebrow, fill=INK)
    hl_y = eyebrow_y + 50
    line_w = 240
    draw.rectangle([(W - line_w) // 2, hl_y, (W + line_w) // 2, hl_y + 1], fill=HAIR)

    # Bottom hairline + focus indicator + domain
    bot_hl_y = H - 160
    draw.rectangle([(W - line_w) // 2, bot_hl_y, (W + line_w) // 2, bot_hl_y + 1], fill=HAIR)
    if highlight_slug:
        proj = next(p for p in PROJECTS if p["slug"] == highlight_slug)
        ft = f"{proj['code']} / 07  ·  {proj['short']}"
        fb = draw.textbbox((0, 0), ft, font=font_meta)
        draw.text(((W - (fb[2] - fb[0])) // 2, bot_hl_y + 24),
                  ft, font=font_meta, fill=proj["accent"])
    else:
        sel = "07 PROJECTS  ·  2024 – 2025"
        sb = draw.textbbox((0, 0), sel, font=font_meta)
        draw.text(((W - (sb[2] - sb[0])) // 2, bot_hl_y + 24),
                  sel, font=font_meta, fill=MUTE)
    domain = "bob.vehicledesign.studio"
    db = draw.textbbox((0, 0), domain, font=font_meta)
    draw.text(((W - (db[2] - db[0])) // 2, H - 70),
              domain, font=font_meta, fill=MUTE)

    # Save as JPG, quality 92
    rgb = canvas.convert("RGB")
    rgb.save(out_path, "JPEG", quality=92, optimize=True, progressive=True)
    print(f"  ✓ {os.path.relpath(out_path, ROOT):<30} {os.path.getsize(out_path) // 1024} KB")

def build_all():
    print("Building share cards →")
    build(None, os.path.join(SHARE_DIR, "index.jpg"))
    for p in PROJECTS:
        build(p["slug"], os.path.join(SHARE_DIR, f"{p['slug']}.jpg"))

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "--all"
    if arg in ("--all", "-a"):
        build_all()
    elif arg == "--index":
        build(None, os.path.join(SHARE_DIR, "index.jpg"))
    else:
        build(arg, os.path.join(SHARE_DIR, f"{arg}.jpg"))
