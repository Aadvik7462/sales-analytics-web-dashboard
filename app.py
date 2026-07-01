from flask import Flask, render_template, request, redirect, send_file
import pandas as pd
import plotly.express as px
import os
from datetime import datetime
from utils.pdf_report import generate_pdf_report

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
REPORT_FOLDER = "reports"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["REPORT_FOLDER"] = REPORT_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORT_FOLDER, exist_ok=True)

CURRENT_FILE = os.path.join(REPORT_FOLDER, "current_sales_data.csv")
CURRENT_FILENAME_FILE = os.path.join(REPORT_FOLDER, "current_filename.txt")
PDF_REPORT_FILE = os.path.join(REPORT_FOLDER, "sales_executive_report.pdf")


def clean_data(df):
    df = df.drop_duplicates()
    df = df.dropna(how="all")

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("-", "_")
    )

    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].astype(str).str.strip()

    return df


def find_column(df, possible_names):
    for name in possible_names:
        if name in df.columns:
            return name
    return None


def format_currency(value):
    try:
        value = float(value)

        if abs(value) >= 10000000:
            return f"₹{value / 10000000:.2f} Cr"
        elif abs(value) >= 100000:
            return f"₹{value / 100000:.2f} L"
        elif abs(value) >= 1000:
            return f"₹{value / 1000:.2f} K"
        else:
            return f"₹{value:.2f}"
    except:
        return "₹0.00"


def format_number(value):
    try:
        value = int(value)

        if value >= 10000000:
            return f"{value / 10000000:.2f} Cr"
        elif value >= 100000:
            return f"{value / 100000:.2f} L"
        elif value >= 1000:
            return f"{value / 1000:.1f}K"
        else:
            return str(value)
    except:
        return "0"


def create_summary(df, sales_col, profit_col, region_col, category_col, product_col, customer_col):
    insights = []
    recommendations = []

    if sales_col and len(df) > 0:
        total_sales = df[sales_col].sum()
        avg_sales = df[sales_col].mean()

        insights.append(f"Total sales generated from the dataset is {format_currency(total_sales)}.")
        insights.append(f"Average sales per order is {format_currency(avg_sales)}.")

    if region_col and sales_col and len(df) > 0:
        best_region = df.groupby(region_col)[sales_col].sum().idxmax()
        insights.append(f"Best performing region is {best_region}.")
        recommendations.append(f"Increase marketing and inventory focus in {best_region} region.")

    if category_col and sales_col and len(df) > 0:
        best_category = df.groupby(category_col)[sales_col].sum().idxmax()
        insights.append(f"Highest revenue category is {best_category}.")
        recommendations.append(f"Promote high-performing category: {best_category}.")

    if product_col and sales_col and len(df) > 0:
        best_product = df.groupby(product_col)[sales_col].sum().idxmax()
        insights.append(f"Top selling product is {best_product}.")
        recommendations.append("Maintain sufficient stock for top-selling products.")

    if profit_col and sales_col and len(df) > 0:
        total_profit = df[profit_col].sum()
        profit_margin = (total_profit / df[sales_col].sum()) * 100 if df[sales_col].sum() else 0
        insights.append(f"Total profit is {format_currency(total_profit)} with profit margin of {profit_margin:.2f}%.")
        recommendations.append("Review low-profit products and optimize discount strategy.")

    if customer_col and sales_col and len(df) > 0:
        top_customer = df.groupby(customer_col)[sales_col].sum().idxmax()
        insights.append(f"Top customer by sales is {top_customer}.")
        recommendations.append("Create loyalty offers for high-value customers.")

    if not recommendations:
        recommendations.append(
            "Upload a complete sales dataset with sales, region, product, and customer columns for better insights."
        )

    return insights, recommendations


def prepare_dashboard(df, filters=None, filename="Uploaded Dataset"):
    sales_col = find_column(df, ["sales", "amount", "revenue", "total_sales"])
    profit_col = find_column(df, ["profit", "net_profit"])
    region_col = find_column(df, ["region", "state", "city"])
    product_col = find_column(df, ["product_name", "product", "item"])
    customer_col = find_column(df, ["customer_name", "customer", "customer_id"])
    category_col = find_column(df, ["category", "product_category"])
    segment_col = find_column(df, ["segment", "customer_segment"])
    date_col = find_column(df, ["order_date", "date", "sales_date"])
    quantity_col = find_column(df, ["quantity", "qty"])
    discount_col = find_column(df, ["discount"])

    if sales_col is None:
        return None

    original_rows = len(df)
    original_columns = len(df.columns)

    df[sales_col] = pd.to_numeric(df[sales_col], errors="coerce")
    df = df.dropna(subset=[sales_col])

    if profit_col:
        df[profit_col] = pd.to_numeric(df[profit_col], errors="coerce").fillna(0)

    if quantity_col:
        df[quantity_col] = pd.to_numeric(df[quantity_col], errors="coerce").fillna(0)

    if discount_col:
        df[discount_col] = pd.to_numeric(df[discount_col], errors="coerce").fillna(0)

    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df["year"] = df[date_col].dt.year
        df["month"] = df[date_col].dt.month_name()

    if filters:
        if region_col and filters.get("region"):
            df = df[df[region_col] == filters["region"]]

        if category_col and filters.get("category"):
            df = df[df[category_col] == filters["category"]]

        if segment_col and filters.get("segment"):
            df = df[df[segment_col] == filters["segment"]]

        if "year" in df.columns and filters.get("year"):
            df = df[df["year"].astype(str) == filters["year"]]

        if "month" in df.columns and filters.get("month"):
            df = df[df["month"] == filters["month"]]

    total_sales = df[sales_col].sum()
    total_orders = len(df)
    avg_sales = df[sales_col].mean() if total_orders > 0 else 0

    total_profit = df[profit_col].sum() if profit_col else 0
    profit_margin = (total_profit / total_sales) * 100 if total_sales else 0

    total_customers = df[customer_col].nunique() if customer_col else "N/A"
    total_products = df[product_col].nunique() if product_col else "N/A"
    total_regions = df[region_col].nunique() if region_col else "N/A"
    total_quantity = df[quantity_col].sum() if quantity_col else 0
    avg_discount = df[discount_col].mean() if discount_col else 0
    highest_sale = df[sales_col].max() if total_orders > 0 else 0
    lowest_sale = df[sales_col].min() if total_orders > 0 else 0

    top_region = "N/A"
    if region_col and total_orders > 0:
        top_region = df.groupby(region_col)[sales_col].sum().idxmax()

    kpis = {
        "total_sales": format_currency(total_sales),
        "total_orders": format_number(total_orders),
        "avg_sales": format_currency(avg_sales),
        "total_profit": format_currency(total_profit),
        "profit_margin": f"{profit_margin:.2f}%",
        "total_customers": total_customers,
        "total_products": total_products,
        "total_regions": total_regions,
        "top_region": top_region,
        "total_quantity": format_number(int(total_quantity)),
        "avg_discount": f"{avg_discount:.2%}",
        "highest_sale": format_currency(highest_sale),
        "lowest_sale": format_currency(lowest_sale)
    }

    dataset_info = {
        "filename": filename,
        "rows": format_number(original_rows),
        "columns": original_columns,
        "filtered_rows": format_number(len(df)),
        "last_updated": datetime.now().strftime("%d %B %Y, %I:%M %p")
    }

    insights, recommendations = create_summary(
        df, sales_col, profit_col, region_col, category_col, product_col, customer_col
    )

    charts = {}

    if date_col and "year" in df.columns:
        monthly_sales = (
            df.dropna(subset=[date_col])
            .groupby(df[date_col].dt.to_period("M"))[sales_col]
            .sum()
            .reset_index()
        )
        monthly_sales[date_col] = monthly_sales[date_col].astype(str)

        fig_monthly = px.line(
            monthly_sales,
            x=date_col,
            y=sales_col,
            title="Monthly Sales Trend",
            markers=True
        )

        fig_monthly.update_layout(height=420)

        charts["monthly_chart"] = fig_monthly.to_html(full_html=False)

    if region_col:
        region_sales = df.groupby(region_col)[sales_col].sum().reset_index()

        fig_region = px.bar(
            region_sales,
            x=region_col,
            y=sales_col,
            title="Sales by Region",
            text_auto=".2s"
        )

        fig_region.update_layout(
            height=450,
            xaxis_title="Region",
            yaxis_title="Sales"
        )

        charts["region_chart"] = fig_region.to_html(full_html=False)

    if product_col:
        product_sales = (
            df.groupby(product_col)[sales_col]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .sort_values()
            .reset_index()
        )

        fig_product = px.bar(
            product_sales,
            x=sales_col,
            y=product_col,
            orientation="h",
            text_auto=".2s",
            color=sales_col,
            color_continuous_scale="Blues",
            title="Top 10 Products by Sales"
        )

        fig_product.update_layout(
            height=600,
            margin=dict(l=260, r=30, t=60, b=40),
            yaxis_title="",
            xaxis_title="Sales",
            coloraxis_showscale=False
        )

        charts["product_chart"] = fig_product.to_html(full_html=False)

    if category_col:
        category_sales = df.groupby(category_col)[sales_col].sum().reset_index()

        fig_category = px.pie(
            category_sales,
            names=category_col,
            values=sales_col,
            title="Sales by Category",
            hole=0.35
        )

        fig_category.update_layout(height=450)

        charts["category_chart"] = fig_category.to_html(full_html=False)

    if profit_col and region_col:
        profit_region = df.groupby(region_col)[profit_col].sum().reset_index()

        fig_profit_region = px.bar(
            profit_region,
            x=region_col,
            y=profit_col,
            title="Profit by Region",
            text_auto=".2s"
        )

        fig_profit_region.update_layout(
            height=450,
            xaxis_title="Region",
            yaxis_title="Profit"
        )

        charts["profit_region_chart"] = fig_profit_region.to_html(full_html=False)

    if profit_col and sales_col:
        fig_scatter = px.scatter(
            df,
            x=sales_col,
            y=profit_col,
            title="Sales vs Profit",
            hover_data=[product_col] if product_col else None
        )

        fig_scatter.update_layout(
            height=450,
            xaxis_title="Sales",
            yaxis_title="Profit"
        )

        charts["sales_profit_chart"] = fig_scatter.to_html(full_html=False)

    if customer_col:
        customer_sales = (
            df.groupby(customer_col)[sales_col]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .sort_values()
            .reset_index()
        )

        fig_customer = px.bar(
            customer_sales,
            x=sales_col,
            y=customer_col,
            orientation="h",
            text_auto=".2s",
            color=sales_col,
            color_continuous_scale="Greens",
            title="Top 10 Customers by Sales"
        )

        fig_customer.update_layout(
            height=600,
            margin=dict(l=190, r=30, t=60, b=40),
            yaxis_title="",
            xaxis_title="Sales",
            coloraxis_showscale=False
        )

        charts["customer_chart"] = fig_customer.to_html(full_html=False)

    if quantity_col and category_col:
        quantity_category = df.groupby(category_col)[quantity_col].sum().reset_index()

        fig_quantity = px.bar(
            quantity_category,
            x=category_col,
            y=quantity_col,
            title="Quantity Sold by Category",
            text_auto=".2s"
        )

        fig_quantity.update_layout(
            height=450,
            xaxis_title="Category",
            yaxis_title="Quantity"
        )

        charts["quantity_chart"] = fig_quantity.to_html(full_html=False)

    filter_options = {
        "regions": sorted(df[region_col].dropna().unique()) if region_col else [],
        "categories": sorted(df[category_col].dropna().unique()) if category_col else [],
        "segments": sorted(df[segment_col].dropna().unique()) if segment_col else [],
        "years": sorted(df["year"].dropna().astype(int).astype(str).unique()) if "year" in df.columns else [],
        "months": [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ] if "month" in df.columns else []
    }

    preview_table = df.head(100).to_html(classes="data-table", index=False)

    return kpis, charts, preview_table, filter_options, dataset_info, insights, recommendations


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return redirect("/")

    file = request.files["file"]

    if file.filename == "":
        return redirect("/")

    if not file.filename.endswith(".csv"):
        return "Only CSV files are allowed."

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(filepath)

    df = pd.read_csv(filepath)
    df = clean_data(df)

    df.to_csv(CURRENT_FILE, index=False)

    with open(CURRENT_FILENAME_FILE, "w") as f:
        f.write(file.filename)

    result = prepare_dashboard(df, filename=file.filename)

    if result is None:
        return "Sales column not found. Use column name: Sales, Amount, Revenue, or Total Sales"

    kpis, charts, preview_table, filter_options, dataset_info, insights, recommendations = result

    generate_pdf_report(
        PDF_REPORT_FILE,
        dataset_info,
        kpis,
        insights,
        recommendations
    )

    return render_template(
        "dashboard.html",
        kpis=kpis,
        charts=charts,
        preview_table=preview_table,
        filter_options=filter_options,
        selected_filters={},
        dataset_info=dataset_info,
        insights=insights,
        recommendations=recommendations
    )


@app.route("/filter", methods=["POST"])
def filter_dashboard():
    if not os.path.exists(CURRENT_FILE):
        return redirect("/")

    df = pd.read_csv(CURRENT_FILE)

    filename = "Uploaded Dataset"
    if os.path.exists(CURRENT_FILENAME_FILE):
        with open(CURRENT_FILENAME_FILE, "r") as f:
            filename = f.read()

    filters = {
        "region": request.form.get("region"),
        "category": request.form.get("category"),
        "segment": request.form.get("segment"),
        "year": request.form.get("year"),
        "month": request.form.get("month")
    }

    result = prepare_dashboard(df, filters, filename=filename)

    if result is None:
        return "Sales column not found."

    kpis, charts, preview_table, filter_options, dataset_info, insights, recommendations = result

    generate_pdf_report(
        PDF_REPORT_FILE,
        dataset_info,
        kpis,
        insights,
        recommendations
    )

    return render_template(
        "dashboard.html",
        kpis=kpis,
        charts=charts,
        preview_table=preview_table,
        filter_options=filter_options,
        selected_filters=filters,
        dataset_info=dataset_info,
        insights=insights,
        recommendations=recommendations
    )


@app.route("/download")
def download_report():
    if os.path.exists(CURRENT_FILE):
        file_path = CURRENT_FILE
    else:
        file_path = os.path.join(app.config["REPORT_FOLDER"], "cleaned_sales_report.csv")

    return send_file(file_path, as_attachment=True)


@app.route("/download-pdf")
def download_pdf():
    if os.path.exists(PDF_REPORT_FILE):
        return send_file(PDF_REPORT_FILE, as_attachment=True)

    return "PDF report not generated yet."


if __name__ == "__main__":
    app.run(debug=True)