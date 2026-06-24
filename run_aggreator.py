from datetime import date
from backend.aggregation.product_snapshot import run_product_snapshot
from backend.aggregation.brand_summary import run_brand_summary
from backend.aggregation.category_summary import run_category_summary
from backend.aggregation.overview_summary import run_overview_summary
from backend.analysis.llm_report import run_llm_analysis
d = date.today()
run_product_snapshot(d)
run_brand_summary(d)
run_category_summary(d)
run_overview_summary(d)
run_llm_analysis(d)
print('done')