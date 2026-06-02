-- db/migrations/001_create_amazon_db.sql
-- Amazon 竞品分析平台：专用数据库 + 聚合/快照/异常/报告表
-- 原始数据源 shadowcraw_db.amazon 不在此处创建（由爬虫维护），本平台跨库只读。

CREATE DATABASE IF NOT EXISTS amazon_db
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE amazon_db;

-- ---------------------------------------------------------------------------
-- 每日 站点 × 品牌 聚合
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- 每日 站点 × 品类 × 品牌 聚合
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- 每日 商品(asin × market) 快照：支持历史走势 + 异常检测基线
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- 异常检测结果
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS anomaly_alerts (
    id             BIGINT AUTO_INCREMENT PRIMARY KEY,
    detected_at    DATETIME NOT NULL,
    asin           VARCHAR(50) NOT NULL,
    market         VARCHAR(20) NOT NULL,
    brand          VARCHAR(100) NOT NULL,
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

-- ---------------------------------------------------------------------------
-- LLM 每日分析报告（定时任务生成）
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- 上传销售文件分析报告（用户触发）
-- ---------------------------------------------------------------------------
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
