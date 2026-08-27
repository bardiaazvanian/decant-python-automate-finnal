import random
import logging
import time
from DrissionPage import ChromiumPage

from config import config, random_user_agent
from database import fetch_pending_links, save_scraped_data

from scrapers.main_accords import MainAccordsScraper
from scrapers.notes import NotesScraper
from scrapers.performance import PerformanceScraper
from scrapers.gender import GenderScraper
from scrapers.seasons import SeasonsScraper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def process_single_url(page: ChromiumPage, item: dict):
    link_id = item['id']
    url = item['url']

    logger.info(f"🔍 در حال پردازش لینک ID {link_id}: {url}")

    try:
        # ۱. باز کردن صفحه
        page.get(url)

        # ۲. بررسی و انتظار برای حل شدن چالش کلودفلر
        if page.ele('text:Just a moment...', timeout=3):
            logger.warning("⚠️ کلودفلر ظاهر شد. در حال انتظار برای عبور...")
            page.wait.ele_deleted('text:Just a moment...', timeout=30)

        # ۳. اسکرول تدریجی جهت فعال‌سازی Lazy Loading المان‌های پایینی
        logger.info("📜 اسکرول تدریجی صفحه برای بارگذاری کامل المان‌ها...")
        for scroll_step in range(11):
            page.scroll.down(750)
            time.sleep(4)

        # ۴. انتظار صریح برای ۵ بخش اصلی با مکانیزم نرم (Soft Wait)
        selectors_to_wait = [
            ('#pyramid', 'نوت‌های عطر'),
            ('.body-accord-container, [class*="max-w-[280px]"]', 'آکوردهای اصلی'),
            ('#voting-gender-container', 'جنسیت'),
            ('#voting-small-charts-container', 'عملکرد/ماندگاری'),
            ('#voting-season-container, .tw-rating-card', 'فصل‌ها و زمان')
        ]

        for selector, name in selectors_to_wait:
            try:
                if page.ele(selector, timeout=3):
                    logger.info(f"  ✓ بخش {name} پیدا شد.")
            except Exception:
                logger.warning(f"  ⚠️ بخش {name} ({selector}) در DOM ظاهر نشد (احتمالاً وجود ندارد).")

        # مکث کوتاه نهایی جهت تثبیت کامل DOM
        time.sleep(1.5)

        # ۵. استخراج داده‌ها توسط اسکرپرها
        accords_html = MainAccordsScraper().extract_and_wrap(page)
        notes_html = NotesScraper().extract_and_wrap(page)

        perf_result = PerformanceScraper().extract_separate(page)
        if perf_result:
            sillage_html, longevity_html = perf_result
        else:
            sillage_html, longevity_html = "", ""

        gender_html = GenderScraper().extract_and_wrap(page)
        seasons_html = SeasonsScraper().extract_and_wrap(page)

        # ۷. ذخیره در دیتابیس
        save_scraped_data(
            link_id=link_id,
            accords_html=accords_html or "",
            notes_html=notes_html or "",
            sillage_html=sillage_html,
            longevity_html=longevity_html,
            gender_html=gender_html or "",
            seasons_html=seasons_html or ""
        )
        logger.info(f"✅ اطلاعات عطر ID {link_id} با موفقیت استخراج و ذخیره شد.")

    except Exception as e:
        logger.error(f"❌ خطا در پردازش آدرس ID {link_id}: {e}", exc_info=True)


def run_pipeline():
    logger.info("🚀 شروع اجرای پایپ‌لاین اسکرپر...")
    items = fetch_pending_links(limit=10)

    if not items:
        logger.warning("⚠️ هیچ لینک در انتظار پردازشی (pending) در دیتابیس یافت نشد!")
        return

    logger.info(f"تعداد {len(items)} لینک برای پردازش یافت شد.")

    page = ChromiumPage()

    try:
        for item in items:
            process_single_url(page, item)

            delay = random.uniform(config.DELAY_BETWEEN_PRODUCTS_MIN, config.DELAY_BETWEEN_PRODUCTS_MAX)
            logger.info(f"💤 مکث {delay:.2f} ثانیه‌ای قبل از عطر بعدی...\n" + "-"*50)
            time.sleep(delay)
    finally:
        page.quit()
        logger.info("✨ تمام عملیات اسکرپ با موفقیت پایان یافت.")


if __name__ == "__main__":
    run_pipeline()