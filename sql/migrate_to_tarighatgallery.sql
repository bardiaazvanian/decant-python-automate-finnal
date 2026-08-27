/* ===========================================================================
   انتقال جداول فرگرنتیکا از Sepidar01 به TarighatGallery_db
   ---------------------------------------------------------------------------
   بعد از این تغییر:
     * Sepidar01           → فقط خوانده می‌شود (POS.Item برای ItemID و Code)
     * TarighatGallery_db  → خانه‌ی fragrantica_links و perfume_data

   این اسکریپت idempotent است: اگر جدول یا ردیفی از قبل باشد دوباره
   ساخته/درج نمی‌شود، پس اجرای چندباره‌اش بی‌خطر است.

   جداول قدیمی در Sepidar01 حذف *نمی‌شوند*. بخش پایانی (کامنت‌شده) را فقط
   بعد از اینکه از درستی همه‌چیز مطمئن شدید اجرا کنید.
   =========================================================================== */

SET NOCOUNT ON;
GO

/* --------------------------------------------------------------- 1. جداول */
IF OBJECT_ID(N'[TarighatGallery_db].[dbo].[fragrantica_links]', N'U') IS NULL
BEGIN
    PRINT N'ساخت جدول fragrantica_links ...';
    CREATE TABLE [TarighatGallery_db].[dbo].[fragrantica_links]
    (
        [id]     INT             IDENTITY(1,1) NOT NULL,
        [url]    NVARCHAR(2083)  NOT NULL,
        [status] NVARCHAR(50)    NULL,
        CONSTRAINT [PK_fragrantica_links] PRIMARY KEY CLUSTERED ([id])
    );
END
ELSE
    PRINT N'جدول fragrantica_links از قبل وجود دارد — رد شد.';
GO

IF OBJECT_ID(N'[TarighatGallery_db].[dbo].[perfume_data]', N'U') IS NULL
BEGIN
    PRINT N'ساخت جدول perfume_data ...';
    CREATE TABLE [TarighatGallery_db].[dbo].[perfume_data]
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
        [created_at]     DATETIME       NULL CONSTRAINT [DF_perfume_data_created_at] DEFAULT (GETDATE()),
        CONSTRAINT [PK_perfume_data] PRIMARY KEY CLUSTERED ([id])
    );
END
ELSE
    PRINT N'جدول perfume_data از قبل وجود دارد — رد شد.';
GO

/* ------------------------------------------------------- 2. ایندکس‌ها */
/* هر link_id باید حداکثر یک ردیف داشته باشد — منطق upsert اسکرپر روی همین
   فرض بنا شده. فیلتر IS NOT NULL تا چند ردیف با link_id خالی مجاز بماند. */
IF NOT EXISTS (
    SELECT 1 FROM [TarighatGallery_db].sys.indexes
    WHERE name = N'UX_perfume_data_link_id'
      AND object_id = OBJECT_ID(N'[TarighatGallery_db].[dbo].[perfume_data]')
)
BEGIN
    PRINT N'ساخت ایندکس یکتا روی perfume_data.link_id ...';
    CREATE UNIQUE INDEX [UX_perfume_data_link_id]
        ON [TarighatGallery_db].[dbo].[perfume_data] ([link_id])
        WHERE [link_id] IS NOT NULL;
END
GO

IF NOT EXISTS (
    SELECT 1 FROM [TarighatGallery_db].sys.indexes
    WHERE name = N'IX_fragrantica_links_status'
      AND object_id = OBJECT_ID(N'[TarighatGallery_db].[dbo].[fragrantica_links]')
)
BEGIN
    PRINT N'ساخت ایندکس روی fragrantica_links.status ...';
    CREATE INDEX [IX_fragrantica_links_status]
        ON [TarighatGallery_db].[dbo].[fragrantica_links] ([status]);
END
GO

/* --------------------------------------------- 3. کپی داده‌های موجود */
/* فقط اگر جدول مبدأ در Sepidar01 هنوز هست. ردیف‌هایی که id آن‌ها از قبل در
   مقصد وجود دارد کپی نمی‌شوند، پس اجرای دوباره ردیف تکراری نمی‌سازد. */
IF OBJECT_ID(N'[Sepidar01].[dbo].[fragrantica_links]', N'U') IS NOT NULL
BEGIN
    DECLARE @linksCopied INT;

    SET IDENTITY_INSERT [TarighatGallery_db].[dbo].[fragrantica_links] ON;

    INSERT INTO [TarighatGallery_db].[dbo].[fragrantica_links] ([id], [url], [status])
    SELECT s.[id], s.[url], s.[status]
    FROM [Sepidar01].[dbo].[fragrantica_links] AS s
    WHERE NOT EXISTS (
        SELECT 1 FROM [TarighatGallery_db].[dbo].[fragrantica_links] AS d
        WHERE d.[id] = s.[id]
    );

    SET @linksCopied = @@ROWCOUNT;
    SET IDENTITY_INSERT [TarighatGallery_db].[dbo].[fragrantica_links] OFF;

    PRINT N'fragrantica_links — ردیف کپی‌شده: ' + CAST(@linksCopied AS NVARCHAR(20));
END
ELSE
    PRINT N'جدول مبدأ Sepidar01.dbo.fragrantica_links وجود ندارد — کپی رد شد.';
GO

IF OBJECT_ID(N'[Sepidar01].[dbo].[perfume_data]', N'U') IS NOT NULL
BEGIN
    DECLARE @dataCopied INT;

    SET IDENTITY_INSERT [TarighatGallery_db].[dbo].[perfume_data] ON;

    INSERT INTO [TarighatGallery_db].[dbo].[perfume_data]
        ([id], [Code], [link_id], [accords_html], [notes_html],
         [sillage_html], [longevity_html], [gender_html], [seasons_html], [created_at])
    SELECT s.[id], s.[Code], s.[link_id], s.[accords_html], s.[notes_html],
           s.[sillage_html], s.[longevity_html], s.[gender_html], s.[seasons_html], s.[created_at]
    FROM [Sepidar01].[dbo].[perfume_data] AS s
    WHERE NOT EXISTS (
        SELECT 1 FROM [TarighatGallery_db].[dbo].[perfume_data] AS d
        WHERE d.[id] = s.[id]
    );

    SET @dataCopied = @@ROWCOUNT;
    SET IDENTITY_INSERT [TarighatGallery_db].[dbo].[perfume_data] OFF;

    PRINT N'perfume_data — ردیف کپی‌شده: ' + CAST(@dataCopied AS NVARCHAR(20));
END
ELSE
    PRINT N'جدول مبدأ Sepidar01.dbo.perfume_data وجود ندارد — کپی رد شد.';
GO

/* ------------------------------------------------ 4. جبران Code های خالی */
/* هر ردیفی که Code ندارد از POS.Item سپیدار پر می‌شود (link_id = ItemID). */
UPDATE d
SET d.[Code] = i.[Code]
FROM [TarighatGallery_db].[dbo].[perfume_data] AS d
JOIN [Sepidar01].[POS].[Item] AS i ON i.[ItemID] = d.[link_id]
WHERE d.[Code] IS NULL OR LTRIM(RTRIM(d.[Code])) = N'';
PRINT N'Code های خالی پر شد: ' + CAST(@@ROWCOUNT AS NVARCHAR(20));
GO

/* -------------------------------------------------------- 5. خلاصه‌ی نهایی */
SELECT
    N'TarighatGallery_db.fragrantica_links' AS [table],
    COUNT(*)                                AS [rows]
FROM [TarighatGallery_db].[dbo].[fragrantica_links]
UNION ALL
SELECT
    N'TarighatGallery_db.perfume_data',
    COUNT(*)
FROM [TarighatGallery_db].[dbo].[perfume_data];
GO

/* ===========================================================================
   ۶. پاک‌سازی Sepidar01 — عمداً کامنت است.
   فقط بعد از اینکه مطمئن شدید پنل، اسکرپر و ویو ASP.NET همه از
   TarighatGallery_db می‌خوانند، این دو خط را از کامنت دربیاورید و اجرا کنید.
   تغییر نام (به‌جای DROP) امکان برگشت را باز می‌گذارد.
   ---------------------------------------------------------------------------
   EXEC [Sepidar01]..sp_rename 'dbo.fragrantica_links', 'fragrantica_links_moved_to_gallery';
   EXEC [Sepidar01]..sp_rename 'dbo.perfume_data',      'perfume_data_moved_to_gallery';
   =========================================================================== */
