GLOBAL_CSS = """
<style>
/* ── Streamlit base overrides ──────────────────────────────────────── */
#MainMenu   { visibility: hidden; }
footer      { visibility: hidden; }
header      { visibility: hidden; }

html, body, .stApp {
    background-color: #0e1117;
}

.block-container {
    padding-top:    0 !important;
    padding-bottom: 2rem !important;
    max-width:      100% !important;
    padding-left:   2rem !important;
    padding-right:  2rem !important;
}

[data-testid="stSidebar"]       { display: none; }
div[data-testid="stDecoration"] { display: none; }

/* ── Navbar sentinel (hidden marker used by CSS :has() selector) ───── */
.navbar-sentinel { display: none; }

/* ── Navbar: horizontal block immediately after the sentinel wrapper ─ */
div:has(> .navbar-sentinel) + div[data-testid="stHorizontalBlock"] {
    background-color: #1A1E2E;
    border-bottom:    1px solid #2D3250;
    margin:           0 -2rem 2rem -2rem;
    padding:          0 2rem;
    position:         sticky;
    top:              0;
    z-index:          999;
    align-items:      center !important;
    min-height:       56px;
}

/* Remove extra padding Streamlit adds inside each column */
div:has(> .navbar-sentinel) + div[data-testid="stHorizontalBlock"]
  div[data-testid="column"] {
    padding-top:    0 !important;
    padding-bottom: 0 !important;
    display:        flex;
    align-items:    center;
}

/* Brand text next to the logo SVG */
.brand {
    display:     flex;
    align-items: center;
    gap:         10px;
    flex-shrink: 0;
}

.brand-name {
    color:          #FAFAFA;
    font-size:      1.05rem;
    font-weight:    700;
    letter-spacing: 0.5px;
    white-space:    nowrap;
}

/* ── Page header ───────────────────────────────────────────────────── */
.page-header   { margin-bottom: 1.5rem; }

.page-title {
    color:       #FAFAFA;
    font-size:   1.65rem;
    font-weight: 700;
    margin:      0 0 4px 0;
}

.page-subtitle {
    color:     #7C85A2;
    font-size: 0.9rem;
    margin:    0;
}

/* ── Card ──────────────────────────────────────────────────────────── */
.card {
    background-color: #1A1E2E;
    border:           1px solid #2D3250;
    border-radius:    10px;
    padding:          24px;
}

.card-title {
    color:       #FAFAFA;
    font-size:   1rem;
    font-weight: 600;
    margin:      0 0 8px 0;
}

/* ── System overview cards ────────────────────────────────────────── */
.overview-card {
    display:        flex;
    flex-direction:  column;
    gap:             10px;
    min-height:      118px;
}

.overview-card-detail {
    color:     #7C85A2;
    font-size: 0.82rem;
    margin:    0;
    line-height: 1.4;
}

.overview-card-status {
    display:        inline-flex;
    align-items:    center;
    align-self:     flex-start;
    margin-top:     auto;
    padding:        3px 10px;
    border:         1px solid currentColor;
    border-radius:  999px;
    font-size:      0.75rem;
    font-weight:    600;
}

/* ── Empty / placeholder state ─────────────────────────────────────── */
.empty-state {
    display:         flex;
    flex-direction:  column;
    align-items:     center;
    justify-content: center;
    padding:         80px 24px;
    text-align:      center;
}

.empty-state-icon  { font-size: 3.5rem; margin-bottom: 16px; opacity: 0.35; }

.empty-state-title {
    color:       #7C85A2;
    font-size:   1.15rem;
    font-weight: 600;
    margin:      0 0 8px 0;
}

.empty-state-desc {
    color:       #4A5070;
    font-size:   0.9rem;
    max-width:   420px;
    line-height: 1.6;
    margin:      0;
}
</style>
<div class="navbar-sentinel"></div>
"""
