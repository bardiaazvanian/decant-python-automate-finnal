/* ===========================================================================
   ساخت جداول فرگرنتیکا:  fragrantica_links  +  perfume_data
   ---------------------------------------------------------------------------
   این اسکریپت مستقل است — هیچ ارجاعی به Sepidar01 یا دیتابیس دیگری ندارد و
   هیچ داده‌ای کپی نمی‌کند. فقط ساختار جداول را می‌سازد.

   طریقه‌ی اجرا:
     الف) در SSMS دیتابیس مقصد را از لیست بالا انتخاب کنید و اجرا کنید،
     ب) یا خط USE پایین را از کامنت دربیاورید و نام دیتابیس را عوض کنید.

   idempotent است: اگر جدول یا ایندکسی از قبل باشد دوباره ساخته نمی‌شود، پس
   اجرای چندباره‌اش بی‌خطر است و داده‌ی موجود را پاک نمی‌کند.
   =========================================================================== */

-- USE [TarighatGallery_db];
-- GO

SET NOCOUNT ON;
GO

/* ---------------------------------------------------------------------------
   ۱. fragrantica_links — صف لینک‌ها برای اسکرپر
   ---------------------------------------------------------------------------
   id     : همان ItemID کالا در سپیدار است (IDENTITY هست ولی پنل با
            SET IDENTITY_INSERT ON مقدار ItemID را مستقیم می‌نویسد).
   url    : آدرس صفحه‌ی عطر در فرگرنتیکا.
   status : NULL یا 'pending' → آماده‌ی اسکرپ، 'scraped' → انجام‌شده،
            'error' → اسکرپ شکست خورده.
   --------------------------------------------------------------------------- */
IF OBJECT_ID(N'[dbo].[fragrantica_links]', N'U') IS NULL
BEGIN
    PRINT N'ساخت جدول dbo.fragrantica_links ...';

    CREATE TABLE [dbo].[fragrantica_links]
    (
        [id]     INT             IDENTITY(1,1) NOT NULL,
        [url]    NVARCHAR(2083)  NOT NULL,
        [status] NVARCHAR(50)    NULL,

        CONSTRAINT [PK_fragrantica_links] PRIMARY KEY CLUSTERED ([id] ASC)
    );
END
ELSE
    PRINT N'جدول dbo.fragrantica_links از قبل وجود دارد — رد شد.';
GO

/* ایندکس روی status: کوئری اصلی اسکرپر روی همین ستون فیلتر می‌کند
   (WHERE status = 'pending' OR status IS NULL). */
IF OBJECT_ID(N'[dbo].[fragrantica_links]', N'U') IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM sys.indexes
                   WHERE name = N'IX_fragrantica_links_status'
                     AND object_id = OBJECT_ID(N'[dbo].[fragrantica_links]'))
BEGIN
    PRINT N'ساخت ایندکس IX_fragrantica_links_status ...';

    CREATE NONCLUSTERED INDEX [IX_fragrantica_links_status]
        ON [dbo].[fragrantica_links] ([status] ASC);
END
GO

/* ---------------------------------------------------------------------------
   ۲. perfume_data — خروجی HTML هر عطر
   ---------------------------------------------------------------------------
   link_id    : کلید اتصال به fragrantica_links.id (و در نتیجه ItemID سپیدار).
   Code       : کد کالا در سپیدار. اینجا هم نگه داشته می‌شود تا این دیتابیس
                خودکفا باشد و برای خواندن نیازی به join بین دو دیتابیس نباشد.
   *_html     : قطعه‌های HTML آماده‌ی نمایش که اسکرپر تولید می‌کند. بدون
                <style> داخلی هستند — CSS مشترک از style.css می‌آید.
   created_at : زمان ساخت ردیف، خودکار.
   --------------------------------------------------------------------------- */
IF OBJECT_ID(N'[dbo].[perfume_data]', N'U') IS NULL
BEGIN
    PRINT N'ساخت جدول dbo.perfume_data ...';

    CREATE TABLE [dbo].[perfume_data]
    (
        [id]             INT            IDENTITY(1,1) NOT NULL,
        [Code]           NVARCHAR(250)  NULL,
        [link_id]        INT            NULL,
        [accords_html]   NVARCHAR(MAX)  NULL,
        [notes_html]     NVARCHAR(MAX)  NULL,
        [sillage_html]   NVARCHAR(MAX)  NULL,
        [longevity_html] NVARCHAR(MAX)  NULL,
        [gender_html]    NVARCHAR(MAX)  NULL,
        [seasons_html]   NVARCHAR(MAX)  NULL,
        [created_at]     DATETIME       NULL
            CONSTRAINT [DF_perfume_data_created_at] DEFAULT (GETDATE()),

        CONSTRAINT [PK_perfume_data] PRIMARY KEY CLUSTERED ([id] ASC)
    );
END
ELSE
    PRINT N'جدول dbo.perfume_data از قبل وجود دارد — رد شد.';
GO

/* ایندکس یکتای فیلترشده روی link_id.
   منطق upsert پنل و اسکرپر فرض می‌کند هر link_id حداکثر یک ردیف دارد؛
   این ایندکس همان فرض را در سطح دیتابیس تضمین می‌کند و کوئری‌های
   WHERE link_id = ? را هم سریع می‌کند. فیلتر IS NOT NULL باعث می‌شود چند
   ردیف با link_id خالی مجاز بماند. */
IF OBJECT_ID(N'[dbo].[perfume_data]', N'U') IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM sys.indexes
                   WHERE name = N'UX_perfume_data_link_id'
                     AND object_id = OBJECT_ID(N'[dbo].[perfume_data]'))
BEGIN
    PRINT N'ساخت ایندکس UX_perfume_data_link_id ...';

    CREATE UNIQUE NONCLUSTERED INDEX [UX_perfume_data_link_id]
        ON [dbo].[perfume_data] ([link_id] ASC)
        WHERE [link_id] IS NOT NULL;
END
GO

/* ایندکس روی Code — اگر ویو ASP.NET با کد کالا کوئری می‌زند. */
IF OBJECT_ID(N'[dbo].[perfume_data]', N'U') IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM sys.indexes
                   WHERE name = N'IX_perfume_data_Code'
                     AND object_id = OBJECT_ID(N'[dbo].[perfume_data]'))
BEGIN
    PRINT N'ساخت ایندکس IX_perfume_data_Code ...';

    CREATE NONCLUSTERED INDEX [IX_perfume_data_Code]
        ON [dbo].[perfume_data] ([Code] ASC);
END
GO

/* ---------------------------------------------------------------------------
   ۳. کلید خارجی — اختیاری، عمداً کامنت است.
   ---------------------------------------------------------------------------
   پنل همیشه اول در fragrantica_links درج می‌کند و بعد در perfume_data، پس
   این کلید با روند فعلی سازگار است و از ردیف یتیم جلوگیری می‌کند.
   اگر جایی دستی در perfume_data درج می‌کنید که link_id متناظری در
   fragrantica_links ندارد، این را روشن نکنید.

   نکته: قبل از اجرا مطمئن شوید ردیف یتیم ندارید:
       SELECT d.* FROM dbo.perfume_data d
       WHERE d.link_id IS NOT NULL
         AND NOT EXISTS (SELECT 1 FROM dbo.fragrantica_links l WHERE l.id = d.link_id);
   ---------------------------------------------------------------------------
   ALTER TABLE [dbo].[perfume_data]
       ADD CONSTRAINT [FK_perfume_data_fragrantica_links]
       FOREIGN KEY ([link_id]) REFERENCES [dbo].[fragrantica_links] ([id]);
   --------------------------------------------------------------------------- */

/* ---------------------------------------------------------------------------
   ۴. تأیید نهایی — ساختار ساخته‌شده را نشان می‌دهد.
   --------------------------------------------------------------------------- */
PRINT N'';
PRINT N'--- ستون‌ها ---';
GO

SELECT
    t.name                      AS [table_name],
    c.column_id                 AS [ord],
    c.name                      AS [column_name],
    ty.name                     AS [data_type],
    CASE WHEN ty.name LIKE N'%char%' AND c.max_length = -1 THEN N'MAX'
         WHEN ty.name LIKE N'n%char%' THEN CAST(c.max_length / 2 AS NVARCHAR(10))
         WHEN ty.name LIKE N'%char%'  THEN CAST(c.max_length AS NVARCHAR(10))
         ELSE N'' END           AS [length],
    c.is_nullable               AS [nullable],
    c.is_identity               AS [identity]
FROM sys.tables            AS t
JOIN sys.columns           AS c  ON c.object_id = t.object_id
JOIN sys.types             AS ty ON ty.user_type_id = c.user_type_id
WHERE t.name IN (N'fragrantica_links', N'perfume_data')
ORDER BY t.name, c.column_id;
GO

SELECT
    OBJECT_NAME(i.object_id) AS [table_name],
    i.name                   AS [index_name],
    i.type_desc              AS [type],
    i.is_unique              AS [is_unique],
    i.is_primary_key         AS [is_pk],
    ISNULL(i.filter_definition, N'') AS [filter]
FROM sys.indexes AS i
WHERE i.object_id IN (OBJECT_ID(N'[dbo].[fragrantica_links]'),
                      OBJECT_ID(N'[dbo].[perfume_data]'))
  AND i.name IS NOT NULL
ORDER BY [table_name], i.name;
GO

PRINT N'✅ تمام شد. جداول آماده‌ی استفاده‌ی پنل و اسکرپر هستند.';
GO
