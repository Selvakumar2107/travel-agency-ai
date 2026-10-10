"""SK Holidays — Luxury Black & Gold Design System & Component Library.

Brand: SK Holidays
Tagline: "Your Journey. Your Budget. Our Intelligence."
Palette:
  Jet Black:        #080808 (Main Canvas)
  Rich Black:       #111111 (Cards & Panels)
  Charcoal:         #1B1B1B (Inputs & Secondary Surfaces)
  Metallic Gold:    #D4AF37 (Primary Brand Accent)
  Bright Gold:      #FFD700 (Interactive Highlights & Hover Glow)
  Champagne Gold:   #F5E6A8 (Subtle Details & Rating Stars)
  Ivory White:      #FAF8F0 (High-Contrast Primary Text)
  Muted Grey:       #A6A6A6 (Secondary Text & Captions)
  Success Green:    #28A879 (Demo Confirmed / Paid)
  Error Red:        #E05252 (Demo Failed / Declined)
"""

LUXURY_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Outfit:wght@400;500;600;700;800;900&family=Playfair+Display:ital,wght@0,600;1,600&display=swap');

    :root {
        --sk-jet-black: #080808;
        --sk-rich-black: #111111;
        --sk-charcoal: #1B1B1B;
        --sk-gold: #D4AF37;
        --sk-bright-gold: #FFD700;
        --sk-champagne: #F5E6A8;
        --sk-ivory: #FAF8F0;
        --sk-muted: #A6A6A6;
        --sk-success: #28A879;
        --sk-error: #E05252;
        --sk-gold-border: rgba(212, 175, 55, 0.3);
        --sk-gold-border-bright: rgba(255, 215, 0, 0.7);
    }

    /* Global Dark Canvas */
    html, body, [class*="css"], [data-testid="stAppViewContainer"], .main, [data-testid="stHeader"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
        background-color: #080808 !important;
        color: #FAF8F0 !important;
    }

    [data-testid="stAppViewBlockContainer"] {
        padding-top: 1.5rem !important;
        padding-bottom: 3rem !important;
    }

    /* Headings */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Outfit', sans-serif !important;
        color: #FAF8F0 !important;
        letter-spacing: -0.01em;
    }

    p, span, label, div {
        color: #FAF8F0;
    }

    /* Streamlit Form & Widget Labels High-Contrast Styling */
    label,
    [data-testid="stWidgetLabel"],
    [data-testid="stWidgetLabel"] p,
    [data-testid="stWidgetLabel"] span,
    [data-testid="stWidgetLabel"] label,
    .stTextInput label,
    .stTextInput label p,
    .stTextArea label,
    .stTextArea label p,
    .stSelectbox label,
    .stSelectbox label p,
    .stNumberInput label,
    .stNumberInput label p,
    .stDateInput label,
    .stDateInput label p,
    .stCheckbox label,
    .stCheckbox label p {
        color: #FAF8F0 !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 0.92rem !important;
        font-weight: 600 !important;
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
        margin-bottom: 0.35rem !important;
    }

    /* Gold Gradient Text Utility */
    .sk-gold-text {
        background: linear-gradient(135deg, #FFF6D6 0%, #FFD700 40%, #D4AF37 80%, #AA7C11 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }

    /* Streamlit Native Inputs Overrides */
    div[data-baseweb="input"] > div,
    div[data-baseweb="select"] > div,
    div[data-baseweb="textarea"] > textarea,
    input, textarea, select {
        background-color: #1B1B1B !important;
        color: #FAF8F0 !important;
        border: 1px solid rgba(212, 175, 55, 0.35) !important;
        border-radius: 10px !important;
    }

    div[data-baseweb="input"] > div:focus-within,
    div[data-baseweb="select"] > div:focus-within {
        border-color: #FFD700 !important;
        box-shadow: 0 0 10px rgba(255, 215, 0, 0.3) !important;
    }

    [data-testid="stNumberInput"] button {
        background-color: #111111 !important;
        color: #D4AF37 !important;
        border: 1px solid rgba(212, 175, 55, 0.3) !important;
    }

    [data-testid="stNumberInput"] button:hover {
        background-color: #D4AF37 !important;
        color: #080808 !important;
    }

    /* Streamlit Slider */
    div[data-baseweb="slider"] div[role="slider"] {
        background-color: #FFD700 !important;
        border: 2px solid #080808 !important;
        box-shadow: 0 0 10px rgba(255, 215, 0, 0.6) !important;
    }
    div[data-baseweb="slider"] div[data-testid="stSliderTickBar"] {
        background: linear-gradient(90deg, #D4AF37, #FFD700) !important;
    }

    /* Streamlit Expander */
    [data-testid="stExpander"] {
        background: #111111 !important;
        border: 1px solid rgba(212, 175, 55, 0.25) !important;
        border-radius: 12px !important;
    }
    [data-testid="stExpander"] details summary {
        color: #FAF8F0 !important;
    }

    /* Streamlit Bordered Container */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: #111111 !important;
        border: 1px solid rgba(212, 175, 55, 0.3) !important;
        border-radius: 18px !important;
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.6) !important;
        margin-bottom: 1.2rem !important;
        transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    }
    [data-testid="stVerticalBlockBorderWrapper"]:hover {
        border-color: rgba(255, 215, 0, 0.6) !important;
        box-shadow: 0 12px 35px rgba(0, 0, 0, 0.8), 0 0 15px rgba(212, 175, 55, 0.2) !important;
    }

    /* Buttons Styling */
    div.stButton > button {
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700 !important;
        font-size: 0.95rem !important;
        padding: 0.65rem 1.4rem !important;
        border-radius: 12px !important;
        letter-spacing: 0.02em !important;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }

    /* Primary buttons (Gold Foil Effect) */
    div.stButton > button[kind="primary"], div.stButton > button[data-testid="baseButton-primary"] {
        background: linear-gradient(135deg, #FFD700 0%, #D4AF37 50%, #B8860B 100%) !important;
        color: #080808 !important;
        border: 1px solid #FFD700 !important;
        box-shadow: 0 4px 18px rgba(212, 175, 55, 0.35) !important;
    }
    div.stButton > button[kind="primary"]:hover, div.stButton > button[data-testid="baseButton-primary"]:hover {
        background: linear-gradient(135deg, #FFF6D6 0%, #FFD700 50%, #D4AF37 100%) !important;
        color: #000000 !important;
        border-color: #FFFFFF !important;
        box-shadow: 0 6px 24px rgba(255, 215, 0, 0.55) !important;
        transform: translateY(-2px);
    }

    /* Secondary buttons (Luxury Dark with Fine Gold Border) */
    div.stButton > button[kind="secondary"], div.stButton > button[data-testid="baseButton-secondary"] {
        background: #111111 !important;
        color: #D4AF37 !important;
        border: 1px solid rgba(212, 175, 55, 0.35) !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.6) !important;
    }
    div.stButton > button[kind="secondary"]:hover, div.stButton > button[data-testid="baseButton-secondary"]:hover {
        background: #1B1B1B !important;
        color: #FFD700 !important;
        border-color: #FFD700 !important;
        box-shadow: 0 4px 15px rgba(212, 175, 55, 0.25) !important;
        transform: translateY(-2px);
    }

    /* Generic buttons fallback */
    div.stButton > button:not([kind="secondary"]):not([data-testid="baseButton-secondary"]) {
        background: linear-gradient(135deg, #FFD700 0%, #D4AF37 100%) !important;
        color: #080808 !important;
        border: 1px solid #FFD700 !important;
        box-shadow: 0 4px 15px rgba(212, 175, 55, 0.3) !important;
    }

    /* Brand Header */
    .sk-brand-header {
        background: #111111;
        border: 1px solid rgba(212, 175, 55, 0.3);
        border-bottom: 2px solid #D4AF37;
        padding: 0.9rem 2rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-radius: 16px;
        margin-bottom: 1.2rem;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.7), 0 0 15px rgba(212, 175, 55, 0.1);
    }
    .sk-logo-wrap {
        display: flex;
        align-items: center;
        gap: 0.9rem;
    }
    .sk-brand-title {
        font-family: 'Outfit', sans-serif;
        font-size: 1.65rem;
        font-weight: 800;
        color: #FAF8F0;
        letter-spacing: 0.03em;
        line-height: 1;
    }
    .sk-brand-title span {
        color: #FFD700;
        background: linear-gradient(135deg, #FFF6D6 0%, #FFD700 60%, #D4AF37 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .sk-brand-tagline {
        font-size: 0.74rem;
        color: #A6A6A6;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        display: block;
        margin-top: 0.2rem;
    }
    .sk-header-badge {
        background: rgba(212, 175, 55, 0.12);
        border: 1px solid rgba(212, 175, 55, 0.4);
        color: #F5E6A8;
        padding: 0.4rem 0.95rem;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }

    /* Hero Section */
    .sk-hero {
        position: relative;
        border-radius: 24px;
        overflow: hidden;
        margin-bottom: 2.2rem;
        border: 1px solid rgba(212, 175, 55, 0.35);
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.8), 0 0 25px rgba(212, 175, 55, 0.15);
    }
    .sk-hero-img {
        width: 100%;
        height: 420px;
        object-fit: cover;
        display: block;
        filter: brightness(0.65) contrast(1.1);
    }
    .sk-hero-overlay {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(180deg, rgba(8, 8, 8, 0.25) 0%, rgba(8, 8, 8, 0.7) 50%, rgba(8, 8, 8, 0.96) 100%);
        display: flex;
        flex-direction: column;
        justify-content: flex-end;
        padding: 3rem 2.8rem;
        color: #FAF8F0;
    }
    .sk-hero-badge {
        background: rgba(212, 175, 55, 0.2);
        border: 1px solid #FFD700;
        color: #FFD700;
        padding: 0.35rem 1rem;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 800;
        display: inline-block;
        width: fit-content;
        margin-bottom: 0.9rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }
    .sk-hero-heading {
        font-size: 3.2rem;
        font-weight: 900;
        line-height: 1.1;
        margin: 0 0 0.8rem 0;
    }
    .sk-hero-desc {
        font-size: 1.18rem;
        color: #FAF8F0;
        max-width: 740px;
        margin-bottom: 1.5rem;
        font-weight: 400;
        line-height: 1.6;
    }

    /* Luxury Panels & Cards */
    .sk-panel {
        background: #111111;
        border: 1px solid rgba(212, 175, 55, 0.25);
        border-radius: 18px;
        padding: 1.8rem;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.6);
        margin-bottom: 1.5rem;
    }
    .sk-panel:hover {
        border-color: rgba(255, 215, 0, 0.45);
    }

    /* Trust / Feature Strip */
    .sk-trust-strip {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1.4rem;
        margin-bottom: 2.4rem;
    }
    .sk-trust-card {
        background: #111111;
        border: 1px solid rgba(212, 175, 55, 0.22);
        border-radius: 16px;
        padding: 1.4rem;
        display: flex;
        align-items: center;
        gap: 1.1rem;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.5);
        transition: all 0.25s ease;
    }
    .sk-trust-card:hover {
        border-color: #D4AF37;
        transform: translateY(-3px);
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.7), 0 0 15px rgba(212, 175, 55, 0.1);
    }
    .sk-trust-icon {
        width: 48px;
        height: 48px;
        border-radius: 12px;
        background: #1B1B1B;
        border: 1px solid rgba(212, 175, 55, 0.4);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.5rem;
        flex-shrink: 0;
        color: #FFD700;
    }
    .sk-trust-title {
        font-weight: 700;
        font-size: 1rem;
        color: #FAF8F0;
    }
    .sk-trust-desc {
        font-size: 0.83rem;
        color: #A6A6A6;
        margin-top: 0.2rem;
    }

    /* Destination Cards */
    .sk-dest-card {
        background: #111111;
        border: 1px solid rgba(212, 175, 55, 0.25);
        border-radius: 18px;
        overflow: hidden;
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.6);
        transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
        display: flex;
        flex-direction: column;
        height: 100%;
        margin-bottom: 1.4rem;
    }
    .sk-dest-card:hover {
        transform: translateY(-5px);
        border-color: #FFD700;
        box-shadow: 0 14px 35px rgba(0, 0, 0, 0.8), 0 0 20px rgba(212, 175, 55, 0.2);
    }
    .sk-dest-img {
        width: 100%;
        height: 200px;
        object-fit: cover;
        filter: brightness(0.9);
        transition: transform 0.3s ease;
    }
    .sk-dest-card:hover .sk-dest-img {
        transform: scale(1.03);
    }
    .sk-dest-body {
        padding: 1.4rem;
        display: flex;
        flex-direction: column;
        flex-grow: 1;
        justify-content: space-between;
    }
    .sk-dest-title {
        font-size: 1.3rem;
        font-weight: 800;
        color: #FAF8F0;
        margin-bottom: 0.2rem;
    }
    .sk-dest-state {
        font-size: 0.78rem;
        color: #FFD700;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .sk-dest-tagline {
        font-size: 0.88rem;
        color: #A6A6A6;
        margin: 0.6rem 0;
        line-height: 1.45;
    }
    .sk-dest-budget {
        background: #1B1B1B;
        border: 1px solid rgba(212, 175, 55, 0.3);
        padding: 0.45rem 0.85rem;
        border-radius: 10px;
        font-size: 0.85rem;
        color: #FAF8F0;
        font-weight: 600;
        margin-bottom: 0.9rem;
    }

    /* Comparison Plan Cards */
    .sk-plan-card {
        background: #111111;
        border: 1px solid rgba(212, 175, 55, 0.25);
        border-radius: 18px;
        padding: 1.6rem;
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.6);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        height: 100%;
        transition: transform 0.25s ease, border-color 0.25s ease;
    }
    .sk-plan-card:hover {
        transform: translateY(-4px);
    }
    .sk-plan-card.plan-eco {
        border-top: 4px solid #28A879;
    }
    .sk-plan-card.plan-bal {
        border-top: 4px solid #D4AF37;
    }
    .sk-plan-card.plan-prem {
        border-top: 4px solid #FFD700;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.7), 0 0 15px rgba(255, 215, 0, 0.12);
    }
    .sk-plan-feasible {
        border-color: rgba(40, 168, 121, 0.6);
    }
    .sk-plan-overbudget {
        border-color: rgba(224, 82, 82, 0.6);
        background: #140F0F;
    }

    /* Agent Tracker */
    .sk-agent-tracker {
        background: #111111;
        border: 1px solid rgba(212, 175, 55, 0.25);
        border-radius: 16px;
        padding: 1.4rem;
        margin-bottom: 1.8rem;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.5);
    }
    .sk-agent-step {
        display: flex;
        align-items: center;
        gap: 0.9rem;
        padding: 0.7rem 1rem;
        border-radius: 10px;
        background: #1B1B1B;
        border: 1px solid rgba(212, 175, 55, 0.2);
        margin-bottom: 0.5rem;
    }
    .sk-agent-pill-completed {
        background: rgba(40, 168, 121, 0.18);
        color: #28A879;
        border: 1px solid #28A879;
        font-size: 0.75rem;
        font-weight: 700;
        padding: 0.22rem 0.65rem;
        border-radius: 9999px;
    }

    /* Footer */
    .sk-footer {
        background: #111111;
        border-top: 2px solid #D4AF37;
        border-radius: 20px;
        color: #A6A6A6;
        padding: 2.5rem 2.8rem;
        margin-top: 3.5rem;
        box-shadow: 0 -10px 30px rgba(0, 0, 0, 0.7);
    }
    .sk-footer-brand {
        font-family: 'Outfit', sans-serif;
        font-size: 1.6rem;
        font-weight: 800;
        color: #FAF8F0;
    }
    .sk-footer-brand span {
        color: #FFD700;
    }
    .sk-footer-tagline {
        color: #A6A6A6;
        font-size: 0.88rem;
        margin-top: 0.3rem;
    }

    /* Badges & Pills */
    .badge-gold {
        background: rgba(212, 175, 55, 0.15);
        border: 1px solid #D4AF37;
        color: #FFD700;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }
    .badge-green {
        background: rgba(40, 168, 121, 0.15);
        border: 1px solid #28A879;
        color: #28A879;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }
    .badge-red {
        background: rgba(224, 82, 82, 0.15);
        border: 1px solid #E05252;
        color: #E05252;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }
    .badge-demo {
        background: rgba(255, 215, 0, 0.12);
        border: 1px dashed #D4AF37;
        color: #F5E6A8;
        padding: 0.25rem 0.65rem;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.05em;
    }
</style>
"""


def get_luxury_header_html() -> str:
    """Renders the top luxury brand navigation header."""
    return """
    <div class="sk-brand-header">
        <div class="sk-logo-wrap">
            <svg width="40" height="40" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect width="40" height="40" rx="12" fill="#080808" stroke="#D4AF37" stroke-width="1.8"/>
                <circle cx="20" cy="20" r="14" stroke="#D4AF37" stroke-width="0.8" stroke-dasharray="2 2"/>
                <path d="M20 7L24.5 16.5L33 20L24.5 23.5L20 33L15.5 23.5L7 20L15.5 16.5L20 7Z" fill="url(#goldGrad)"/>
                <circle cx="20" cy="20" r="3.5" fill="#FAF8F0"/>
                <circle cx="20" cy="20" r="1.5" fill="#080808"/>
                <defs>
                    <linearGradient id="goldGrad" x1="7" y1="7" x2="33" y2="33" gradientUnits="userSpaceOnUse">
                        <stop stop-color="#FFD700"/>
                        <stop offset="0.5" stop-color="#D4AF37"/>
                        <stop offset="1" stop-color="#996515"/>
                    </linearGradient>
                </defs>
            </svg>
            <div>
                <div class="sk-brand-title">SK <span>HOLIDAYS</span></div>
                <div class="sk-brand-tagline">Your Journey. Your Budget. Our Intelligence.</div>
            </div>
        </div>
        <div class="sk-header-badge">
            ✨ Intelligent Luxury Travel Platform
        </div>
    </div>
    """


def get_luxury_footer_html() -> str:
    """Renders the luxury footer component."""
    return """
    <div class="sk-footer">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 2rem;">
            <div>
                <div class="sk-footer-brand">SK <span>HOLIDAYS</span></div>
                <div class="sk-footer-tagline">“Your Journey. Your Budget. Our Intelligence.”</div>
                <p style="color: #A6A6A6; font-size: 0.85rem; max-width: 480px; margin-top: 0.8rem; line-height: 1.6;">
                    A luxury agentic AI travel orchestrator and hotel booking demonstration built with Google Gemini and Google ADK.
                    Tailoring memorable journeys with strict budget invariants starting from ₹3,000 INR.
                </p>
            </div>
            <div>
                <div style="font-weight: 700; color: #FAF8F0; margin-bottom: 0.8rem; font-size: 0.95rem; text-transform: uppercase; letter-spacing: 0.05em;">Curated Destinations</div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.4rem 1.8rem; font-size: 0.85rem; color: #A6A6A6;">
                    <span>• Ooty, Tamil Nadu</span>
                    <span>• Coorg, Karnataka</span>
                    <span>• Mysuru, Karnataka</span>
                    <span>• Pondicherry</span>
                    <span>• Munnar, Kerala</span>
                    <span>• Jaipur, Rajasthan</span>
                    <span>• Goa (Heritage Coast)</span>
                    <span>• Rishikesh, Uttarakhand</span>
                </div>
            </div>
            <div>
                <div style="font-weight: 700; color: #FAF8F0; margin-bottom: 0.8rem; font-size: 0.95rem; text-transform: uppercase; letter-spacing: 0.05em;">Demonstration Notice</div>
                <p style="color: #A6A6A6; font-size: 0.82rem; max-width: 320px; line-height: 1.5;">
                    🛡️ All hotel inventory, availability, bookings, and payments are mock/simulated. No real monetary charges are collected.
                </p>
                <div style="margin-top: 0.8rem;">
                    <span class="badge-demo">PROTOTYPE DEMONSTRATION</span>
                </div>
            </div>
        </div>
        <div style="border-top: 1px solid rgba(212, 175, 55, 0.2); margin-top: 2rem; padding-top: 1.2rem; display: flex; justify-content: space-between; font-size: 0.8rem; color: #A6A6A6;">
            <div>© 2026 SK Holidays. All rights reserved. International Travel Demonstration.</div>
            <div style="color: #D4AF37;">Engineered with Google Gemini API & Google Agent Development Kit</div>
        </div>
    </div>
    """
