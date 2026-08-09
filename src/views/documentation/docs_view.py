import json
import streamlit as st
import streamlit.components.v1 as components
from src.controllers.docs_controller import DocsController

_ctrl = DocsController()


def render() -> None:
    st.markdown(
'<div class="page-header">'
'<h1 class="page-title">Documentation</h1>'
'<p class="page-subtitle">User guides and technical reference</p>'
'</div>',
        unsafe_allow_html=True,
    )

    articles = _ctrl.get_articles()
    if not articles:
        st.markdown(
'<div class="card">'
'<div class="empty-state">'
'<div class="empty-state-icon">&#128214;</div>'
'<h3 class="empty-state-title">Documentation</h3>'
'<p class="empty-state-desc">User guides, API references, and configuration examples will appear here.</p>'
'</div>'
'</div>',
            unsafe_allow_html=True,
        )
        return

    ids = [article["id"] for article in articles]
    if "docs_selected" not in st.session_state or st.session_state["docs_selected"] not in ids:
        st.session_state["docs_selected"] = ids[0]

    col_list, col_content = st.columns([1, 3])

    with col_list:
        with st.container(border=True):
            st.markdown('<div class="docs-tree-sentinel"></div>', unsafe_allow_html=True)
            for article in articles:
                if st.button(
                    f"\U0001F4C4  {article['title']}",
                    key=f"doc_nav_{article['id']}",
                    width='stretch',
                ):
                    st.session_state["docs_selected"] = article["id"]
                    st.rerun()

            _inject_tree_styles(
                ids,
                st.session_state["docs_selected"],
                [article["description"] for article in articles],
            )

    with col_content:
        with st.container(border=True):
            content = _ctrl.get_article_content(st.session_state["docs_selected"])
            st.markdown(content)


def _inject_tree_styles(doc_ids: list, active_id: str, descriptions: list) -> None:
    """
    Flattens the doc-nav buttons into a treeview-style list and attaches the
    description as a native hover tooltip. Plain CSS !important rules lose to
    Streamlit's emotion-injected styles (see navbar.py), so styles are applied
    via inline setProperty() instead.
    """
    ids_json   = json.dumps(doc_ids)
    active_json = json.dumps(active_id)
    desc_json  = json.dumps(descriptions)

    components.html(
        f"""
        <script>
        (function() {{
            var IDS    = {ids_json};
            var ACTIVE = {active_json};
            var DESCS  = {desc_json};

            function sp(el, prop, val) {{
                el.style.setProperty(prop, val, 'important');
            }}

            function applyStyles() {{
                try {{
                    var doc      = window.parent.document;
                    var sentinel = doc.querySelector('.docs-tree-sentinel');
                    if (!sentinel) return false;
                    var block    = sentinel.closest('[data-testid="stVerticalBlock"]');
                    if (!block)   return false;
                    var buttons  = block.querySelectorAll('button');
                    if (buttons.length !== IDS.length) return false;

                    sp(block, 'gap', '0px');

                    buttons.forEach(function(btn, i) {{
                        var wrap = btn.closest('[data-testid="stElementContainer"]');
                        if (wrap) {{
                            sp(wrap, 'margin',  '0');
                            sp(wrap, 'padding', '0');
                        }}
                        var active = (IDS[i] === ACTIVE);
                        var tag = ACTIVE + ':' + i;
                        if (btn.getAttribute('data-ds') === tag) return;
                        btn.setAttribute('data-ds', tag);
                        btn.setAttribute('data-tree-active', active ? '1' : '0');
                        btn.title = DESCS[i];

                        sp(btn, 'all',              'unset');
                        sp(btn, 'cursor',           'pointer');
                        sp(btn, 'display',          'flex');
                        sp(btn, 'align-items',      'center');
                        sp(btn, 'justify-content',  'flex-start');
                        sp(btn, 'width',            '100%');
                        sp(btn, 'box-sizing',       'border-box');
                        sp(btn, 'padding',          '6px 10px');
                        sp(btn, 'margin',           '0');
                        sp(btn, 'text-align',       'left');
                        sp(btn, 'border-radius',    '6px');
                        sp(btn, 'border-left',      '3px solid ' + (active ? '#4F9CF9' : 'transparent'));
                        sp(btn, 'background',       active ? 'rgba(79,156,249,0.14)' : 'transparent');
                        sp(btn, 'color',            active ? '#4F9CF9' : '#C7CCE0');
                        sp(btn, 'font-family',      'inherit');
                        sp(btn, 'font-size',        '0.875rem');
                        sp(btn, 'font-weight',      active ? '600' : '500');
                        sp(btn, 'transition',       'background 0.15s ease, color 0.15s ease');
                        sp(btn, 'white-space',      'nowrap');
                        sp(btn, 'overflow',         'hidden');
                        sp(btn, 'text-overflow',    'ellipsis');

                        var inner = btn.querySelector('p, div');
                        if (inner) {{
                            sp(inner, 'margin',     '0');
                            sp(inner, 'padding',    '0');
                            sp(inner, 'color',      'inherit');
                            sp(inner, 'text-align', 'left');
                            sp(inner, 'width',      '100%');
                            sp(inner, 'overflow',   'hidden');
                            sp(inner, 'text-overflow', 'ellipsis');
                        }}

                        if (!btn._treeHover) {{
                            btn._treeHover = true;
                            btn.addEventListener('mouseenter', function() {{
                                if (this.getAttribute('data-tree-active') !== '1') {{
                                    sp(this, 'background', 'rgba(255,255,255,0.06)');
                                    sp(this, 'color',      '#FAFAFA');
                                }}
                            }});
                            btn.addEventListener('mouseleave', function() {{
                                if (this.getAttribute('data-tree-active') !== '1') {{
                                    sp(this, 'background', 'transparent');
                                    sp(this, 'color',      '#C7CCE0');
                                }}
                            }});
                        }}
                    }});
                    return true;
                }} catch (e) {{
                    return false;
                }}
            }}

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
