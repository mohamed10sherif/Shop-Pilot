"""Pandas based sales, inventory, and supplier analysis for ShopPilot."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd


def _read_json(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Required data file was not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path.name}: {exc}") from exc


def calculate_sales_metrics(sales: pd.DataFrame) -> dict:
    """Return summary metrics, including a well-defined empty-sales result."""
    if sales.empty:
        return {
            "revenue": 0.0,
            "cost": 0.0,
            "gross_profit": 0.0,
            "top_sku": "No sales",
            "top_quantity": 0,
        }

    by_sku = sales.groupby("SKU", as_index=False)["Quantity"].sum()
    by_sku = by_sku.sort_values(["Quantity", "SKU"], ascending=[False, True])
    top = by_sku.iloc[0]
    return {
        "revenue": float(sales["Revenue"].sum()),
        "cost": float(sales["Cost"].sum()),
        "gross_profit": float(sales["Gross Profit"].sum()),
        "top_sku": str(top["SKU"]),
        "top_quantity": int(top["Quantity"]),
    }


def _load_sales(data_dir: Path, product_categories: dict[str, str]) -> pd.DataFrame:
    payload = _read_json(data_dir / "sales.json")
    records = payload.get("sales", [])
    if not isinstance(records, list):
        raise ValueError("sales.json must contain a list named 'sales'")

    columns = [
        "Sale ID", "Date", "SKU", "Quantity", "Unit selling price at sale",
        "Unit cost at sale", "Discount %",
    ]
    frame = pd.DataFrame(records)
    for column in columns:
        if column not in frame.columns:
            frame[column] = pd.Series(dtype="object")
    frame = frame[columns].copy()
    frame["Quantity"] = pd.to_numeric(frame["Quantity"], errors="coerce")
    frame["Unit selling price at sale"] = pd.to_numeric(
        frame["Unit selling price at sale"], errors="coerce"
    )
    frame["Unit cost at sale"] = pd.to_numeric(frame["Unit cost at sale"], errors="coerce")
    frame["Discount %"] = pd.to_numeric(frame["Discount %"], errors="coerce").fillna(0)
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")

    # Rows without the numeric inputs needed for arithmetic are excluded from
    # calculations, while the original sales.json remains unchanged.
    frame = frame.dropna(subset=["Quantity", "Unit selling price at sale", "Unit cost at sale"])
    frame["Quantity"] = frame["Quantity"].astype(int)
    frame["Category"] = frame["SKU"].map(product_categories).fillna("Unknown")
    frame["Gross Sales"] = frame["Quantity"] * frame["Unit selling price at sale"]
    frame["Revenue"] = frame["Gross Sales"] * (1 - frame["Discount %"] / 100)
    frame["Cost"] = frame["Quantity"] * frame["Unit cost at sale"]
    frame["Gross Profit"] = frame["Revenue"] - frame["Cost"]
    return frame.reset_index(drop=True)


def _load_products(data_dir: Path) -> pd.DataFrame:
    payload = _read_json(data_dir / "products.json")
    records = payload.get("products", [])
    if not isinstance(records, list):
        raise ValueError("products.json must contain a list named 'products'")

    products = pd.DataFrame(records)
    aliases = {
        "Unit cost": "Unit_Cost",
        "Selling price": "Selling_Price",
        "Reorder level": "Reorder_Level",
    }
    products = products.rename(columns=aliases)
    expected = ["SKU", "Name", "Category", "Unit_Cost", "Selling_Price", "Stock", "Reorder_Level", "Active"]
    for column in expected:
        if column not in products.columns:
            products[column] = True if column == "Active" else pd.NA
    products["Active"] = products["Active"].fillna(True).astype(bool)
    for column in ("Unit_Cost", "Selling_Price", "Stock", "Reorder_Level"):
        products[column] = pd.to_numeric(products[column], errors="coerce")
    return products[expected].copy()


def _supplier_recommendations(data_dir: Path, products: pd.DataFrame) -> pd.DataFrame:
    offers = []

    supplier_a = _read_json(data_dir / "Supplier_A.json")
    supplier_a_name = supplier_a.get("supplier", {}).get("name", "Supplier A")
    currency_a = supplier_a.get("currency", "")
    for record in supplier_a.get("products", []):
        offer = record.get("offer", {})
        offers.append({
            "SKU": str(record.get("sku", "")).strip(),
            "Supplier": supplier_a_name,
            "Unit Cost": pd.to_numeric(offer.get("unit_cost"), errors="coerce"),
            "Available": offer.get("available") is True,
            "Currency": currency_a,
            "Valid": True,
        })

    supplier_b_path = data_dir / "supplier_b_extracted.csv"
    if supplier_b_path.exists():
        supplier_b = pd.read_csv(supplier_b_path)
        for _, record in supplier_b.iterrows():
            valid_price = str(record.get("Price_Status", "")).strip().lower() == "valid"
            valid_record = str(record.get("Record_Status", "Valid")).strip().lower() == "valid"
            offers.append({
                "SKU": str(record.get("SKU", "")).strip(),
                "Supplier": "Supplier B",
                "Unit Cost": pd.to_numeric(record.get("Price_EGP"), errors="coerce"),
                "Available": str(record.get("Availability", "")).strip().lower() == "in stock",
                "Currency": "EGP",
                "Valid": valid_price and valid_record,
            })

    offer_frame = pd.DataFrame(offers)
    if offer_frame.empty:
        offer_frame = pd.DataFrame(columns=["SKU", "Supplier", "Unit Cost", "Available", "Currency", "Valid"])
    if "Valid" not in offer_frame:
        offer_frame["Valid"] = True
    offer_frame["Unit Cost"] = pd.to_numeric(offer_frame["Unit Cost"], errors="coerce")
    eligible = offer_frame[
        offer_frame["Available"].fillna(False)
        & offer_frame["Valid"].fillna(False)
        & offer_frame["Unit Cost"].notna()
        & (offer_frame["Currency"] == "EGP")
    ].copy()

    results = []
    # Tie rule: choose the supplier name that sorts first alphabetically.
    for _, product in products.iterrows():
        sku = str(product["SKU"])
        matches = eligible[eligible["SKU"] == sku].sort_values(["Unit Cost", "Supplier"])
        if matches.empty:
            supplier_name, unit_cost = "No eligible offer", pd.NA
        else:
            best = matches.iloc[0]
            supplier_name, unit_cost = best["Supplier"], float(best["Unit Cost"])
        results.append({
            "SKU": sku,
            "Product": product["Name"],
            "Recommended supplier": supplier_name,
            "Recommended unit cost (EGP)": unit_cost,
            "Tie rule": "Lowest cost; supplier name alphabetically for ties",
        })
    return pd.DataFrame(results)


def _build_dirty_and_cleaned_copy(sales: pd.DataFrame, products: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    dirty = sales.copy(deep=True)
    if len(dirty) >= 2:
        dirty.loc[0, "Category"] = pd.NA
        dirty.loc[1, "Quantity"] = pd.NA
        dirty = pd.concat([dirty, dirty.iloc[[0]]], ignore_index=True)
    elif len(dirty) == 1:
        dirty.loc[0, "Category"] = pd.NA
        dirty.loc[0, "Quantity"] = pd.NA
        dirty = pd.concat([dirty, dirty.iloc[[0]]], ignore_index=True)

    cleaned = dirty.drop_duplicates().copy()
    categories = products.set_index("SKU")["Category"].to_dict()
    missing_category = cleaned["Category"].isna()
    cleaned.loc[missing_category, "Category"] = cleaned.loc[missing_category, "SKU"].map(categories)
    cleaned["Category"] = cleaned["Category"].fillna("Unknown")
    before_quantity_drop = len(cleaned)
    cleaned = cleaned.dropna(subset=["Quantity"]).copy()
    quantity_rows_dropped = before_quantity_drop - len(cleaned)

    explanation = (
        "This is a separate copy. Exact duplicate rows were removed. Missing categories were filled "
        "from the product master by SKU, or labeled Unknown if no match exists. Rows with missing "
        f"quantity were dropped ({quantity_rows_dropped} row(s)); no quantity was invented."
    )
    return dirty, cleaned, explanation


def _category_summary(sales: pd.DataFrame) -> pd.DataFrame:
    columns = ["Category", "Quantity", "Revenue", "Cost", "Gross Profit"]
    if sales.empty:
        return pd.DataFrame(columns=columns)
    summary = sales.groupby("Category", dropna=False).agg({
        "Quantity": "sum",
        "Revenue": "sum",
        "Cost": "sum",
        "Gross Profit": "sum",
    }).reset_index()
    return summary[columns].sort_values("Revenue", ascending=False).reset_index(drop=True)


def _write_excel_round_trip(report_dir: Path, sales: pd.DataFrame) -> str:
    path = report_dir / "sales_excel_round_trip.xlsx"
    try:
        sales.to_excel(path, index=False, sheet_name="Sales")
        reread = pd.read_excel(path, sheet_name="Sales")
    except ImportError as exc:
        return f"Skipped: install openpyxl to run the Excel round trip ({exc})."
    if len(reread) != len(sales):
        return "Failed: row count changed during the Excel round trip."
    return f"Completed: wrote and read {len(reread)} rows in {path.name}."


def run_analysis(project_dir: str | Path) -> dict:
    """Load project data, compute reports, and export reusable analysis files."""
    project_dir = Path(project_dir).resolve()
    data_dir = project_dir / "data"
    report_dir = project_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    products = _load_products(data_dir)
    product_categories = products.set_index("SKU")["Category"].to_dict()
    sales = _load_sales(data_dir, product_categories)
    metrics = calculate_sales_metrics(sales)

    if sales["Date"].notna().any():
        period = f"{sales['Date'].min():%Y-%m-%d} to {sales['Date'].max():%Y-%m-%d}"
    else:
        period = "No dated sales"
    metrics["reporting_period"] = period
    metrics["sales_rows"] = int(len(sales))

    category_summary = _category_summary(sales)
    low_stock = products[
        products["Active"]
        & products["Stock"].notna()
        & products["Reorder_Level"].notna()
        & (products["Stock"] <= products["Reorder_Level"])
    ][["SKU", "Name", "Category", "Stock", "Reorder_Level"]].rename(
        columns={"Reorder_Level": "Reorder level"}
    ).reset_index(drop=True)
    recommendations = _supplier_recommendations(data_dir, products)
    dirty, cleaned, cleaning_explanation = _build_dirty_and_cleaned_copy(sales, products)

    # Data exploration evidence: head, dimensions, columns, dtypes, info, describe,
    # column selection, loc, iloc, filtering, query, and sorting.
    info_buffer = io.StringIO()
    sales.info(buf=info_buffer)
    exploration = {
        "head": sales.head(),
        "shape": sales.shape,
        "columns": list(sales.columns),
        "dtypes": sales.dtypes.astype(str).to_dict(),
        "info": info_buffer.getvalue(),
        "describe": sales.describe(include="all").transpose(),
        "selected_columns": sales[["SKU", "Quantity", "Revenue", "Gross Profit"]].head(),
        "loc_example": sales.loc[:2, ["SKU", "Date", "Revenue"]],
        "iloc_example": sales.iloc[:3, :5],
        "conditional_filter": sales[sales["Gross Profit"] > 0].head(),
        "query_example": sales.query("Quantity > 0").head(),
        "sorted_by_revenue": sales.sort_values("Revenue", ascending=False).head(),
        "product_name_series": products["Name"],
    }

    # Keep exact source values and source files unchanged; all outputs are separate.
    csv_sales = sales.copy()
    for column in ("Gross Sales", "Revenue", "Cost", "Gross Profit"):
        csv_sales[column] = csv_sales[column].round(2)
    csv_sales.to_csv(report_dir / "sales_analysis.csv", index=False)
    category_summary.to_csv(report_dir / "category_summary.csv", index=False)
    low_stock.to_csv(report_dir / "low_stock_report.csv", index=False)
    recommendations.to_csv(report_dir / "supplier_recommendations.csv", index=False)
    dirty.to_csv(report_dir / "dirty_sales_copy.csv", index=False)
    cleaned.to_csv(report_dir / "cleaned_sales_copy.csv", index=False)

    excel_status = _write_excel_round_trip(report_dir, sales)
    empty_result = calculate_sales_metrics(pd.DataFrame())
    return {
        "metrics": metrics,
        "sales": sales,
        "products": products,
        "category_summary": category_summary,
        "low_stock": low_stock,
        "recommendations": recommendations,
        "dirty_sales": dirty,
        "cleaned_sales": cleaned,
        "cleaning_explanation": cleaning_explanation,
        "exploration": exploration,
        "empty_sales_result": empty_result,
        "excel_status": excel_status,
        "report_dir": report_dir,
    }
