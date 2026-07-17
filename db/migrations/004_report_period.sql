-- 004_report_period.sql
-- daily_analysis_reports 原本只存日报(唯一键就是 report_date),
-- 周报/月报要各自生成 LLM 分析,同一天会存在多份不同周期的报告
-- → 加 period 列,唯一键改为 (report_date, period)。
-- 存量行全部视为日报(period 默认 'daily'),无需回填。

USE amazon_sellersprite_db;

ALTER TABLE daily_analysis_reports
    ADD COLUMN period ENUM('daily', 'weekly', 'monthly') NOT NULL DEFAULT 'daily'
        COMMENT '报告周期' AFTER report_date,
    DROP INDEX uq_report_date,
    ADD UNIQUE KEY uq_report_date_period (report_date, period);
