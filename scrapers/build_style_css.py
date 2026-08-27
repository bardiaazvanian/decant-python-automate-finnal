"""Regenerate scrapers/style.css from the scrapers' offline_css definitions.

Run after editing any scraper's offline_css / container_class::

    python scrapers/build_style_css.py
"""
from pathlib import Path

from scrapers.base import build_shared_css
from scrapers.main_accords import MainAccordsScraper
from scrapers.notes import NotesScraper
from scrapers.performance import PerformanceScraper
from scrapers.gender import GenderScraper
from scrapers.seasons import SeasonsScraper


def main() -> None:
    scrapers = [MainAccordsScraper(), NotesScraper(), PerformanceScraper(),
                GenderScraper(), SeasonsScraper()]
    out = Path(__file__).parent / "style.css"
    out.write_text(build_shared_css(scrapers), encoding="utf-8")
    print(f"Wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
