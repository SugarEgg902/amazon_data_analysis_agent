-- 003_amazon_sellersprite_db.sql
-- 储能竞品分析项目专用:独立数据库 + 物理迁移原始表 + 聚合表
-- 与手机项目(amazon_db)完全隔离。

-- 1. 新建独立数据库 ----------------------------------------------------------
CREATE DATABASE IF NOT EXISTS amazon_sellersprite_db
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE amazon_sellersprite_db;

-- 2. 物理迁移原始表并改名为 amazon(连带数据+结构+索引一起搬) ------------------
--    迁移后本库的 amazon 表即代码引用的原始表,18 处 FROM amazon 无需改动。
--    注意:迁移后爬虫(影刀)需改写库/表为 amazon_sellersprite_db.amazon。
RENAME TABLE amazon_db.amazon_sellersprite TO amazon_sellersprite_db.amazon;

-- 3. 原始表索引(RENAME 通常会带过来,此处幂等补建,缺则建、有则忽略报错) -------
--    若已存在会抛错,可忽略;或先 SHOW INDEX 确认后再决定是否执行。
-- CREATE INDEX idx_crawl_date_brand        ON amazon (crawl_date, brand);
-- CREATE INDEX idx_crawl_date_asin_market  ON amazon (crawl_date, asin, market);
-- CREATE INDEX idx_asin                     ON amazon (asin);

-- 4. 聚合表(搬自 001 + 002,库改为本库;COLLATE 统一 utf8mb4_unicode_ci) --------
CREATE TABLE IF NOT EXISTS daily_brand_summary (
    id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
    data_date           DATE NOT NULL,
    market              VARCHAR(20) NOT NULL,
    brand               VARCHAR(100) NOT NULL,
    product_count       INT DEFAULT 0,
    total_revenue       DECIMAL(18,2) DEFAULT 0,
    total_monthly_sales BIGINT DEFAULT 0,
    avg_price           DECIMAL(10,2) DEFAULT 0,
    avg_rating          DECIMAL(3,2) DEFAULT 0,
    avg_growth_rate     DECIMAL(10,4) DEFAULT 0,
    avg_gross_margin    DECIMAL(6,4) DEFAULT 0,
    fba_ratio           DECIMAL(5,4) DEFAULT 0,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_date_market_brand (data_date, market, brand),
    KEY idx_market (market),
    KEY idx_date (data_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS daily_category_summary (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    data_date           DATE NOT NULL,
    market              VARCHAR(20) NOT NULL,
    main_category       VARCHAR(100),
    sub_category        VARCHAR(100) NOT NULL,
    brand               VARCHAR(100) NOT NULL,
    product_count       INT DEFAULT 0,
    total_revenue       DECIMAL(18,2) DEFAULT 0,
    total_monthly_sales BIGINT DEFAULT 0,
    avg_price           DECIMAL(10,2) DEFAULT 0,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_date_market_cat_brand (data_date, market, sub_category, brand),
    KEY idx_market (market),
    KEY idx_main_category (main_category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS product_daily_snapshot (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    snapshot_date   DATE NOT NULL,
    asin            VARCHAR(50) NOT NULL,
    market          VARCHAR(20) NOT NULL,
    brand           VARCHAR(100),
    sub_category    VARCHAR(100),
    price           DECIMAL(10,2),
    monthly_sales   BIGINT,
    monthly_revenue DECIMAL(18,2),
    main_bsr        INT,
    sub_bsr         INT,
    rating          DECIMAL(3,2),
    rating_count    INT,
    gross_margin    DECIMAL(6,4),
    growth_rate     DECIMAL(10,4),
    UNIQUE KEY uq_snapshot_asin_market (snapshot_date, asin, market),
    KEY idx_asin_market (asin, market),
    KEY idx_brand (brand)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS anomaly_alerts (
    id             BIGINT AUTO_INCREMENT PRIMARY KEY,
    detected_at    DATETIME NOT NULL,
    asin           VARCHAR(50) NOT NULL,
    market         VARCHAR(20) NOT NULL,
    brand           VARCHAR(100) NOT NULL,
    anomaly_type   ENUM('sales_amount','sales_volume','price','main_bsr','sub_bsr') NOT NULL,
    current_value  DECIMAL(18,4) NOT NULL,
    baseline_value DECIMAL(18,4) NOT NULL,
    change_pct     DECIMAL(10,4) NOT NULL,
    threshold_pct  DECIMAL(10,4) NOT NULL,
    direction      ENUM('up','down') NOT NULL,
    KEY idx_detected_at (detected_at),
    KEY idx_market (market),
    KEY idx_brand (brand),
    KEY idx_type (anomaly_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS daily_analysis_reports (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    report_date   DATE NOT NULL,
    content       MEDIUMTEXT,
    model         VARCHAR(100) NOT NULL,
    generated_at  DATETIME NOT NULL,
    status        ENUM('success','failed') NOT NULL DEFAULT 'success',
    error_message TEXT,
    UNIQUE KEY uq_report_date (report_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS sales_analysis_reports (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    filename      VARCHAR(255) NOT NULL,
    row_count     INT NOT NULL,
    report_date   DATETIME NOT NULL,
    content       MEDIUMTEXT,
    model         VARCHAR(100) NOT NULL,
    status        ENUM('success','failed') NOT NULL DEFAULT 'success',
    error_message TEXT,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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

CREATE TABLE IF NOT EXISTS daily_overview_category (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    data_date   DATE NOT NULL,
    sub_category VARCHAR(255) NOT NULL,
    revenue     DECIMAL(18,2) DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_date_cat (data_date, sub_category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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

-- 型号列表+参数表:建空表(储能品牌暂无型号清单,型号排名页显示空状态)
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
