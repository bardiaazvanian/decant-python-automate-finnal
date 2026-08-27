"""دسترسی دیتابیس اسکرپر.

جداول فرگرنتیکا (``fragrantica_links`` و ``perfume_data``) در دیتابیس
``TarighatGallery_db`` هستند؛ دیتابیس اصلی سپیدار (``Sepidar01``) فقط برای
خواندن ``POS.Item`` در پنل استفاده می‌شود (‏url_panel.py‏).

همه‌ی کوئری‌ها با نام کامل سه‌قسمتی جدول نوشته شده‌اند (از ``config``)، پس
مهم نیست اتصال به کدام کاتالوگ باز شده باشد.
"""
import pyodbc

from config import config


def get_connection():
    """اتصال به دیتابیس گالری (خانه‌ی جداول فرگرنتیکا)."""
    return pyodbc.connect(config.gallery_conn_str)


def fetch_pending_links(limit=10):
    conn = get_connection()
    cursor = conn.cursor()

    query = f"""
    SELECT TOP (?) id, url
    FROM {config.tbl_links}
    WHERE status = 'pending' OR status IS NULL
    """
    cursor.execute(query, (limit,))
    rows = cursor.fetchall()

    conn.close()
    return [{"id": row.id, "url": row.url} for row in rows]


def save_scraped_data(link_id, accords_html, notes_html, sillage_html, longevity_html, gender_html, seasons_html):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(f"""
            IF EXISTS (SELECT 1 FROM {config.tbl_perfume_data} WHERE link_id = ?)
                UPDATE {config.tbl_perfume_data}
                SET accords_html = ?, notes_html = ?, sillage_html = ?, longevity_html = ?, gender_html = ?, seasons_html = ?
                WHERE link_id = ?
            ELSE
                INSERT INTO {config.tbl_perfume_data} (link_id, accords_html, notes_html, sillage_html, longevity_html, gender_html, seasons_html)
                VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (link_id, accords_html, notes_html, sillage_html, longevity_html, gender_html, seasons_html, link_id,
              link_id, accords_html, notes_html, sillage_html, longevity_html, gender_html, seasons_html))

        cursor.execute(
            f"UPDATE {config.tbl_links} SET status = 'scraped' WHERE id = ?", (link_id,)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error saving data for link_id {link_id}: {e}")
        cursor.execute(
            f"UPDATE {config.tbl_links} SET status = 'error' WHERE id = ?", (link_id,)
        )
        conn.commit()
    finally:
        conn.close()
