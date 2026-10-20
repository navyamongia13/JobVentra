import base64
import html
import json
import re
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from tinyfish import TinyFish

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
load_dotenv()  # reads TINYFISH_API_KEY and GEMINI_API_KEY from .env

st.set_page_config(page_title="JobVentra", page_icon="🧭", layout="wide")

tf_client = TinyFish()
gemini_client = genai.Client()
MODEL = "gemini-3.8-flash"

BLUE = "#2F6FED"
GREEN = "#16A34A"
AMBER = "#D97706"
RED = "#DC2626"

if "page" not in st.session_state:
    st.session_state["page"] = "home"


def go(page: str):
    st.session_state["page"] = page


# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"], .stMarkdown, button, input, textarea {
  font-family: 'Plus Jakarta Sans', sans-serif !important;
}
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDeployButton"] { visibility: hidden; height: 0; }
header[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1rem; max-width: 1150px; }

/* ---------- Home hero ---------- */
.home-hero {
  background: linear-gradient(135deg, #2F6FED 0%, #3AA6D9 55%, #34C38F 100%);
  border-radius: 28px; padding: 38px 40px 34px; color: #fff; text-align: center;
  box-shadow: 0 16px 40px rgba(47,111,237,.25); margin-bottom: 20px;
}
.home-hero .eyebrow { font-weight: 700; letter-spacing: .18em; font-size: .85rem; opacity: .85; text-transform: uppercase; }
.home-hero h1 {
  margin: 4px 0 6px; font-size: 4.2rem; font-weight: 800; letter-spacing: -.03em; color: #fff; line-height: 1.05;
}
.home-hero p { margin: 0 auto; max-width: 640px; font-size: 1.15rem; opacity: .96; color: #fff; }
.pill {
  display: inline-block; background: rgba(255,255,255,.2); border: 1px solid rgba(255,255,255,.35);
  padding: 7px 16px; border-radius: 999px; font-size: .88rem; font-weight: 600; margin: 0 5px;
}

/* ---------- Feature cards on home ---------- */
.feature {
  background: #fff; border: 1px solid #E3EAF8; border-radius: 22px 22px 0 0; padding: 22px 22px 16px;
  text-align: center; box-shadow: 0 6px 18px rgba(15,23,42,.05); border-bottom: none;
}
.feature .icon { display: flex; justify-content: center; }
.feature .icon img { height: 84px; width: 84px; object-fit: contain; }
.feature .icon .ph {
  height: 84px; width: 84px; border-radius: 50%; background: linear-gradient(135deg, #2F6FED, #34C38F);
  color: #fff; font-size: 2.2rem; font-weight: 800; display: flex; align-items: center; justify-content: center;
}
.feature h3 { margin: 8px 0 6px; font-size: 1.35rem; font-weight: 800; color: #0F172A; }
.feature p { margin: 0; color: #475569; line-height: 1.5; font-size: .98rem; }

/* Big nav buttons (keys start with nav_) */
[class*="st-key-nav_"] button {
  width: 100%; height: 58px; font-size: 1.1rem !important; font-weight: 800 !important;
  border-radius: 0 0 22px 22px !important; border: 1px solid #2F6FED !important;
  background: #2F6FED !important; color: #fff !important; transition: all .15s ease;
}
[class*="st-key-nav_"] button:hover { background: #1F57C9 !important; transform: translateY(-2px); }
[class*="st-key-nav_"] button p { font-size: 1.12rem !important; font-weight: 800 !important; }

/* ---------- Sub page top bar ---------- */
.topbar-brand { font-size: 1.5rem; font-weight: 800; color: #2F6FED; text-align: right; padding-top: 6px; }
.page-title { font-size: 1.9rem; font-weight: 800; margin: 6px 0 4px; color: #0F172A; }
.page-sub { color: #64748B; margin-bottom: 18px; }

/* ---------- Cards ---------- */
.card {
  background: #fff; border: 1px solid #E3EAF8; border-radius: 18px; padding: 20px 22px;
  box-shadow: 0 4px 14px rgba(15,23,42,.04); margin-bottom: 16px;
}
.card h4 { margin: 0 0 10px; font-size: 1rem; font-weight: 700; color: #0F172A; }
.card ul { margin: 0; padding-left: 18px; }
.card li { margin-bottom: 6px; line-height: 1.45; color: #334155; }
.card p { color: #334155; line-height: 1.55; margin: 0; }

.tile { background:#fff; border:1px solid #E3EAF8; border-radius:16px; padding:16px 18px; height:100%; }
.tile .label { font-size:.75rem; text-transform:uppercase; letter-spacing:.06em; color:#64748B; font-weight:700; }
.tile .value { font-size:1.15rem; font-weight:700; color:#0F172A; margin-top:4px; }

.chip { display:inline-block; padding:6px 12px; border-radius:999px; font-size:.85rem; font-weight:600; margin:0 6px 8px 0; }
.chip.blue  { background:#E8F0FF; color:#2F6FED; }
.chip.red   { background:#FEE9E9; color:#B91C1C; }
.chip.green { background:#E3F7EA; color:#15803D; }

.badge { display:inline-block; padding:8px 18px; border-radius:999px; font-weight:800; font-size:1rem; }

.timeline { border-left: 3px solid #D6E2FB; margin: 6px 0 4px 8px; padding-left: 18px; }
.timeline .step { position: relative; margin-bottom: 10px; color:#334155; font-size:.92rem; }
.timeline .step::before {
  content:''; position:absolute; left:-27px; top:5px; width:11px; height:11px;
  background:#2F6FED; border-radius:50%; border:2px solid #fff; box-shadow:0 0 0 2px #D6E2FB;
}

.stButton > button { border-radius: 12px; font-weight: 700; padding: .55rem 1.2rem; }
.stTextInput input, .stTextArea textarea { border-radius: 12px !important; }
a { color: #2F6FED; }

.bd { margin-bottom: 14px; }
.bd-top { display: flex; justify-content: space-between; font-weight: 700; font-size: .92rem; color: #0F172A; }
.bar { height: 8px; background: #E5EAF3; border-radius: 999px; margin: 6px 0 4px; overflow: hidden; }
.bar .fill { height: 100%; border-radius: 999px; }
.bd-ev { font-size: .86rem; color: #64748B; line-height: 1.4; }
.capnote { background: #FFF3DC; color: #92400E; border-radius: 12px; padding: 10px 14px; font-size: .9rem; font-weight: 600; margin-bottom: 14px; }

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
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


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


def card(title: str, body_html: str) -> str:
    return f'<div class="card"><h4>{esc(title)}</h4>{body_html}</div>'


def ul(items: list[str]) -> str:
    if not items:
        return "<p>Nothing found.</p>"
    return "<ul>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>"


def chips(items: list[str], kind: str = "blue") -> str:
    if not items:
        return "<p>Nothing found.</p>"
    return "".join(f'<span class="chip {kind}">{esc(i)}</span>' for i in items)


def tile(label: str, value: str) -> str:
    return f'<div class="tile"><div class="label">{esc(label)}</div><div class="value">{esc(value)}</div></div>'


def sources_html(urls: list[str]) -> str:
    if not urls:
        return "<p>No sources.</p>"
    return "<ul>" + "".join(
        f'<li><a href="{esc(u)}" target="_blank">{esc(u)}</a></li>' for u in urls
    ) + "</ul>"


def timeline_html(steps: list[str]) -> str:
    return '<div class="timeline">' + "".join(f'<div class="step">{esc(s)}</div>' for s in steps) + "</div>"


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
        '<circle cx="70" cy="70" r="54" fill="none" stroke="#E5EAF3" stroke-width="12"/>'
        f'<circle cx="70" cy="70" r="54" fill="none" stroke="{color}" stroke-width="12" '
        f'stroke-linecap="round" stroke-dasharray="{filled:.1f} {circ}" transform="rotate(-90 70 70)">'
        f'<animate attributeName="stroke-dasharray" from="0 {circ}" to="{filled:.1f} {circ}" '
        'dur="1.2s" fill="freeze" calcMode="spline" keySplines="0.2 0.8 0.2 1" keyTimes="0;1"/></circle>'
        f'<text x="70" y="72" text-anchor="middle" font-size="34" font-weight="800" fill="#0F172A">{score}</text>'
        '<text x="70" y="92" text-anchor="middle" font-size="11" fill="#64748B">out of 100</text>'
        "</svg>"
    )


# ---------------------------------------------------------------------------
# Schemas for structured Gemini output
# ---------------------------------------------------------------------------
class CompanyDossier(BaseModel):
    company_name: str
    summary: str
    tech_stack: list[str] = Field(description="Technologies, languages, frameworks used")
    recent_news: list[str] = Field(description="2-4 recent updates or news items")
    hiring_trends: str = Field(description="Active roles or hiring focus areas")
    interview_experiences: str = Field(description="What candidates report about the interview process")
    estimated_salary_range: str = Field(description="Rough CTC / salary estimates found")


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


class InterviewPrep(BaseModel):
    technical_questions: list[str]
    behavioral_questions: list[str]
    company_specific_questions: list[str] = Field(
        description="Questions grounded in the company's recent news or products"
    )
    talking_points: list[str] = Field(description="Points the student should weave into answers")
    skill_gaps: list[str] = Field(description="Gaps between the student's profile and the role")


# ---------------------------------------------------------------------------
# TinyFish helpers (Search -> Fetch)
# ---------------------------------------------------------------------------
def tf_search(query: str, limit: int = 4) -> list:
    resp = tf_client.search.query(query=query)
    return list(resp.results[:limit])


def tf_fetch(urls: list[str], chars_per_page: int = 2500) -> str:
    if not urls:
        return ""
    resp = tf_client.fetch.get_contents(urls=urls, format="markdown")
    parts = []
    for i, item in enumerate(resp.results):
        text = (item.text or "")[:chars_per_page]
        parts.append(f"\n--- Source {i + 1}: {item.title} ({item.url}) ---\n{text}")
    return "\n".join(parts)


def domain_of(url: str) -> str:
    m = re.match(r"https?://([^/]+)", url)
    return m.group(1).replace("www.", "") if m else url


def log(steps: list[str], msg: str):
    steps.append(msg)
    st.write("• " + msg)


def research(query: str, steps: list[str], limit: int = 3) -> tuple[str, list[str]]:
    """Search then Fetch, logging each action to the timeline."""
    log(steps, f'TinyFish Search: "{query[:70]}"')
    results = tf_search(query, limit)
    urls = [r.url for r in results]
    log(steps, f"Found {len(urls)} pages: " + ", ".join(domain_of(u) for u in urls))
    log(steps, "TinyFish Fetch: reading pages as clean markdown")
    return tf_fetch(urls), urls


# ---------------------------------------------------------------------------
# Gemini helper
# ---------------------------------------------------------------------------
def gemini_structured(prompt: str, schema: type[BaseModel]) -> dict:
    resp = gemini_client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.2,
        ),
    )
    return json.loads(resp.text)


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
def subpage_header(title: str, subtitle: str):
    c1, c2 = st.columns([1, 3])
    c1.button("← Back to home", on_click=go, args=("home",), key="back_home")
    c2.markdown('<div class="topbar-brand">JobVentra</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="page-title">{esc(title)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="page-sub">{esc(subtitle)}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# PAGE: Home
# ---------------------------------------------------------------------------
def page_home():
    st.markdown(
        """
<div class="home-hero">
  <div class="eyebrow">Placement intelligence, live from the web</div>
  <h1>JobVentra</h1>
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
    cols = st.columns(3, gap="large")
    for i, (col, (key, title, desc)) in enumerate(zip(cols, features)):
        with col:
            st.markdown(
                f'<div class="feature" style="animation-delay:{0.9 + i * 0.12}s"><div class="icon">{img_tag(key, title)}</div><h3>{esc(title)}</h3><p>{esc(desc)}</p></div>',
                unsafe_allow_html=True,
            )
            st.button(f"Open {title}  →", on_click=go, args=(key,), key=f"nav_{key}")


# ---------------------------------------------------------------------------
# PAGE: Company Dossier
# ---------------------------------------------------------------------------
def page_dossier():
    subpage_header("Company Dossier", "A live, one-page profile of any company, built from the open web.")
    company = st.text_input("Company name", placeholder="e.g. Razorpay, Swiggy, Zerodha", key="d_company")

    if st.button("Generate live dossier", type="primary", key="d_btn"):
        if not company.strip():
            st.warning("Please enter a company name.")
        else:
            steps: list[str] = []
            try:
                with st.status("Agent is researching the live web...", expanded=True) as status:
                    context, urls = research(
                        f"{company} company tech stack recent news hiring salary interview experience", steps
                    )
                    log(steps, "Gemini: turning raw pages into a structured dossier")
                    prompt = f"""You are a placement intelligence analyst. Using ONLY the live web context
below, produce a one-page dossier on '{company}' for a student preparing for placements.
If something is not in the context, say 'Not found in sources' rather than guessing.

Live web context:
{context}"""
                    dossier = gemini_structured(prompt, CompanyDossier)
                    status.update(label="Dossier complete", state="complete", expanded=False)
                st.session_state["dossier"] = dossier
                st.session_state["dossier_urls"] = urls
                st.session_state["dossier_steps"] = steps
            except Exception as e:
                st.error(f"Something went wrong: {e}")

    d = st.session_state.get("dossier")
    if d:
        st.markdown(f"### {esc(d['company_name'])}")
        t1, t2, t3 = st.columns(3)
        t1.markdown(tile("Salary range", d["estimated_salary_range"]), unsafe_allow_html=True)
        t2.markdown(tile("Tech stack size", f"{len(d['tech_stack'])} technologies"), unsafe_allow_html=True)
        t3.markdown(tile("News items", f"{len(d['recent_news'])} recent updates"), unsafe_allow_html=True)
        st.write("")

        c1, c2 = st.columns([3, 2])
        with c1:
            st.markdown(card("Overview", f"<p>{esc(d['summary'])}</p>"), unsafe_allow_html=True)
            st.markdown(card("Recent news", ul(d["recent_news"])), unsafe_allow_html=True)
            st.markdown(card("Hiring focus", f"<p>{esc(d['hiring_trends'])}</p>"), unsafe_allow_html=True)
            st.markdown(
                card("Interview experiences", f"<p>{esc(d['interview_experiences'])}</p>"), unsafe_allow_html=True
            )
        with c2:
            st.markdown(card("Tech stack", chips(d["tech_stack"], "blue")), unsafe_allow_html=True)
            st.markdown(
                card("How the agent got this", timeline_html(st.session_state.get("dossier_steps", []))),
                unsafe_allow_html=True,
            )
            st.markdown(card("Sources", sources_html(st.session_state.get("dossier_urls", []))), unsafe_allow_html=True)

        md = (
            f"# {d['company_name']} - JobVentra Dossier\n\n{d['summary']}\n\n"
            "## Recent news\n" + "\n".join(f"- {n}" for n in d["recent_news"]) +
            f"\n\n## Hiring focus\n{d['hiring_trends']}\n\n"
            f"## Interview experiences\n{d['interview_experiences']}\n\n"
            f"## Tech stack\n{', '.join(d['tech_stack'])}\n\n"
            f"## Salary range\n{d['estimated_salary_range']}\n\n"
            "## Sources\n" + "\n".join(f"- {u}" for u in st.session_state.get("dossier_urls", []))
        )
        st.download_button("Download dossier (.md)", md, file_name="dossier.md")


# ---------------------------------------------------------------------------
# PAGE: Posting Verifier
# ---------------------------------------------------------------------------
def page_verify():
    subpage_header("Posting Verifier", "Paste a job posting, offer message or link. We check it against the live web.")
    b1, b2, _ = st.columns([1.3, 1.3, 3])
    b1.button("Try a scam posting", on_click=load_sample, args=(SCAM_SAMPLE,), key="s_scam")
    b2.button("Try a legit company", on_click=load_sample, args=(LEGIT_SAMPLE,), key="s_legit")

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
                    web_ctx, web_urls = research(f"{name} official website careers reviews scam fraud", steps, limit=4)

                    log(steps, "Gemini: weighing the evidence into a trust score")
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
                    report = gemini_structured(prompt, TrustReport)
                    status.update(label="Verification complete", state="complete", expanded=False)

                report["red_flags"] = list(dict.fromkeys(flags + report["red_flags"]))
                report.update(finalize_score(report, posting_text))
                st.session_state["report"] = report
                st.session_state["report_urls"] = web_urls
                st.session_state["report_steps"] = steps
            except Exception as e:
                st.error(f"Something went wrong: {e}")

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
    subpage_header("Interview Prep", "Questions and talking points grounded in live company news and your profile.")
    default_company = st.session_state.get("dossier", {}).get("company_name", "")
    p_company = st.text_input("Company", key="p_company", value=default_company)
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
                        f"{p_company} {p_role} interview questions experience tech stack recent news", steps
                    )
                    log(steps, "Gemini: personalising questions to your profile")
                    profile_block = (("Resume:\n" + resume_text[:6000] + "\n\n") if resume_text else "") + (
                        p_profile or ("" if resume_text else "Not provided")
                    )
                    prompt = f"""You are an interview coach. Using the live web context and the student's
profile, create interview prep for the role '{p_role}' at '{p_company}'.
Ground company-specific questions in the context. Do not fabricate facts about the company.
If a resume is included, refer to its real projects and skills in the talking points and skill gaps,
and never invent resume details.

Student profile:
{profile_block}

Live web context:
{ctx}"""
                    prep = gemini_structured(prompt, InterviewPrep)
                    status.update(label="Prep ready", state="complete", expanded=False)
                st.session_state["prep"] = prep
                st.session_state["prep_urls"] = urls
            except Exception as e:
                st.error(f"Something went wrong: {e}")

    prep = st.session_state.get("prep")
    if prep:
        a, b = st.columns(2)
        with a:
            st.markdown(card("Technical questions", ul(prep["technical_questions"])), unsafe_allow_html=True)
            st.markdown(
                card("Company-specific questions", ul(prep["company_specific_questions"])), unsafe_allow_html=True
            )
            st.markdown(card("Skill gaps to work on", ul(prep["skill_gaps"])), unsafe_allow_html=True)
        with b:
            st.markdown(card("Behavioral questions", ul(prep["behavioral_questions"])), unsafe_allow_html=True)
            st.markdown(card("Talking points", ul(prep["talking_points"])), unsafe_allow_html=True)
            st.markdown(card("Sources", sources_html(st.session_state.get("prep_urls", []))), unsafe_allow_html=True)


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