"""Base utilities shared by all Fragrantica scrapers.

These scrapers run browser-side JavaScript via DrissionPage's
``page.run_js`` to extract the exact same DOM fragments that the
legacy standalone scripts produced (see ``old-script/``).  Each
``extract`` method returns the raw HTML fragment of the relevant
Fragrantica component (already cleaned of Vue artifacts) and a
shared :func:`wrap_html` builds a standalone, offline HTML document
around it — identical to the files the old scripts wrote to disk.
"""
from __future__ import annotations

import logging
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
import urllib.request

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Base class for all Fragrantica scrapers."""

    #: Title shown in the <title> tag of the produced HTML document.
    document_title: str = "Fragrantica Component"

    #: Inline <style> body to embed in every generated document.  These CSS
    #: rules are authored using the legacy unscoped selectors (e.g.
    #: ``.minimal-container``, ``.bg-white``, ``.grid`` ...) and are
    #: automatically re-scoped under :attr:`container_class` by
    #: :meth:`_scope_css` so they never leak into the host page.
    offline_css: str = ""

    #: Unique root class applied to the outer wrapper ``<div>``.  Each scraper
    #: uses a distinct value (``fragrantica-accords-container``,
    #: ``fragrantica-notes-container``, ...) so that several perfume blocks
    #: rendered on the same products page can coexist without their styles
    #: ever clashing with each other or with the host page's own CSS.
    container_class: str = "fragrantica-component"

    #: Tailwind-like classes re-emitted on the scoped wrapper ``<div>``.
    #:
    #: This is deliberately the SAME string for every scraper and it carries
    #: **no geometry** — no ``max-w-*``, no ``mx-auto``, no ``my-*``.  Each
    #: section used to declare its own (accords ``max-w-2xl``, notes
    #: ``max-w-3xl``, performance ``max-w-5xl``, plus three different paddings
    #: and three different vertical margins), which is what made the cards
    #: render at different sizes once they were placed side by side on the
    #: product page.  How wide a card is, and how tall, is the product page's
    #: grid decision -- see the ``.frg-row`` / card-contract rules in
    #: :data:`CARD_CONTRACT_CSS`.  A scraper only says "this is a card".
    #:
    #: The classes kept here are chrome only, and all of them exist in
    #: :data:`SHARED_TAILWIND_CSS`, so the standalone offline previews still
    #: render correctly.
    wrapper_classes: str = (
        "bg-white p-6 rounded-3xl shadow-lg border border-slate-100 w-full h-full"
    )

    @abstractmethod
    def extract(self, page) -> str | None:
        """Run JS in ``page`` (DrissionPage) and return the raw component HTML, or ``None``."""

    # ------------------------------------------------------------------ #
    # CSS scoping                                                         #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _scope_css(css: str, scope: str) -> str:
        """Re-scope every top-level selector in ``css`` under ``scope``.

        The legacy ``offline_css`` rules are written against the global
        un-scoped Tailwind utility classes (``.bg-white``, ``.minimal-container``,
        ``.grid`` ...).  When several perfume blocks are pasted into a single
        products page those rules collide with each other and with the host
        page.  To make every block fully self-contained we prefix each
        selector with the unique :attr:`container_class` of the scraper, so
        e.g. ``.minimal-container .bg-white`` becomes
        ``.fragrantica-accords-container .bg-white``.

        ``@media`` / ``@keyframes`` at-rules are preserved (their inner rules
        are scoped).  Raw type selectors (``div``, ``p`` ...) are also
        prefixed so they only apply inside the wrapper.
        """
        if not css or not css.strip():
            return css

        # Normalise the legacy outer-container selector to our unique scope.
        css = css.replace(".minimal-container", scope)

        out = []
        i = 0
        n = len(css)
        depth = 0
        buf = []
        # We walk the stylesheet block by block, respecting nested braces so
        # that @media / @supports at-rules keep their inner rules scoped too.
        while i < n:
            ch = css[i]

            if ch == "{":
                block = "".join(buf).strip()
                # Emit a scoped selector list (only at rule level; nested
                # property declarations are left untouched).
                out.append(BaseScraper._scope_selector_list(block, scope))
                out.append(" {")
                buf = []
                depth += 1
                i += 1
                continue

            if ch == "}":
                depth -= 1
                # Flush the captured rule body (property declarations like
                # "gap: 0.5rem; color: red;") before closing the block.  For
                # at-rule bodies (e.g. @media) `buf` here is the whitespace
                # between the last inner rule and the closing brace.
                body = "".join(buf).strip()
                if body:
                    out.append(" " + body + " ")
                out.append("}")
                buf = []
                i += 1
                continue

            buf.append(ch)
            i += 1

        return "".join(out)

    @staticmethod
    def _scope_selector_list(selector_list: str, scope: str) -> str:
        """Prefix each comma-separated selector with ``scope`` unless it already
        starts with the scope (e.g. after the ``.minimal-container`` swap) or
        is an at-rule keyword (``@media``, ``@keyframes``, ``@supports``).
        """
        sel = selector_list.strip()
        if not sel:
            return sel

        # Keep at-rule headers untouched (e.g. "@media (min-width: 640px)").
        if sel.startswith("@"):
            return sel

        parts = [p.strip() for p in sel.split(",")]
        scoped = []
        for p in parts:
            if not p:
                continue
            # Already scoped (e.g. ".fragrantica-accords-container .bg-white").
            if p.startswith(scope) or p.startswith(scope.replace(".", "")):
                scoped.append(p)
                continue
            # Bare type/universal selector (div, p, *, ::before ...) —
            # use descendant combinator so we don't restyle the wrapper
            # itself only its descendants.
            if p.startswith(("*", ":")):
                scoped.append(f"{scope} {p}")
            else:
                scoped.append(f"{scope} {p}")
        return ", ".join(scoped)

    # ------------------------------------------------------------------ #
    # Document construction                                                #
    # ------------------------------------------------------------------ #
    def wrap_html(self, raw_html: str) -> str:
        """Wrap ``raw_html`` as a **self-contained, scoped HTML fragment**
        safe to drop anywhere on a shared products page.

        Only the raw HTML fragment is emitted — **no inline ``<style>``**.
        The matching scoped CSS lives once in ``scrapers/style.css`` (see
        :meth:`build_shared_css`) which the host products page includes a
        single time via ``<link rel="stylesheet" href="style.css">``.  This
        keeps the rows stored in ``perfume_data`` small (they carry only the
        component markup) and guarantees the markup never duplicates the same
        ~10KB stylesheet on every single product.

        The output is just::

            <div class="{container_class} {wrapper_classes}">
                {raw_html}
            </div>

        Because each scraper subclass sets a unique ``container_class`` (e.g.
        ``fragrantica-accords-container``, ``fragrantica-notes-container``),
        any number of perfume blocks can coexist on the same products page
        without their styles colliding.
        """
        scope = self.container_class
        wrapper_classes = self.wrapper_classes

        return (
            f'<div class="{scope} {wrapper_classes}">\n'
            f"    {raw_html}\n"
            f"</div>"
        )

    def extract_and_wrap(self, page) -> str:
        """Run :meth:`extract` and wrap the result into a full HTML document.

        Returns the wrapped HTML string, or an empty string if the component was
        not found on the page (matching the legacy behaviour of writing a
        placeholder/fallback only when needed).
        """
        # Lazily-trigger any IntersectionObserver-bound content before
        # extracting.  Subclasses that know their target selector override
        # :meth:`scroll_target_into_view` to ensure Vue-driven XHRs fire.
        try:
            self.scroll_target_into_view(page)
        except Exception as e:  # pragma: no cover - non-fatal
            logger.debug("scroll_target_into_view failed for %s: %s",
                         type(self).__name__, e)

        raw = self.extract(page)
        if not raw:
            return ""
        return self.wrap_html(raw)

    # ------------------------------------------------------------------ #
    # Lazy-load helpers                                                  #
    # ------------------------------------------------------------------ #
    #: Optional CSS selector (or JS snippet returning an element) used by
    #: :meth:`scroll_target_into_view` to scroll the relevant section into the
    #: viewport before extraction.  ``None`` disables pre-extraction scrolling.
    scroll_selector: str | None = None

    #: How many polling cycles to wait for the target to render text content.
    scroll_wait_polls: int = 8

    #: Seconds to wait between polling cycles.
    scroll_wait_sleep: float = 1.0

    def scroll_target_into_view(self, page) -> None:
        """Scroll the target element into the viewport and wait for it to gain
        text content.  Fragrantica now lazy-loads the gender / season voting
        bars via IntersectionObserver + XHR, so the extractor must (a) scroll
        the (initially empty) card into view and (b) wait for Vue to render.
        """
        selector = self.scroll_selector
        if not selector:
            return

        for _ in range(self.scroll_wait_polls):
            text = page.run_js(
                r"""
                return (() => {
                    const el = document.querySelector(%r);
                    if (!el) return null;
                    el.scrollIntoView({block: 'center'});
                    return el.textContent.trim();
                })();
                """ % selector,
            )
            if text:
                return
            time.sleep(self.scroll_wait_sleep)


# ---------------------------------------------------------------------- #
# Shared offline Tailwind CSS                                            #
# ---------------------------------------------------------------------- #
#: Baseline Tailwind utility CSS used by the legacy notes / accords / seasons
#: scripts.  These are the exact class definitions copied from the old
#: ``fragmentia-html-scraper-seasons.html`` / ``fragrantica-html-top-notes.html``
#: outputs so the generated files render offline exactly like the originals.
SHARED_TAILWIND_CSS = """
*, ::before, ::after { box-sizing: border-box; margin: 0; padding: 0; }
.bg-gray-50 { background-color: #f9fafb; }
.bg-white { background-color: #ffffff; }
.min-h-screen { min-height: 100vh; }
.flex { display: flex; }
.flex-col { flex-direction: column; }
.flex-wrap { flex-wrap: wrap; }
.flex-1 { flex: 1 1 0%; }
.items-center { align-items: center; }
.items-end { align-items: flex-end; }
.items-stretch { align-items: stretch; }
.justify-center { justify-content: center; }
.justify-evenly { justify-content: space-evenly; }
.justify-between { justify-content: space-between; }
.gap-2 { gap: 0.5rem; }
.gap-4 { gap: 1rem; }
.gap-8 { gap: 2rem; }
.gap-1\\.5 { gap: 0.375rem; }
.grid { display: grid; }
.grid-cols-1 { grid-template-columns: repeat(1, minmax(0, 1fr)); }
.w-full { width: 100%; }
.w-4 { width: 1rem; }
.w-7 { width: 1.75rem; }
.w-8 { width: 2rem; }
.w-9 { width: 2.25rem; }
.w-16 { width: 4rem; }
.w-20 { width: 5rem; }
.h-4 { height: 1rem; }
.h-7 { height: 1.75rem; }
.h-8 { height: 2rem; }
.h-full { height: 100%; }
.h-1\\.5 { height: 0.375rem; }
.h-2 { height: 0.5rem; }
.h-2\\.5 { height: 0.625rem; }
.h-px { height: 1px; }
.h-5 { height: 1.25rem; }
.md\\:h-7 { height: 1.75rem; }
.max-w-3xl { max-width: 48rem; }
.max-w-4xl { max-width: 56rem; }
.max-w-5xl { max-width: 64rem; }
.max-w-2xl { max-width: 42rem; }
.max-w-xl { max-width: 36rem; }
.max-w-md { max-width: 28rem; }
.max-w-\\[280px\\] { max-width: 280px; }
.md\\:max-w-\\[320px\\] { max-width: 320px; }
.min-w-\\[2rem\\] { min-width: 2rem; }
.min-w-\\[40px\\] { min-width: 40px; }
.sm\\:min-w-\\[2.5rem\\] { min-width: 2.5rem; }
.max-w-\\[5rem\\] { max-width: 5rem; }
.sm\\:max-w-\\[5rem\\] { max-width: 5rem; }
.shrink-0 { flex-shrink: 0; }
.relative { position: relative; }
.absolute { position: absolute; }
.inset-x-0 { left: 0; right: 0; }
.p-2 { padding: 0.5rem; }
.p-4 { padding: 1rem; }
.p-6 { padding: 1.5rem; }
.p-8 { padding: 2rem; }
.px-2 { padding-left: 0.5rem; padding-right: 0.5rem; }
.py-1\\.5 { padding-top: 0.375rem; padding-bottom: 0.375rem; }
.py-2 { padding-top: 0.5rem; padding-bottom: 0.5rem; }
.mt-0\\.5 { margin-top: 0.125rem; }
.mt-1 { margin-top: 0.25rem; }
.mt-3 { margin-top: 0.75rem; }
.mt-4 { margin-top: 1rem; }
.mt-6 { margin-top: 1.5rem; }
.md\\:mb-6 { margin-bottom: 1.5rem; }
.mb-8 { margin-bottom: 2rem; }
.mb-5 { margin-bottom: 1.25rem; }
.mb-6 { margin-bottom: 1.5rem; }
.mx-auto { margin-left: auto; margin-right: auto; }
.sm\\:mt-1 { margin-top: 0.25rem; }
.sm\\:mt-1\\.5 { margin-top: 0.375rem; }
.sm\\:gap-2 { gap: 0.5rem; }
.sm\\:w-11 { width: 2.75rem; }
.sm\\:w-20 { width: 5rem; }
.sm\\:w-24 { width: 6rem; }
.sm\\:w-7 { width: 1.75rem; }
.sm\\:h-7 { height: 1.75rem; }
.lg\\:w-8 { width: 2rem; }
.lg\\:h-8 { height: 2rem; }
.lg\\:w-28 { width: 7rem; }
.space-y-1 > * + * { margin-top: 0.25rem; }
.space-y-2 > * + * { margin-top: 0.5rem; }
.text-xs { font-size: 0.75rem; line-height: 1rem; }
.text-sm { font-size: 0.875rem; line-height: 1.25rem; }
.text-\\[9px\\] { font-size: 9px; }
.text-\\[10px\\] { font-size: 10px; }
.text-\\[11px\\] { font-size: 11px; }
.sm\\:text-xs { font-size: 0.75rem; line-height: 1rem; }
.sm\\:text-sm { font-size: 0.875rem; line-height: 1.25rem; }
.sm\\:text-\\[10px\\] { font-size: 10px; }
.sm\\:text-\\[11px\\] { font-size: 11px; }
.lg\\:text-xs { font-size: 0.75rem; line-height: 1rem; }
.font-medium { font-weight: 500; }
.font-bold { font-weight: 700; }
.font-semibold { font-weight: 600; }
.text-center { text-align: center; }
.text-right { text-align: right; }
.text-zinc-300 { color: #d4d4d8; }
.text-zinc-400 { color: #a1a1aa; }
.text-zinc-500 { color: #71717a; }
.text-zinc-600 { color: #52525b; }
.text-amber-400 { color: #fbbf24; }
.text-pink-400 { color: #f472b6; }
.text-pink-300 { color: #f9a8d4; }
.text-teal-600 { color: #0d9488; }
.text-zinc-100 { color: #f4f4f5; }
.text-zinc-700 { color: #3f3f46; }
.uppercase { text-transform: uppercase; }
.tracking-wide { letter-spacing: 0.025em; }
.tracking-\\[0.2em\\] { letter-spacing: 0.2em; }
.line-clamp-1 { overflow: hidden; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 1; }
.truncate { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.whitespace-nowrap { white-space: nowrap; }
.rounded { border-radius: 0.25rem; }
.rounded-md { border-radius: 0.375rem; }
.rounded-lg { border-radius: 0.5rem; }
.rounded-xl { border-radius: 0.75rem; }
.rounded-2xl { border-radius: 1rem; }
.rounded-3xl { border-radius: 1.5rem; }
.rounded-br-lg { border-bottom-right-radius: 0.5rem; }
.rounded-full { border-radius: 9999px; }
.cursor-pointer { cursor: pointer; }
.overflow-hidden { overflow: hidden; }
.border { border-width: 1px; border-style: solid; }
.border-b { border-bottom-width: 1px; border-style: solid; }
.border-gray-100 { border-color: #f3f4f6; }
.border-slate-100 { border-color: #f1f5f9; }
.bg-zinc-50\\/50 { background-color: rgba(250, 250, 251, 0.5); }
.bg-zinc-100\\/70 { background-color: rgba(244, 244, 245, 0.7); }
.bg-zinc-200 { background-color: #e4e4e7; }
.bg-\\[\\#E5E7EB\\] { background-color: #E5E7EB; }
.bg-zinc-600 { background-color: #52525b; }
.bg-amber-400 { background-color: #fbbf24; }
.bg-pink-400 { background-color: #f472b6; }
.bg-pink-300 { background-color: #f9a8d4; }
.from-transparent { background-image: linear-gradient(to right, transparent, transparent); }
.to-transparent { background-image: linear-gradient(to right, transparent, transparent); }
.shadow-sm { box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05); }
.shadow-xs { box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.03); }
.shadow-md { box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1); }
.shadow-lg { box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1); }
.transition-all { transition-property: all; transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1); transition-duration: 150ms; }
.transition-colors { transition-property: color, background-color, border-color; transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1); }
.transition-all { transition-property: all; transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1); transition-duration: 300ms; }
.duration-200 { transition-duration: 200ms; }
.duration-300 { transition-duration: 300ms; }
.hover\\:shadow-md:hover { box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1); }
.hover\\:scale-\\[1.02\\]:hover { transform: scale(1.02); }
.hover\\:text-zinc-800:hover { color: #27272a; }
.ring-1 { box-shadow: 0 0 0 1px var(--ring-color, #e4e4e7); }
.ring-zinc-200\\/20 { --ring-color: rgba(228, 228, 231, 0.2); }
.ease-out { transition-timing-function: cubic-bezier(0, 0, 0.2, 1); }
.top-1\\/2 { top: 50%; }
.bg-gradient-to-r { background-image: linear-gradient(to right, var(--tw-gradient-stops)); }
.via-zinc-300\\/50 { --tw-gradient-stops: transparent, rgba(212, 212, 216, 0.5), transparent; }
.group-hover\\:scale-110:hover { transform: scale(1.1); }
.group-hover\\:shadow-md:hover { box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1); }
.group-hover\\:ring-teal-400\\/40 { --ring-color: rgba(45, 212, 191, 0.4); }
.group-hover\\:text-teal-600:hover { color: #0d9488; }
.to-fuchsia-50\\/30 { background-image: linear-gradient(to right bottom, #fff, rgba(250, 232, 255, 0.3)); }
.to-sky-50\\/30 { background-image: linear-gradient(to right bottom, #fff, rgba(224, 242, 254, 0.3)); }
.to-violet-50\\/30 { background-image: linear-gradient(to right bottom, #fff, rgba(245, 243, 255, 0.3)); }
.tabular-nums { font-variant-numeric: tabular-nums; }
.flex-1 { flex: 1 1 0%; }
.flex-wrap { flex-wrap: wrap; }
.inline-block { display: inline-block; }
.block { display: block; }
@media (min-width: 640px) {
    .sm\\:gap-2 { gap: 0.5rem; }
    .sm\\:gap-4 { gap: 1rem; }
}
@media (min-width: 768px) {
    .md\\:grid-cols-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .md\\:flex-row { flex-direction: row; }
    .md\\:items-center { align-items: center; }
    .md\\:justify-between { justify-content: space-between; }
    .md\\:justify-end { justify-content: flex-end; }
    .md\\:gap-4 { gap: 1rem; }
    .md\\:mb-6 { margin-bottom: 1.5rem; }
}
@media (min-width: 1024px) {
    .lg\\:w-28 { width: 7rem; }
}

.minimal-container {
    direction: ltr !important;
    background-color: #ffffff !important;
    font-family: ui-sans-serif, system-ui, sans-serif;
    width: 100%;
}
.minimal-container div,
.minimal-container p,
.minimal-container span,
.minimal-container a {
    box-shadow: none !important;
}
"""

#: Generic minimal container styles shared by multiple legacy outputs.
MINIMAL_CONTAINER_CSS = """
.minimal-container {
    direction: ltr !important;
    background-color: #ffffff !important;
    font-family: ui-sans-serif, system-ui, sans-serif;
    width: 100%;
}
.minimal-container div,
.minimal-container p,
.minimal-container span,
.minimal-container a {
    box-shadow: none !important;
}
"""

#: The single card contract, emitted once at the end of the shared stylesheet
#: by :func:`build_shared_css`.
#:
#: This lives here rather than being hand-maintained in the host site's
#: ``frg_style.css`` because that file is GENERATED by :func:`build_shared_css`
#: — anything hand-appended to it is destroyed the next time the stylesheet is
#: rebuilt.  Keeping it in the generator makes a rebuild reproduce it verbatim.
#:
#: It is intentionally NOT scoped per component: its whole purpose is to make
#: all five components resolve to the same box.
CARD_CONTRACT_CSS = r"""
/* =================================================================
   Fragrantica card contract
   -----------------------------------------------------------------
   Every Fragrantica section is one card, and every card is a grid
   item of a .frg-row. The row owns the geometry (how wide a card is,
   how many fit on a line); the card owns only its own chrome
   (padding, radius, border, shadow). No card sizes itself from its
   own content.

   The !important here is load-bearing, not decoration. The card
   markup is stored in the database, was produced by several
   generations of the scraper, and carries per-section Tailwind
   geometry baked into its class attribute -- max-w-2xl / max-w-3xl /
   max-w-5xl / mx-auto / my-6 / my-8 / p-6 / p-8, a different
   combination for every section. Stored HTML cannot be edited
   retroactively, so those classes have to be overridden from here
   for old rows and freshly scraped rows to resolve identically.
   ================================================================= */

/* --- The row: the layout system, and the only thing that decides how
       wide a card is.

       minmax(0, 1fr) rather than 1fr so that a long note name or a
       wide accord bar can never push its own track wider than its
       sibling's -- 1fr floors at min-content, minmax(0, 1fr) does not.

       Declared here rather than as Tailwind utilities in the view
       because app.css is a pre-purged Tailwind subset with no build
       step in this project: any utility the rest of the site does not
       already use is absent and silently does nothing. The old
       `items-stretch` on the seasons/gender row was exactly that. */
.frg-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    align-items: stretch;
    gap: 1.5rem;
    margin-top: 1.5rem;
}

@media (min-width: 768px) {
    .frg-row {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}

/* --- The card: one identical box for all six sections. */
.fragrantica-accords-container,
.fragrantica-notes-container,
.fragrantica-perf-wrapper,
.fragrantica-seasons-container,
.fragrantica-gender-container {
    box-sizing: border-box !important;

    /* Geometry comes from the grid track, never from the content.
       max-width:none neutralises the baked-in max-w-* classes.
       margin:0 neutralises my-* and mx-auto -- auto side margins would
       re-centre the card inside its own track, and top/bottom margins
       are what made NOTES and MAIN ACCORDS different heights: a grid
       item stretches its MARGIN box, so notes' my-8 (2rem top + 2rem
       bottom) came straight off its visible height.
       height:100% makes every card fill its row, so sibling cards
       share a common top and bottom edge whatever their content. */
    width: 100% !important;
    max-width: none !important;
    height: 100% !important;
    margin: 0 !important;

    /* Identical chrome. */
    padding: 1.5rem !important;
    background-color: #ffffff !important;
    border: 1px solid #f1f5f9 !important;
    border-radius: 1.5rem !important;
    box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1) !important;

    /* Two cards in a row rarely hold the same amount of content, so
       once height:100% has stretched the shorter one, centre its
       content column instead of leaving it top-heavy. */
    display: flex !important;
    flex-direction: column !important;
    justify-content: center !important;
}

/* --- The card's content: fill the card.

       Some stored generations cap their own content column. Accords
       ships `w-full max-w-[280px] md:max-w-[320px]`, and
       .fragrantica-accords-container .max-w-\[280px\] is defined
       further up this very file, so it binds: the accords bars were
       drawn 280px wide inside a 652px card. That is what made MAIN
       ACCORDS read as a narrower card than NOTES even when both boxes
       measured identically -- the box matched, the content inside did
       not. Notes already forces its tiers to 100% with inline styles;
       this does the same for every section from one place, as a
       percentage, with no fixed pixel width. */
.fragrantica-accords-container > *,
.fragrantica-notes-container > *,
.fragrantica-perf-wrapper > *,
.fragrantica-seasons-container > *,
.fragrantica-gender-container > * {
    width: 100% !important;
    max-width: none !important;
    margin-left: 0 !important;
    margin-right: 0 !important;
}
"""


def download_note_images(html: str, images_dir: Path) -> str:
    """Download all note images from ``fimgs.net`` and rewrite their URLs to the
    local shared folder.  Mirrors :func:`download_note_images` from the legacy
    ``fragrantica-html-top-notes.py`` script.
    """
    images_dir = Path(images_dir)
    images_dir.mkdir(parents=True, exist_ok=True)

    img_urls = re.findall(r'https://fimgs\.net/mdimg/sastojci/(t\.\d+\.jpg)', html)
    for filename in set(img_urls):
        local_path = images_dir / filename
        if not local_path.exists():
            url = f"https://fimgs.net/mdimg/sastojci/{filename}"
            logger.info("Downloading note image: %s", url)
            try:
                urllib.request.urlretrieve(url, str(local_path))
            except Exception as e:  # pragma: no cover - network errors
                logger.warning("Failed to download %s: %s", url, e)
    # Replace the remote prefix with the local dir path (forward slashes so the
    # resulting HTML works on both Windows and POSIX web servers).
    local_prefix = str(images_dir).replace("\\", "/")
    return html.replace("https://fimgs.net/mdimg/sastojci/", f"{local_prefix}/")


def strip_note_links(html: str) -> str:
    """Replace ``<a href=".../notes/...">`` links with ``<div>`` wrappers, matching
    the legacy :func:`strip_note_links` behaviour."""
    html = re.sub(
        r'<a\s+href="https://www\.fragrantica\.com/notes/[^"]*"([^>]*)>',
        lambda m: '<div' + re.sub(r'\bpyramid-note-link\b', 'pyramid-note-item', m.group(1)) + '>',
        html,
    )
    html = html.replace('</a>', '</div>')
    return html


def build_shared_css(scrapers) -> str:
    """Build the single shared, fully-scoped stylesheet for all ``scrapers``.

    Each scraper's :attr:`offline_css` (+ optional ``extra_head_style``) is
    re-scoped under its own :attr:`container_class` via
    :meth:`BaseScraper._scope_css` and concatenated.  The returned string is
    meant to be written once to ``scrapers/style.css`` and served as a single
    ``<link>`` on the products page; the per-product HTML stored in
    ``perfume_data`` then carries no inline ``<style>`` of its own.

    Usage::

        from scrapers.base import build_shared_css
        from scrapers.main_accords import MainAccordsScraper
        # ... etc.
        Path("scrapers/style.css").write_text(
            build_shared_css([MainAccordsScraper(), NotesScraper(),
                              PerformanceScraper(), GenderScraper(),
                              SeasonsScraper()]),
            encoding="utf-8",
        )
    """
    parts = [
        "/* =================================================================\n"
        "   Auto-generated single shared stylesheet for all Fragrantica scraper\n"
        "   outputs.  Every selector is scoped under a unique per-component\n"
        "   wrapper class so that multiple perfume blocks can be pasted onto\n"
        "   one products page without their styles colliding with each other,\n"
        "   or with the host page.\n"
        "\n"
        "   Include this file ONCE on your products page:\n"
        "       <link rel=\"stylesheet\" href=\"style.css\">\n"
        "   The scraper HTML stored in perfume_data then needs NO inline <style>.\n"
        "   ================================================================= */\n"
    ]
    for s in scrapers:
        scope = ".%s" % s.container_class
        full = s.offline_css + ("\n" + s.extra_head_style if getattr(s, "extra_head_style", "") else "")
        scoped = BaseScraper._scope_css(full, scope)
        parts.append("\n/* ---- %s ---- */\n%s\n" % (s.container_class, scoped))
    # The card contract goes last so it wins on source order against the
    # per-component container rules emitted above (several of which set their
    # own width/height), independently of specificity.
    parts.append(CARD_CONTRACT_CSS)
    return "".join(parts)

