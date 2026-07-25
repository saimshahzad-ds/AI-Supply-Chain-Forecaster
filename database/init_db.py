# database/init_db.py
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "scm_forecaster.db")

def init_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. User Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS User (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            email TEXT,
            role TEXT NOT NULL CHECK(role IN ('Admin', 'Staff')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2. FoodItem Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS FoodItem (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT UNIQUE NOT NULL,
            category TEXT,
            unit TEXT NOT NULL
        )
    ''')

    # 3. Dataset Table  ← REQUIRED by spec, was missing
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

    # 4. Sales Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Sales (
            sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            sale_date DATE NOT NULL,
            quantity INTEGER NOT NULL,
            day_of_week TEXT,
            is_holiday INTEGER DEFAULT 0,
            FOREIGN KEY (item_id) REFERENCES FoodItem(item_id)
        )
    ''')

    # 5. CustomerCount Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS CustomerCount (
            count_id INTEGER PRIMARY KEY AUTOINCREMENT,
            count_date DATE UNIQUE NOT NULL,
            customer_count INTEGER NOT NULL,
            day_of_week TEXT,
            is_holiday INTEGER DEFAULT 0
        )
    ''')

    # 6. Prediction Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Prediction (
            pred_id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            pred_date DATE NOT NULL,
            predicted_quantity INTEGER NOT NULL,
            model_used TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (item_id) REFERENCES FoodItem(item_id)
        )
    ''')

    # 7. InventorySuggestion Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS InventorySuggestion (
            suggestion_id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            suggestion_date DATE NOT NULL,
            suggested_quantity INTEGER NOT NULL,
            raw_material TEXT,
            FOREIGN KEY (item_id) REFERENCES FoodItem(item_id)
        )
    ''')

    # 8. Alert Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Alert (
            alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER,
            alert_date DATE NOT NULL,
            alert_type TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            FOREIGN KEY (item_id) REFERENCES FoodItem(item_id)
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")
    print(f"📁 Location: {DB_PATH}")

if __name__ == "__main__":
    init_database()
