# PRD-133: Navigation Overhaul

## Summary
Replaces Streamlit's automatic flat-list page discovery with `st.navigation()` + `st.Page()`, organizing 102 dashboard pages into 10 collapsible sidebar sections with Material Design icons.

## Changes

| File | Action | Description |
|------|--------|-------------|
| `requirements.txt` | Modified | `streamlit>=1.36.0` (was `>=1.30.0`) |
| `app/styles.py` | Created | Extracted ~520-line CSS block into `inject_global_styles()` |
| `app/nav_config.py` | Created | `build_navigation_pages()` — 10 sections, 102 `st.Page()` entries |
| `app/pages/home.py` | Created | AI Chat landing page (extracted from entrypoint) |
| `app/streamlit_app.py` | Rewritten | Slim nav router (~230 lines, was ~1400) |
| `tests/test_navigation.py` | Created | Navigation config verification tests |
| `docs/PRD-133-Navigation-Overhaul.md` | Created | This document |

## Architecture

```
streamlit_app.py (entrypoint)
├── set_page_config()
├── inject_global_styles()        ← app/styles.py
├── init_session_state()
├── st.navigation(pages)          ← app/nav_config.py
├── Shared sidebar (logo, provider/model, agent)
└── pg.run()                      ← delegates to selected page
```

## Navigation Sections (10 groups, 102 pages)

| Section | Pages |
|---------|-------|
| Home | 1 (AI Chat) |
| Market Analysis | 16 |
| Sentiment & Data | 7 |
| Trading & Execution | 12 |
| Portfolio & Risk | 14 |
| Options & Derivatives | 3 |
| ML & AI | 5 |
| Enterprise & Compliance | 12 |
| Research & Tools | 10 |
| Infrastructure & DevOps | 22 |

## Key Design Decisions

1. **Zero changes to existing 101 page files** — their `try/except set_page_config()` pattern already handles the new flow
2. **Chat-specific sidebar** (Research, AI Picks, Portfolios, Options buttons) moved into `home.py`, only visible on the chat page
3. **Shared sidebar** (provider/model/agent selectors) remains in the entrypoint, visible on all pages
4. **API key shared via `st.session_state["_api_key"]`** — pages read it from session state

## Testing

```bash
python3 -m pytest tests/test_navigation.py -v
```
