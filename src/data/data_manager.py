# src/data/data_manager.py
import sqlite3
import os
import pandas as pd
from datetime import datetime
import streamlit as st  # Added for frontend warnings during bulk upload

def _get_db_path():
    """
    Find scm_forecaster.db by searching from CWD upward.
    This works regardless of where streamlit run is called from.
    """
    search_paths = [
        os.path.join(os.getcwd(), "database", "scm_forecaster.db"),
        os.path.join(os.getcwd(), "scm_forecaster.db"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "database", "scm_forecaster.db"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "scm_forecaster.db"),
    ]
    for p in search_paths:
        if os.path.exists(p):
            return os.path.abspath(p)
    # Default — will be created here if it doesn't exist yet
    return os.path.abspath(search_paths[0])

DB_PATH = _get_db_path()

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

# ---- Pakistani Holidays (Ramadan/Eid approximations) ----
# These are approximate dates — update yearly as needed
PAKISTANI_HOLIDAYS = {
    # Eid ul-Fitr 2024
    "2024-04-10", "2024-04-11", "2024-04-12",
    # Eid ul-Adha 2024
    "2024-06-17", "2024-06-18", "2024-06-19",
    # Pakistan Independence Day
    "2024-08-14",
    # Eid Milad-un-Nabi 2024
    "2024-09-16",
    # Eid ul-Fitr 2025
    "2025-03-31", "2025-04-01", "2025-04-02",
    # Eid ul-Adha 2025
    "2025-06-07", "2025-06-08", "2025-06-09",
    # Pakistan Independence Day 2025
    "2025-08-14",
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
        # Update if date already exists
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
def bulk_upload_sales(df, uploaded_by_user_id=None, filename="unknown"):
    # --- NEW VALIDATION CODE: Strip out future dates ---
    date_col = next((col for col in ['Date', 'date', 'sale_date'] if col in df.columns), None)
    if date_col:
        df['temp_date'] = pd.to_datetime(df[date_col], errors='coerce')
        today = pd.Timestamp(datetime.now().date())
        
        original_len = len(df)
        df = df[df['temp_date'] <= today]
        dropped_rows = original_len - len(df)
        
        if dropped_rows > 0:
            st.warning(f"Blocked {dropped_rows} rows containing future dates to protect database integrity.")
    # ---------------------------------------------------

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    count = 0

    for _, row in df.iterrows():
        item_name = row.get('Item') or row.get('item_name') or row.get('FoodItem')
        quantity = row.get('Quantity') or row.get('quantity') or row.get('Qty')
        sale_date = row.get('Date') or row.get('sale_date') or row.get('date')

        if item_name and quantity and sale_date:
            cursor.execute("SELECT item_id FROM FoodItem WHERE item_name = ?", (str(item_name),))
            result = cursor.fetchone()
            if result:
                item_id = result[0]
            else:
                cursor.execute(
                    "INSERT INTO FoodItem (item_name, category, unit) VALUES (?, ?, ?)",
                    (str(item_name), "General", "units")
                )
                item_id = cursor.lastrowid

            date_str = str(sale_date)[:10]
            day_of_week = pd.to_datetime(date_str).strftime("%A")
            holiday_flag = is_pakistani_holiday(date_str)

            cursor.execute(
                "INSERT INTO Sales (item_id, sale_date, quantity, day_of_week, is_holiday) VALUES (?, ?, ?, ?, ?)",
                (item_id, date_str, int(quantity), day_of_week, holiday_flag)
            )
            count += 1

    conn.commit()
    conn.close()

    # Log the upload in Dataset table
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
    """
    Compare predicted customer count to historical average.
    Generate Alert records only for days where demand is ±20% from average.
    Deletes ALL previous alerts first so re-running never duplicates.
    """
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

    # Use a single connection — delete all old alerts then insert fresh ones atomically
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