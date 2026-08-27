"""Performance (longevity/sillage) scraper — data-driven template approach.

Instead of cloning the Vue-rendered ``.tw-perf-card`` elements (whose
structure changes as Fragrantica updates their site), this scraper:

1. Extracts structured data from each card: rows with label, vote count,
   and calculated bar width percentage.
2. Renders the data through fixed Python HTML templates that always
   produce the same markup matching the reference layout.

The reference structure (from a known-good product page) is:
    .fragrantica-perf-wrapper.bg-white.p-8.rounded-3xl
      div.tw-perf-card
        div.p-4 > div > div (icon + title + rows)
"""
from __future__ import annotations

import re

from .base import BaseScraper, SHARED_TAILWIND_CSS


# ---------------------------------------------------------------------------
# JS extraction — returns { sillage: { iconSvg, rows: [...] },
#                                    longevity: { iconSvg, rows: [...] } }
# Each row: { label, count, pct }  (pct = 0..100 for bar width)
# ---------------------------------------------------------------------------
_EXTRACT_JS = r"""
return (() => {
    const perfContainer = document.getElementById('performance');
    if (!perfContainer) return null;

    const allCards = Array.from(perfContainer.querySelectorAll('.tw-perf-card'));
    if (allCards.length === 0) return null;

    function extractCardData(card) {
        if (!card) return null;

        // 1. Extract the icon SVG (first svg inside the card header).
        const svgEl = card.querySelector('svg');
        const iconSvg = svgEl ? svgEl.outerHTML : '';

        // 2. Collect voting rows. Each row has: label, count, and a bar
        //    whose width is set via inline style on the inner fill div.
        const rowEls = card.querySelectorAll('.flex.items-center.gap-1\\.5, .flex.items-center.gap-2');
        const rows = [];
        let maxCount = 0;

        rowEls.forEach(row => {
            // Label: first span with text.
            const labelSpan = row.querySelector('span.text-xs, span.text-sm');
            // Count: the small numeric span.
            const countSpan = row.querySelector('span.text-\\[10px\\], span.text-xs.font-medium');
            // Bar fill: the inner div with width style.
            const fillDiv = row.querySelector('.h-full.rounded-full');

            if (!labelSpan || !countSpan) return;
            const label = labelSpan.textContent.trim();
            if (label.toLowerCase() === 'no vote') return;

            const count = parseInt(countSpan.textContent.trim(), 10) || 0;
            if (count > maxCount) maxCount = count;

            // Get width from inline style on the fill div.
            let pct = 0;
            if (fillDiv) {
                const fillStyle = fillDiv.getAttribute('style') || '';
                const widthMatch = fillStyle.match(/width:\s*([\d.]+)%/);
                if (widthMatch) {
                    pct = parseFloat(widthMatch[1]);
                }
            }

            rows.push({ label, count, pct });
        });

        // If no widths were set (e.g. Vue hasn't rendered yet), calculate
        // percentages from vote counts.
        if (maxCount > 0 && rows.every(r => r.pct === 0)) {
            rows.forEach(r => {
                r.pct = Math.round((r.count / maxCount) * 100);
            });
        }

        return { iconSvg, rows };
    }

    // Fragrantica accents these two cards differently: the LONGEVITY card
    // carries `to-violet`, the SILLAGE card carries `to-sky`. Verified against
    // a real product page -- the to-violet card holds the longevity scale
    // (very weak / weak / moderate / long lasting / eternal) and the to-sky
    // card holds the sillage scale (intimate / moderate / strong / enormous).
    //
    // These two lookups were inverted, so the card titled "SILLAGE" was
    // rendered from longevity's votes and vice versa. Besides being wrong
    // data, it also gave the two cards a different number of rows (5 vs 4)
    // and therefore different heights when shown side by side.
    const longevityCard = allCards.find(c => c.className.includes('to-violet'));
    const sillageCard = allCards.find(c => c.className.includes('to-sky'));

    const sillage = extractCardData(sillageCard);
    const longevity = extractCardData(longevityCard);

    if (!sillage && !longevity) return null;
    return { sillage, longevity };
})();
"""


def _esc(s: str) -> str:
    """Minimal HTML-escape."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _render_perf_row(row: dict) -> str:
    """Render a single voting row (label + count + bar)."""
    return (
        '                <div class="flex items-center gap-1.5 sm:gap-2">\n'
        '                  <div class="w-20 sm:w-24 lg:w-28 shrink-0">\n'
        f'                    <span class="text-xs sm:text-sm text-zinc-600 line-clamp-1">'
        f'{_esc(row["label"])}</span>\n'
        '                  </div>\n'
        '                  <div class="w-9 sm:w-11 shrink-0 text-right">\n'
        f'                    <span class="text-[10px] sm:text-xs font-medium text-zinc-500">'
        f'{row["count"]}</span>\n'
        '                  </div>\n'
        '                  <div class="flex-1 min-w-[40px]">\n'
        '                    <div class="w-full h-2.5 bg-zinc-200 rounded-full '
        'overflow-hidden cursor-pointer">\n'
        '                      <div class="h-full rounded-full transition-all '
        f'duration-300" style="width: {row["pct"]}%; '
        'background-color: rgb(13, 148, 136);"></div>\n'
        '                    </div>\n'
        '                  </div>\n'
        '                </div>'
    )


def _render_perf_card(title: str, card_data: dict, wrapper_cls: str) -> str:
    """Render one performance card (longevity or sillage).

    ``wrapper_cls`` is supplied by the caller from the scraper's shared
    ``container_class`` / ``wrapper_classes`` so these two cards use exactly the
    same card contract as every other section. This function used to hard-code
    its own wrapper (``p-8 ... my-8 mx-auto max-w-5xl``), which is why the
    performance cards were the only ones with a 64rem cap and 2rem margins.
    """
    rows_html = "\n".join(_render_perf_row(r) for r in card_data.get("rows", []))
    icon_svg = card_data.get("iconSvg", "")

    # Build the "no vote" placeholder div (hidden, matching reference).
    no_vote_div = (
        '              <div style="display: none">\n'
        '                <span class="text-sm text-zinc-600">no vote</span>\n'
        '                <div class="custom-track">\n'
        '                  <div class="custom-fill" style="width: 0%; '
        'background-color: rgb(0, 148, 135);"></div>\n'
        '                </div>\n'
        '              </div>'
    )

    return (
        f'<div class="{wrapper_cls}">\n'
        '  <div class="tw-perf-card" style="\n'
        '    background: linear-gradient(to right bottom, rgb(255,255,255) 0px, '
        'rgb(255,255,255) 50%, rgba(240,240,255,0.3) 100%) 0% 0% / auto repeat '
        'scroll padding-box border-box rgba(0,0,0,0);\n'
        '    border-radius: 16px;\n'
        '  ">\n'
        '    <div class="p-4">\n'
        '      <div>\n'
        '        <div class="flex flex-col items-center flex-wrap">\n'
        f'          <div class="w-8 h-8 text-zinc-500" style="display: inline-block">\n'
        f'            {icon_svg}\n'
        '          </div>\n'
        f'          <span class="text-xs font-medium text-zinc-600 uppercase '
        f'tracking-wide mt-1">{_esc(title)}</span>\n'
        '        </div>\n'
        f'{no_vote_div}\n'
        '        <div class="mt-3 space-y-2">\n'
        f'{rows_html}\n'
        '        </div>\n'
        '      </div>\n'
        '    </div>\n'
        '  </div>\n'
        '</div>'
    )


class PerformanceScraper(BaseScraper):
    document_title = "Fragrantica Performance Cards - Perfect"

    container_class = "fragrantica-perf-wrapper"

    offline_css = SHARED_TAILWIND_CSS + """
.custom-track {
    width: 100%;
    height: 8px;
    background-color: #E5E7EB;
    border-radius: 999px;
    position: relative;
    overflow: visible;
    margin-top: 6px;
}
.custom-fill {
    height: 100%;
    border-radius: 999px;
    position: absolute;
    left: 0;
    top: 0;
    transition: width 0.5s ease-in-out;
}
.fragrantica-perf-wrapper .tw-perf-card,
.fragrantica-perf-wrapper .tw-perf-card h4,
.fragrantica-perf-wrapper .tw-perf-card b,
.fragrantica-perf-wrapper .tw-perf-card span,
.fragrantica-perf-wrapper .tw-perf-card p,
.fragrantica-perf-wrapper .tw-perf-card div {
    color: #4B5563 !important;
    font-weight: 600 !important;
}
.fragrantica-perf-wrapper .tw-perf-card svg,
.fragrantica-perf-wrapper .tw-perf-card svg path,
.fragrantica-perf-wrapper .tw-perf-card svg fill {
    fill: #4B5563 !important;
    stroke: #4B5563 !important;
}
"""

    scroll_selector: str = '.tw-perf-card[class*="to-sky"]'
    scroll_wait_polls: int = 12
    scroll_wait_sleep: float = 1.0

    # wrapper_classes intentionally not overridden: every section shares the
    # geometry-free card contract from BaseScraper.

    def extract(self, page) -> str | None:
        """Legacy single-output path (kept for backward-compat)."""
        result = self.extract_separate(page)
        if not result:
            return None
        sillage, longevity = result
        combined = sillage or longevity or ""
        return combined

    def extract_separate(self, page) -> tuple[str, str] | None:
        """Run the browser JS and return ``(sillage_html, longevity_html)``.

        Each fragment is individually wrapped with :meth:`wrap_html`.
        Returns ``None`` only when *neither* card could be extracted.
        """
        try:
            raw = page.run_js(_EXTRACT_JS)
        except Exception as e:
            from logging import getLogger
            getLogger(__name__).warning("PerformanceScraper.run_js failed: %s", e)
            return None
        if not raw or not isinstance(raw, dict):
            return None

        sillage_data = raw.get("sillage")
        longevity_data = raw.get("longevity")

        if not sillage_data and not longevity_data:
            return None

        # Same wrapper for both cards, and the same one every other section
        # uses -- see BaseScraper.wrapper_classes and CARD_CONTRACT_CSS.
        wrapper_cls = f"{self.container_class} {self.wrapper_classes}"

        sillage_html = (
            _render_perf_card("SILLAGE", sillage_data, wrapper_cls)
            if sillage_data else ""
        )
        longevity_html = (
            _render_perf_card("LONGEVITY", longevity_data, wrapper_cls)
            if longevity_data else ""
        )

        return sillage_html, longevity_html
