from __future__ import annotations

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from data import available_years, build_metric_frames, date_range_label, filter_options, filter_tables
from runtime import load_cached_free_tier_tables
from ui import PALETTE, apply_theme, money, pct, prepare_chart, year_delta


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


st.set_page_config(page_title="Maycee Retail Analytics", page_icon="", layout="wide")
apply_theme()

st.title("Maycee Retail Analytics")
st.caption("A focused three-year view of public synthetic retail sales, margin, and returns.")

try:
    tables = load_cached_free_tier_tables()
except FileNotFoundError as exc:
    st.error("Maycee public data is not available locally.")
    st.code(".\\.venv\\Scripts\\python.exe scripts\\fetch_free_data.py", language="powershell")
    st.caption(str(exc))
    st.stop()

options = filter_options(tables)
years = available_years(tables)

st.sidebar.header("View")
selected_years = st.sidebar.multiselect("Years", years, default=years)
selected_regions = st.sidebar.multiselect("Regions", options["regions"], default=[])
selected_categories = st.sidebar.multiselect("Categories", options["categories"], default=[])
st.sidebar.markdown(
    '<div class="coverage-note"><strong>Public data</strong><br>Maycee free tier<br>2017-2019</div>',
    unsafe_allow_html=True,
)

if not selected_years:
    st.warning("Select at least one year.")
    st.stop()

filtered = filter_tables(
    tables,
    years=selected_years,
    regions=selected_regions,
    categories=selected_categories,
)
metrics = build_metric_frames(filtered)
if metrics["monthly_sales"].empty:
    st.warning("No public-data rows match the selected filters.")
    st.stop()

kpis = metrics["kpis"].iloc[0]
yearly = metrics["yearly_kpis"]
selected_label = ", ".join(str(year) for year in selected_years)
st.info(f"Showing {selected_label}. Available public coverage: {date_range_label(tables)}.")

kpi_columns = st.columns(5)
kpi_columns[0].metric("Revenue", money(kpis["revenue"]), year_delta(yearly, "revenue"))
kpi_columns[1].metric("Transactions", f"{int(kpis['transactions']):,}", year_delta(yearly, "transactions"))
kpi_columns[2].metric("Average Order Value", f"${kpis['avg_basket']:,.2f}", year_delta(yearly, "avg_basket"))
kpi_columns[3].metric(
    "Gross Margin",
    pct(kpis["gross_margin_pct"]),
    year_delta(yearly, "gross_margin_pct", points=True),
)
kpi_columns[4].metric(
    "Return Value Rate",
    pct(kpis["return_value_pct"], 2),
    year_delta(yearly, "return_value_pct", points=True, digits=2),
)

monthly = metrics["monthly_sales"].copy()
monthly["month_name"] = monthly["month_number"].map(lambda value: MONTHS[int(value) - 1])
monthly["year"] = monthly["year"].astype(str)
trend = px.line(
    monthly,
    x="month_name",
    y="revenue",
    color="year",
    markers=True,
    color_discrete_sequence=[PALETTE["blue"], PALETTE["emerald"], PALETTE["amber"]],
    labels={"month_name": "Month", "revenue": "Revenue ($)", "year": "Year"},
    title="Monthly Revenue By Year",
)
trend.update_xaxes(categoryorder="array", categoryarray=MONTHS)
st.plotly_chart(prepare_chart(trend, 410), use_container_width=True)

left, right = st.columns(2)

with left:
    regions = metrics["region_sales"].sort_values("revenue", ascending=True)
    region_chart = px.bar(
        regions,
        x="revenue",
        y="region",
        orientation="h",
        color="revenue",
        color_continuous_scale=["#dbeafe", PALETTE["blue"], PALETTE["navy"]],
        labels={"revenue": "Revenue ($)", "region": "Region"},
        title="Revenue By Region",
    )
    region_chart.update_coloraxes(showscale=False)
    st.plotly_chart(prepare_chart(region_chart), use_container_width=True)

with right:
    categories = metrics["category_sales"].nlargest(8, "revenue").sort_values("gross_margin_pct")
    category_chart = px.bar(
        categories,
        x="gross_margin_pct",
        y="category_name",
        orientation="h",
        color="revenue",
        color_continuous_scale=["#d1fae5", PALETTE["emerald"], PALETTE["teal"]],
        labels={"gross_margin_pct": "Gross margin (%)", "category_name": "Category", "revenue": "Revenue ($)"},
        title="Margin Across Leading Categories",
    )
    st.plotly_chart(prepare_chart(category_chart), use_container_width=True)

returns = metrics["category_returns"].nlargest(8, "return_amount").copy()
return_chart = px.scatter(
    returns,
    x="return_value_pct",
    y="unit_return_rate_pct",
    size="return_amount",
    color="category_name",
    hover_name="category_name",
    color_discrete_sequence=[
        PALETTE["rose"],
        PALETTE["amber"],
        PALETTE["blue"],
        PALETTE["emerald"],
        PALETTE["teal"],
    ],
    labels={
        "return_value_pct": "Return value / revenue (%)",
        "unit_return_rate_pct": "Units returned / units sold (%)",
        "category_name": "Category",
    },
    title="Where Returns Have The Most Impact",
)
st.plotly_chart(prepare_chart(return_chart, 410), use_container_width=True)

top_region = metrics["region_sales"].iloc[0]
top_category = metrics["category_sales"].iloc[0]
highest_return = metrics["category_returns"].iloc[0]
st.markdown(
    f"""
    <div class="insight-band">
    <strong>What stands out:</strong> {top_region['region']} leads revenue at
    {money(top_region['revenue'])}; {top_category['category_name']} is the top
    category at {money(top_category['revenue'])}; and
    {highest_return['category_name']} has the highest return-value rate at
    {pct(highest_return['return_value_pct'], 2)}.
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption("Maycee Retail public/free synthetic data, 2017-2019. Dataset: SDataPro, CC BY 4.0.")
