"""Top notes / pyramid scraper — data-driven template approach.

Instead of cloning the DOM of the notes pyramid (which varies with
Fragrantica's Vue component updates), this scraper:

1. Extracts structured data for each note tier (top, middle, base):
   each note's name, image URL, opacity, and calculated icon size.
2. Renders the data through a fixed Python HTML template that always
   produces markup matching the reference layout.

The reference structure (from a known-good product page) is:
    .fragrantica-notes-container.bg-white.p-8.rounded-3xl
      div.mt-6.space-y-1
        div.mx-auto.max-w-{md|xl|2xl}   (one per tier)
          div.note-section-header ...
          div.pyramid-level-container
            div.pyramid-note-item  (one per note)
              img (note icon)
              span.pyramid-note-label (note name)
"""
from __future__ import annotations

from pathlib import Path

from config import config
from .base import BaseScraper, SHARED_TAILWIND_CSS, download_note_images, strip_note_links


# ---------------------------------------------------------------------------
# JS extraction — returns { top: [...], middle: [...], base: [...] }
# Each note: { name, imgSrc, opacity }
# ---------------------------------------------------------------------------
_EXTRACT_JS = r"""
return (() => {
    const SELECTOR = '.mt-6.space-y-1';
    let el = document.querySelector(SELECTOR);
    if (!el) el = document.querySelector('#pyramid');
    if (!el) return null;

    const tiers = {};

    // Walk all children to find section headers and note items.
    const allElements = el.querySelectorAll('div, p, span, b, strong, h4, h5');

    // Find the tier headings and their parent containers.
    const headings = [];
    allElements.forEach(node => {
        const text = (node.textContent || '').trim().toLowerCase();
        if (text === 'top notes' || text === 'middle notes' || text === 'base notes') {
            const tier = text.replace(' notes', '');
            let section = node.closest('div[class*="max-w-"]') || node.parentElement;
            headings.push({ tier, section });
        }
    });

    if (headings.length === 0) {
        // Fallback: try to find note items directly via img[alt] inside the pyramid.
        const noteItems = el.querySelectorAll(
            '.pyramid-note-link, .pyramid-note-item, [class*="pyramid-note"], a[href*="/notes/"]'
        );
        if (noteItems.length === 0) return null;

        const allNotes = [];
        noteItems.forEach(item => {
            const img = item.querySelector('img');
            const span = item.querySelector('span');
            if (!img || !span) return;
            const name = span.textContent.trim();
            const imgSrc = img.getAttribute('src') || '';
            const opacity = parseFloat(
                (item.getAttribute('style') || '').match(/opacity:\s*([\d.]+)/)?.[1] || '1'
            );
            const width = (img.getAttribute('style') || '').match(
                /width:\s*([\d.]+(?:rem|px))/
            )?.[1] || '';
            allNotes.push({ name, imgSrc, opacity, width });
        });

        if (allNotes.length === 0) return null;
        return { top: allNotes, middle: [], base: [] };
    }

    // For each heading, collect the note items that follow it.
    // Note item selector: pyramid-note-link (current) or pyramid-note-item (legacy)
    const NOTE_SEL = '.pyramid-note-link, .pyramid-note-item, [class*="pyramid-note"], a[href*="/notes/"]';

    headings.forEach(({ tier, section }) => {
        const notes = [];
        let container = section;

        // Find the div with pyramid-level-container class.
        const flexContainers = container.querySelectorAll('.flex.flex-wrap, .pyramid-level-container');
        let noteContainer = null;
        if (flexContainers.length > 0) {
            noteContainer = flexContainers[flexContainers.length - 1];
        }

        if (!noteContainer) {
            // Try walking siblings after the heading section.
            let sibling = section.nextElementSibling;
            for (let i = 0; i < 5 && sibling; i++) {
                if (sibling.querySelector(NOTE_SEL) || sibling.querySelector('img[alt]')) {
                    noteContainer = sibling;
                    break;
                }
                sibling = sibling.nextElementSibling;
            }
        }

        if (!noteContainer) return;

        const items = noteContainer.querySelectorAll(NOTE_SEL);
        items.forEach(item => {
            const img = item.querySelector('img');
            const span = item.querySelector('span');
            if (!img || !span) return;

            const name = span.textContent.trim();
            const imgSrc = img.getAttribute('src') || '';

            const itemStyle = item.getAttribute('style') || '';
            const opacityMatch = itemStyle.match(/opacity:\s*([\d.]+)/);
            const opacity = opacityMatch ? parseFloat(opacityMatch[1]) : 1;

            const imgStyle = img.getAttribute('style') || '';
            const widthMatch = imgStyle.match(/width:\s*([\d.]+(?:rem|px))/);
            const width = widthMatch ? widthMatch[1] : '';

            notes.push({ name, imgSrc, opacity, width });
        });

        tiers[tier] = notes;
    });

    if (!tiers.top) tiers.top = [];
    if (!tiers.middle) tiers.middle = [];
    if (!tiers.base) tiers.base = [];

    const totalNotes = tiers.top.length + tiers.middle.length + tiers.base.length;
    return totalNotes > 0 ? tiers : null;
})();
"""


# Tier widths: top = narrowest, base = widest (matching reference).
_TIER_MAX_WIDTH = {
    "top": "max-w-md",
    "middle": "max-w-xl",
    "base": "max-w-2xl",
}


def _calc_icon_width(note: dict) -> str:
    """Calculate the icon width based on opacity.

    Matches the reference convention where the most prominent note (opacity ~1)
    gets 5rem and the least prominent gets ~2.5rem.
    """
    # If the JS already captured an explicit width, use it.
    w = note.get("width", "")
    if w:
        return w
    opacity = note.get("opacity", 1.0)
    # Linear mapping: opacity 1.0 → 5rem, opacity 0.5 → 3.75rem, opacity 0 → 2.5rem
    rem = 2.5 + 2.5 * opacity
    return f"{rem:.2f}rem"


def _esc(s: str) -> str:
    """Minimal HTML-escape."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _render_note_item(note: dict) -> str:
    """Render a single note item (icon + label)."""
    width = _calc_icon_width(note)
    return (
        '            <div class="group relative flex flex-col items-center text-center '
        'pyramid-note-item" style="opacity: '
        f'{note.get("opacity", 1)}">\n'
        '              <div class="relative">\n'
        f'                <img loading="lazy" src="{_esc(note.get("imgSrc", ""))}" '
        'class="rounded-md shadow-xs ring-1 ring-zinc-200/20 transition-all '
        'duration-300 ease-out group-hover:scale-110 group-hover:shadow-md '
        'group-hover:ring-teal-400/40" alt="' + _esc(note["name"]) + '" '
        f'style="width: {width}">\n'
        '              </div>\n'
        '              <span class="pyramid-note-label mt-1.5 text-[11px] sm:text-sm '
        'font-medium text-zinc-600 group-hover:text-teal-600 transition-colors '
        'duration-200 whitespace-nowrap">\n'
        f'                {_esc(note["name"])}\n'
        '              </span>\n'
        '            </div>'
    )


def _render_tier(tier_name: str, notes: list[dict]) -> str:
    """Render one tier (top/middle/base) of the note pyramid."""
    max_w = _TIER_MAX_WIDTH[tier_name]
    label = f"{tier_name.capitalize()} Notes"
    items_html = "\n".join(_render_note_item(n) for n in notes)

    return (
        f'      <div class="mx-auto {max_w}" style="\n'
        '        width: 100% !important;\n'
        '        max-width: 100% !important;\n'
        '        display: flex !important;\n'
        '        flex-direction: column !important;\n'
        '        align-items: center !important;\n'
        '      ">\n'
        '        <div class="note-section-header" style="\n'
        '          width: 100% !important;\n'
        '          max-width: 100% !important;\n'
        '          display: flex !important;\n'
        '          flex-direction: column !important;\n'
        '          align-items: center !important;\n'
        '        ">\n'
        '          <div class="absolute inset-x-0 top-1/2 h-px bg-gradient-to-r '
        'from-transparent via-zinc-300/50 to-transparent"></div>\n'
        '          <h4 class="note-section-header" style="\n'
        '            width: 100% !important;\n'
        '            max-width: 100% !important;\n'
        '            display: flex !important;\n'
        '            flex-direction: column !important;\n'
        '            align-items: center !important;\n'
        '          ">\n'
        f'            <span class="note-section-header"> {label} </span>\n'
        '          </h4>\n'
        '        </div>\n'
        '        <div>\n'
        '          <div class="flex flex-wrap justify-center items-end py-3 px-2 '
        'pyramid-level-container" style="gap: 0.75rem">\n'
        f'{items_html}\n'
        '          </div>\n'
        '        </div>\n'
        '      </div>'
    )


def _render_notes_html(tiers: dict) -> str:
    """Render the full notes pyramid from tier data."""
    parts = []
    for tier_name in ("top", "middle", "base"):
        notes = tiers.get(tier_name, [])
        if notes:
            parts.append(_render_tier(tier_name, notes))

    inner = "\n".join(parts)
    return (
        '<div class="mt-6 space-y-1">\n'
        f'{inner}\n'
        '</div>'
    )


class NotesScraper(BaseScraper):
    document_title = "Fragrantica Notes Component"

    container_class = "fragrantica-notes-container"

    offline_css = SHARED_TAILWIND_CSS + """
.fragrantica-notes-container * {
    text-align: center !important;
    margin-top: 0 !important;
    padding-top: 0 !important;
    box-sizing: border-box !important;
}
.fragrantica-notes-container {
    direction: ltr !important;
    background-color: #ffffff !important;
}
.fragrantica-notes-container div,
.fragrantica-notes-container p,
.fragrantica-notes-container span {
    background-color: transparent !important;
    background: transparent !important;
    box-shadow: none !important;
}
.fragrantica-notes-container,
.fragrantica-notes-container div,
.fragrantica-notes-container span,
.fragrantica-notes-container p {
    color: #52525B !important;
    text-decoration: none !important;
}
.note-section-header {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 100% !important;
    max-width: 100% !important;
    margin-top: 2rem !important;
    margin-bottom: 0.5rem !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
    color: #18181B !important;
}
.note-section-header::before {
    content: "" !important;
    flex: 1 !important;
    border-bottom: 1px solid #18181B !important;
    opacity: 0.15 !important;
    margin-right: 15px !important;
    margin-left: 0 !important;
}
.note-section-header::after {
    content: "" !important;
    flex: 1 !important;
    border-bottom: 1px solid #18181B !important;
    opacity: 0.15 !important;
    margin-left: 15px !important;
    margin-right: 0 !important;
}
.fragrantica-notes-container .note-section-header:first-of-type {
    margin-top: 0.5rem !important;
}
.fragrantica-notes-container .pyramid-level-container {
    width: 100% !important;
    max-width: 100% !important;
    display: flex !important;
    justify-content: center !important;
    flex-wrap: wrap !important;
}
.fragrantica-notes-container img {
    margin-bottom: 0.25rem !important;
}
.fragrantica-notes-container .pyramid-note-item:hover,
.fragrantica-notes-container .pyramid-note-item:hover * {
    color: #43B1A8 !important;
    cursor: default;
}
"""

    # wrapper_classes intentionally not overridden: every section shares the
    # geometry-free card contract from BaseScraper. This used to declare
    # "my-8 mx-auto max-w-3xl", whose 2rem top/bottom margins came straight
    # off the card's visible height once it became a stretched grid item.

    def extract(self, page) -> str | None:
        try:
            data = page.run_js(_EXTRACT_JS)
        except Exception as e:
            from logging import getLogger
            getLogger(__name__).warning("NotesScraper.run_js failed: %s", e)
            return None
        if not data or not isinstance(data, dict):
            return None
        total = sum(len(v) for v in data.values() if isinstance(v, list))
        if total == 0:
            return None
        raw = _render_notes_html(data)
        raw = download_note_images(raw, Path(config.NOTE_IMAGES_DIR))
        raw = strip_note_links(raw)
        return raw
