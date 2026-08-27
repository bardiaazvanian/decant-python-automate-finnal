"""اجراکننده‌ی مایگریشن دیتابیس.

جداول فرگرنتیکا را در ``TarighatGallery_db`` می‌سازد و ردیف‌های موجود را از
``Sepidar01`` کپی می‌کند. اسکریپت SQL در ``sql/migrate_to_tarighatgallery.sql``
است و idempotent؛ اجرای چندباره بی‌خطر است.

    python migrate_db.py            # اجرای مایگریشن
    python migrate_db.py --check    # فقط وضعیت فعلی را نشان بده
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pyodbc

from config import config

# کنسول ویندوز پیش‌فرض cp1252 است و متن فارسی را نمی‌تواند چاپ کند.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

SQL_FILE = Path(__file__).with_name("sql") / "migrate_to_tarighatgallery.sql"

# جداکننده‌ی بچ در T-SQL. pyodbc نمی‌تواند GO را اجرا کند، پس دستی جدا می‌کنیم.
_GO_SPLIT = re.compile(r"^\s*GO\s*;?\s*$", re.IGNORECASE | re.MULTILINE)

TABLES = ("fragrantica_links", "perfume_data")


def _connect(database: str) -> pyodbc.Connection:
    return pyodbc.connect(config._conn_str(database), autocommit=True)


def _table_exists(cursor, database: str, table: str) -> bool:
    cursor.execute(
        "SELECT OBJECT_ID(?, N'U')", (f"[{database}].[dbo].[{table}]",)
    )
    return cursor.fetchone()[0] is not None


def _row_count(cursor, database: str, table: str) -> int | None:
    if not _table_exists(cursor, database, table):
        return None
    cursor.execute(f"SELECT COUNT(*) FROM [{database}].[dbo].[{table}]")
    return cursor.fetchone()[0]


def show_status() -> None:
    """وضعیت جداول در هر دو دیتابیس."""
    with _connect("master") as conn:
        cursor = conn.cursor()
        print(f"سرور: {config.DB_SERVER}")
        print("-" * 62)
        for database in (config.DB_SEPIDAR, config.DB_GALLERY):
            print(f"  {database}")
            for table in TABLES:
                count = _row_count(cursor, database, table)
                if count is None:
                    print(f"    {table:22} —  وجود ندارد")
                else:
                    print(f"    {table:22} {count:>5} ردیف")
        print("-" * 62)


def run_migration() -> int:
    if not SQL_FILE.is_file():
        print(f"❌ فایل SQL پیدا نشد: {SQL_FILE}", file=sys.stderr)
        return 1

    sql = SQL_FILE.read_text(encoding="utf-8")
    batches = [b.strip() for b in _GO_SPLIT.split(sql) if b.strip()]

    print("=== وضعیت قبل از مایگریشن ===")
    show_status()
    print()

    with _connect(config.DB_GALLERY) as conn:
        cursor = conn.cursor()
        for index, batch in enumerate(batches, start=1):
            try:
                cursor.execute(batch)
                # PRINT های داخل بچ به‌صورت پیام pyodbc برمی‌گردند.
                for message in getattr(cursor, "messages", []) or []:
                    text = str(message[1]).strip()
                    if text:
                        print(f"   {text}")
                # اگر بچ نتیجه‌ای برگرداند (بچ خلاصه‌ی نهایی) نمایش بده.
                while True:
                    if cursor.description:
                        for row in cursor.fetchall():
                            print("   " + " | ".join(str(v) for v in row))
                    if not cursor.nextset():
                        break
            except pyodbc.Error as exc:
                print(f"❌ خطا در بچ #{index}: {exc}", file=sys.stderr)
                print("--- SQL ---", file=sys.stderr)
                print(batch[:600], file=sys.stderr)
                return 1

    print()
    print("=== وضعیت بعد از مایگریشن ===")
    show_status()
    print()
    print("✅ مایگریشن تمام شد. جداول قدیمی در Sepidar01 دست‌نخورده باقی ماندند.")
    print("   بعد از تست کامل، بخش ۶ فایل SQL را برای تغییر نامشان اجرا کنید.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="انتقال جداول فرگرنتیکا به TarighatGallery_db"
    )
    parser.add_argument(
        "--check", action="store_true", help="فقط وضعیت فعلی را نشان بده"
    )
    args = parser.parse_args()

    if args.check:
        show_status()
        return 0
    return run_migration()


if __name__ == "__main__":
    raise SystemExit(main())
