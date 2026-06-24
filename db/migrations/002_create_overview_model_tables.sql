-- 002_create_overview_model_tables.sql
-- 补齐后来新增的表: 总览聚合 / 品类营收 / 型号销量 / 型号参数表

USE amazon_db;

-- ---------------------------------------------------------------------------
-- amazon 原始表索引 (应对数据增长到百万行)
-- 注意: amazon 表本身由爬虫创建,此处只补索引
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_crawl_date_brand ON amazon (crawl_date, brand);
CREATE INDEX IF NOT EXISTS idx_crawl_date_asin_market ON amazon (crawl_date, asin, market);
CREATE INDEX IF NOT EXISTS idx_asin ON amazon (asin);

-- ---------------------------------------------------------------------------
-- 总览日聚合 (仅手机品类, 跨站点按品牌)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS daily_overview_summary (
    id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
    data_date           DATE NOT NULL,
    brand               VARCHAR(100) NOT NULL,
    markets             VARCHAR(255),
    product_count       INT DEFAULT 0,
    total_revenue       DECIMAL(18,2) DEFAULT 0,
    total_monthly_sales INT DEFAULT 0,
    avg_price           DECIMAL(10,2) DEFAULT 0,
    avg_rating          DECIMAL(3,2) DEFAULT NULL,
    avg_growth_rate     DECIMAL(10,4) DEFAULT NULL,
    avg_gross_margin    DECIMAL(6,4) DEFAULT NULL,
    fba_ratio           DECIMAL(5,4) DEFAULT NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_date_brand (data_date, brand)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- 品类营收 Top10 (全品类全站点)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS daily_overview_category (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    data_date   DATE NOT NULL,
    sub_category VARCHAR(255) NOT NULL,
    revenue     DECIMAL(18,2) DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_date_cat (data_date, sub_category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- 型号日销量聚合 (品牌 × 型号 × 站点)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS daily_model_summary (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    data_date     DATE NOT NULL,
    brand         VARCHAR(50) NOT NULL,
    model         VARCHAR(100) NOT NULL,
    type          VARCHAR(20) NOT NULL,
    market        VARCHAR(10) NOT NULL,
    total_sales   BIGINT DEFAULT 0,
    total_revenue DECIMAL(18,2) DEFAULT 0,
    sku_count     INT DEFAULT 0,
    avg_price     DECIMAL(10,2) DEFAULT 0,
    UNIQUE KEY uniq_date_brand_model_market (data_date, brand, model, market),
    KEY idx_date_brand_type (data_date, brand, type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- 型号列表 + 参数
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS brand_models (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    brand          VARCHAR(50) NOT NULL,
    model          VARCHAR(100) NOT NULL,
    type           VARCHAR(20) NOT NULL,
    camera         VARCHAR(50) DEFAULT NULL,
    battery        VARCHAR(50) DEFAULT NULL,
    cpu            VARCHAR(100) DEFAULT NULL,
    memory_storage VARCHAR(100) DEFAULT NULL,
    screen_size    VARCHAR(50) DEFAULT NULL,
    network        VARCHAR(20) DEFAULT NULL,
    UNIQUE KEY uniq_brand_model (brand, model),
    KEY idx_brand_type (brand, type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
