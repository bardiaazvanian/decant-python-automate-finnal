"""Seasons / "When To Wear" scraper — data-driven template approach.

Instead of cloning the entire ``.tw-rating-card`` DOM element (which varies
as Fragrantica updates their site), this scraper:

1. Extracts structured data for each season/time item: name, SVG icon,
   vote count, bar width percentage, and bar color.
2. Renders the data through a fixed Python HTML template that always
   produces markup matching the reference layout.

The reference structure (from a known-good product page) is:
    .fragrantica-seasons-container.bg-white.p-6.rounded-3xl
      div.tw-rating-card.w-full
        div.tw-rating-card-header  (clock icon + "When To Wear" label)
        div.p-2 > div.flex.justify-evenly.gap-2
          div.flex.flex-col (one per season/time)
            div (SVG icon)
            span (label)
            div (progress bar)
            span (vote count)
"""
from __future__ import annotations

from .base import BaseScraper, SHARED_TAILWIND_CSS


# ---------------------------------------------------------------------------
# JS extraction — returns [ { name, svgHtml, votes, pct, barColor }, ... ]
# Ordered: winter, spring, summer, fall, day, night
# ---------------------------------------------------------------------------
_EXTRACT_JS = r"""
return (() => {
    // Find the "When To Wear" heading.
    const targetHeader = Array.from(document.querySelectorAll('*')).find(
        el => el.textContent && el.textContent.trim() === 'When To Wear'
    );
    if (!targetHeader) return null;

    const container = targetHeader.closest('.tw-rating-card') || targetHeader.parentElement;
    if (!container) return null;

    // Collect season/time items.
    const items = container.querySelectorAll('.flex.flex-col.items-center');
    if (items.length === 0) return null;

    // Known season colors as fallback (from reference).
    const SEASON_COLORS = {
        winter: 'rgb(120, 214, 240)',
        spring: 'rgb(159, 229, 132)',
        summer: 'rgb(252, 149, 138)',
        fall: 'rgb(249, 190, 110)',
        day: 'rgb(245, 158, 11)',
        night: 'rgb(139, 184, 212)'
    };

    const result = [];
    let maxVotes = 0;

    // First pass: find max votes for percentage calculation.
    items.forEach(item => {
        const voteSpan = item.querySelector('span.block, span[style*="tabular-nums"]');
        if (voteSpan) {
            const v = parseInt(voteSpan.textContent.trim(), 10) || 0;
            if (v > maxVotes) maxVotes = v;
        }
    });

    items.forEach(item => {
        // Label (winter, spring, etc.)
        const labelSpan = item.querySelector('span.font-medium');
        if (!labelSpan) return;
        const name = labelSpan.textContent.trim().toLowerCase();

        // SVG icon (first svg in the item).
        const svgEl = item.querySelector('svg');
        const svgHtml = svgEl ? svgEl.outerHTML : '';

        // Vote count and color — try multiple sources.
        const voteSpans = item.querySelectorAll('span');
        let votes = 0;
        let barColor = SEASON_COLORS[name] || 'rgb(200, 200, 200)';

        // Source 1: color from the vote count span's inline style.
        voteSpans.forEach(span => {
            const text = span.textContent.trim();
            const num = parseInt(text, 10);
            if (!isNaN(num) && num > 0) {
                const cls = span.getAttribute('class') || '';
                if (cls.includes('font-semibold')) {
                    votes = num;
                    const style = span.getAttribute('style') || '';
                    const colorMatch = style.match(/color:\s*([^;]+)/);
                    if (colorMatch) {
                        barColor = colorMatch[1].trim();
                    }
                }
            }
        });

        // Source 2: color from the bar fill div's background-color.
        const fillDiv = item.querySelector('.h-full.rounded');
        if (fillDiv) {
            const fillStyle = fillDiv.getAttribute('style') || '';
            const bgColorMatch = fillStyle.match(/background-color:\s*([^;]+)/);
            if (bgColorMatch) {
                barColor = bgColorMatch[1].trim();
            }
        }

        // Bar width from the fill div.
        let pct = 0;
        if (fillDiv) {
            const fillStyle = fillDiv.getAttribute('style') || '';
            const widthMatch = fillStyle.match(/width:\s*([\d.]+)%/);
            if (widthMatch) {
                pct = parseFloat(widthMatch[1]);
            }
        }

        // Calculate from votes if no explicit width.
        if (pct === 0 && maxVotes > 0 && votes > 0) {
            pct = Math.round((votes / maxVotes) * 100);
        }

        result.push({ name, svgHtml, votes, pct, barColor });
    });

    return result.length > 0 ? result : null;
})();
"""


# Ordered list of valid season/time names for consistent ordering.
_SEASON_ORDER = ["winter", "spring", "summer", "fall", "day", "night"]


def _esc(s: str) -> str:
    """Minimal HTML-escape."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _render_season_item(item: dict) -> str:
    """Render a single season/time item."""
    return (
        '          <div class="flex flex-col items-center cursor-pointer flex-1 '
        'min-w-[2rem] sm:min-w-[2.5rem] max-w-[5rem]">\n'
        '            <div class="relative w-7 h-7 sm:w-7 sm:h-7 lg:w-8 lg:h-8 '
        'flex items-center justify-center">\n'
        f'              <div class="w-7 h-7 sm:w-7 sm:h-7 lg:w-8 lg:h-8 '
        f'transition-all duration-200 text-zinc-300" '
        f'style="display: inline-block">\n'
        f'                {item.get("svgHtml", "")}\n'
        '              </div>\n'
        '            </div>\n'
        f'            <span class="text-[10px] sm:text-[11px] lg:text-xs font-medium '
        f'mt-0.5 transition-colors duration-200 text-zinc-500">'
        f'{_esc(item["name"])}</span>\n'
        '            <div class="w-full mt-1 sm:mt-1.5">\n'
        '              <div class="relative h-1.5 sm:h-2 bg-zinc-200 rounded '
        'overflow-hidden">\n'
        f'                <div class="h-full rounded" style="width: {item["pct"]}%; '
        f'background-color: {item["barColor"]};"></div>\n'
        '              </div>\n'
        f'              <span class="block text-[9px] sm:text-[10px] font-semibold '
        f'text-center mt-0.5 tabular-nums" style="color: {item["barColor"]}">'
        f'{item["votes"]}</span>\n'
        '            </div>\n'
        '          </div>'
    )


def _render_seasons_html(items: list[dict]) -> str:
    """Render the full seasons/time section from extracted data."""
    # Sort items by the canonical order.
    ordered = sorted(items, key=lambda x: _SEASON_ORDER.index(x["name"])
                     if x["name"] in _SEASON_ORDER else 99)

    items_html = "\n".join(_render_season_item(it) for it in ordered)

    return (
        '<div class="tw-rating-card w-full">\n'
        '  <div class="tw-rating-card-header">\n'
        '    <div class="flex items-center gap-2">\n'
        '      <svg class="w-4 h-4 text-amber-400" fill="currentColor" '
        'viewBox="0 0 24 24">\n'
        '        <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 '
        '10-10S17.5 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 '
        '8 8-3.59 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67V7z"></path>\n'
        '      </svg>\n'
        '      <span class="tw-rating-card-label">When To Wear</span>\n'
        '    </div>\n'
        '  </div>\n'
        '  <div class="p-2">\n'
        '    <div class="flex justify-evenly gap-2 md:gap-4">\n'
        f'{items_html}\n'
        '    </div>\n'
        '  </div>\n'
        '</div>'
    )


class SeasonsScraper(BaseScraper):
    document_title = "Fragrantica - When To Wear"

    container_class = "fragrantica-seasons-container"

    scroll_selector: str = '.tw-rating-card'
    scroll_wait_polls: int = 10
    scroll_wait_sleep: float = 1.0

    offline_css = SHARED_TAILWIND_CSS + """
.fragrantica-seasons-container * {
    text-align: center !important;
}
.fragrantica-seasons-container {
    direction: ltr !important;
}
"""

    # wrapper_classes intentionally not overridden: every section shares the
    # geometry-free card contract from BaseScraper.

    def extract(self, page) -> str | None:
        try:
            data = page.run_js(_EXTRACT_JS)
        except Exception as e:
            from logging import getLogger
            getLogger(__name__).warning("SeasonsScraper.run_js failed: %s", e)
            return None
        if not data or not isinstance(data, list):
            return None
        return _render_seasons_html(data)
