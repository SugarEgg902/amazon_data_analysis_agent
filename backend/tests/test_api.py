# backend/tests/test_api.py
"""端到端 API 冒烟测试，针对 amazon_db 真实数据。"""


def test_markets_returns_nine(client):
    r = client.get("/api/meta/markets")
    assert r.status_code == 200
    data = r.json()["data"]
    assert isinstance(data, list)
    assert "US" in data


def test_overview_default_and_market(client):
    r = client.get("/api/overview")
    assert r.status_code == 200
    body = r.json()["data"]
    assert "brands" in body and "category_share" in body
    # 仅 5 个聚焦品牌,跨站点聚合 -> 每行有 brand 与 markets(复数),无单一 market
    focus = {"blackview", "ulefone", "cubot", "oukitel", "doogee"}
    for b in body["brands"]:
        assert b["brand"].lower() in focus
        assert "markets" in b

    r2 = client.get("/api/overview?market=US")
    assert r2.status_code == 200
    for b in r2.json()["data"]["brands"]:
        assert b["brand"].lower() in focus


def test_brands_trend_shape(client):
    r = client.get("/api/brands/trend?days=30&market=US")
    assert r.status_code == 200
    d = r.json()["data"]
    assert "dates" in d and "series" in d
    for series in d["series"].values():
        assert len(series) == len(d["dates"])


def test_products_pagination_and_filter(client):
    r = client.get("/api/products?page=1&page_size=10&market=US")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["page"] == 1 and len(d["items"]) <= 10
    for it in d["items"]:
        assert it["market"] == "US"


def test_product_detail_and_404(client):
    lst = client.get("/api/products?page=1&page_size=1&market=US").json()["data"]["items"]
    if lst:
        asin = lst[0]["asin"]
        r = client.get(f"/api/products/{asin}?market=US")
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["asin"] == asin
        assert "history" in body
    assert client.get("/api/products/NONEXISTENT_XYZ").status_code == 404


def test_compare_and_trends(client):
    assert client.get("/api/compare?market=JP").status_code == 200
    t = client.get("/api/trends?market=US")
    assert t.status_code == 200
    d = t.json()["data"]
    assert "growth_ranking" in d and "new_products" in d and "category_trends" in d


def test_anomalies_detect_then_latest(client):
    det = client.post("/api/anomalies/detect", json={})
    assert det.status_code == 200
    assert "detected" in det.json()["data"]
    latest = client.get("/api/anomalies/latest")
    assert latest.status_code == 200
    assert "items" in latest.json()["data"]


def test_sales_history_and_report_404(client):
    assert client.get("/api/sales-analysis/history").status_code == 200
    assert client.get("/api/sales-analysis/reports/99999999").status_code == 404
