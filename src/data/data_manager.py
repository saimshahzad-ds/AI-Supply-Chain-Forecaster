# src/data/data_manager.py
import sqlite3
import os
import re
import difflib
import pandas as pd
from datetime import datetime
import streamlit as st  # Added for frontend warnings during bulk upload

def _get_db_path():
    """Search from CWD upward so this works regardless of where streamlit run is called from."""
    search_paths = [
        os.path.join(os.getcwd(), "database", "scm_forecaster.db"),
        os.path.join(os.getcwd(), "scm_forecaster.db"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "database", "scm_forecaster.db"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "scm_forecaster.db"),
    ]
    for p in search_paths:
        if os.path.exists(p):
            return os.path.abspath(p)
    return os.path.abspath(search_paths[0])

DB_PATH = _get_db_path()

def _ensure_all_tables():
    """Create all tables if missing. Runs at import time; deleting the .db file resets everything."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS User (
            user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    NOT NULL UNIQUE,
            password_hash TEXT    NOT NULL,
            full_name     TEXT,
            email         TEXT,
            role          TEXT    NOT NULL DEFAULT 'Staff',
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS FoodItem (
            item_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL UNIQUE,
            category  TEXT,
            unit      TEXT NOT NULL DEFAULT 'units'
        );

        CREATE TABLE IF NOT EXISTS Sales (
            sale_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id     INTEGER NOT NULL,
            sale_date   DATE    NOT NULL,
            quantity    INTEGER NOT NULL,
            day_of_week TEXT,
            is_holiday  INTEGER DEFAULT 0,
            FOREIGN KEY (item_id) REFERENCES FoodItem(item_id)
        );

        CREATE TABLE IF NOT EXISTS CustomerCount (
            count_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            count_date     DATE    NOT NULL UNIQUE,
            customer_count INTEGER NOT NULL,
            day_of_week    TEXT,
            is_holiday     INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS Prediction (
            pred_id            INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id            INTEGER NOT NULL,
            pred_date          DATE    NOT NULL,
            predicted_quantity INTEGER NOT NULL,
            model_used         TEXT,
            created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (item_id) REFERENCES FoodItem(item_id)
        );

        CREATE TABLE IF NOT EXISTS InventorySuggestion (
            suggestion_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id           INTEGER NOT NULL,
            suggestion_date   DATE    NOT NULL,
            suggested_quantity INTEGER NOT NULL,
            raw_material      TEXT,
            FOREIGN KEY (item_id) REFERENCES FoodItem(item_id)
        );

        CREATE TABLE IF NOT EXISTS Alert (
            alert_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id    INTEGER,
            alert_date DATE    NOT NULL,
            alert_type TEXT    NOT NULL,
            message    TEXT    NOT NULL,
            is_read    INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS Dataset (
            dataset_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            filename    TEXT NOT NULL,
            uploaded_by INTEGER,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            row_count   INTEGER,
            notes       TEXT,
            FOREIGN KEY (uploaded_by) REFERENCES User(user_id)
        );
    """)
    conn.commit()
    conn.close()

_ensure_all_tables()


def _ensure_dataset_table():
    """Auto-create Dataset table if it doesn't exist (backwards compatibility)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Dataset (
            dataset_id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            uploaded_by INTEGER,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            row_count INTEGER,
            notes TEXT,
            FOREIGN KEY (uploaded_by) REFERENCES User(user_id)
        )
    ''')
    conn.commit()
    conn.close()

# Approximate Pakistani holiday dates - update yearly.
PAKISTANI_HOLIDAYS = {
    "2024-04-10", "2024-04-11", "2024-04-12",  # Eid ul-Fitr 2024
    "2024-06-17", "2024-06-18", "2024-06-19",  # Eid ul-Adha 2024
    "2024-08-14",                              # Independence Day 2024
    "2024-09-16",                              # Eid Milad-un-Nabi 2024
    "2025-03-31", "2025-04-01", "2025-04-02",  # Eid ul-Fitr 2025
    "2025-06-07", "2025-06-08", "2025-06-09",  # Eid ul-Adha 2025
    "2025-08-14",                              # Independence Day 2025
}

def is_pakistani_holiday(date_str):
    try:
        return 1 if str(date_str)[:10] in PAKISTANI_HOLIDAYS else 0
    except Exception:
        return 0

# ---- Food Items ----
def add_food_item(item_name, category, unit):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO FoodItem (item_name, category, unit) VALUES (?, ?, ?)",
            (item_name, category, unit)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_all_food_items():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT item_id, item_name, category, unit FROM FoodItem ORDER BY item_name")
    items = cursor.fetchall()
    conn.close()
    return items

def get_food_item_by_name(item_name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT item_id FROM FoodItem WHERE item_name = ?", (item_name,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# ---- Sales ----
def add_sale(item_id, sale_date, quantity, day_of_week=None, is_holiday=None):
    date_str = str(sale_date)
    if day_of_week is None:
        day_of_week = pd.to_datetime(date_str).strftime("%A")
    if is_holiday is None:
        is_holiday = is_pakistani_holiday(date_str)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO Sales (item_id, sale_date, quantity, day_of_week, is_holiday) VALUES (?, ?, ?, ?, ?)",
        (item_id, date_str, quantity, day_of_week, is_holiday)
    )
    conn.commit()
    conn.close()
    return True

def get_all_sales():
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT s.sale_date, f.item_name, s.quantity, s.day_of_week, s.is_holiday
        FROM Sales s
        JOIN FoodItem f ON s.item_id = f.item_id
        ORDER BY s.sale_date DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def get_sales_by_date_range(start_date, end_date):
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT s.sale_date, f.item_name, s.quantity, s.day_of_week, s.is_holiday
        FROM Sales s
        JOIN FoodItem f ON s.item_id = f.item_id
        WHERE s.sale_date BETWEEN ? AND ?
        ORDER BY s.sale_date
    """
    df = pd.read_sql_query(query, conn, params=(start_date, end_date))
    conn.close()
    return df

# ---- Customer Count ----
def add_customer_count(count_date, customer_count, day_of_week=None, is_holiday=None):
    date_str = str(count_date)
    if day_of_week is None:
        day_of_week = pd.to_datetime(date_str).strftime("%A")
    if is_holiday is None:
        is_holiday = is_pakistani_holiday(date_str)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO CustomerCount (count_date, customer_count, day_of_week, is_holiday) VALUES (?, ?, ?, ?)",
            (date_str, customer_count, day_of_week, is_holiday)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        cursor.execute(
            "UPDATE CustomerCount SET customer_count = ?, day_of_week = ?, is_holiday = ? WHERE count_date = ?",
            (customer_count, day_of_week, is_holiday, date_str)
        )
        conn.commit()
        return True
    finally:
        conn.close()

def get_customer_counts():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM CustomerCount ORDER BY count_date", conn)
    conn.close()
    return df

# ---- Dataset Upload Log ----
def log_dataset_upload(filename, uploaded_by_user_id, row_count, notes=""):
    _ensure_dataset_table()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO Dataset (filename, uploaded_by, row_count, notes) VALUES (?, ?, ?, ?)",
        (filename, uploaded_by_user_id, row_count, notes)
    )
    conn.commit()
    conn.close()

def get_dataset_uploads():
    _ensure_dataset_table()
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT d.dataset_id, d.filename, u.username, d.upload_date, d.row_count, d.notes
        FROM Dataset d
        LEFT JOIN User u ON d.uploaded_by = u.user_id
        ORDER BY d.upload_date DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# ---- Bulk Upload from CSV/Excel ----

# Synonym lists for fuzzy column matching against messy POS export headers.
COLUMN_ALIASES = {
    'item':           ['item', 'item_name', 'fooditem', 'food_item', 'product',
                        'product_name', 'menu_item', 'dish', 'sku', 'name'],
    'quantity':       ['quantity', 'qty', 'amount', 'units', 'units_sold',
                        'sold', 'count', 'sales', 'unitssold'],
    'date':           ['date', 'sale_date', 'order_date', 'transaction_date',
                        'saledate', 'orderdate', 'day', 'timestamp'],
    'customer_count':  ['customer count', 'customer_count', 'customercount',
                        'customers', 'footfall', 'visitors', 'foot_traffic',
                        'walkins', 'walk_ins'],
}


def _normalize_col(col):
    """Lowercase + strip non-alphanumerics so 'Order Date' == 'order_date' == 'OrderDate'."""
    return re.sub(r'[^a-z0-9]', '', str(col).lower())


def _match_column(df_columns, target_key):
    """Match a column to a canonical field via exact alias, substring, or closest difflib match."""
    normalized = {_normalize_col(c): c for c in df_columns}
    aliases = [_normalize_col(a) for a in COLUMN_ALIASES[target_key]]

    # 1. Exact alias match
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
            
    # 2. Substring fallback (The Upgrade)
    # Automatically catches "date" inside "date_of_sale" or "item" inside "food_item_name"
    target_base = _normalize_col(target_key)
    for norm_col, orig_col in normalized.items():
        if target_base in norm_col:
            return orig_col

    # 3. Fuzzy match
    best_col, best_score = None, 0.0
    for norm_col, orig_col in normalized.items():
        for alias in aliases:
            score = difflib.SequenceMatcher(None, norm_col, alias).ratio()
            if score > best_score:
                best_score, best_col = score, orig_col
    return best_col if best_score >= 0.72 else None


def _clean_numeric(value):
    """Strip currency/commas/units from a value and return a float, or None. e.g. "Rs. 1,200" -> 1200.0"""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) if not pd.isna(value) else None
    s = str(value).strip()
    if not s:
        return None
    cleaned = re.sub(r'[^0-9.\-]', '', s)
    if cleaned in ('', '-', '.', '-.'):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def bulk_upload_sales(df, uploaded_by_user_id=None, filename="unknown"):
    """Import a sales CSV/Excel export: fuzzy-matches messy headers, cleans dirty
    numeric fields, aggregates duplicate item/date rows, and drops future dates."""
    if df is None or df.empty:
        st.warning("The uploaded file is empty.")
        return 0

    df = df.copy()

    item_col = _match_column(df.columns, 'item')
    qty_col  = _match_column(df.columns, 'quantity')
    date_col = _match_column(df.columns, 'date')
    cust_col = _match_column(df.columns, 'customer_count')

    missing = [name for name, col in
               [('item', item_col), ('quantity', qty_col), ('date', date_col)] if not col]
    if missing:
        st.error(
            f"Could not confidently match columns for: {', '.join(missing)}. "
            f"Found columns in file: {list(df.columns)}. "
            "Rename headers to something like Item/Product, Quantity/Qty, Date and re-upload."
        )
        return 0

    df['_item'] = df[item_col].astype(str).str.strip()
    df['_qty']  = df[qty_col].apply(_clean_numeric)
    df['_date'] = pd.to_datetime(df[date_col], errors='coerce')
    df['_cust'] = df[cust_col].apply(_clean_numeric) if cust_col else None

    before = len(df)
    df = df[
        df['_item'].ne('') & df['_item'].str.lower().ne('nan') &
        df['_qty'].notna() & df['_date'].notna()
    ]
    dropped_dirty = before - len(df)
    if dropped_dirty > 0:
        st.warning(f"Skipped {dropped_dirty} rows with missing/unreadable item, quantity, or date.")

    # block future dates to protect database integrity
    today = pd.Timestamp(datetime.now().date())
    before = len(df)
    df = df[df['_date'] <= today]
    dropped_future = before - len(df)
    if dropped_future > 0:
        st.warning(f"Blocked {dropped_future} rows containing future dates to protect database integrity.")

    if df.empty:
        return 0

    df['_date_str'] = df['_date'].dt.strftime('%Y-%m-%d')

    # aggregate duplicate (item, date) rows so multiple receipts/day become one row
    sales_agg = df.groupby(['_item', '_date_str'], as_index=False)['_qty'].sum()

    cust_agg = {}
    if cust_col:
        cust_df = df.dropna(subset=['_cust'])
        if not cust_df.empty:
            cust_agg = cust_df.groupby('_date_str')['_cust'].max().to_dict()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    count = 0
    try:
        for _, row in sales_agg.iterrows():
            item_name = row['_item']
            date_str  = row['_date_str']
            quantity  = int(round(row['_qty']))

            cursor.execute("SELECT item_id FROM FoodItem WHERE item_name = ?", (item_name,))
            result = cursor.fetchone()
            if result:
                item_id = result[0]
            else:
                cursor.execute(
                    "INSERT INTO FoodItem (item_name, category, unit) VALUES (?, ?, ?)",
                    (item_name, "General", "units")
                )
                item_id = cursor.lastrowid

            day_of_week  = pd.to_datetime(date_str).strftime("%A")
            holiday_flag = is_pakistani_holiday(date_str)

            cursor.execute(
                "INSERT INTO Sales (item_id, sale_date, quantity, day_of_week, is_holiday) VALUES (?, ?, ?, ?, ?)",
                (item_id, date_str, quantity, day_of_week, holiday_flag)
            )
            count += 1

        for date_str, customer_count in cust_agg.items():
            day_of_week  = pd.to_datetime(date_str).strftime("%A")
            holiday_flag = is_pakistani_holiday(date_str)
            try:
                cursor.execute(
                    "INSERT INTO CustomerCount (count_date, customer_count, day_of_week, is_holiday) VALUES (?, ?, ?, ?)",
                    (date_str, int(round(customer_count)), day_of_week, holiday_flag)
                )
            except sqlite3.IntegrityError:
                cursor.execute(
                    "UPDATE CustomerCount SET customer_count = ?, day_of_week = ?, is_holiday = ? WHERE count_date = ?",
                    (int(round(customer_count)), day_of_week, holiday_flag, date_str)
                )

        conn.commit()
    finally:
        conn.close()

    if count > 0:
        log_dataset_upload(filename, uploaded_by_user_id, count)

    return count

# ---- Predictions ----
def save_prediction(item_id, pred_date, predicted_quantity, model_used):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO Prediction (item_id, pred_date, predicted_quantity, model_used) VALUES (?, ?, ?, ?)",
        (item_id, pred_date, predicted_quantity, model_used)
    )
    conn.commit()
    conn.close()

def get_predictions():
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT p.pred_date, f.item_name, p.predicted_quantity, p.model_used
        FROM Prediction p
        JOIN FoodItem f ON p.item_id = f.item_id
        ORDER BY p.pred_date
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# ---- Inventory Suggestions ----
def save_inventory_suggestion(item_id, suggestion_date, suggested_quantity, raw_material):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO InventorySuggestion (item_id, suggestion_date, suggested_quantity, raw_material) VALUES (?, ?, ?, ?)",
        (item_id, suggestion_date, suggested_quantity, raw_material)
    )
    conn.commit()
    conn.close()

def get_inventory_suggestions():
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT i.suggestion_date, f.item_name, i.suggested_quantity, i.raw_material
        FROM InventorySuggestion i
        JOIN FoodItem f ON i.item_id = f.item_id
        ORDER BY i.suggestion_date DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# ---- Alerts ----
def save_alert(item_id, alert_date, alert_type, message):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO Alert (item_id, alert_date, alert_type, message) VALUES (?, ?, ?, ?)",
        (item_id, alert_date, alert_type, message)
    )
    conn.commit()
    conn.close()

def get_alerts():
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT a.alert_date, f.item_name, a.alert_type, a.message, a.is_read
        FROM Alert a
        LEFT JOIN FoodItem f ON a.item_id = f.item_id
        ORDER BY a.alert_date DESC
        LIMIT 20
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def generate_demand_alerts(predictions, model_used="ARIMA"):
    """Flag days where predicted demand is +-20% from the historical average.
    Deletes all previous alerts first so re-running never duplicates."""
    if not predictions or not predictions.get("customer_forecast"):
        return

    historical = get_customer_counts()
    if historical.empty:
        return

    avg_customers = historical['customer_count'].mean()
    if avg_customers == 0:
        return

    threshold_high = avg_customers * 1.20
    threshold_low  = avg_customers * 0.80

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM Alert")
        conn.commit()

        for date_str, pred_count in zip(predictions["dates"], predictions["customer_forecast"]):
            if pred_count >= threshold_high:
                pct = round((pred_count / avg_customers - 1) * 100)
                conn.execute(
                    "INSERT INTO Alert (item_id, alert_date, alert_type, message) VALUES (?, ?, ?, ?)",
                    (None, date_str, "High Demand",
                     f"Predicted {pred_count} customers on {date_str} — {pct}% above average ({round(avg_customers)}). Stock up!")
                )
            elif pred_count <= threshold_low:
                pct = round((1 - pred_count / avg_customers) * 100)
                conn.execute(
                    "INSERT INTO Alert (item_id, alert_date, alert_type, message) VALUES (?, ?, ?, ?)",
                    (None, date_str, "Low Demand",
                     f"Predicted {pred_count} customers on {date_str} — {pct}% below average ({round(avg_customers)}). Reduce stock.")
                )
        conn.commit()
    finally:
        conn.close()