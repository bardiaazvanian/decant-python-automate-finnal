"""Gender scraper — data-driven template approach.

Instead of cloning the gender ``.tw-perf-card`` element (which varies as
Fragrantica updates their site), this scraper:

1. Extracts structured data: icon SVG, and rows with label, vote count,
   bar width percentage, and bar color class.
2. Renders the data through a fixed Python HTML template that always
   produces markup matching the reference layout.

The reference structure (from a known-good product page) is:
    .fragrantica-gender-container.bg-white.p-6.rounded-3xl
      div.tw-perf-card
        div.p-4 > div > div.mb-6 (icon + title + hidden no-vote + rows)
"""
from __future__ import annotations

import re

from .base import BaseScraper, SHARED_TAILWIND_CSS


# ---------------------------------------------------------------------------
# JS extraction — returns { iconSvg, rows: [...] }
# Each row: { label, count, pct, colorClass }
# ---------------------------------------------------------------------------
_EXTRACT_JS = r"""
return (() => {
    const allCards = Array.from(document.querySelectorAll('.tw-perf-card'));
    if (allCards.length === 0) return null;

    // 1. Find the gender card by text content.
    let genderCard = allCards.find(card => {
        const text = card.textContent.toLowerCase();
        return text.includes('unisex') || text.includes('more male') || text.includes('more female');
    });

    // 2. Fallback — by accent class.
    if (!genderCard) {
        genderCard = allCards.find(card => {
            const cls = card.className || '';
            return cls.includes('to-fuchsia') && !cls.includes('to-sky') && !cls.includes('to-violet');
        });
    }

    if (!genderCard) return null;

    // 1. Extract icon SVG.
    const svgEl = genderCard.querySelector('svg');
    const iconSvg = svgEl ? svgEl.outerHTML : '';

    // 2. Collect voting rows (same structure as performance cards,
    //    but with colored fill bars).
    const rowEls = genderCard.querySelectorAll('.flex.items-center.gap-1\\.5, .flex.items-center.gap-2');
    const rows = [];
    let maxCount = 0;

    rowEls.forEach(row => {
        const labelSpan = row.querySelector('span.text-xs, span.text-sm');
        const countSpan = row.querySelector('span.text-\\[10px\\], span.text-xs.font-medium');
        const fillDiv = row.querySelector('.h-full.rounded-full');

        if (!labelSpan || !countSpan) return;
        const label = labelSpan.textContent.trim();
        if (label.toLowerCase() === 'no vote') return;

        const count = parseInt(countSpan.textContent.trim(), 10) || 0;
        if (count > maxCount) maxCount = count;

        // Get width from inline style.
        let pct = 0;
        if (fillDiv) {
            const fillStyle = fillDiv.getAttribute('style') || '';
            const widthMatch = fillStyle.match(/width:\s*([\d.]+)%/);
            if (widthMatch) {
                pct = parseFloat(widthMatch[1]);
            }
        }

        // Get color class from the fill div.
        let colorClass = '';
        if (fillDiv) {
            const cls = fillDiv.className || '';
            // Find the Tailwind color class (bg-pink-400, bg-teal-500, etc.)
            const colorMatch = cls.match(/bg-(pink-\d+|teal-\d+|blue-\d+|purple-\d+|violet-\d+|rose-\d+)/);
            if (colorMatch) {
                colorClass = 'bg-' + colorMatch[1];
            }
        }

        rows.push({ label, count, pct, colorClass });
    });

    // Calculate percentages from counts if widths weren't set.
    if (maxCount > 0 && rows.every(r => r.pct === 0)) {
        rows.forEach(r => {
            r.pct = Math.round((r.count / maxCount) * 100);
        });
    }

    return { iconSvg, rows };
})();
"""


def _esc(s: str) -> str:
    """Minimal HTML-escape."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# Default fallback colors when the JS can't detect a color class.
_DEFAULT_GENDER_COLORS = {
    "female": "bg-pink-400",
    "more female": "bg-pink-300",
    "unisex": "bg-teal-500",
    "more male": "bg-blue-300",
    "male": "bg-blue-400",
}


def _render_gender_row(row: dict) -> str:
    """Render a single gender voting row."""
    color_class = row.get("colorClass", "")
    if not color_class:
        color_class = _DEFAULT_GENDER_COLORS.get(row["label"], "bg-zinc-400")

    return (
        '                <div class="flex items-center gap-1.5 sm:gap-2">\n'
        '                  <div class="w-16 sm:w-20 lg:w-24 shrink-0">\n'
        f'                    <span class="text-xs sm:text-sm text-zinc-600 line-clamp-1">'
        f'{_esc(row["label"])}</span>\n'
        '                  </div>\n'
        '                  <div class="w-9 sm:w-11 shrink-0 text-right">\n'
        f'                    <span class="text-[10px] sm:text-xs font-medium text-zinc-500">'
        f'{row["count"]}</span>\n'
        '                  </div>\n'
        '                  <div class="flex-1 min-w-[40px]">\n'
        '                    <div class="w-full h-2.5 bg-[#E5E7EB] rounded-full '
        'overflow-hidden cursor-pointer">\n'
        f'                      <div class="h-full rounded-full transition-all '
        f'duration-300 {color_class}" style="width: {row["pct"]}%"></div>\n'
        '                    </div>\n'
        '                  </div>\n'
        '                </div>'
    )


def _render_gender_html(data: dict) -> str:
    """Render the full gender card from extracted data."""
    rows_html = "\n".join(_render_gender_row(r) for r in data.get("rows", []))
    icon_svg = data.get("iconSvg", "")

    return (
        '<div class="tw-perf-card">\n'
        '  <div class="p-4">\n'
        '    <div>\n'
        '      <div class="mb-6">\n'
        '        <div class="flex flex-col items-center flex-wrap">\n'
        f'          <div class="w-8 h-8 text-zinc-500" style="display: inline-block">\n'
        f'            {icon_svg}\n'
        '          </div>\n'
        '          <span class="text-xs font-medium text-zinc-600 uppercase '
        'tracking-wide mt-1">GENDER</span>\n'
        '        </div>\n'
        '        <div>\n'
        '          <div style="visibility: hidden">\n'
        '            <span class="text-sm text-zinc-600">no vote</span>\n'
        '          </div>\n'
        '        </div>\n'
        '        <div class="mt-4">\n'
        '          <div class="mt-3 space-y-2">\n'
        f'{rows_html}\n'
        '          </div>\n'
        '        </div>\n'
        '      </div>\n'
        '    </div>\n'
        '  </div>\n'
        '</div>'
    )


class GenderScraper(BaseScraper):
    document_title = "Fragrantica Gender Card - Perfect Color"

    container_class = "fragrantica-gender-container"

    scroll_selector: str = '.tw-perf-card[class*="to-fuchsia"]'
    scroll_wait_polls: int = 12
    scroll_wait_sleep: float = 1.0

    offline_css = SHARED_TAILWIND_CSS + """
.fragrantica-gender-container {
    direction: ltr !important;
    background-color: #ffffff !important;
    font-family: ui-sans-serif, system-ui, sans-serif;
    width: 100%;
}
.fragrantica-gender-container div,
.fragrantica-gender-container p,
.fragrantica-gender-container span,
.fragrantica-gender-container a {
    box-shadow: none !important;
}
.fragrantica-gender-container .tw-perf-card,
.fragrantica-gender-container .tw-perf-card h4,
.fragrantica-gender-container .tw-perf-card b,
.fragrantica-gender-container .tw-perf-card span,
.fragrantica-gender-container .tw-perf-card p,
.fragrantica-gender-container .tw-perf-card div {
    color: #4B5563 !important;
    font-weight: 600 !important;
}
.fragrantica-gender-container .tw-perf-card svg,
.fragrantica-gender-container .tw-perf-card svg path,
.fragrantica-gender-container .tw-perf-card svg fill {
    fill: #4B5563 !important;
    stroke: #4B5563 !important;
}
"""

    # wrapper_classes intentionally not overridden: every section shares the
    # geometry-free card contract from BaseScraper.

    def extract(self, page) -> str | None:
        try:
            data = page.run_js(_EXTRACT_JS)
        except Exception as e:
            from logging import getLogger
            getLogger(__name__).warning("GenderScraper.run_js failed: %s", e)
            return None
        if not data or not isinstance(data, dict):
            return None
        rows = data.get("rows", [])
        if not rows:
            return None
        return _render_gender_html(data)
