from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
FREE_START = "2017-01-01"
FREE_END = "2019-12-31"
LOCAL_FREE_DATA_DIR = REPO_ROOT / "data" / "free_v1_0"


def resolve_free_data_dir(data_dir: Path | None = None) -> Path:
    """Return the public/free Maycee parquet export directory."""
    candidates = []
    if data_dir is not None:
        candidates.append(Path(data_dir))
    env_dir = os.environ.get("MAYCEE_FREE_DATA_DIR")
    if env_dir:
        candidates.append(Path(env_dir))
    candidates.append(LOCAL_FREE_DATA_DIR)

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    searched = "\n".join(f"- {candidate}" for candidate in candidates)
    raise FileNotFoundError(
        "Maycee free-tier parquet data was not found. Download the public/free "
        "dataset to data/free_v1_0 or set MAYCEE_FREE_DATA_DIR.\n"
        f"Searched:\n{searched}"
    )


def _parquet_glob(data_dir: Path, table: str) -> str:
    if list(data_dir.glob(f"dt=*/{table}.parquet")):
        return (data_dir / "dt=*" / f"{table}.parquet").as_posix()
    if (data_dir / "data" / table).exists():
        return (data_dir / "data" / table / "*.parquet").as_posix()
    if (data_dir / f"{table}.parquet").exists():
        return (data_dir / f"{table}.parquet").as_posix()
    raise FileNotFoundError(f"Missing free-tier parquet table: {table}")


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _read_latest_dimension(con: duckdb.DuckDBPyConnection, data_dir: Path, table: str, key: str) -> str:
    view_name = f"latest_{table}"
    parquet_path = _sql_literal(_parquet_glob(data_dir, table))
    con.execute(
        f"""
        create or replace temp view {view_name} as
        select * exclude (rn)
        from (
            select
                *,
                row_number() over (partition by {key} order by dt desc) as rn
            from read_parquet({parquet_path})
        )
        where rn = 1
        """
    )
    return view_name


def load_free_tier_tables(data_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    """Load dashboard-ready tables from the public/free Maycee parquet export."""
    source_dir = resolve_free_data_dir(data_dir)
    con = duckdb.connect(database=":memory:")
    items_path = _sql_literal(_parquet_glob(source_dir, "items"))
    returns_path = _sql_literal(_parquet_glob(source_dir, "returns"))
    con.execute(f"create or replace temp view items_raw as select * from read_parquet({items_path})")
    con.execute(
        f"create or replace temp view returns_raw as select * from read_parquet({returns_path})"
    )

    customers = _read_latest_dimension(con, source_dir, "customers", "customer_id")
    stores = _read_latest_dimension(con, source_dir, "stores", "store_id")
    districts = _read_latest_dimension(con, source_dir, "districts", "district_id")
    regions = _read_latest_dimension(con, source_dir, "regions", "region_id")
    products = _read_latest_dimension(con, source_dir, "products", "product_id")
    categories = _read_latest_dimension(con, source_dir, "categories", "category_id")

    stores_df = con.execute(
        f"""
        select
            s.store_id,
            s.name as store_name,
            s.city,
            replace(s.store_type, '_', ' ') as store_type,
            coalesce(r.name, d.name, s.country) as region
        from {stores} s
        left join {districts} d using (district_id)
        left join {regions} r using (region_id)
        """
    ).df()

    products_df = con.execute(
        f"""
        select
            p.product_id,
            p.name as product_name,
            p.category_id
        from {products} p
        """
    ).df()

    categories_df = con.execute(
        f"""
        select
            category_id,
            name as category_name
        from {categories}
        """
    ).df()

    transactions_df = con.execute(
        f"""
        select
            t.transaction_id,
            t.customer_id,
            t.store_id,
            cast(t.transaction_date as timestamp) as transaction_date,
            t.payment_method,
            coalesce(nullif(c.loyalty_tier, ''), 'Guest') as customer_segment,
            t.total_amount
        from read_parquet(?) t
        left join {customers} c using (customer_id)
        where cast(t.transaction_date as date) between date '{FREE_START}' and date '{FREE_END}'
        """,
        [_parquet_glob(source_dir, "transactions")],
    ).df()

    items_df = con.execute(
        """
        select
            item_id,
            transaction_id,
            product_id,
            quantity,
            line_total,
            gross_profit,
            discount_amount
        from items_raw
        """
    ).df()

    returns_df = con.execute(
        """
        select
            r.return_id,
            r.transaction_id,
            i.product_id,
            cast(r.return_date as timestamp) as return_date,
            r.refund_amount as return_amount,
            r.quantity_returned,
            replace(coalesce(r.reason_code, 'unknown'), '_', ' ') as reason
        from returns_raw r
        left join items_raw i using (item_id)
        where cast(r.return_date as date) between date '2017-01-01' and date '2019-12-31'
        """
    ).df()

    return {
        "transactions": transactions_df,
        "items": items_df,
        "stores": stores_df,
        "products": products_df,
        "categories": categories_df,
        "returns": returns_df,
        "source_dir": pd.DataFrame({"path": [str(source_dir)]}),
    }


def available_years(tables: dict[str, pd.DataFrame]) -> list[int]:
    return sorted(tables["transactions"]["transaction_date"].dt.year.unique().tolist())


def date_range_label(tables: dict[str, pd.DataFrame]) -> str:
    dates = tables["transactions"]["transaction_date"]
    return f"{dates.min().date().isoformat()} to {dates.max().date().isoformat()}"


def filter_tables_by_years(tables: dict[str, pd.DataFrame], years: list[int]) -> dict[str, pd.DataFrame]:
    return filter_tables(tables, years=years)


def filter_options(tables: dict[str, pd.DataFrame]) -> dict[str, list[str]]:
    return {
        "regions": sorted(tables["stores"]["region"].dropna().unique().tolist()),
        "categories": sorted(tables["categories"]["category_name"].dropna().unique().tolist()),
        "store_types": sorted(tables["stores"]["store_type"].dropna().unique().tolist()),
        "payment_methods": sorted(
            tables["transactions"]["payment_method"].dropna().str.replace("_", " ", regex=False).unique().tolist()
        ),
    }


def filter_tables(
    tables: dict[str, pd.DataFrame],
    *,
    years: list[int],
    regions: list[str] | None = None,
    categories: list[str] | None = None,
    store_types: list[str] | None = None,
    payment_methods: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    selected_years = set(years)
    transactions = tables["transactions"][
        tables["transactions"]["transaction_date"].dt.year.isin(selected_years)
    ].copy()

    stores = tables["stores"].copy()
    if regions:
        stores = stores[stores["region"].isin(regions)]
    if store_types:
        stores = stores[stores["store_type"].isin(store_types)]
    transactions = transactions[transactions["store_id"].isin(set(stores["store_id"]))]

    if payment_methods:
        selected_payments = {payment.replace(" ", "_") for payment in payment_methods}
        transactions = transactions[transactions["payment_method"].isin(selected_payments)]

    items = tables["items"][tables["items"]["transaction_id"].isin(set(transactions["transaction_id"]))].copy()
    products = tables["products"].copy()
    categories_frame = tables["categories"].copy()

    if categories:
        selected_category_ids = set(categories_frame[categories_frame["category_name"].isin(categories)]["category_id"])
        products = products[products["category_id"].isin(selected_category_ids)]
        items = items[items["product_id"].isin(set(products["product_id"]))]
        transactions = transactions[transactions["transaction_id"].isin(set(items["transaction_id"]))]

    returns = tables["returns"][tables["returns"]["transaction_id"].isin(set(transactions["transaction_id"]))].copy()
    if categories:
        returns = returns[returns["product_id"].isin(set(products["product_id"]))]

    return {
        **tables,
        "transactions": transactions,
        "items": items,
        "stores": stores,
        "products": products,
        "categories": categories_frame,
        "returns": returns,
    }


def _connection(tables: dict[str, pd.DataFrame]) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(database=":memory:")
    for name, frame in tables.items():
        con.register(name, frame)
    return con


def enriched_transactions(tables: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    """Return transaction rows enriched with store/date fields."""
    con = _connection(tables or load_free_tier_tables())
    return con.execute(
        """
        select
            t.transaction_id,
            t.transaction_date,
            strftime(t.transaction_date, '%Y-%m') as year_month,
            year(t.transaction_date) as year,
            month(t.transaction_date) as month_number,
            dayname(t.transaction_date) as day_name,
            t.customer_segment,
            replace(t.payment_method, '_', ' ') as payment_method,
            t.total_amount,
            s.region,
            s.city,
            s.store_type,
            s.store_name
        from transactions t
        join stores s using (store_id)
        order by t.transaction_date
        """
    ).df()


def enriched_items(tables: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    """Return item rows enriched with product/category/store/date fields."""
    con = _connection(tables or load_free_tier_tables())
    return con.execute(
        """
        select
            i.transaction_id,
            t.transaction_date,
            strftime(t.transaction_date, '%Y-%m') as year_month,
            year(t.transaction_date) as year,
            i.product_id,
            p.product_name,
            c.category_name,
            i.quantity,
            i.line_total,
            i.gross_profit,
            i.discount_amount,
            i.discount_amount > 0 as has_promo,
            s.region,
            s.store_type
        from items i
        join transactions t using (transaction_id)
        join products p using (product_id)
        join categories c using (category_id)
        join stores s using (store_id)
        """
    ).df()


def enriched_returns(tables: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    """Return return rows enriched with product/category/store fields."""
    con = _connection(tables or load_free_tier_tables())
    return con.execute(
        """
        select
            r.return_id,
            r.transaction_id,
            r.product_id,
            p.product_name,
            c.category_name,
            r.return_date,
            strftime(r.return_date, '%Y-%m') as year_month,
            r.return_amount,
            r.reason,
            s.region,
            s.store_type
        from returns r
        join products p using (product_id)
        join categories c using (category_id)
        join transactions t using (transaction_id)
        join stores s using (store_id)
        order by r.return_date
        """
    ).df()


def build_metric_frames(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Build dashboard-ready aggregates through DuckDB SQL."""
    con = _connection(tables)

    overview = con.execute(
        """
        with item_totals as (
            select
                count(distinct t.transaction_id) as transactions,
                round(sum(i.line_total), 2) as revenue,
                round(sum(line_total), 2) as item_revenue,
                round(sum(gross_profit), 2) as gross_profit,
                round(sum(discount_amount), 2) as discount_value
            from items i
            join transactions t using (transaction_id)
        ),
        return_totals as (
            select
                count(*) as returns_count,
                round(coalesce(sum(return_amount), 0), 2) as returns_value
            from returns
        )
        select
            item_totals.transactions,
            item_totals.revenue,
            item_totals.gross_profit,
            return_totals.returns_value,
            item_totals.discount_value,
            round(item_totals.gross_profit / nullif(item_totals.item_revenue, 0) * 100, 1) as gross_margin_pct,
            round(return_totals.returns_value / nullif(item_totals.revenue, 0) * 100, 2) as return_value_pct,
            round(return_totals.returns_count / nullif(item_totals.transactions, 0) * 100, 2) as return_count_rate_pct,
            round(item_totals.discount_value / nullif(item_totals.revenue, 0) * 100, 2) as discount_rate_pct
        from item_totals
        cross join return_totals
        """
    ).df()

    kpis = con.execute(
        """
        with item_totals as (
            select
                count(distinct t.transaction_id) as transactions,
                round(sum(line_total), 2) as item_revenue,
                round(sum(line_total), 2) as revenue,
                round(sum(gross_profit), 2) as gross_profit
            from items i
            join transactions t using (transaction_id)
        ),
        return_totals as (
            select
                count(*) as returns_count,
                round(coalesce(sum(return_amount), 0), 2) as returns_value
            from returns
        ),
        discount_totals as (
            select round(sum(discount_amount), 2) as discount_value
            from items
        )
        select
            item_totals.transactions,
            item_totals.revenue,
            round(item_totals.revenue / nullif(item_totals.transactions, 0), 2) as avg_basket,
            item_totals.gross_profit,
            round(item_totals.gross_profit / nullif(item_totals.item_revenue, 0) * 100, 1) as gross_margin_pct,
            return_totals.returns_value,
            return_totals.returns_count,
            round(return_totals.returns_value / nullif(item_totals.revenue, 0) * 100, 2) as return_value_pct,
            round(return_totals.returns_count / nullif(item_totals.transactions, 0) * 100, 2) as return_count_rate_pct,
            discount_totals.discount_value,
            round(discount_totals.discount_value / nullif(item_totals.revenue, 0) * 100, 2) as discount_rate_pct
        from item_totals
        cross join return_totals
        cross join discount_totals
        """
    ).df()

    yearly_kpis = con.execute(
        """
        with item_year as (
            select
                year(t.transaction_date) as year,
                count(distinct t.transaction_id) as transactions,
                round(sum(i.line_total), 2) as revenue,
                round(sum(i.gross_profit), 2) as gross_profit,
                round(sum(i.discount_amount), 2) as discount_value
            from items i
            join transactions t using (transaction_id)
            group by 1
        ),
        return_year as (
            select
                year(return_date) as year,
                count(*) as returns_count,
                round(sum(return_amount), 2) as returns_value
            from returns
            group by 1
        )
        select
            item_year.year,
            item_year.transactions,
            item_year.revenue,
            round(item_year.revenue / nullif(item_year.transactions, 0), 2) as avg_basket,
            item_year.gross_profit,
            round(item_year.gross_profit / nullif(item_year.revenue, 0) * 100, 1) as gross_margin_pct,
            coalesce(return_year.returns_count, 0) as returns_count,
            round(coalesce(return_year.returns_value, 0), 2) as returns_value,
            round(coalesce(return_year.returns_value, 0) / nullif(item_year.revenue, 0) * 100, 2) as return_value_pct,
            round(coalesce(return_year.returns_count, 0) / nullif(item_year.transactions, 0) * 100, 2) as return_count_rate_pct,
            item_year.discount_value,
            round(item_year.discount_value / nullif(item_year.revenue, 0) * 100, 2) as discount_rate_pct
        from item_year
        left join return_year using (year)
        order by item_year.year
        """
    ).df()

    monthly_sales = con.execute(
        """
        select
            strftime(t.transaction_date, '%Y-%m') as month,
            year(t.transaction_date) as year,
            month(t.transaction_date) as month_number,
            round(sum(i.line_total), 2) as revenue,
            count(distinct t.transaction_id) as transactions,
            round(sum(i.line_total) / nullif(count(distinct t.transaction_id), 0), 2) as avg_basket
        from items i
        join transactions t using (transaction_id)
        group by 1, 2, 3
        order by 1
        """
    ).df()

    region_sales = con.execute(
        """
        select
            s.region,
            round(sum(i.line_total), 2) as revenue,
            count(distinct t.transaction_id) as transactions
        from items i
        join transactions t using (transaction_id)
        join stores s using (store_id)
        group by 1
        order by revenue desc
        """
    ).df()

    payment_mix = con.execute(
        """
        select
            replace(payment_method, '_', ' ') as payment_method,
            round(sum(i.line_total), 2) as revenue,
            count(distinct t.transaction_id) as transactions
        from items i
        join transactions t using (transaction_id)
        group by 1
        order by revenue desc
        """
    ).df()

    customer_segments = con.execute(
        """
        select
            customer_segment,
            count(distinct t.transaction_id) as transactions,
            round(sum(i.line_total), 2) as revenue,
            round(sum(i.line_total) / nullif(count(distinct t.transaction_id), 0), 2) as avg_basket
        from items i
        join transactions t using (transaction_id)
        group by 1
        order by revenue desc
        """
    ).df()

    category_sales = con.execute(
        """
        select
            c.category_name,
            sum(i.quantity) as units_sold,
            round(sum(i.line_total), 2) as revenue,
            round(sum(i.gross_profit), 2) as gross_profit,
            round(sum(i.discount_amount), 2) as discount_value,
            round(sum(i.gross_profit) / nullif(sum(i.line_total), 0) * 100, 1) as gross_margin_pct,
            round(sum(i.discount_amount) / nullif(sum(i.line_total), 0) * 100, 2) as discount_rate_pct
        from items i
        join products p using (product_id)
        join categories c using (category_id)
        group by 1
        order by revenue desc
        """
    ).df()

    product_leaders = con.execute(
        """
        select
            p.product_name,
            c.category_name,
            sum(i.quantity) as units,
            round(sum(i.line_total), 2) as revenue,
            round(sum(i.gross_profit), 2) as gross_profit,
            round(sum(i.gross_profit) / nullif(sum(i.line_total), 0) * 100, 1) as gross_margin_pct
        from items i
        join products p using (product_id)
        join categories c using (category_id)
        group by 1, 2
        order by revenue desc
        """
    ).df()

    promotion_impact = con.execute(
        """
        select
            case when discount_amount > 0 then 'Discounted' else 'Standard price' end as pricing_mode,
            round(sum(line_total), 2) as revenue,
            round(sum(gross_profit), 2) as gross_profit,
            round(avg(discount_amount), 2) as avg_discount,
            sum(quantity) as units
        from items
        group by 1
        order by revenue desc
        """
    ).df()

    returns_summary = con.execute(
        """
        select
            r.reason,
            count(*) as returns,
            sum(r.quantity_returned) as units_returned,
            round(sum(r.return_amount), 2) as return_amount
        from returns r
        group by 1
        order by return_amount desc
        """
    ).df()

    category_returns = con.execute(
        """
        with category_items as (
            select
                c.category_name,
                sum(i.quantity) as units_sold,
                count(distinct i.transaction_id) as transactions,
                round(sum(i.line_total), 2) as revenue
            from items i
            join products p using (product_id)
            join categories c using (category_id)
            group by 1
        ),
        category_return_totals as (
            select
                c.category_name,
                count(*) as returns,
                sum(r.quantity_returned) as units_returned,
                round(sum(r.return_amount), 2) as return_amount
            from returns r
            join products p using (product_id)
            join categories c using (category_id)
            group by 1
        )
        select
            category_items.category_name,
            category_items.transactions,
            category_items.units_sold,
            category_items.revenue,
            coalesce(category_return_totals.returns, 0) as returns,
            coalesce(category_return_totals.units_returned, 0) as units_returned,
            round(coalesce(category_return_totals.return_amount, 0), 2) as return_amount,
            round(coalesce(category_return_totals.units_returned, 0) / nullif(category_items.units_sold, 0) * 100, 2)
                as unit_return_rate_pct,
            round(coalesce(category_return_totals.return_amount, 0) / nullif(category_items.revenue, 0) * 100, 2)
                as return_value_pct
        from category_items
        left join category_return_totals using (category_name)
        order by return_value_pct desc, return_amount desc
        """
    ).df()

    return {
        "overview": overview,
        "kpis": kpis,
        "monthly_sales": monthly_sales,
        "region_sales": region_sales,
        "payment_mix": payment_mix,
        "customer_segments": customer_segments,
        "category_sales": category_sales,
        "product_leaders": product_leaders,
        "promotion_impact": promotion_impact,
        "returns_summary": returns_summary,
        "yearly_kpis": yearly_kpis,
        "category_returns": category_returns,
    }
