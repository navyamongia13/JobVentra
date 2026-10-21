import base64
import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError
from tinyfish import TinyFish

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
load_dotenv()  # reads TINYFISH_API_KEY and GEMINI_API_KEY from .env

st.set_page_config(page_title="JobVentra", page_icon=str(Path(__file__).parent / "assets" / "favicon.png"), layout="wide")

tf_client = TinyFish()

# --- LLM settings (all optional, set in .env) ---
# LLM_PROVIDER=groq|gemini   GROQ_MODEL=a,b   GEMINI_MODEL=a,b
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()
GROQ_MODELS = [m.strip() for m in os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile,llama-3.1-8b-instant").split(",") if m.strip()]
GEMINI_MODELS = [m.strip() for m in os.getenv("GEMINI_MODEL", "gemini-3.8-flash").split(",") if m.strip()]
RETRYABLE = {429, 500, 502, 503, 504}

BLUE = "#1F5C47"
GREEN = "#2E8B57"
AMBER = "#D97706"
RED = "#DC2626"

if "page" not in st.session_state:
    st.session_state["page"] = "home"


def go(page: str):
    st.session_state["page"] = page


def go_prep(company: str):
    """Open Interview Prep with this company already filled in."""
    st.session_state["p_company"] = company
    st.session_state["page"] = "prep"


# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"], .stMarkdown, .stMarkdown p, h1, h2, h3, h4, h5, h6, button, button p, input, textarea,
[data-baseweb="tab"], [data-testid="stCaptionContainer"], .stMarkdown div, .stMarkdown span, .stMarkdown li {
  font-family: 'Plus Jakarta Sans', 'Source Sans Pro', sans-serif !important;
}
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDeployButton"] { visibility: hidden; height: 0; }
header[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1rem; max-width: 1150px; }

/* ---------- Home hero ---------- */
.home-hero {
  background: linear-gradient(120deg, #0B3226 0%, #1F5C47 55%, #4F8A68 100%);
  border-radius: 24px; padding: 38px 40px 34px; color: #fff; text-align: center;
  box-shadow: 0 16px 40px rgba(14,59,45,.28); margin-bottom: 20px;
}
.home-hero .eyebrow { font-weight: 700; letter-spacing: .18em; font-size: .85rem; opacity: .85; text-transform: uppercase; }
.home-hero h1 {
  margin: 4px 0 6px; font-size: 3.8rem; font-weight: 800; letter-spacing: -.03em; color: #fff; line-height: 1.05;
}
.home-hero p { margin: 0 auto; max-width: 640px; font-size: 1.15rem; opacity: .96; color: #fff; }
.pill {
  display: inline-block; background: rgba(255,255,255,.2); border: 1px solid rgba(255,255,255,.35);
  padding: 7px 16px; border-radius: 999px; font-size: .88rem; font-weight: 600; margin: 0 5px;
}

/* ---------- Feature cards on home ---------- */
.feature {
  background: #fff; border: 1px solid #E3EBDD; border-radius: 18px 18px 0 0; padding: 26px 22px 18px; min-height: 278px; box-sizing: border-box;
  text-align: center; box-shadow: 0 6px 18px rgba(15,40,30,.06); border-bottom: none;
}
.feature .icon { display: flex; justify-content: center; margin-bottom: 4px; }
.badge-icon { width: 68px; height: 68px; border-radius: 20px; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #1F5C47, #5E9473); box-shadow: 0 8px 18px rgba(14,59,45,.28); }
.icon-tint { background: #EEF5EF; border-radius: 22px; padding: 10px; }
.home-foot { text-align: center; color: #8FA095; font-size: .85rem; margin-top: 22px; }
.feature .icon img { height: 84px; width: 84px; object-fit: contain; }
.feature .icon .ph {
  height: 84px; width: 84px; border-radius: 50%; background: linear-gradient(135deg, #1F5C47, #8DBB9B);
  color: #fff; font-size: 2.2rem; font-weight: 800; display: flex; align-items: center; justify-content: center;
}
.feature h3 { margin: 8px 0 6px; font-size: 1.35rem; font-weight: 800; color: #12261D; }
.feature p { margin: 0; color: #4A5B50; line-height: 1.5; font-size: .98rem; }

/* Big nav buttons (keys start with nav_) */
[class*="st-key-nav_"], [class*="st-key-nav_"] [data-testid="stButton"], [class*="st-key-nav_"] .stButton {
  width: 100% !important; display: block !important;
}
[class*="st-key-nav_"] button {
  width: 100% !important; height: 56px; font-size: 1.05rem !important; font-weight: 700 !important;
  border-radius: 0 0 18px 18px !important; border: 1px solid #1F5C47 !important;
  background: #1F5C47 !important; color: #fff !important; transition: all .15s ease;
}
[class*="st-key-nav_"] button:hover { background: #174A39 !important; transform: translateY(-2px); }
[class*="st-key-nav_"] button p { font-size: 1.05rem !important; font-weight: 700 !important; }

/* ---------- Sub page top bar ---------- */
.topbar-brand { font-size: 1.5rem; font-weight: 800; color: #1F5C47; text-align: right; padding-top: 6px; }
.page-title { font-size: 1.9rem; font-weight: 800; margin: 6px 0 4px; color: #12261D; }
.page-sub { color: #66766B; margin-bottom: 18px; }

/* ---------- Cards ---------- */
.card {
  background: #fff; border: 1px solid #E3EBDD; border-radius: 18px; padding: 20px 22px;
  box-shadow: 0 4px 14px rgba(15,40,30,.05); margin-bottom: 16px;
}
.card h4 { margin: 0 0 10px; font-size: 1rem; font-weight: 700; color: #12261D; }
.card ul { margin: 0; padding-left: 18px; }
.card li { margin-bottom: 6px; line-height: 1.45; color: #33453B; }
.card p { color: #33453B; line-height: 1.55; margin: 0; }

.tile { background:#fff; border:1px solid #E3EBDD; border-radius:16px; padding:16px 18px; height:100%; }
.tile .label { font-size:.75rem; text-transform:uppercase; letter-spacing:.06em; color:#66766B; font-weight:700; }
.tile .value { font-size:1.15rem; font-weight:700; color:#12261D; margin-top:4px; }

.chip { display:inline-block; padding:6px 12px; border-radius:999px; font-size:.85rem; font-weight:600; margin:0 6px 8px 0; }
.chip.blue  { background:#E6F0E9; color:#1F5C47; }
.chip.red   { background:#FEE9E9; color:#B91C1C; }
.chip.green { background:#E3F7EA; color:#15803D; }

.badge { display:inline-block; padding:8px 18px; border-radius:999px; font-weight:800; font-size:1rem; }

.timeline { border-left: 3px solid #CFE0D2; margin: 6px 0 4px 8px; padding-left: 18px; }
.timeline .step { position: relative; margin-bottom: 10px; color:#33453B; font-size:.92rem; }
.timeline .step::before {
  content:''; position:absolute; left:-27px; top:5px; width:11px; height:11px;
  background:#1F5C47; border-radius:50%; border:2px solid #fff; box-shadow:0 0 0 2px #CFE0D2;
}

.stButton > button { border-radius: 12px; font-weight: 700; padding: .55rem 1.2rem; }
.stTextInput input, .stTextArea textarea { border-radius: 12px !important; }
a { color: #1F5C47; }

.bd { margin-bottom: 14px; }
.bd-top { display: flex; justify-content: space-between; font-weight: 700; font-size: .92rem; color: #12261D; }
.bar { height: 8px; background: #E4E9DD; border-radius: 999px; margin: 6px 0 4px; overflow: hidden; }
.bar .fill { height: 100%; border-radius: 999px; }
.bd-ev { font-size: .86rem; color: #66766B; line-height: 1.4; }
.capnote { background: #FFF3DC; color: #92400E; border-radius: 12px; padding: 10px 14px; font-size: .9rem; font-weight: 600; margin-bottom: 14px; }

.q { display: flex; gap: 12px; padding: 12px 0; border-bottom: 1px solid #EDF1E6; align-items: flex-start; }
.q:last-child { border-bottom: none; }
.q-num { flex: 0 0 26px; height: 26px; border-radius: 50%; background: #E6F0E9; color: #1F5C47; font-weight: 800;
  font-size: .8rem; display: flex; align-items: center; justify-content: center; margin-top: 1px; }
.q-text { color: #12261D; font-weight: 600; line-height: 1.45; margin-bottom: 6px; }
.tag { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: .75rem; font-weight: 700; margin-right: 6px; }
.tag.topic { background: #E6F0E9; color: #1F5C47; }
.tag.easy { background: #E3F7EA; color: #15803D; }
.tag.medium { background: #FFF3DC; color: #B45309; }
.tag.hard { background: #FEE9E9; color: #B91C1C; }
.chip.amber { background: #FFF3DC; color: #B45309; }
.bar.big { height: 12px; }

.rounds { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 22px; margin-bottom: 8px; }
.round { position: relative; background: #F3F7F0; border: 1px solid #E3EBDD; border-radius: 16px; padding: 14px; }
.round:not(:last-child)::after { content: "→"; position: absolute; right: -19px; top: 18px; color: #1F5C47; font-weight: 800; }
.rnum { width: 28px; height: 28px; border-radius: 50%; background: #1F5C47; color: #fff; font-weight: 800; font-size: .85rem;
  display: flex; align-items: center; justify-content: center; margin-bottom: 8px; }
.rname { font-weight: 800; color: #12261D; margin-bottom: 8px; }
.rnote { font-size: .84rem; color: #66766B; line-height: 1.4; margin-top: 4px; }
.tips { margin-top: 14px; }
.tips b { color: #12261D; font-size: .95rem; }

.tldr { font-size: 1.08rem; color: #4A5B50; line-height: 1.5; margin: -2px 0 16px; max-width: 820px; }
.timeline .when { color: #1F5C47; font-weight: 800; font-size: .8rem; margin-right: 8px; }

/* ---------- Colour accents ---------- */
.card.accent-blue,   .tile.accent-blue   { border-top: 4px solid #1F5C47; }
.card.accent-teal,   .tile.accent-teal   { border-top: 4px solid #5E9473; }
.card.accent-green,  .tile.accent-green  { border-top: 4px solid #8DBB9B; }
.card.accent-amber,  .tile.accent-amber  { border-top: 4px solid #C0933F; }
.card.accent-violet, .tile.accent-violet { border-top: 4px solid #C0933F; }
.card.accent-slate,  .tile.accent-slate  { border-top: 4px solid #8FA095; }

.co-head {
  background: linear-gradient(135deg, #E9F2EA 0%, #F7F0DA 100%); border: 1px solid #D5E3D6;
  border-left: 6px solid #1F5C47; border-radius: 20px; padding: 22px 26px; margin-bottom: 16px;
}
.co-name { font-size: 2.1rem; font-weight: 800; color: #12261D; letter-spacing: -.02em; line-height: 1.15; }
.co-tldr { margin-top: 6px; color: #4A5B50; font-size: 1.05rem; line-height: 1.5; max-width: 820px; }

/* ---------- Pill tabs ---------- */
.stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: none; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none; }
.stTabs [data-baseweb="tab"] {
  background: #fff; border: 1px solid #E3EBDD; border-radius: 999px; padding: 8px 18px; height: auto;
}
.stTabs [data-baseweb="tab"] p { font-weight: 700; color: #33453B; }
.stTabs [data-baseweb="tab"][aria-selected="true"] { background: #1F5C47; border-color: #1F5C47; }
.stTabs [data-baseweb="tab"][aria-selected="true"] p { color: #fff; }

/* ---------- Motion ---------- */
@keyframes fadeUp   { from { opacity: 0; transform: translateY(22px); } to { opacity: 1; transform: none; } }
@keyframes fadeDown { from { opacity: 0; transform: translateY(-18px) scale(.985); } to { opacity: 1; transform: none; } }
@keyframes popIn    { 0% { opacity: 0; transform: scale(.88); } 60% { opacity: 1; transform: scale(1.03); } 100% { opacity: 1; transform: scale(1); } }

.home-hero { animation: fadeDown .7s cubic-bezier(.2,.8,.2,1) both; }
.home-hero .eyebrow { animation: fadeUp .6s ease .25s both; }
.home-hero h1 { animation: popIn .8s cubic-bezier(.2,.8,.2,1) .35s both; }
.home-hero p { animation: fadeUp .6s ease .6s both; }

.feature { animation: fadeUp .65s cubic-bezier(.2,.8,.2,1) both; }
.feature .icon img, .feature .icon .ph { animation: popIn .7s cubic-bezier(.2,.8,.2,1) .7s both; }
[class*="st-key-nav_"] { animation: fadeUp .65s cubic-bezier(.2,.8,.2,1) both; }
.st-key-nav_dossier { animation-delay: .9s; }
.st-key-nav_verify  { animation-delay: 1.02s; }
.st-key-nav_prep    { animation-delay: 1.14s; }

.page-title, .page-sub { animation: fadeDown .5s ease both; }
.card, .tile { animation: fadeUp .55s cubic-bezier(.2,.8,.2,1) both; }
.badge { animation: popIn .6s ease .6s both; }
.chip { animation: popIn .4s ease both; }
.chip:nth-child(1) { animation-delay: .3s; }
.chip:nth-child(2) { animation-delay: .38s; }
.chip:nth-child(3) { animation-delay: .46s; }
.chip:nth-child(4) { animation-delay: .54s; }
.chip:nth-child(n+5) { animation-delay: .62s; }
.timeline .step { animation: fadeUp .4s ease both; }
.timeline .step:nth-child(1) { animation-delay: .2s; }
.timeline .step:nth-child(2) { animation-delay: .3s; }
.timeline .step:nth-child(3) { animation-delay: .4s; }
.timeline .step:nth-child(4) { animation-delay: .5s; }
.timeline .step:nth-child(n+5) { animation-delay: .6s; }

@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }

/* ---------- Logo ---------- */
.brand-logo { text-align: center; margin: 2px 0 14px; animation: fadeDown .6s ease both; }
.brand-logo img { width: 480px; max-width: 100%; height: auto; image-rendering: auto; }
.topbar-logo { text-align: right; padding-top: 2px; }
.topbar-logo img { height: 64px; width: auto; max-width: none; }
.home-hero.nologo p { font-size: 1.3rem; max-width: 700px; margin-top: 10px; }
.home-hero.nologo { padding: 30px 40px 32px; }

/* ---------- Brand: serif headings + gold accents (matches logo) ---------- */
.home-hero h1, .page-title, .co-name, .feature h3, .topbar-brand, .rname, .card h4,
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
  font-family: 'Lora', Georgia, 'Times New Roman', serif !important; letter-spacing: -.01em;
}
.home-hero h1 { font-weight: 700; letter-spacing: -.02em; }
.home-hero .eyebrow { color: #E3B867; opacity: 1; }
.home-hero .eyebrow::before, .home-hero .eyebrow::after { content: "✦"; margin: 0 10px; color: #C0933F; }
.page-title { color: #0E3B2D; }
.page-title { display: flex; align-items: center; gap: 14px; }
.page-title .badge-icon { width: 52px; height: 52px; border-radius: 15px; flex: 0 0 52px; }
.page-title .badge-icon svg { width: 26px; height: 26px; }
.co-head { border-left-color: #C0933F; }
.stApp { background-color: #FBF7EA; }

/* ---------- Sample postings box ---------- */
.st-key-samples {
  background: #fff; border: 1px solid #E3EBDD; border-top: 4px solid #C0933F; border-radius: 18px;
  padding: 16px 20px 8px; margin-bottom: 18px; box-shadow: 0 4px 14px rgba(15,40,30,.05);
}
.samples-title { font-family: 'Lora', Georgia, serif; font-weight: 700; font-size: 1.05rem; color: #12261D; }
.samples-sub { color: #66766B; font-size: .9rem; margin: 2px 0 12px; }
.st-key-s_scam button { border-color: #F3C2C2 !important; color: #B91C1C !important; background: #FFF6F6 !important; }
.st-key-s_scam button:hover { border-color: #DC2626 !important; background: #FEE9E9 !important; }
.st-key-s_legit button { border-color: #BFDCC8 !important; color: #15803D !important; background: #F4FBF6 !important; }
.st-key-s_legit button:hover { border-color: #2E8B57 !important; background: #E3F7EA !important; }

/* hide the anchor-link icons Streamlit adds beside headings */
[data-testid="stHeaderActionElements"], [data-testid="stHeadingActionElements"],
[data-testid="stMarkdownContainer"] :is(h1,h2,h3,h4,h5,h6) a[href^="#"],
[data-testid="stMarkdownContainer"] :is(h1,h2,h3,h4,h5,h6) .stHeadingActionElements,
.stMarkdown :is(h1,h2,h3,h4,h5,h6) a.anchor-link { display: none !important; }
</style>
"""
try:
    from jobventra_fonts import FONT_CSS  # embedded font, works offline and on any host
except ImportError:
    FONT_CSS = ""
st.markdown(CSS, unsafe_allow_html=True)
if FONT_CSS:
    st.markdown(f"<style>{FONT_CSS}</style>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# HTML helpers (all LLM/web text is escaped)
# ---------------------------------------------------------------------------
def esc(x) -> str:
    return html.escape(str(x))


ASSETS = Path(__file__).parent / "assets"


def img_tag(name: str, alt: str = "") -> str:
    """Embed assets/<name>.(png|jpg|jpeg|webp|svg) as an inline image.
    Falls back to a coloured letter badge if the file is missing."""
    for ext in ("png", "jpg", "jpeg", "webp", "svg"):
        p = ASSETS / f"{name}.{ext}"
        if p.exists():
            mime = {"svg": "image/svg+xml", "jpg": "image/jpeg"}.get(ext, f"image/{ext}")
            data = base64.b64encode(p.read_bytes()).decode()
            return f'<img src="data:{mime};base64,{data}" alt="{esc(alt)}">'
    return f'<div class="ph">{esc(alt[:1].upper())}</div>'


ICON_MODE = "brand"  # "brand" = matching built-in icons, "custom" = your own images from assets/
_SV = ('<svg xmlns="http://www.w3.org/2000/svg" width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#fff" '
       'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{}</svg>')
BRAND_ICONS = {
    "dossier": _SV.format('<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>'
                          '<path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/>'),
    "verify": _SV.format('<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 '
                         '4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>'),
    "prep": _SV.format('<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>'),
}


# One accent per feature: (base, light, dark). Change these to recolour the home cards.
ACCENTS = {
    "dossier": ("#1F5C47", "#5E9473", "#174A39"),  # forest green
    "verify":  ("#B8862F", "#E3B867", "#9A6F22"),  # gold
    "prep":    ("#2A7F7B", "#6FB5AF", "#1F6360"),  # teal
}


def feature_icon(key: str, title: str) -> str:
    if ICON_MODE == "custom":
        return f'<div class="icon-tint">{img_tag(key, title)}</div>'
    base, light, _ = ACCENTS[key]
    return (f'<div class="badge-icon" style="background:linear-gradient(135deg,{base},{light});'
            f'box-shadow:0 8px 18px {base}47">{BRAND_ICONS[key]}</div>')


def card(title: str, body_html: str, accent: str = "") -> str:
    cls = f"card accent-{accent}" if accent else "card"
    return f'<div class="{cls}"><h4>{esc(title)}</h4>{body_html}</div>'


def ul(items: list[str]) -> str:
    if not items:
        return "<p>Nothing found.</p>"
    return "<ul>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>"


def chips(items: list[str], kind: str = "blue") -> str:
    if not items:
        return "<p>Nothing found.</p>"
    return "".join(f'<span class="chip {kind}">{esc(i)}</span>' for i in items)


def tile(label: str, value: str, accent: str = "") -> str:
    cls = f"tile accent-{accent}" if accent else "tile"
    return f'<div class="{cls}"><div class="label">{esc(label)}</div><div class="value">{esc(value)}</div></div>'


def sources_html(urls: list[str]) -> str:
    if not urls:
        return "<p>No sources.</p>"
    return "<ul>" + "".join(
        f'<li><a href="{esc(u)}" target="_blank">{esc(u)}</a></li>' for u in urls
    ) + "</ul>"


def timeline_html(steps: list[str]) -> str:
    return '<div class="timeline">' + "".join(f'<div class="step">{esc(s)}</div>' for s in steps) + "</div>"


def real(items) -> list[str]:
    """Drop empty or placeholder entries so counts and cards reflect real content."""
    if isinstance(items, str):
        items = [items]
    return [str(i).strip() for i in (items or []) if str(i).strip() and "not found" not in str(i).lower()]


def txt(x) -> str:
    r_ = real(x)
    return r_[0] if r_ else ""


def news_html(items: list[dict]) -> str:
    if not items:
        return "<p>Nothing found in the pages we could read.</p>"
    return '<div class="timeline">' + "".join(
        f'<div class="step">' + (f'<span class="when">{esc(n["date"])}</span>' if n["date"] else "") + esc(n["headline"]) + "</div>"
        for n in items
    ) + "</div>"


def _diff_class(d: str) -> str:
    d = str(d).strip().lower()
    return "easy" if d.startswith("e") else "hard" if d.startswith("h") else "medium"


def q_html(qs) -> str:
    """Questions as numbered rows with a topic tag and a difficulty tag."""
    rows = ""
    for i, q in enumerate(qs or [], 1):
        if isinstance(q, str):
            q = {"question": q, "topic": "", "difficulty": "Medium"}
        text = str(q.get("question", "")).strip()
        if not text:
            continue
        topic = str(q.get("topic", "")).strip()
        diff = str(q.get("difficulty", "Medium")).strip().title() or "Medium"
        tags = (f'<span class="tag topic">{esc(topic)}</span>' if topic else "") + \
               f'<span class="tag {_diff_class(diff)}">{esc(diff)}</span>'
        rows += f'<div class="q"><span class="q-num">{i}</span><div><div class="q-text">{esc(text)}</div>{tags}</div></div>'
    return rows or "<p>Nothing found.</p>"


ROUND_COLORS = ["#1F5C47", "#5E9473", "#8DBB9B", "#C0933F", "#C0933F"]


def rounds_html(rounds: list[dict], tips: list[str]) -> str:
    if not rounds and not tips:
        return "<p>Nothing found in the pages we could read.</p>"
    out = ""
    if rounds:
        out += '<div class="rounds">'
        for i, r_ in enumerate(rounds, 1):
            topics = "".join(f'<span class="chip blue">{esc(t)}</span>' for t in r_["topics"])
            note = f'<div class="rnote">{esc(r_["notes"])}</div>' if r_["notes"] else ""
            col_ = ROUND_COLORS[(i - 1) % len(ROUND_COLORS)]
            out += (f'<div class="round"><div class="rnum" style="background:{col_}">{i}</div><div class="rname">{esc(r_["name"])}</div>'
                    f'<div>{topics}</div>{note}</div>')
        out += "</div>"
    if tips:
        out += '<div class="tips"><b>Tips</b>' + ul(tips) + "</div>"
    return out


def match_html(matched: list[str], missing: list[str]) -> str:
    if not matched and not missing:
        return "<p>Upload a resume on the form above to see how your skills match this role.</p>"
    total = len(matched) + len(missing)
    pct = round(100 * len(matched) / total) if total else 0
    return (
        f'<div class="bd-top"><span>Skills covered</span><span>{len(matched)} of {total}</span></div>'
        f'<div class="bar big"><div class="fill" style="width:{pct}%;background:{score_color(pct)}"></div></div>'
        '<h4 style="margin-top:16px">You have</h4>' + chips(matched, "green") +
        '<h4 style="margin-top:12px">To work on</h4>' + chips(missing, "amber")
    )


def breakdown_html(parts: list[dict]) -> str:
    rows = ""
    for p_ in parts:
        pct = 100 * p_["value"] / p_["max"]
        color = score_color(int(pct))
        rows += (
            f'<div class="bd"><div class="bd-top"><span>{esc(p_["label"])}</span>'
            f'<span>{p_["value"]}/{p_["max"]}</span></div>'
            f'<div class="bar"><div class="fill" style="width:{pct:.0f}%;background:{color}"></div></div>'
            f'<div class="bd-ev">{esc(p_["evidence"])}</div></div>'
        )
    return rows


def score_color(score: int) -> str:
    if score >= 70:
        return GREEN
    if score >= 40:
        return AMBER
    return RED


def gauge_svg(score: int) -> str:
    color = score_color(score)
    circ = 339.29
    filled = circ * score / 100
    return (
        '<svg width="190" height="190" viewBox="0 0 140 140" xmlns="http://www.w3.org/2000/svg">'
        '<circle cx="70" cy="70" r="54" fill="none" stroke="#E4E9DD" stroke-width="12"/>'
        f'<circle cx="70" cy="70" r="54" fill="none" stroke="{color}" stroke-width="12" '
        f'stroke-linecap="round" stroke-dasharray="{filled:.1f} {circ}" transform="rotate(-90 70 70)">'
        f'<animate attributeName="stroke-dasharray" from="0 {circ}" to="{filled:.1f} {circ}" '
        'dur="1.2s" fill="freeze" calcMode="spline" keySplines="0.2 0.8 0.2 1" keyTimes="0;1"/></circle>'
        f'<text x="70" y="72" text-anchor="middle" font-size="34" font-weight="800" fill="#12261D">{score}</text>'
        '<text x="70" y="92" text-anchor="middle" font-size="11" fill="#66766B">out of 100</text>'
        "</svg>"
    )


# ---------------------------------------------------------------------------
# Schemas for structured Gemini output
# ---------------------------------------------------------------------------
class NewsItem(BaseModel):
    date: str = Field(description="e.g. 'Oct 2026' or '2025'; empty string if unknown")
    headline: str = Field(description="One short sentence")


class Round(BaseModel):
    name: str = Field(description="e.g. Online Assessment, DSA Round, System Design, Hiring Manager, HR")
    topics: list[str] = Field(description="2-4 short topics asked in this round")
    notes: str = Field(description="One line on difficulty or tips; add '(one user report)' if from a single source")


class CompanyDossier(BaseModel):
    company_name: str
    tldr: str = Field(description="One or two sentences: what the company is, in plain words")
    founded: str = Field(description="Year founded; empty string if unknown")
    headquarters: str = Field(description="City and country; empty string if unknown")
    employees: str = Field(description="Approximate headcount with year if known; empty string if unknown")
    funding: str = Field(description="Funding or listing status in one short phrase; empty string if unknown")
    summary: str = Field(description="3-4 sentences: what the company does, scale, main products")
    tech_stack: list[str] = Field(description="Concrete technologies named in the sources; empty list if none")
    recent_news: list[NewsItem] = Field(description="Up to 4 recent items, newest first; empty list if none")
    hiring_trends: str = Field(description="Active roles or hiring focus; empty string if unknown")
    interview_rounds: list[Round] = Field(description="The interview process as 2-5 ordered rounds; empty list if unknown")
    interview_tips: list[str] = Field(description="Up to 3 short, high-confidence tips; empty list if none")
    estimated_salary_range: str = Field(description="Salary or CTC ranges with source if possible; empty string if unknown")


class TrustReport(BaseModel):
    domain_presence: int = Field(description="0-30: official site, careers page and company presence found in the sources")
    domain_presence_evidence: str = Field(description="One sentence citing the evidence (or its absence)")
    no_upfront_fees: int = Field(description="0-30: 30 if no payment is requested anywhere, 0 if payment is requested")
    no_upfront_fees_evidence: str
    consistency: int = Field(description="0-20: posting details match the company's official careers page")
    consistency_evidence: str
    sentiment: int = Field(description="0-20: public reviews and scam reports")
    sentiment_evidence: str
    red_flags: list[str]
    positive_signals: list[str]
    reasoning: str = Field(description="Short overall explanation referencing the evidence")


class Question(BaseModel):
    question: str = Field(description="One clear sentence")
    topic: str = Field(description="Short tag, e.g. DSA, System Design, SQL, OOP, Leadership, Teamwork, Product")
    difficulty: str = Field(description="Easy, Medium or Hard")


class InterviewPrep(BaseModel):
    technical_questions: list[Question]
    behavioral_questions: list[Question]
    company_specific_questions: list[Question] = Field(
        description="Questions grounded in the company's recent news or products"
    )
    talking_points: list[str] = Field(description="Up to 5 one-line points the student should weave into answers")
    skills_matched: list[str] = Field(description="Skills from the student's resume that fit this role; empty if no resume")
    skills_missing: list[str] = Field(description="Skills this role needs that the resume lacks")


# ---------------------------------------------------------------------------
# TinyFish helpers (Search -> Fetch)
# ---------------------------------------------------------------------------
def tf_search(query: str, limit: int = 4) -> list:
    resp = tf_client.search.query(query=query)
    return list(resp.results[:limit])


def tf_fetch_items(urls: list[str], chars_per_page: int = 2500, min_chars: int = 300) -> list[dict]:
    """Fetch pages as markdown. Drops pages with too little readable text (video pages, login walls)."""
    items = []
    for start in range(0, len(urls), 10):  # TinyFish accepts at most 10 URLs per call
        resp = tf_client.fetch.get_contents(urls=urls[start:start + 10], format="markdown")
        for item in resp.results:
            text = (item.text or "").strip()
            if len(text) >= min_chars:
                items.append({"url": item.url, "title": item.title or item.url, "text": text[:chars_per_page]})
    return items


def items_to_context(items: list[dict]) -> str:
    return "\n".join(
        f"\n--- Source {i + 1}: {it['title']} ({it['url']}) ---\n{it['text']}" for i, it in enumerate(items)
    )


def tf_fetch(urls: list[str], chars_per_page: int = 2500) -> str:
    return items_to_context(tf_fetch_items(urls, chars_per_page))


def domain_of(url: str) -> str:
    m = re.match(r"https?://([^/]+)", url)
    return m.group(1).replace("www.", "") if m else url


def log(steps: list[str], msg: str):
    steps.append(msg)
    st.write("• " + msg)


# Pages that rarely give readable text (video, social) are skipped.
BLOCKED_DOMAINS = (
    "youtube.com", "youtu.be", "facebook.com", "instagram.com", "twitter.com", "x.com",
    "tiktok.com", "pinterest.com", "snapchat.com",
)
LOW_PRIORITY = ("linkedin.com", "quora.com", "glassdoor.com", "fishbowlapp.com")

REDDIT_UA = "Mozilla/5.0 (compatible; JobVentra/1.0; student hackathon project)"


_reddit_status = {"err": ""}


def _reddit_get(url: str):
    last = None
    for u in (url, url.replace("://www.reddit.com", "://old.reddit.com")):
        try:
            req = urllib.request.Request(u, headers={"User-Agent": REDDIT_UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=8) as r:
                return json.loads(r.read().decode("utf-8", "ignore"))
        except Exception as e:  # blocked, rate limited, offline...
            last = e
    _reddit_status["err"] = f"HTTP {getattr(last, 'code', '')}".strip() if hasattr(last, "code") else type(last).__name__
    raise last


def _reddit_norm(url: str) -> str:
    return re.sub(r"^https?://[^/]*reddit\.com", "https://www.reddit.com", re.split(r"[?#]", url)[0]).rstrip("/")


def reddit_search(q: str, n: int = 3) -> list[str]:
    """Find the most upvoted / discussed Reddit threads for a query."""
    try:
        data = _reddit_get(
            "https://www.reddit.com/search.json?"
            + urllib.parse.urlencode({"q": q, "sort": "relevance", "t": "all", "limit": 10, "raw_json": 1})
        )
        posts = [c["data"] for c in data["data"]["children"] if c.get("kind") == "t3"]
    except Exception:
        return []
    posts = [p_ for p_ in posts if p_.get("score", 0) >= 3 or p_.get("num_comments", 0) >= 5]
    posts.sort(key=lambda p_: p_.get("score", 0) + 2 * p_.get("num_comments", 0), reverse=True)
    return ["https://www.reddit.com" + p_["permalink"] for p_ in posts[:n]]


def reddit_thread_text(url: str) -> str | None:
    """Return a thread as text with upvote scores, keeping only well-upvoted comments."""
    if "/comments/" not in url:
        return None
    try:
        data = _reddit_get(
            _reddit_norm(url) + ".json?" + urllib.parse.urlencode({"sort": "top", "limit": 15, "raw_json": 1})
        )
        post = data[0]["data"]["children"][0]["data"]
        comments = [c["data"] for c in data[1]["data"]["children"] if c.get("kind") == "t1" and c["data"].get("body")]
    except Exception:
        return None
    comments.sort(key=lambda c: c.get("score", 0), reverse=True)
    strong = [c for c in comments if c.get("score", 0) >= 2] or comments[:3]
    lines = [
        f"[Reddit r/{post.get('subreddit', '?')}, thread score +{post.get('score', 0)}, "
        f"{post.get('num_comments', 0)} comments] {post.get('title', '')}",
        f"Post: {(post.get('selftext') or '')[:800]}",
        "Top comments:",
    ]
    for c in strong[:6]:
        lines.append(f"  [+{c.get('score', 0)}] {re.sub(chr(10) + '+', ' ', c['body'])[:450]}")
    return "\n".join(lines)


def _safe_search(q: str, limit: int) -> list:
    try:
        return tf_search(q, limit)
    except Exception:
        return []


def research(queries, steps: list[str], limit: int = 8, reddit_query: str | None = None) -> tuple[str, list[str]]:
    """Run several focused TinyFish searches, read the best distinct pages, and add
    upvote-scored Reddit discussion. Returns (context text, source urls actually read)."""
    if isinstance(queries, str):
        queries = [queries]
    log(steps, f"TinyFish Search: {len(queries)} focused queries")
    with ThreadPoolExecutor(max_workers=min(7, len(queries))) as pool:
        batches = list(pool.map(lambda q: _safe_search(q, 4), queries))

    good, low, reddit_urls, seen_domains = [], [], [], {}
    for batch in batches:
        for r in batch:
            dom = domain_of(r.url)
            if any(dom == b or dom.endswith("." + b) for b in BLOCKED_DOMAINS):
                continue
            if dom.endswith("reddit.com"):
                reddit_urls.append(r.url)
                continue
            if seen_domains.get(dom, 0) >= 2:
                continue
            seen_domains[dom] = seen_domains.get(dom, 0) + 1
            (low if any(dom.endswith(l) for l in LOW_PRIORITY) else good).append(r.url)

    if reddit_query:
        reddit_urls = reddit_search(reddit_query) + reddit_urls
    seen_ids, threads, thread_urls, fallback = set(), [], [], []
    for u in reddit_urls:
        m = re.search(r"/comments/(\w+)", u)
        key = m.group(1) if m else u
        if key in seen_ids or len(seen_ids) >= 4:
            continue
        seen_ids.add(key)
        text = reddit_thread_text(u)
        if text:
            threads.append(text)
            thread_urls.append(_reddit_norm(u))
        else:
            fallback.append(u)
    if threads:
        log(steps, f"Reddit: read {len(threads)} thread(s) with upvote scores")
    elif reddit_urls:
        why = f" ({_reddit_status['err']})" if _reddit_status["err"] else ""
        log(steps, f"Reddit: upvote scores unavailable{why}, reading thread text instead")

    urls = list(dict.fromkeys(fallback[:3] + (good + low[:2])[:limit]))[:10]
    log(steps, f"Picked {len(urls)} web pages: " + ", ".join(dict.fromkeys(domain_of(u) for u in urls)))
    log(steps, "TinyFish Fetch: reading pages as clean markdown")
    items = tf_fetch_items(urls)
    skipped = len(urls) - len(items)
    if skipped:
        log(steps, f"Skipped {skipped} page(s) with no readable text")

    context = items_to_context(items)
    if threads:
        context += (
            "\n\n--- COMMUNITY DISCUSSION (Reddit). [+N] is the upvote count; higher means more community "
            "agreement ---\n" + "\n\n".join(threads)[:7000]
        )
    return context, [it["url"] for it in items] + thread_urls


# ---------------------------------------------------------------------------
# Gemini helper
# ---------------------------------------------------------------------------
_clients: dict = {}


def _call_groq(model: str, prompt: str, schema: type[BaseModel]) -> str:
    if "groq" not in _clients:
        from groq import Groq

        _clients["groq"] = Groq()  # reads GROQ_API_KEY from the environment
    resp = _clients["groq"].chat.completions.create(
        model=model,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You are a careful analyst. Reply with one valid JSON object and nothing else."},
            {
                "role": "user",
                "content": prompt + "\n\nReturn ONLY a JSON object that matches this JSON schema:\n"
                + json.dumps(schema.model_json_schema()),
            },
        ],
    )
    return resp.choices[0].message.content


def _call_gemini(model: str, prompt: str, schema: type[BaseModel]) -> str:
    from google import genai
    from google.genai import types

    if "gemini" not in _clients:
        _clients["gemini"] = genai.Client()  # reads GEMINI_API_KEY
    resp = _clients["gemini"].models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json", response_schema=schema, temperature=0.2
        ),
    )
    return resp.text


def _plans() -> list[tuple[str, list[str], object]]:
    """Provider order: the chosen one first, then the other if its API key exists."""
    plans = {
        "groq": ("groq", GROQ_MODELS, _call_groq, bool(os.getenv("GROQ_API_KEY"))),
        "gemini": ("gemini", GEMINI_MODELS, _call_gemini, bool(os.getenv("GEMINI_API_KEY"))),
    }
    order = [LLM_PROVIDER] + [k for k in plans if k != LLM_PROVIDER]
    return [(n, m, fn) for k in order if k in plans for (n, m, fn, has_key) in [plans[k]] if has_key or k == LLM_PROVIDER]


def _code(e: Exception):
    return getattr(e, "status_code", None) or getattr(e, "code", None)


def _wait_for(e: Exception, attempt: int) -> int:
    try:
        ra = float(e.response.headers.get("retry-after"))  # Groq sends this on 429
        return int(min(max(ra, 1), 20))
    except Exception:
        return 2 ** (attempt + 1)


def _short(e: Exception) -> str:
    msg = getattr(e, "message", None) or str(e)
    return re.sub(r"\s+", " ", str(msg))[:160]


def _discover_groq(exclude: list[str]) -> list[str]:
    """Ask Groq which chat models this key can use, preferring large general ones."""
    try:
        if "groq" not in _clients:
            from groq import Groq

            _clients["groq"] = Groq()
        ids = [m.id for m in _clients["groq"].models.list().data]
    except Exception:
        return []
    skip = ("whisper", "guard", "tts", "orpheus", "embed", "playai", "distil")
    ids = [i for i in ids if i not in exclude and not any(k in i.lower() for k in skip)]
    ids.sort(key=lambda i: (not any(k in i.lower() for k in ("70b", "120b", "versatile", "scout", "maverick")), i))
    return ids[:3]


def llm_structured(prompt: str, schema: type[BaseModel], status=None) -> dict:
    """Ask the LLM for JSON matching `schema`. Retries busy errors with backoff,
    fixes malformed JSON once, then falls back to the next model or provider."""
    last_err: Exception | None = None
    for provider, models, call in _plans():
        models, dead, discovered, i = list(models), set(), False, 0
        while i < len(models):
            model = models[i]
            i += 1
            for attempt in range(4):
                try:
                    raw = call(model, prompt, schema)
                    try:
                        return schema.model_validate_json(raw).model_dump()
                    except ValidationError:
                        raw = call(model, prompt + "\n\nYour previous JSON was invalid. Return corrected JSON only.", schema)
                        return schema.model_validate_json(raw).model_dump()
                except ValidationError as e:
                    last_err = e
                    if status is not None:
                        st.write(f"• {model} returned badly formatted output")
                    break
                except Exception as e:
                    last_err = e
                    code = _code(e)
                    name = type(e).__name__
                    if code in (400, 404):
                        dead.add(model)
                        if status is not None:
                            st.write(f"• {model} unavailable ({code}): {_short(e)}")
                        break
                    if code in (401, 403) or (code is None and "Connection" not in name and "Timeout" not in name):
                        raise
                    if attempt < 3:
                        wait = _wait_for(e, attempt)
                        if status is not None:
                            st.write(f"• {model} is busy ({code or 'network'}), retrying in {wait}s...")
                        time.sleep(wait)
                    elif status is not None:
                        st.write(f"• {model} stayed busy, moving on...")
            if provider == "groq" and not discovered and i == len(models) and len(dead) == len(models):
                discovered = True
                extra = _discover_groq(models)
                if extra and status is not None:
                    st.write("• Looking up models your Groq key can use: " + ", ".join(extra))
                models += extra
    if last_err is None:
        raise RuntimeError("No AI provider is configured. Add GROQ_API_KEY to your .env file.")
    raise last_err


def friendly_error(e: Exception) -> str:
    code = _code(e)
    if code in RETRYABLE:
        return "The AI service is busy or rate limited. Wait about a minute and press the button again."
    if code in (401, 403):
        return "The AI provider rejected the API key. Check GROQ_API_KEY in your .env file."
    if isinstance(e, ValidationError):
        return "The AI returned an answer in the wrong format. Please press the button again."
    if isinstance(e, ModuleNotFoundError):
        return f"A package is missing: {e}. Run: pip install groq"
    return f"Something went wrong: {e}"


# ---------------------------------------------------------------------------
# Rule-based red flag scan
# ---------------------------------------------------------------------------
FEE_PATTERNS = [
    (r"registration fee", "Asks for a registration fee"),
    (r"security deposit", "Asks for a security deposit"),
    (r"training fee|training kit", "Asks for a training fee or kit payment"),
    (r"processing fee", "Asks for a processing fee"),
    (r"refundable deposit", "Asks for a 'refundable' deposit"),
    (r"document verification (fee|charge)", "Charges for document verification"),
    (r"laptop deposit", "Asks for a laptop deposit"),
]
CONTACT_PATTERNS = [
    (r"whatsapp", "Recruiter contact is via WhatsApp"),
    (r"telegram", "Recruiter contact is via Telegram"),
    (r"@(gmail|yahoo|outlook|hotmail)\.com", "Free email domain instead of a company domain"),
]
HYPE_PATTERNS = [
    (r"earn (rs\.?|₹)\s?\d[\d,]*\s?(/|per)\s?(day|week)", "Unrealistic pay promise"),
    (r"no interview", "Promises a job with no interview"),
    (r"guaranteed (job|placement)", "Guarantees a job or placement"),
]


def rule_based_flags(text: str) -> list[str]:
    t = text.lower()
    return [msg for pat, msg in FEE_PATTERNS + CONTACT_PATTERNS + HYPE_PATTERNS if re.search(pat, t)]


# ---------------------------------------------------------------------------
# Scoring: sub-scores come from Gemini, the total and verdict are computed here
# ---------------------------------------------------------------------------
SCORE_PARTS = [
    ("Web presence", "domain_presence", "domain_presence_evidence", 30),
    ("No upfront fees", "no_upfront_fees", "no_upfront_fees_evidence", 30),
    ("Consistency with official sources", "consistency", "consistency_evidence", 20),
    ("Public sentiment", "sentiment", "sentiment_evidence", 20),
]


def score_cap(text: str) -> tuple[int, str]:
    """Hard ceilings from deterministic rules, so a fee scam can never score high."""
    t = text.lower()
    if any(re.search(pat, t) for pat, _ in FEE_PATTERNS):
        return 35, "The posting asks for upfront payment, so the score is capped at 35."
    soft = sum(1 for pat, _ in CONTACT_PATTERNS + HYPE_PATTERNS if re.search(pat, t))
    if soft >= 2:
        return 50, "Several scam-style patterns were found in the posting, so the score is capped at 50."
    return 100, ""


def verdict_for(score: int) -> str:
    if score >= 90:
        return "Highly Trusted"
    if score >= 70:
        return "Trusted"
    if score >= 40:
        return "Use Caution"
    return "High Risk"


def finalize_score(report: dict, posting_text: str) -> dict:
    breakdown, total = [], 0
    for label, key, ev_key, mx in SCORE_PARTS:
        try:
            val = max(0, min(mx, int(report.get(key, 0))))
        except (TypeError, ValueError):
            val = 0
        total += val
        breakdown.append({"label": label, "value": val, "max": mx, "evidence": report.get(ev_key, "")})
    cap, note = score_cap(posting_text)
    score = min(total, cap)
    return {
        "trust_score": score,
        "verdict": verdict_for(score),
        "breakdown": breakdown,
        "cap_note": note if total > cap else "",
    }


def extract_resume(f) -> str:
    """Read text from an uploaded PDF or TXT resume. Returns '' if nothing readable."""
    try:
        if f.name.lower().endswith(".pdf"):
            from pypdf import PdfReader

            reader = PdfReader(f)
            return "\n".join((pg.extract_text() or "") for pg in reader.pages).strip()
        return f.getvalue().decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Demo samples
# ---------------------------------------------------------------------------
SCAM_SAMPLE = {
    "v_company": "GlobalTech Solutions Pvt Ltd",
    "v_url": "",
    "v_text": (
        "URGENT HIRING! Work from home data entry. Earn ₹50,000 per week, no interview, "
        "guaranteed job. Pay a refundable security deposit of ₹2,500 and registration fee of ₹1,000 "
        "to confirm your seat. Contact HR on WhatsApp +91 90000 00000 or globaltech.hr@gmail.com"
    ),
}
LEGIT_SAMPLE = {
    "v_company": "Razorpay",
    "v_url": "",
    "v_text": (
        "Software Development Engineer Intern - Bengaluru. Apply via our careers page. "
        "Selection includes an online assessment and technical interviews. Stipend as per company policy."
    ),
}


def load_sample(sample: dict):
    for k, v in sample.items():
        st.session_state[k] = v


# ---------------------------------------------------------------------------
# Shared sub-page header
# ---------------------------------------------------------------------------
def subpage_header(title: str, subtitle: str, key: str = "", side=None):
    c1, c2 = st.columns([1, 3])
    c1.button("← Back to home", on_click=go, args=("home",), key="back_home")
    c2.markdown(f'<div class="topbar-logo">{img_tag("logo_small", "JobVentra")}</div>', unsafe_allow_html=True)
    icon = feature_icon(key, title) if key in ACCENTS else ""

    def _title_block():
        st.markdown(f'<div class="page-title">{icon}<span>{esc(title)}</span></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="page-sub">{esc(subtitle)}</div>', unsafe_allow_html=True)

    if side is None:
        _title_block()
    else:
        left, right = st.columns([1.35, 1], gap="large")
        with left:
            _title_block()
        with right:
            side()


# ---------------------------------------------------------------------------
# PAGE: Home
# ---------------------------------------------------------------------------
def page_home():
    st.markdown(f'<div class="brand-logo">{img_tag("logo", "JobVentra")}</div>', unsafe_allow_html=True)
    st.markdown(
        """
<div class="home-hero nologo">
  <div class="eyebrow">Placement intelligence, live from the web</div>
  <p>Is this offer real? Know the company, the risks and the questions before you apply.</p>
</div>
""",
        unsafe_allow_html=True,
    )

    features = [
        ("dossier", "Company Dossier",
         "Get a one-page live profile: news, tech stack, hiring focus, salaries and interview experiences."),
        ("verify", "Posting Verifier",
         "Paste a job offer or link and get a trust score with red flags, backed by live web checks."),
        ("prep", "Interview Prep",
         "Questions and talking points tailored to the company's latest news and your own profile."),
    ]
    st.markdown(
        "<style>" + "".join(
            f'.st-key-nav_{k} button {{ background:{b} !important; border-color:{b} !important; }}'
            f'.st-key-nav_{k} button:hover {{ background:{d} !important; border-color:{d} !important; }}'
            for k, (b, _l, d) in ACCENTS.items()) + "</style>",
        unsafe_allow_html=True,
    )
    cols = st.columns(3, gap="large")
    for i, (col, (key, title, desc)) in enumerate(zip(cols, features)):
        with col:
            st.markdown(
                f'<div class="feature" style="animation-delay:{0.9 + i * 0.12}s;border-top:5px solid {ACCENTS[key][0]}"><div class="icon">{feature_icon(key, title)}</div><h3>{esc(title)}</h3><p>{esc(desc)}</p></div>',
                unsafe_allow_html=True,
            )
            st.button(f"Open {title}  →", on_click=go, args=(key,), key=f"nav_{key}")
    st.markdown(
        '<div class="home-foot">Live web evidence from TinyFish Search and Fetch · analysis by Groq</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# PAGE: Company Dossier
# ---------------------------------------------------------------------------
def page_dossier():
    subpage_header("Company Dossier", "A live, one-page profile of any company, built from the open web.", "dossier")
    company = st.text_input("Company name", placeholder="e.g. Razorpay, Swiggy, Zerodha", key="d_company")

    if st.button("Generate live dossier", type="primary", key="d_btn"):
        if not company.strip():
            st.warning("Please enter a company name.")
        else:
            steps: list[str] = []
            try:
                with st.status("Agent is researching the live web...", expanded=True) as status:
                    context, urls = research(
                        [
                            f"{company} company overview wikipedia",
                            f"{company} latest news",
                            f"{company} careers hiring roles",
                            f"{company} tech stack engineering blog stackshare",
                            f"{company} interview experience questions DSA rounds",
                            f"{company} salary CTC SDE",
                            f"{company} headquarters founded employees funding",
                            f"{company} interview experience reddit",
                        ],
                        steps,
                        reddit_query=f"{company} interview experience",
                    )
                    log(steps, "AI analysis: cross-checking sources into a structured dossier")
                    prompt = f"""You are a placement intelligence analyst. Using ONLY the context below, build a useful
dossier on '{company}' for a student preparing for placements.

Rules:
- tldr: one or two plain sentences saying what the company is.
- founded, headquarters, employees, funding: short facts from the sources; empty string if not stated.
- summary: 3-4 informative sentences (what it does, scale, main products) from the sources.
- tech_stack: concrete technologies named in the sources (languages, frameworks, cloud, data tools).
- interview_rounds: the interview process as 2-5 ordered rounds. For each: a name, 2-4 short topics asked
  (DSA, system design, CS fundamentals...), and a one-line note on difficulty or tips. Trust points confirmed by
  two or more sources, or by comments with many upvotes (shown as [+N]). Label single-source claims
  "(one user report)". Ignore jokes, rants and unverifiable claims.
- interview_tips: up to 3 short tips that several sources agree on.
- recent_news: up to 4 items, newest first, each with a date (month and year if possible) and a short headline.
- salary: ranges and where they came from.
- If something truly is not in the context, use an empty list or empty string. Never write "Not found".

Context:
{context}"""
                    dossier = llm_structured(prompt, CompanyDossier, status)
                    status.update(label="Dossier complete", state="complete", expanded=False)
                st.session_state["dossier"] = dossier
                st.session_state["dossier_urls"] = urls
                st.session_state["dossier_steps"] = steps
            except Exception as e:
                st.error(friendly_error(e))

    d = st.session_state.get("dossier")
    if d:
        d = dict(d)
        for k in ("tech_stack", "interview_tips"):
            d[k] = real(d.get(k))
        for k in ("summary", "tldr", "hiring_trends", "estimated_salary_range", "founded", "headquarters", "employees", "funding"):
            d[k] = txt(d.get(k))
        if not d["tldr"] and d["summary"]:
            d["tldr"] = re.split(r"(?<=[.!?])\s", d["summary"])[0][:200]
        news = []
        for n_ in d.get("recent_news") or []:
            if isinstance(n_, str):  # older saved result
                n_ = {"date": "", "headline": n_}
            if txt(n_.get("headline")):
                news.append({"date": txt(n_.get("date")), "headline": txt(n_.get("headline"))})
        d["recent_news"] = news
        rounds = []
        for r_ in d.get("interview_rounds") or []:
            if isinstance(r_, dict) and txt(r_.get("name")):
                rounds.append({"name": txt(r_.get("name")), "topics": real(r_.get("topics")), "notes": txt(r_.get("notes"))})
        d["interview_rounds"] = rounds
        if not rounds and not d["interview_tips"] and d.get("interview_experiences"):  # older saved result
            d["interview_tips"] = real(d["interview_experiences"])

        name = d["company_name"]
        urls = st.session_state.get("dossier_urls", [])
        none_msg = "Nothing found in the pages we could read."

        st.markdown(
            f'<div class="co-head"><div class="co-name">{esc(name)}</div>'
            + (f'<div class="co-tldr">{esc(d["tldr"])}</div>' if d["tldr"] else "")
            + "</div>",
            unsafe_allow_html=True,
        )
        if len(urls) < 3:
            st.info(f"Only {len(urls)} readable source(s) were found, so some sections may be thin. "
                    "Try the company's full name, for example 'Swiggy Limited'.")

        facts = [(l_, v_) for l_, v_ in (("Founded", d["founded"]), ("Headquarters", d["headquarters"]),
                                          ("Employees", d["employees"]), ("Funding", d["funding"])) if v_]
        if facts:
            for col, (l_, v_), ac in zip(st.columns(len(facts)), facts, ["blue", "teal", "green", "amber"]):
                col.markdown(tile(l_, v_, ac), unsafe_allow_html=True)
            st.write("")

        t_over, t_int, t_tech, t_sal, t_src = st.tabs(
            [":material/apartment: Overview", ":material/groups: Interview", ":material/code: Tech & hiring",
             ":material/payments: Salary", ":material/link: Sources"]
        )
        with t_over:
            st.markdown(card("About", f"<p>{esc(d['summary'] or none_msg)}</p>", "blue"), unsafe_allow_html=True)
            st.markdown(card("Recent news", news_html(d["recent_news"]), "teal"), unsafe_allow_html=True)
        with t_int:
            st.markdown(card("Interview process", rounds_html(d["interview_rounds"], d["interview_tips"]), "green"), unsafe_allow_html=True)
            st.button("Prepare for this company  \u2192", type="primary", on_click=go_prep, args=(name,), key="to_prep")
        with t_tech:
            st.markdown(card("Tech stack", chips(d["tech_stack"], "blue"), "violet"), unsafe_allow_html=True)
            st.markdown(card("Hiring focus", f"<p>{esc(d['hiring_trends'] or none_msg)}</p>", "amber"), unsafe_allow_html=True)
        with t_sal:
            st.markdown(card("Salary & compensation", f"<p>{esc(d['estimated_salary_range'] or none_msg)}</p>", "green"), unsafe_allow_html=True)
            st.caption("Salary figures come from public posts and can be out of date. Treat them as rough ranges.")
        with t_src:
            st.markdown(card("Sources", sources_html(urls), "slate"), unsafe_allow_html=True)
            st.markdown(card("How the agent got this", timeline_html(st.session_state.get("dossier_steps", [])), "slate"), unsafe_allow_html=True)
            md = (
                f"# {name} - JobVentra Dossier\n\n{d['tldr']}\n\n{d['summary']}\n\n"
                f"Founded: {d['founded']} | HQ: {d['headquarters']} | Employees: {d['employees']} | Funding: {d['funding']}\n\n"
                "## Recent news\n" + "\n".join(f"- {n['date']} {n['headline']}".strip() for n in d["recent_news"]) + "\n\n"
                "## Interview process\n"
                + "\n".join(f"{i}. {r_['name']}: {', '.join(r_['topics'])}. {r_['notes']}" for i, r_ in enumerate(d["interview_rounds"], 1))
                + "\n" + "\n".join(f"- Tip: {x}" for x in d["interview_tips"]) + "\n\n"
                f"## Hiring focus\n{d['hiring_trends']}\n\n"
                f"## Tech stack\n{', '.join(d['tech_stack'])}\n\n"
                f"## Salary range\n{d['estimated_salary_range']}\n\n"
                "## Sources\n" + "\n".join(f"- {u}" for u in urls)
            )
            st.download_button("Download dossier (.md)", md, file_name="dossier.md")


# ---------------------------------------------------------------------------
# PAGE: Posting Verifier
# ---------------------------------------------------------------------------
def page_verify():
    def samples_box():
        with st.container(key="samples"):
            st.markdown(
                '<div class="samples-title">Sample postings</div>'
                '<div class="samples-sub">Load an example to see how the verifier works.</div>',
                unsafe_allow_html=True,
            )
            b1, b2 = st.columns(2)
            b1.button("Scam posting", icon=":material/gpp_bad:", on_click=load_sample, args=(SCAM_SAMPLE,),
                      key="s_scam", use_container_width=True)
            b2.button("Legit company", icon=":material/verified_user:", on_click=load_sample, args=(LEGIT_SAMPLE,),
                      key="s_legit", use_container_width=True)

    subpage_header("Posting Verifier", "Paste a job posting, offer message or link. We check it against the live web.",
                   "verify", side=samples_box)

    v_company = st.text_input("Company name", key="v_company")
    v_url = st.text_input("Job posting URL (optional)", key="v_url")
    v_text = st.text_area("Posting / offer text (optional)", height=150, key="v_text")

    if st.button("Verify posting", type="primary", key="v_btn"):
        if not (v_company.strip() or v_url.strip() or v_text.strip()):
            st.warning("Give at least a company name, a URL, or the posting text.")
        else:
            steps: list[str] = []
            try:
                with st.status("Verifying against the live web...", expanded=True) as status:
                    posting_text = v_text
                    if v_url.strip():
                        log(steps, f"TinyFish Fetch: reading the posting at {domain_of(v_url.strip())}")
                        posting_text += "\n" + tf_fetch([v_url.strip()], chars_per_page=4000)

                    flags = rule_based_flags(posting_text)
                    log(steps, f"Rule scan: {len(flags)} red flag pattern(s) found in the posting text")

                    name = v_company.strip() or "the company in this job posting"
                    web_ctx, web_urls = research(
                        [f"{name} official website careers", f"{name} reviews scam fraud complaints"],
                        steps,
                        limit=6,
                        reddit_query=f"{name} scam OR fake OR legit",
                    )

                    log(steps, "AI analysis: weighing the evidence into a trust score")
                    prompt = f"""You are a recruitment-fraud analyst helping Indian college students.
Judge this job posting and company by scoring four separate criteria. Do NOT give an
overall score; the app adds them up.

- domain_presence (0-30): official website, careers page and real company presence in the sources
- no_upfront_fees (0-30): 30 if nothing asks the candidate to pay, 0 if any payment is requested
- consistency (0-20): posting details match the company's official careers page
- sentiment (0-20): public reviews and scam reports

Rules: score only what the sources support. If there is NO evidence for a criterion, give it 0,
not a middle value, and say "no evidence found". Be strict and specific, and give one sentence
of evidence for each criterion. Do not invent facts.

Company: {name}
Posting URL: {v_url or 'n/a'}

Rule-based red flags already detected: {flags or 'none'}

Posting text:
{posting_text[:5000] or 'n/a'}

Live web research:
{web_ctx}"""
                    report = llm_structured(prompt, TrustReport, status)
                    status.update(label="Verification complete", state="complete", expanded=False)

                report["red_flags"] = list(dict.fromkeys(flags + report["red_flags"]))
                report.update(finalize_score(report, posting_text))
                st.session_state["report"] = report
                st.session_state["report_urls"] = web_urls
                st.session_state["report_steps"] = steps
            except Exception as e:
                st.error(friendly_error(e))

    r = st.session_state.get("report")
    if r:
        score = max(0, min(100, int(r["trust_score"])))
        color = score_color(score)
        bg = {GREEN: "#E3F7EA", AMBER: "#FFF3DC", RED: "#FEE9E9"}[color]

        left, right = st.columns([1, 2])
        with left:
            st.markdown(
                f'<div class="card" style="text-align:center">{gauge_svg(score)}<br>'
                f'<span class="badge" style="background:{bg};color:{color}">{esc(r["verdict"])}</span></div>',
                unsafe_allow_html=True,
            )
        with right:
            if r.get("cap_note"):
                st.markdown(f'<div class="capnote">{esc(r["cap_note"])}</div>', unsafe_allow_html=True)
            st.markdown(card("Why this score", f"<p>{esc(r['reasoning'])}</p>"), unsafe_allow_html=True)
            st.markdown(card("Score breakdown", breakdown_html(r.get("breakdown", []))), unsafe_allow_html=True)
            st.markdown(
                card("How the agent checked", timeline_html(st.session_state.get("report_steps", []))),
                unsafe_allow_html=True,
            )

        c3, c4 = st.columns(2)
        with c3:
            st.markdown(card("Red flags", chips(r["red_flags"], "red")), unsafe_allow_html=True)
        with c4:
            st.markdown(card("Positive signals", chips(r["positive_signals"], "green")), unsafe_allow_html=True)
        st.markdown(card("Sources", sources_html(st.session_state.get("report_urls", []))), unsafe_allow_html=True)
        st.caption("Automated assessment, not a guarantee. Never pay money to secure a job.")


# ---------------------------------------------------------------------------
# PAGE: Interview Prep
# ---------------------------------------------------------------------------
def page_prep():
    subpage_header("Interview Prep", "Questions and talking points grounded in live company news and your profile.", "prep")
    if not st.session_state.get("p_company"):
        st.session_state["p_company"] = st.session_state.get("dossier", {}).get("company_name", "")
    p_company = st.text_input("Company", key="p_company")
    p_role = st.text_input("Role", placeholder="e.g. Backend Engineer Intern", key="p_role")
    resume_file = st.file_uploader("Upload your resume (PDF or TXT, optional)", type=["pdf", "txt"], key="p_resume")
    resume_text = extract_resume(resume_file) if resume_file else ""
    if resume_file and not resume_text:
        st.warning("Couldn't read text from that file (scanned PDFs can't be read). Type your skills below instead.")
    elif resume_text:
        st.success(f"Resume read: about {len(resume_text.split())} words.")
    p_profile = st.text_area(
        "Extra details (optional: skills, projects, year, CGPA)",
        height=110,
        key="p_profile",
        placeholder="e.g. 3rd year CSE, Python, FastAPI, built a RAG chatbot, 8.2 CGPA",
    )

    if st.button("Build interview prep", type="primary", key="p_btn"):
        if not p_company.strip() or not p_role.strip():
            st.warning("Enter both company and role.")
        else:
            steps: list[str] = []
            try:
                with st.status("Preparing grounded interview prep...", expanded=True) as status:
                    ctx, urls = research(
                        [
                            f"{p_company} {p_role} interview questions",
                            f"{p_company} interview experience",
                            f"{p_company} latest news",
                            f"{p_company} engineering tech stack",
                            f"{p_company} interview experience reddit",
                        ],
                        steps,
                        reddit_query=f"{p_company} {p_role} interview",
                    )
                    log(steps, "AI analysis: personalising questions to your profile")
                    profile_block = (("Resume:\n" + resume_text[:6000] + "\n\n") if resume_text else "") + (
                        p_profile or ("" if resume_text else "Not provided")
                    )
                    prompt = f"""You are an interview coach. Using the live web context and the student's
profile, create interview prep for the role '{p_role}' at '{p_company}'.
Ground company-specific questions in the context. Do not fabricate facts about the company.
Reddit comments show upvotes as [+N]; prefer topics repeated across sources or heavily upvoted.
Give 5 technical, 4 behavioral and 4 company-specific questions, one sentence each, each with a short topic tag
and a difficulty of Easy, Medium or Hard. Give at most 5 one-line talking points.
If a resume is included, list in skills_matched the resume skills that fit the role and in skills_missing the
skills the role needs that the resume lacks, and refer to its real projects in the talking points.
Never invent resume details. If there is no resume, leave skills_matched empty.

Student profile:
{profile_block}

Live web context:
{ctx}"""
                    prep = llm_structured(prompt, InterviewPrep, status)
                    status.update(label="Prep ready", state="complete", expanded=False)
                st.session_state["prep"] = prep
                st.session_state["prep_urls"] = urls
            except Exception as e:
                st.error(friendly_error(e))

    prep = st.session_state.get("prep")
    if prep:
        prep = dict(prep)
        matched, missing = real(prep.get("skills_matched")), real(prep.get("skills_missing"))
        if not matched and not missing:  # older saved result
            missing = real(prep.get("skill_gaps"))
        t_tech, t_beh, t_co, t_talk, t_skill = st.tabs(
            [":material/code: Technical", ":material/psychology: Behavioral", ":material/apartment: Company-specific",
             ":material/forum: Talking points", ":material/checklist: Skill match"]
        )
        with t_tech:
            st.markdown(card("Technical questions", q_html(prep.get("technical_questions"))), unsafe_allow_html=True)
        with t_beh:
            st.markdown(card("Behavioral questions", q_html(prep.get("behavioral_questions"))), unsafe_allow_html=True)
        with t_co:
            st.markdown(
                card("Company-specific questions", q_html(prep.get("company_specific_questions"))), unsafe_allow_html=True
            )
        with t_talk:
            st.markdown(card("Talking points", ul(real(prep.get("talking_points")))), unsafe_allow_html=True)
        with t_skill:
            st.markdown(card("How your resume fits this role", match_html(matched, missing)), unsafe_allow_html=True)
        with st.expander("Sources"):
            st.markdown(sources_html(st.session_state.get("prep_urls", [])), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
PAGES = {
    "home": page_home,
    "dossier": page_dossier,
    "verify": page_verify,
    "prep": page_prep,
}
PAGES.get(st.session_state["page"], page_home)()