"""Quick smoke test: call each scraper's render function with sample data
and verify the output contains expected HTML structures."""
import sys
sys.path.insert(0, ".")

from scrapers.main_accords import MainAccordsScraper, _render_accords_html
from scrapers.notes import NotesScraper, _render_notes_html
from scrapers.performance import PerformanceScraper, _render_perf_card, _render_perf_row
from scrapers.gender import GenderScraper, _render_gender_html
from scrapers.seasons import SeasonsScraper, _render_seasons_html


def test_accords():
    items = [
        {"name": "sweet", "color": "#e11d48", "bgColor": "rgba(225,29,72,0.18)", "opacity": 0.73, "width": 73},
        {"name": "floral", "color": "#e879f9", "bgColor": "rgba(232,121,249,0.18)", "opacity": 0.63, "width": 63},
        {"name": "powdery", "color": "#a78bfa", "bgColor": "rgba(167,139,250,0.18)", "opacity": 0.56, "width": 56},
    ]
    html = _render_accords_html(items)
    s = MainAccordsScraper()
    wrapped = s.wrap_html(html)
    assert 'fragrantica-accords-container' in wrapped
    assert 'sweet' in wrapped
    assert 'floral' in wrapped
    assert 'powdery' in wrapped
    assert 'e11d48' in wrapped.lower()
    assert 'Main Accords' in html
    print("  accords OK")


def test_notes():
    data = {
        "top": [
            {"name": "Bergamot", "imgSrc": "https://fimgs.net/mdimg/sastojci/t.123.jpg", "opacity": 0.9, "width": 90},
            {"name": "Black Currant", "imgSrc": "", "opacity": 0.5, "width": 50},
        ],
        "middle": [
            {"name": "Rose", "imgSrc": "https://fimgs.net/mdimg/sastojci/t.456.jpg", "opacity": 0.7, "width": 70},
        ],
        "base": [
            {"name": "Vanilla", "imgSrc": "", "opacity": 1.0, "width": 100},
        ],
    }
    html = _render_notes_html(data)
    s = NotesScraper()
    wrapped = s.wrap_html(html)
    assert 'fragrantica-notes-container' in wrapped
    assert 'Top Notes' in html
    assert 'Middle Notes' in html
    assert 'Base Notes' in html
    assert 'Bergamot' in html
    assert 'Rose' in html
    assert 'Vanilla' in html
    assert 'note-section-header' in html
    print("  notes OK")


def test_longevity():
    rows = [
        {"label": "weak", "count": 1, "pct": 5},
        {"label": "moderate", "count": 10, "pct": 50},
        {"label": "long lasting", "count": 8, "pct": 40},
        {"label": "eternal", "count": 1, "pct": 5},
    ]
    card_html = _render_perf_card("longevity", {"rows": rows}, '<svg viewBox="0 0 24 24"></svg>')
    assert 'longevity' in card_html.lower()
    assert 'moderate' in card_html
    assert 'long lasting' in card_html
    print("  longevity OK")


def test_sillage():
    rows = [
        {"label": "intimate", "count": 2, "pct": 20},
        {"label": "moderate", "count": 5, "pct": 50},
        {"label": "strong", "count": 3, "pct": 30},
        {"label": "enormous", "count": 0, "pct": 0},
    ]
    card_html = _render_perf_card("sillage", {"rows": rows}, '<svg viewBox="0 0 24 24"></svg>')
    assert 'sillage' in card_html.lower()
    assert 'intimate' in card_html
    assert 'strong' in card_html
    print("  sillage OK")


def test_gender():
    rows = [
        {"label": "female", "pct": 33, "count": 50, "colorClass": "bg-pink-400"},
        {"label": "more female", "pct": 27, "count": 41, "colorClass": "bg-pink-300"},
        {"label": "unisex", "pct": 20, "count": 30, "colorClass": "bg-teal-500"},
        {"label": "more male", "pct": 13, "count": 20, "colorClass": "bg-blue-300"},
        {"label": "male", "pct": 7, "count": 10, "colorClass": "bg-blue-400"},
    ]
    html = _render_gender_html({"iconSvg": '<svg viewBox="0 0 24 24"></svg>', "rows": rows})
    s = GenderScraper()
    wrapped = s.wrap_html(html)
    assert 'fragrantica-gender-container' in wrapped
    assert 'female' in html
    assert 'unisex' in html
    assert 'male' in html
    assert 'bg-pink-400' in html
    print("  gender OK")


def test_seasons():
    items = [
        {"name": "winter", "svgHtml": '<svg viewBox="0 0 128 128"></svg>', "votes": 293, "pct": 93, "barColor": "rgb(120, 214, 240)"},
        {"name": "spring", "svgHtml": '<svg viewBox="0 0 128 128"></svg>', "votes": 105, "pct": 33, "barColor": "rgb(159, 229, 132)"},
        {"name": "summer", "svgHtml": '<svg viewBox="0 0 128 128"></svg>', "votes": 68, "pct": 21, "barColor": "rgb(252, 149, 138)"},
        {"name": "fall", "svgHtml": '<svg viewBox="0 0 128 128"></svg>', "votes": 124, "pct": 39, "barColor": "rgb(249, 190, 110)"},
        {"name": "day", "svgHtml": '<svg viewBox="0 0 128 128"></svg>', "votes": 211, "pct": 66, "barColor": "rgb(245, 158, 11)"},
        {"name": "night", "svgHtml": '<svg viewBox="0 0 128 128"></svg>', "votes": 255, "pct": 80, "barColor": "rgb(139, 184, 212)"},
    ]
    html = _render_seasons_html(items)
    s = SeasonsScraper()
    wrapped = s.wrap_html(html)
    assert 'fragrantica-seasons-container' in wrapped
    assert 'winter' in html
    assert 'spring' in html
    assert 'summer' in html
    assert 'fall' in html
    assert 'day' in html
    assert 'night' in html
    assert 'When To Wear' in html
    assert 'rgb(120, 214, 240)' in html
    assert '293' in html
    print("  seasons OK")


if __name__ == "__main__":
    print("Testing scraper template rendering...")
    test_accords()
    test_notes()
    test_longevity()
    test_sillage()
    test_gender()
    test_seasons()
    print("\nAll tests passed!")
