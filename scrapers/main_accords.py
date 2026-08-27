"""Main accords scraper — data-driven template approach.

Instead of cloning arbitrary DOM elements (which varies as Fragrantica
updates their site), this scraper:

1. Extracts structured data (name, color, opacity, width) from each
   accord bar via a targeted JS query.
2. Renders the data through a fixed Python HTML template that always
   produces the same markup — matching the reference layout exactly.

The reference structure (from a known-good product page) is:
    .fragrantica-accords-container.bg-white.rounded-3xl
      div.flex.flex-col.w-full.mx-auto.p-6
        h3  "Main Accords"
        div.w-full > div[inline-styled bar] > span.truncate (name)
"""
from __future__ import annotations

from .base import BaseScraper, SHARED_TAILWIND_CSS


# ---------------------------------------------------------------------------
# JS extraction — returns [ { name, color, bgColor, opacity, width }, ... ]
# Targets the accords section by looking for the heading or a known container,
# then collects each bar's data from its inline styles.
# ---------------------------------------------------------------------------
_EXTRACT_JS = r"""
return (() => {
    let container = null;

    // 1. Try heading first (may exist on some page versions).
    let heading = Array.from(document.querySelectorAll('h3, h4, h5, span')).find(
        el => el.textContent && el.textContent.trim() === 'Main Accords'
    );
    if (heading) {
        container = heading.closest('.body-accord-container')
                 || heading.closest('[class*="accord"]')
                 || heading.parentElement;
    }

    // 2. Try .body-accord-container directly.
    if (!container) {
        container = document.querySelector('.body-accord-container');
    }

    // 3. Find by class: flex flex-col w-full with bars, NOT inside notes.
    if (!container) {
        const notesRoot = document.querySelector('#pyramid, .mt-6.space-y-1');
        const all = document.querySelectorAll('div');
        for (const el of all) {
            if (notesRoot && notesRoot.contains(el)) continue;
            const cls = el.getAttribute('class') || '';
            if (/\bflex\b/.test(cls) && /\bflex-col\b/.test(cls) && /\bw-full\b/.test(cls)) {
                const bars = el.querySelectorAll('div[style*="background"]');
                if (bars.length >= 3) { container = el; break; }
            }
        }
    }
    if (!container) return null;

    // 2. Collect all bar elements.
    const bars = Array.from(container.querySelectorAll('div[style*="background"]'));
    if (bars.length === 0) return null;

    const result = [];
    for (const bar of bars) {
        const span = bar.querySelector('span');
        if (!span) continue;
        const name = span.textContent.trim();
        if (!name) continue;

        const style = bar.getAttribute('style') || '';

        const colorMatch = style.match(/color:\s*([^;]+)/);
        const color = colorMatch ? colorMatch[1].trim() : 'rgb(0, 0, 0)';

        const bgMatch = style.match(/background:\s*([^;]+)/);
        const bgColor = bgMatch ? bgMatch[1].trim() : 'rgb(200, 200, 200)';

        const opacityMatch = style.match(/opacity:\s*([\d.]+)/);
        const opacity = opacityMatch ? parseFloat(opacityMatch[1]) : 1;

        const widthMatch = style.match(/width:\s*([\d.]+%)/);
        const width = widthMatch ? widthMatch[1] : '100%';

        result.push({ name, color, bgColor, opacity, width });
    }
    return result.length > 0 ? result : null;
})();
"""


def _render_accords_html(accords: list[dict]) -> str:
    """Render the accords data list into the canonical HTML template."""
    bars_html = "\n".join(
        f'            <div class="w-full">\n'
        f'              <div class="h-9 md:h-20 rounded-br-lg flex items-center justify-center '
        f'px-2 md:px-3 text-s md:text-sm font-medium transition-all duration-200 '
        f'hover:scale-[1.02]" style="\n'
        f'                color: {a["color"]};\n'
        f'                background: {a["bgColor"]};\n'
        f'                opacity: {a["opacity"]};\n'
        f'                width: {a["width"]};\n'
        f'              ">\n'
        f'                <span class="truncate">{_esc(a["name"])}</span>\n'
        f'              </div>\n'
        f'            </div>'
        for a in accords
    )
    return (
        # No mx-auto and no p-6 here: the card wrapper supplies the padding,
        # uniformly for every section. This element also used to carry
        # "max-w-[280px] md:max-w-[320px]", which capped the accord bars at
        # 280px inside a much wider card and made MAIN ACCORDS look narrower
        # than NOTES. Content must not decide the card's width.
        '<div class="flex flex-col w-full">\n'
        '  <h3 class="text-sm font-medium text-slate-600 mb-4 text-center">'
        'Main Accords</h3>\n'
        f'  {bars_html}\n'
        '</div>'
    )


def _esc(s: str) -> str:
    """Minimal HTML-escape for note/accord names."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class MainAccordsScraper(BaseScraper):
    document_title = "Fragrantica Minimal Component"

    container_class = "fragrantica-accords-container"

    offline_css = SHARED_TAILWIND_CSS + """
.fragrantica-accords-container * {
    text-align: center !important;
}
.fragrantica-accords-container {
    direction: ltr !important;
}
"""

    # wrapper_classes intentionally not overridden: every section shares the
    # geometry-free card contract from BaseScraper. This used to declare
    # "bg-white rounded-3xl flex border border-slate-100 items-center
    # justify-center" -- no padding at all, unlike every other section.

    def extract(self, page) -> str | None:
        try:
            data = page.run_js(_EXTRACT_JS)
        except Exception as e:
            from logging import getLogger
            getLogger(__name__).warning("MainAccordsScraper.run_js failed: %s", e)
            return None
        if not data or not isinstance(data, list):
            return None
        return _render_accords_html(data)
