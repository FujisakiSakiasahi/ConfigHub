import json
import streamlit as st
import streamlit.components.v1 as components
from src.views.shared.styles import GLOBAL_CSS

PAGES = [
    ("Dashboard",                "dashboard"),
    ("Topology Manager",         "topology"),
    ("Configuration Generation", "config"),
    ("Logs",                     "logs"),
    ("Documentation",            "docs"),
]

_SLUGS       = [slug for _, slug in PAGES]
_VALID_SLUGS = set(_SLUGS)

_LOGO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 40 40" fill="none">'
    '<circle cx="20" cy="20" r="18" stroke="#4F9CF9" stroke-width="2.5"/>'
    '<circle cx="20" cy="20" r="5" fill="#4F9CF9"/>'
    '<circle cx="20" cy="8" r="3" fill="#4F9CF9"/>'
    '<circle cx="20" cy="32" r="3" fill="#4F9CF9"/>'
    '<circle cx="8" cy="20" r="3" fill="#4F9CF9"/>'
    '<circle cx="32" cy="20" r="3" fill="#4F9CF9"/>'
    '<line x1="20" y1="11" x2="20" y2="15" stroke="#4F9CF9" stroke-width="1.5"/>'
    '<line x1="20" y1="25" x2="20" y2="29" stroke="#4F9CF9" stroke-width="1.5"/>'
    '<line x1="11" y1="20" x2="15" y2="20" stroke="#4F9CF9" stroke-width="1.5"/>'
    '<line x1="25" y1="20" x2="29" y2="20" stroke="#4F9CF9" stroke-width="1.5"/>'
    '</svg>'
)

_BRAND_HTML = (
    '<div class="brand">'
    + _LOGO_SVG
    + '<span class="brand-name">ConfigHub</span>'
    '</div>'
)


def render_navbar() -> str:
    if "page" not in st.session_state:
        slug = st.query_params.get("page", "dashboard")
        st.session_state["page"] = slug if slug in _VALID_SLUGS else "dashboard"

    active_slug = st.session_state["page"]

    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

    col_logo, *col_pages = st.columns([1.6, 1.4, 1.8, 2.4, 1.1, 1.7])

    with col_logo:
        st.markdown(_BRAND_HTML, unsafe_allow_html=True)

    for (label, slug), col in zip(PAGES, col_pages):
        with col:
            if st.button(label, key=f"nav_{slug}", width='stretch'):
                st.session_state["page"] = slug
                st.query_params["page"]  = slug
                st.rerun()

    _inject_nav_styles(active_slug)
    return active_slug


def _inject_nav_styles(active_slug: str) -> None:
    """
    Streamlit's emotion CSS is injected dynamically and wins the CSS cascade war
    even against !important rules in st.markdown.  The only reliable override is
    JavaScript inline-style assignment via setProperty(), which has the highest
    possible specificity.  components.html() is same-origin, so window.parent.document
    is accessible.
    """
    slugs_json  = json.dumps(_SLUGS)
    active_json = json.dumps(active_slug)

    components.html(
        f"""
        <script>
        (function() {{
            var ACTIVE = {active_json};
            var SLUGS  = {slugs_json};

            function sp(el, prop, val) {{
                el.style.setProperty(prop, val, 'important');
            }}

            function applyStyles() {{
                try {{
                    var doc      = window.parent.document;
                    var sentinel = doc.querySelector('.navbar-sentinel');
                    if (!sentinel) return false;
                    var wrapper  = sentinel.parentElement;
                    var navbar   = wrapper && wrapper.nextElementSibling;
                    if (!navbar)  return false;
                    var buttons  = navbar.querySelectorAll('button');
                    if (buttons.length !== SLUGS.length) return false;

                    buttons.forEach(function(btn, i) {{
                        var active = (SLUGS[i] === ACTIVE);

                        /* skip if already styled for this active state */
                        var tag = ACTIVE + ':' + i;
                        if (btn.getAttribute('data-ns') === tag) return;
                        btn.setAttribute('data-ns', tag);
                        btn.setAttribute('data-nav-active', active ? '1' : '0');

                        /* ── reset every property Streamlit touches ── */
                        sp(btn, 'all',              'unset');
                        sp(btn, 'cursor',           'pointer');
                        sp(btn, 'display',          'flex');
                        sp(btn, 'align-items',      'center');
                        sp(btn, 'justify-content',  'center');
                        sp(btn, 'width',            '100%');
                        sp(btn, 'height',           '56px');
                        sp(btn, 'padding',          '0 8px');
                        sp(btn, 'border-top',       'none');
                        sp(btn, 'border-left',      'none');
                        sp(btn, 'border-right',     'none');
                        sp(btn, 'border-bottom',    '2px solid ' + (active ? '#4F9CF9' : 'transparent'));
                        sp(btn, 'background',       'transparent');
                        sp(btn, 'box-shadow',       'none');
                        sp(btn, 'outline',          'none');
                        sp(btn, 'color',            active ? '#4F9CF9' : '#7C85A2');
                        sp(btn, 'font-family',      'inherit');
                        sp(btn, 'font-size',        '0.875rem');
                        sp(btn, 'font-weight',      active ? '600' : '500');
                        sp(btn, 'letter-spacing',   '0.01em');
                        sp(btn, 'transition',       'color 0.15s ease, border-color 0.15s ease');
                        sp(btn, 'white-space',      'nowrap');

                        /* strip margin/padding from the inner <p> Streamlit wraps text in */
                        var inner = btn.querySelector('p, div');
                        if (inner) {{
                            sp(inner, 'margin',  '0');
                            sp(inner, 'padding', '0');
                            sp(inner, 'color',   'inherit');
                        }}

                        /* attach hover only once per element lifetime */
                        if (!btn._navHover) {{
                            btn._navHover = true;
                            btn.addEventListener('mouseenter', function() {{
                                if (this.getAttribute('data-nav-active') !== '1') {{
                                    sp(this, 'color',              '#FAFAFA');
                                    sp(this, 'border-bottom-color','rgba(79,156,249,0.5)');
                                }}
                            }});
                            btn.addEventListener('mouseleave', function() {{
                                if (this.getAttribute('data-nav-active') !== '1') {{
                                    sp(this, 'color',              '#7C85A2');
                                    sp(this, 'border-bottom-color','transparent');
                                }}
                            }});
                        }}
                    }});
                    return true;
                }} catch(e) {{
                    return false;
                }}
            }}

            /* run immediately; if buttons aren't in DOM yet, poll until they are */
            if (!applyStyles()) {{
                var n = 0;
                var t = setInterval(function() {{
                    if (applyStyles() || ++n > 40) clearInterval(t);
                }}, 50);
            }}
        }})();
        </script>
        """,
        height=0,
        scrolling=False,
    )
