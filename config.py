from dataclasses import dataclass, field
from ipaddress import ip_address, ip_network
import os
import random


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]


def random_user_agent() -> str:
    return random.choice(USER_AGENTS)


# ---------------------------------------------------------------------------
# آی‌پی‌های مجاز پنل
# پیش‌فرض: سیستم حسابداری (همان آی‌پی پروژه decant-query-automate-finnal)
# + لوکال‌هاست تا خود همین سرور هم بتواند پنل را باز کند.
# قابل بازنویسی با متغیر محیطی:  set PANEL_ALLOWED_IPS=192.168.10.54,192.168.10.0/24
# ---------------------------------------------------------------------------
_DEFAULT_ALLOWED_IPS = "192.168.10.54,127.0.0.1,::1"


def _allowed_ips_from_env() -> tuple[str, ...]:
    raw = os.environ.get("PANEL_ALLOWED_IPS", _DEFAULT_ALLOWED_IPS)
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _panel_port_from_env() -> int:
    """پورت پنل، قابل تغییر با متغیر محیطی PANEL_PORT."""
    try:
        return int(os.environ.get("PANEL_PORT", "5000"))
    except ValueError:
        return 5000


@dataclass(frozen=True)
class Config:
    # ---------------------------------------------------------------- SQL Server
    DB_DRIVER: str = "ODBC Driver 17 for SQL Server"
    DB_SERVER: str = "DESKTOP-DOOJ4J2"

    # دیتابیس اصلی سپیدار — فقط برای *خواندن* POS.Item (ItemID / Code / Title).
    # هیچ نوشتنی روی این دیتابیس انجام نمی‌شود.
    DB_SEPIDAR: str = "Sepidar01"

    # دیتابیس گالری — جداول فرگرنتیکا (fragrantica_links / perfume_data) اینجاست.
    DB_GALLERY: str = "TarighatGallery_db"

    # ---------------------------------------------------------------- Panel (URL panel)
    PANEL_HOST: str = "0.0.0.0"
    # پورت پنل. با متغیر محیطی PANEL_PORT هم قابل تغییر است.
    PANEL_PORT: int = field(default_factory=_panel_port_from_env)
    # اگر پورت اصلی توسط ویندوز رزرو شده باشد (WinError 10013) یا پروسه‌ی
    # دیگری آن را گرفته باشد، به‌ترتیب این پورت‌ها امتحان می‌شوند.
    PANEL_PORT_FALLBACKS: tuple[int, ...] = (5001, 5050, 5080, 8000, 8080, 8090)
    # فقط این آی‌پی‌ها اجازه‌ی استفاده از پنل را دارند. هر عضو می‌تواند
    # یک آی‌پی تکی ("192.168.10.54") یا یک رنج CIDR ("192.168.10.0/24") باشد.
    PANEL_ALLOWED_IPS: tuple[str, ...] = field(default_factory=_allowed_ips_from_env)

    # ---------------------------------------------------------------- Proxy
    USE_PROXY: bool = False
    PROXY_HOST: str = "127.0.0.1"
    PROXY_PORT: int = 10808

    # ---------------------------------------------------------------- Browser
    HEADLESS: bool = False
    VIEWPORT_WIDTH: int = 1440
    VIEWPORT_HEIGHT: int = 900

    # ---------------------------------------------------------------- Retry
    MAX_RETRIES: int = 3
    RETRY_DELAY_SECONDS: float = 5.0

    # ---------------------------------------------------------------- Fragrantica
    FRAGRANTICA_BASE_URL: str = "https://www.fragrantica.com"

    # Note images (shared directory for downloaded note ingredient images)
    NOTE_IMAGES_DIR: str = r"D:\shared-image"

    # ---------------------------------------------------------------- Delays
    # Anti-detection delays (seconds) — all randomized around these base values
    DELAY_BETWEEN_PRODUCTS_MIN: float = 15.0
    DELAY_BETWEEN_PRODUCTS_MAX: float = 30.0
    DELAY_AFTER_SEARCH_MIN: float = 3.0
    DELAY_AFTER_SEARCH_MAX: float = 6.0
    DELAY_AFTER_PAGE_LOAD_MIN: float = 4.0
    DELAY_AFTER_PAGE_LOAD_MAX: float = 8.0
    DELAY_BETWEEN_SCRAPERS_MIN: float = 2.0
    DELAY_BETWEEN_SCRAPERS_MAX: float = 5.0
    DELAY_TYPING_MIN: float = 0.05
    DELAY_TYPING_MAX: float = 0.15
    SCROLL_PAUSE_MIN: float = 0.3
    SCROLL_PAUSE_MAX: float = 0.8

    # ------------------------------------------------------------------------
    # رشته‌های اتصال
    # ------------------------------------------------------------------------
    def _conn_str(self, database: str) -> str:
        return (
            f"Driver={{{self.DB_DRIVER}}};"
            f"Server={self.DB_SERVER};"
            f"Database={database};"
            f"Trusted_Connection=yes;"
        )

    @property
    def sepidar_conn_str(self) -> str:
        """اتصال با کاتالوگ پیش‌فرض Sepidar01 (برای خواندن POS.Item)."""
        return self._conn_str(self.DB_SEPIDAR)

    @property
    def gallery_conn_str(self) -> str:
        """اتصال با کاتالوگ پیش‌فرض TarighatGallery_db (جداول فرگرنتیکا)."""
        return self._conn_str(self.DB_GALLERY)

    @property
    def conn_str(self) -> str:
        """اتصال پیش‌فرض پروژه.

        پنل و اسکرپر هر دو با نام کامل سه‌قسمتی جدول کار می‌کنند، پس این
        اتصال هم به جداول سپیدار دسترسی دارد و هم به جداول گالری. کاتالوگ
        پیش‌فرض روی سپیدار است چون دیتابیس اصلی سیستم همان است.
        """
        return self.sepidar_conn_str

    # ------------------------------------------------------------------------
    # نام کامل جداول (سه‌قسمتی) — تا مهم نباشد اتصال به کدام کاتالوگ باز شده
    # ------------------------------------------------------------------------
    @property
    def tbl_item(self) -> str:
        """جدول کالای سپیدار — منبع ItemID و Code."""
        return f"[{self.DB_SEPIDAR}].[POS].[Item]"

    @property
    def tbl_links(self) -> str:
        return f"[{self.DB_GALLERY}].[dbo].[fragrantica_links]"

    @property
    def tbl_perfume_data(self) -> str:
        return f"[{self.DB_GALLERY}].[dbo].[perfume_data]"

    @property
    def proxy_url(self) -> str:
        return f"socks5://{self.PROXY_HOST}:{self.PROXY_PORT}"


config = Config()


def is_ip_allowed(client_ip: str | None, allowed: tuple[str, ...] | None = None) -> bool:
    """آیا این آی‌پی اجازه‌ی استفاده از پنل را دارد؟

    هر عضو لیست مجاز می‌تواند یک آی‌پی تکی یا یک رنج CIDR باشد. آدرس‌های
    IPv4-mapped IPv6 (مثل ``::ffff:192.168.10.54``) هم به شکل IPv4 مقایسه
    می‌شوند تا اتصال از طریق IPv6 باعث رد شدن اشتباهی نشود.
    """
    if not client_ip:
        return False
    if allowed is None:
        allowed = config.PANEL_ALLOWED_IPS

    try:
        addr = ip_address(client_ip)
    except ValueError:
        return False

    # ::ffff:192.168.10.54  →  192.168.10.54
    mapped = getattr(addr, "ipv4_mapped", None)
    candidates = [addr] + ([mapped] if mapped else [])

    for entry in allowed:
        for candidate in candidates:
            try:
                if "/" in entry:
                    if candidate in ip_network(entry, strict=False):
                        return True
                elif candidate == ip_address(entry):
                    return True
            except ValueError:
                continue
    return False
