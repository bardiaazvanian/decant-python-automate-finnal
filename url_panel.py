"""پنل ثبت لینک فرگرنتیکا.

دو دیتابیس در کار است:
  * ``Sepidar01``          → فقط *خواندن* ``POS.Item`` برای گرفتن ItemID و Code
  * ``TarighatGallery_db`` → جداول ``fragrantica_links`` و ``perfume_data``

هر دو با یک اتصال و نام کامل سه‌قسمتی جدول نوشته می‌شوند، پس همه‌ی درج‌ها
داخل یک تراکنش هستند و امکان نیمه‌کاره ماندن وجود ندارد.

دسترسی به پنل به آی‌پی‌های ``config.PANEL_ALLOWED_IPS`` محدود است.
"""
import logging
import socket

from flask import Flask, render_template_string, request, jsonify
import pyodbc

from config import config, is_ip_allowed

logger = logging.getLogger(__name__)

panel_app = Flask(__name__)


def get_db_connection():
    """اتصال به سرور با کاتالوگ پیش‌فرض سپیدار.

    نام جداول از ``config`` می‌آید و سه‌قسمتی است، پس این یک اتصال به هر دو
    دیتابیس دسترسی دارد و کل ثبت در یک تراکنش انجام می‌شود.
    """
    return pyodbc.connect(config.conn_str)


# ---------------------------------------------------------------------------
# محدودیت آی‌پی — فقط سیستم(های) مجاز می‌توانند پنل را باز کنند.
# عمداً از X-Forwarded-For استفاده نمی‌کنیم: آن هدر از سمت کلاینت قابل جعل
# است و کل این کنترل را بی‌اثر می‌کند. remote_addr آی‌پی واقعی سوکت است.
# ---------------------------------------------------------------------------
DENIED_HTML = """<!DOCTYPE html>
<html lang="fa" dir="rtl"><head><meta charset="UTF-8">
<title>دسترسی غیرمجاز</title>
<style>
  body {{ font-family: Tahoma, sans-serif; background:#1b1f24; color:#eee;
         display:flex; align-items:center; justify-content:center;
         min-height:100vh; margin:0; }}
  .box {{ background:#262b31; border:1px solid #3a4149; border-radius:16px;
          padding:40px 50px; text-align:center; max-width:520px; }}
  h1 {{ margin:0 0 14px; font-size:1.4rem; color:#ff6b6b; }}
  code {{ background:#1b1f24; padding:3px 8px; border-radius:6px; color:#ffd166; }}
  p {{ line-height:1.9; opacity:.85; }}
</style></head><body>
<div class="box">
  <h1>⛔ دسترسی غیرمجاز</h1>
  <p>آی‌پی شما <code>{client_ip}</code> اجازه‌ی استفاده از این پنل را ندارد.</p>
  <p>برای دریافت دسترسی، آی‌پی خود را در <code>PANEL_ALLOWED_IPS</code>
     (فایل <code>config.py</code>) اضافه کنید.</p>
</div></body></html>"""


@panel_app.before_request
def restrict_by_ip():
    client_ip = request.remote_addr
    if is_ip_allowed(client_ip):
        return None

    logger.warning("⛔ تلاش دسترسی غیرمجاز از %s به %s", client_ip, request.path)

    if request.path.startswith('/api/'):
        return jsonify({
            'success': False,
            'message': f'دسترسی غیرمجاز! آی‌پی شما ({client_ip}) اجازه اجرا ندارد.'
        }), 403
    return DENIED_HTML.format(client_ip=client_ip), 403


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ثبت لینک فرگرنتیکا با کد کالا</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.rtl.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;600;700&display=swap');
        
        body {
            font-family: 'Vazirmatn', sans-serif;
            background: linear-gradient(135deg, #eef2f3 0%, #8e9eab 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .main-card {
            background: #ffffff;
            border-radius: 20px;
            box-shadow: 0 15px 35px rgba(0,0,0,0.12);
            border: none;
            overflow: hidden;
            max-width: 650px;
            width: 100%;
        }

        .card-header-custom {
            background: linear-gradient(45deg, #0f2027, #203a43, #2c5364);
            color: white;
            padding: 30px;
            text-align: center;
        }

        .card-header-custom h3 {
            margin: 0;
            font-weight: 700;
            font-size: 1.6rem;
        }

        .card-header-custom p {
            margin-top: 8px;
            opacity: 0.8;
            font-size: 0.9rem;
        }

        .card-body-custom {
            padding: 35px;
        }

        .form-label {
            font-weight: 600;
            color: #333;
            margin-bottom: 8px;
        }

        .form-control {
            border-radius: 12px;
            padding: 12px 16px;
            border: 1px solid #e0e0e0;
            background-color: #f9fafb;
            transition: all 0.3s ease;
        }

        .form-control:focus {
            background-color: #fff;
            border-color: #2c5364;
            box-shadow: 0 0 0 4px rgba(44, 83, 100, 0.15);
        }

        .btn-submit {
            background: linear-gradient(45deg, #0f2027, #2c5364);
            border: none;
            border-radius: 12px;
            padding: 14px;
            font-weight: 700;
            font-size: 1rem;
            color: white;
            width: 100%;
            transition: transform 0.2s, box-shadow 0.2s;
        }

        .btn-submit:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(15, 32, 39, 0.3);
            color: white;
        }

        .btn-submit:active {
            transform: translateY(0);
        }

        #resultAlert {
            display: none;
            border-radius: 12px;
            padding: 15px 20px;
            margin-top: 20px;
        }

        .product-info-box {
            background: #f0f4f8;
            border-right: 4px solid #2c5364;
            border-radius: 8px;
            padding: 12px 15px;
            margin-top: 15px;
            font-size: 0.95rem;
        }

        .env-footer {
            border-top: 1px solid #eceff1;
            margin-top: 25px;
            padding-top: 15px;
            font-size: 0.78rem;
            color: #78909c;
            display: flex;
            flex-wrap: wrap;
            gap: 6px 18px;
            justify-content: center;
        }

        .env-footer code {
            background: #eceff1;
            color: #37474f;
            padding: 2px 7px;
            border-radius: 5px;
            direction: ltr;
            display: inline-block;
        }
    </style>
</head>
<body>

<div class="main-card">
    <div class="card-header-custom">
        <h3><i class="fa-solid fa-flask-vial me-2"></i>ثبت لینک فرگرنتیکا با کد کالا</h3>
        <p>دریافت کد محصول و استخراج خودکار ItemID جهت همگام‌سازی دیتابیس</p>
    </div>
    <div class="card-body-custom">
        <form id="linkForm">
            <div class="mb-4">
                <label for="itemCode" class="form-label">کد محصول (Code)</label>
                <div class="input-group">
                    <span class="input-group-text bg-light border-0"><i class="fa-solid fa-barcode text-muted"></i></span>
                    <input type="text" class="form-control" id="itemCode" placeholder="مثلاً: 100234" required autocomplete="off">
                </div>
            </div>

            <div class="mb-4">
                <label for="fragranticaUrl" class="form-label">لینک فرگرنتیکا (Fragrantica URL)</label>
                <div class="input-group">
                    <span class="input-group-text bg-light border-0"><i class="fa-solid fa-link text-muted"></i></span>
                    <input type="url" class="form-control" id="fragranticaUrl" placeholder="https://www.fragrantica.com/perfume/..." required autocomplete="off">
                </div>
            </div>

            <button type="submit" class="btn btn-submit" id="submitBtn">
                <i class="fa-solid fa-square-plus me-2"></i>بررسی و ثبت در دیتابیس
            </button>
        </form>

        <div id="resultAlert" class="alert" role="alert"></div>

        <div class="env-footer">
            <span><i class="fa-solid fa-database me-1"></i>کد کالا از <code>{{ sepidar_db }}</code></span>
            <span><i class="fa-solid fa-flask me-1"></i>جداول فرگرنتیکا در <code>{{ gallery_db }}</code></span>
            <span><i class="fa-solid fa-shield-halved me-1"></i>آی‌پی شما <code>{{ client_ip }}</code></span>
        </div>
    </div>
</div>

<script>
document.getElementById('linkForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const code = document.getElementById('itemCode').value.trim();
    const url = document.getElementById('fragranticaUrl').value.trim();
    const btn = document.getElementById('submitBtn');
    const alertBox = document.getElementById('resultAlert');

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>در حال استخراج ItemID...';
    alertBox.style.display = 'none';

    try {
        const response = await fetch('/api/add-link', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: code, url: url })
        });

        const result = await response.json();

        if (response.ok && result.success) {
            alertBox.className = 'alert alert-success mt-4';
            alertBox.innerHTML = `
                <div class="d-flex align-items-center mb-2">
                    <i class="fa-solid fa-circle-check fa-lg me-2 text-success"></i>
                    <strong>${result.message}</strong>
                </div>
                <div class="product-info-box">
                    <strong>کد کالا:</strong> ${result.item_code}<br>
                    <strong>شناسه استخراج‌شده (ItemID):</strong> ${result.item_id}<br>
                    <strong>عنوان کالا:</strong> ${result.item_title}<br>
                    <strong>وضعیت:</strong> آماده برای استخراج اسکرپر (pending)
                </div>
            `;
            document.getElementById('itemCode').value = '';
            document.getElementById('fragranticaUrl').value = '';
        } else {
            alertBox.className = 'alert alert-danger mt-4';
            alertBox.innerHTML = `<i class="fa-solid fa-triangle-exclamation me-2"></i>${result.message}`;
        }
    } catch (err) {
        alertBox.className = 'alert alert-danger mt-4';
        alertBox.innerHTML = `<i class="fa-solid fa-xmark me-2"></i>خطا در ارتباط با سرور!`;
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-square-plus me-2"></i>بررسی و ثبت در دیتابیس';
        alertBox.style.display = 'block';
    }
});
</script>

</body>
</html>
"""

@panel_app.route('/')
def home():
    return render_template_string(
        HTML_TEMPLATE,
        sepidar_db=config.DB_SEPIDAR,
        gallery_db=config.DB_GALLERY,
        client_ip=request.remote_addr,
    )

@panel_app.route('/api/add-link', methods=['POST'])
def add_link():
    data = request.json or {}
    code = data.get('code', '').strip()
    url = data.get('url', '').strip()

    if not code or not url:
        return jsonify({'success': False, 'message': 'وارد کردن کد محصول و لینک الزامی است.'}), 400

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # ۱. پیدا کردن ItemID بر اساس Code از دیتابیس اصلی سپیدار (فقط خواندن).
        cursor.execute(
            f"SELECT ItemID, Title, Code FROM {config.tbl_item} WHERE Code = ?", (code,)
        )
        row = cursor.fetchone()

        if not row:
            return jsonify({'success': False, 'message': f'کالایی با کد "{code}" پیدا نشد!'}), 404

        item_id = row.ItemID
        item_title = row.Title
        item_code = row.Code

        # ۲. درج یا آپدیت در fragrantica_links دیتابیس گالری.
        #    id همان ItemID سپیدار است، پس IDENTITY_INSERT موقتاً روشن می‌شود.
        cursor.execute(f"""
            IF EXISTS (SELECT 1 FROM {config.tbl_links} WHERE id = ?)
            BEGIN
                UPDATE {config.tbl_links}
                SET url = ?, status = 'pending'
                WHERE id = ?
            END
            ELSE
            BEGIN
                SET IDENTITY_INSERT {config.tbl_links} ON;

                INSERT INTO {config.tbl_links} (id, url, status)
                VALUES (?, ?, 'pending');

                SET IDENTITY_INSERT {config.tbl_links} OFF;
            END
        """, (item_id, url, item_id, item_id, url))

        # ۳. ردیف perfume_data با link_id = ItemID و Code کالا.
        #    Code اینجا هم ذخیره می‌شود تا دیتابیس گالری خودکفا باشد و برای
        #    خواندن اطلاعات نیازی به join بین دو دیتابیس نداشته باشیم.
        cursor.execute(f"""
            IF EXISTS (SELECT 1 FROM {config.tbl_perfume_data} WHERE link_id = ?)
            BEGIN
                UPDATE {config.tbl_perfume_data}
                SET Code = ?
                WHERE link_id = ?
            END
            ELSE
            BEGIN
                INSERT INTO {config.tbl_perfume_data} (link_id, Code)
                VALUES (?, ?)
            END
        """, (item_id, item_code, item_id, item_id, item_code))

        conn.commit()

        logger.info(
            "✅ ثبت لینک: Code=%s ItemID=%s (%s)", item_code, item_id, item_title
        )

        return jsonify({
            'success': True,
            'message': 'اطلاعات با موفقیت ثبت شد و شناساگرها کاملاً مچ شدند.',
            'item_id': item_id,
            'item_code': item_code,
            'item_title': item_title
        })

    except Exception as e:
        if conn:
            conn.rollback()
        logger.exception("خطای دیتابیس در ثبت لینک")
        return jsonify({'success': False, 'message': f'خطای دیتابیس: {str(e)}'}), 500
    finally:
        if conn:
            conn.close()


def _port_error(host: str, port: int) -> str | None:
    """آیا می‌توان روی این پورت گوش داد؟ در صورت خطا، توضیحش را برمی‌گرداند."""
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
        except OSError as exc:
            # WinError 10013 → پورت توسط ویندوز رزرو شده، یا پروسه‌ی دیگری
            #                  آن را گرفته، یا دسترسی لازم را ندارید.
            # WinError 10048 / errno 98 → پورت قطعاً در حال استفاده است.
            if getattr(exc, "winerror", None) == 10013 or exc.errno in (13, 10013):
                return "رزروشده توسط ویندوز، اشغال، یا بدون دسترسی (WinError 10013)"
            if getattr(exc, "winerror", None) == 10048 or exc.errno in (48, 98, 10048):
                return "در حال استفاده توسط پروسه‌ی دیگر"
            return str(exc)
    return None


def _pick_port(host: str, preferred: int) -> int:
    """پورت آزاد پیدا کن: اول پورت انتخابی، بعد لیست جایگزین‌ها."""
    error = _port_error(host, preferred)
    if error is None:
        return preferred

    print(f"⚠️  پورت {preferred} قابل استفاده نیست — {error}")

    for candidate in config.PANEL_PORT_FALLBACKS:
        if candidate == preferred:
            continue
        if _port_error(host, candidate) is None:
            print(f"↪️  به‌جای آن از پورت {candidate} استفاده می‌شود.")
            return candidate

    tried = ", ".join(str(p) for p in (preferred, *config.PANEL_PORT_FALLBACKS))
    raise SystemExit(
        "\n❌ هیچ‌کدام از این پورت‌ها قابل استفاده نبود: " + tried + "\n"
        "\nراه‌حل‌ها:\n"
        "  ۱) پورت دلخواه خود را دستی بدهید:\n"
        "       set PANEL_PORT=8123 && python url_panel.py\n"
        "\n  ۲) ببینید ویندوز چه پورت‌هایی را رزرو کرده:\n"
        "       netsh interface ipv4 show excludedportrange protocol=tcp\n"
        "     اگر پورت شما داخل این محدوده‌ها بود، یا پورت دیگری انتخاب کنید\n"
        "     یا آن را رزرو کنید (نیازمند دسترسی Administrator):\n"
        "       net stop winnat\n"
        "       netsh int ipv4 add excludedportrange protocol=tcp startport=5000 numberofports=1\n"
        "       net start winnat\n"
        "\n  ۳) ببینید چه پروسه‌ای پورت را گرفته:\n"
        "       netstat -ano | findstr :5000\n"
        "       tasklist /fi \"pid eq <PID>\"\n"
        "\n  ۴) در فایروال ویندوز برای پورت انتخابی یک Inbound Rule بسازید تا\n"
        "     سیستم حسابداری هم بتواند به پنل وصل شود.\n"
    )


def run_panel(host=None, port=None, debug=True):
    host = config.PANEL_HOST if host is None else host
    port = config.PANEL_PORT if port is None else port
    port = _pick_port(host, port)

    print(f"🔒 آی‌پی‌های مجاز: {', '.join(config.PANEL_ALLOWED_IPS)}")
    print(f"🗄️  کالا/کد از: {config.DB_SEPIDAR}   |   جداول فرگرنتیکا در: {config.DB_GALLERY}")
    print(f"🌐 آدرس پنل: http://localhost:{port}")
    panel_app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S',
    )
    run_panel()