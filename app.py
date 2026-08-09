# app.py
import streamlit as st
import sqlite3
import sys
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
from io import BytesIO

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from auth.auth_manager import create_user, authenticate_user, get_all_users, delete_user, update_user_role, create_default_admin
from data.data_manager import (
    add_food_item, get_all_food_items, get_food_item_by_name,
    add_sale, add_customer_count, get_all_sales, get_customer_counts,
    bulk_upload_sales, get_predictions, get_inventory_suggestions,
    get_alerts, generate_demand_alerts, save_inventory_suggestion,
    get_dataset_uploads, save_prediction
)
from models.predictor import generate_all_predictions, get_prediction_summary, evaluate_models

# ── Page Config ──
st.set_page_config(page_title="SCM Forecaster", page_icon="📊", layout="wide")

# Automatically setup the master admin without slowing down the app
@st.cache_resource
def init_admin():
    create_default_admin()

init_admin()

# ── CSS ──
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer    {visibility: hidden;}

    .stApp { background-color: #f0f2f6; }

    /* Sidebar */
    section[data-testid="stSidebar"] { background-color: #1a1a2e; }
    section[data-testid="stSidebar"] * { color: #ffffff !important; }
    section[data-testid="stSidebar"] button {
        background-color: transparent !important;
        border: 1px solid #333366 !important;
        text-align: left !important;
        padding: 10px 15px;
        border-radius: 6px;
        margin: 2px 0;
    }
    section[data-testid="stSidebar"] button:hover { background-color: #333366 !important; }

    /* Page title */
    .page-title { color:#1a1a2e; font-size:1.8rem; font-weight:700; }

    /* Custom metric cards (used on Dashboard) */
    .metric-card  { background:#ffffff; border-radius:10px; padding:20px; box-shadow:0 1px 5px rgba(0,0,0,0.1); margin:5px 0; }
    .metric-value { font-size:1.8rem; font-weight:700; color:#1a1a2e; }
    .metric-label { font-size:0.75rem; color:#666666; text-transform:uppercase; letter-spacing:1px; }
    .metric-change { font-size:0.85rem; font-weight:600; }
    .positive { color:#00a844; }
    .warning  { color:#e06000; }
    .negative { color:#e01020; }

    /* Inputs */
    .stTextInput input, input[type="text"], input[type="password"],
    input[type="number"], input[type="date"], textarea, select {
        color:#000000 !important; background-color:#ffffff !important; border:1px solid #cccccc !important;
    }
    input::placeholder, textarea::placeholder { color:#999999 !important; }
    label { color:#1a1a2e !important; font-weight:500 !important; }
    h1,h2,h3,h4,h5,h6 { color:#1a1a2e !important; }

    /* Buttons */
    .stButton > button       { border-radius:8px; font-weight:600; }
    .stDownloadButton > button { border-radius:8px; font-weight:600; }

    /* Tabs */
    .stTabs [aria-selected="true"] { color:#1a1a2e !important; font-weight:600; background-color:#e8e8e8 !important; }
    .stTabs [data-baseweb="tab"]   { color:#333333 !important; }

    /* Captions */
    .stCaption { color:#444444 !important; font-size:0.9rem !important; }

    /* Alert boxes */
    .stSuccess { color:#004d00 !important; font-weight:700 !important; font-size:0.95rem !important; background-color:#b8f0c8 !important; border:2px solid #1a7a30 !important; }
    .stError   { color:#7a0000 !important; font-weight:700 !important; font-size:0.95rem !important; background-color:#ffd6d6 !important; border:2px solid #cc0000 !important; }
    .stWarning { color:#5a2800 !important; font-weight:700 !important; font-size:0.95rem !important; background-color:#ffd199 !important; border:2px solid #cc5500 !important; }
    .stInfo    { color:#003d4d !important; font-weight:700 !important; font-size:0.95rem !important; background-color:#b8e8f5 !important; border:2px solid #0088aa !important; }
    .stSuccess p, .stSuccess span, .stSuccess [data-testid="stMarkdownContainer"] { color:#004d00 !important; font-weight:700 !important; }
    .stError p, .stError span, .stError [data-testid="stMarkdownContainer"] { color:#7a0000 !important; font-weight:700 !important; }
    .stWarning p, .stWarning span, .stWarning [data-testid="stMarkdownContainer"] { color:#5a2800 !important; font-weight:700 !important; }
    .stInfo p, .stInfo span, .stInfo [data-testid="stMarkdownContainer"] { color:#003d4d !important; font-weight:700 !important; }

    /* Dataframe */
    .stDataFrame { color:#1a1a2e !important; }

    /* Static Tables (st.table) */
    [data-testid="stTable"] { background-color: #ffffff !important; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.05); }
    [data-testid="stTable"] th { background-color: #1a1a2e !important; color: #ffffff !important; font-weight: 600 !important; border: 1px solid #d0d0d0 !important; padding: 10px !important; }
    [data-testid="stTable"] td { color: #1a1a2e !important; border: 1px solid #e0e0e0 !important; padding: 10px !important; }

    /* Animated metric cards */
    .metric-card {
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        cursor: default;
    }
    .metric-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 6px 20px rgba(0,0,0,0.15) !important;
    }
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(16px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    .metric-card { animation: fadeInUp 0.4s ease forwards; }
</style>
""", unsafe_allow_html=True)

# ── Session State ──
for key, default in [
    ("logged_in", False),
    ("user", None),
    ("page", "Dashboard"),
    ("predictions", None),
    ("eval_df", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════
def require_admin():
    if st.session_state.user['role'] != 'Admin':
        st.error("Access denied. This section is for Admins only.")
        st.stop()

def df_to_excel_bytes(sheets: dict) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    return buf.getvalue()

def subtitle(text):
    st.markdown(f'<p style="color:#1a1a2e;font-size:1rem;font-weight:500;margin-bottom:8px;">{text}</p>', unsafe_allow_html=True)

def info_text(text):
    st.markdown(f'<p style="color:#444444;font-size:0.9rem;">{text}</p>', unsafe_allow_html=True)

def persist_predictions(results):
    """
    Fix #6: generate_all_predictions() only returns forecasts in memory -
    nothing ever called save_prediction(), so the Prediction table stayed
    empty. This writes every (item, date, predicted_quantity) triple to the
    database so forecasts survive a restart and show up in get_predictions().
    Returns the number of rows saved.
    """
    if not results or not results.get("item_forecasts"):
        return 0
    dates      = results["dates"]
    model_used = results.get("model_used", "N/A")
    saved      = 0
    for item_name, forecast in results["item_forecasts"].items():
        item_id = get_food_item_by_name(item_name)
        if item_id is None:
            continue
        for pred_date, predicted_quantity in zip(dates, forecast):
            save_prediction(item_id, pred_date, int(predicted_quantity), model_used)
            saved += 1
    return saved

# ════════════════════════════════════════════════════════
# LOGIN
# ════════════════════════════════════════════════════════
def show_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("""
        <div style="text-align:center;background:#ffffff;padding:40px;border-radius:12px;box-shadow:0 2px 10px rgba(0,0,0,0.08);">
            <h2 style="color:#1a1a2e;">SCM Forecaster</h2>
            <p style="color:#555555;">AI-Driven Food Supply Chain Management</p>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["Login", "Sign Up"])

        with tab1:
            username = st.text_input("Username", key="login_user", placeholder="Enter your username")
            password = st.text_input("Password", type="password", key="login_pass", placeholder="Enter your password")
            if st.button("Login", use_container_width=True, type="primary"):
                if username and password:
                    user = authenticate_user(username, password)
                    if user:
                        st.session_state.logged_in = True
                        st.session_state.user = user
                        st.rerun()
                    else:
                        st.error("Invalid username or password")
                else:
                    st.warning("Please enter username and password")

        with tab2:
            new_user = st.text_input("Username", key="new_user", placeholder="Choose a username")
            new_pass = st.text_input("Password", type="password", key="new_pass", placeholder="Choose a password")
            new_name = st.text_input("Full Name", key="new_name", placeholder="Your full name")
            
            if st.button("Create Account", use_container_width=True, type="primary"):
                if new_user and new_pass:
                    success, msg = create_user(new_user, new_pass, "Staff", new_name)  # sign-ups always get Staff role
                    st.success(msg + " Go to Login tab.") if success else st.error(msg)
                else:
                    st.warning("Please fill all required fields")

# ════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════
def show_sidebar():
    user = st.session_state.user
    with st.sidebar:
        st.markdown("## SCM Forecaster")
        st.divider()
        nav_items = ["Dashboard", "Upload Dataset", "Data Entry",
                     "Prediction Model", "View Predictions", "Inventory Report"]
        if user['role'] == 'Admin':
            nav_items.append("Manage Users")
        for item in nav_items:
            if st.button(item, use_container_width=True):
                st.session_state.page = item
                st.rerun()
        st.divider()
        st.caption(f"User: {user['full_name'] or user['username']}")
        st.caption(f"Role: {user['role']}")
        st.caption("ID: F25PROJECTA07AD")
        if st.button("Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.session_state.predictions = None
            st.rerun()

# ════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ════════════════════════════════════════════════════════
def page_dashboard():
    st.markdown('<p class="page-title">SCM Forecaster</p>', unsafe_allow_html=True)
    st.markdown("### Overview Dashboard")
    st.divider()

    sales_df    = get_all_sales()
    customer_df = get_customer_counts()
    alerts_df   = get_alerts()

    today_str = str(date.today())
    today_sales = int(sales_df[sales_df['sale_date'] == today_str]['quantity'].sum()) if not sales_df.empty and 'sale_date' in sales_df.columns else 0

    if not customer_df.empty:
        latest_count = int(customer_df.iloc[-1]['customer_count'])
        avg_count    = round(customer_df['customer_count'].mean(), 1)
    else:
        latest_count = avg_count = 0

    unread_alerts = int((alerts_df['is_read'] == 0).sum()) if not alerts_df.empty and 'is_read' in alerts_df.columns else 0

    c1, c2, c3 = st.columns(3)
    with c1:
        total_sales = int(sales_df['quantity'].sum()) if not sales_df.empty else 0
        st.markdown(f"""<div class="metric-card" style="border-left:4px solid #1a1a2e;">
            <div class="metric-label">TODAY'S UNITS SOLD</div>
            <div class="metric-value">{today_sales}</div>
            <div class="metric-change positive">Total all time: {total_sales} units</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        dc = "warning" if latest_count > avg_count * 1.2 else "positive"
        dl = "High" if latest_count > avg_count * 1.2 else "Normal"
        trend_icon = "↑" if latest_count > avg_count else "↓" if latest_count < avg_count else "→"
        border_col = "#e06000" if dc == "warning" else "#00a844"
        st.markdown(f"""<div class="metric-card" style="border-left:4px solid {border_col};">
            <div class="metric-label">LATEST CUSTOMER COUNT</div>
            <div class="metric-value {dc}">{trend_icon} {latest_count}</div>
            <div class="metric-change {dc}">Avg: {avg_count} — {dl} demand</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        ac = "negative" if unread_alerts > 0 else "positive"
        alert_border = "#e01020" if unread_alerts > 0 else "#00a844"
        alert_icon = "⚠" if unread_alerts > 0 else "✓"
        st.markdown(f"""<div class="metric-card" style="border-left:4px solid {alert_border};">
            <div class="metric-label">ACTIVE ALERTS</div>
            <div class="metric-value">{unread_alerts}</div>
            <div class="metric-change {ac}">{alert_icon} {'Needs attention' if unread_alerts > 0 else 'All clear'}</div>
        </div>""", unsafe_allow_html=True)

    st.divider()
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.subheader("Customer Count — Last 30 Days (Actual vs Predicted)")
        if not customer_df.empty and 'count_date' in customer_df.columns:
            actual = customer_df.tail(30).copy()
            actual['count_date'] = pd.to_datetime(actual['count_date'])

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=actual['count_date'], y=actual['customer_count'],
                mode='lines+markers', name='Actual',
                line=dict(color='#1a1a2e', width=2),
                marker=dict(size=6)
            ))
            if st.session_state.predictions:
                p = st.session_state.predictions
                fig.add_trace(go.Scatter(
                    x=pd.to_datetime(p['dates']), y=p['customer_forecast'],
                    mode='lines+markers', name='Predicted',
                    line=dict(color='#e06000', width=2, dash='dash'),
                    marker=dict(size=6)
                ))
            fig.update_layout(
                height=340, plot_bgcolor='#ffffff', paper_bgcolor='#ffffff',
                margin=dict(l=10, r=10, t=10, b=10),
                legend=dict(orientation="h", y=-0.15, font=dict(size=13, color='#1a1a2e')),
                xaxis=dict(
                    title="Date",
                    title_font=dict(size=14, color='#1a1a2e', family='Arial Black'),
                    tickfont=dict(size=12, color='#1a1a2e', family='Arial'),
                    tickformat="%d %b",
                    showgrid=False,
                    linecolor='#333333', linewidth=2,
                ),
                yaxis=dict(
                    title="Customers",
                    title_font=dict(size=14, color='#1a1a2e', family='Arial Black'),
                    tickfont=dict(size=12, color='#1a1a2e', family='Arial'),
                    gridcolor='#bbbbbb', gridwidth=1,
                    linecolor='#333333', linewidth=2,
                    showgrid=True,
                ),
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No customer data yet. Add entries via Data Entry.")

    with col_right:
        st.subheader("Active Alerts")
        if not alerts_df.empty:
            row = alerts_df.iloc[0]
            alert_type = row.get('alert_type', '')
            msg        = row.get('message', '')
            
            if 'High' in alert_type:
                bg_col, border_col, text_col = "#ffebee", "#d32f2f", "#b71c1c"
                icon = "🚨"
            elif 'Low' in alert_type:
                bg_col, border_col, text_col = "#fff3e0", "#f57c00", "#e65100"
                icon = "⚠️"
            else:
                bg_col, border_col, text_col = "#e3f2fd", "#1976d2", "#0d47a1"
                icon = "ℹ️"

            st.markdown(f"""
            <div style="background-color:{bg_col}; border-left:6px solid {border_col}; padding:16px; border-radius:8px; box-shadow:0 2px 5px rgba(0,0,0,0.05);">
                <div style="color:{text_col}; font-size:1.05rem; font-weight:800; margin-bottom:6px;">{icon} {alert_type}</div>
                <div style="color:{text_col}; font-size:0.95rem; font-weight:600; line-height:1.4;">{msg}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown('<div style="background:#fff;padding:15px;border-radius:8px;border:1px solid #e0e0e0;"><span style="color:#00a844;font-weight:600;">No active alerts</span></div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════
# PAGE: UPLOAD DATASET  (Admin only)
# ════════════════════════════════════════════════════════
def page_upload_dataset():
    require_admin()
    st.markdown('<p class="page-title">Upload Dataset</p>', unsafe_allow_html=True)
    subtitle("Upload historical sales data (CSV or Excel). Admin only.")
    st.divider()

    uploaded_file = st.file_uploader("Choose file", type=["csv", "xlsx"])
    if uploaded_file:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
        st.success(f"File loaded: {uploaded_file.name}")
        st.subheader("Data Preview")
        
        st.table(df.head(10).set_index(df.columns[0]))
        
        info_text(f"Total rows: {len(df)}")
        info_text(
            "Columns are matched automatically (e.g. `Qty`, `Product`, `Order Date` all work) - "
            "no need for exact names. Multiple rows for the same item/date are aggregated automatically."
        )

        if st.button("Save to Database", use_container_width=True, type="primary"):
            count = bulk_upload_sales(df, uploaded_by_user_id=st.session_state.user['user_id'], filename=uploaded_file.name)
            if count > 0:
                st.success(f"Saved {count} sales records (after cleaning/aggregating duplicates). Holiday flags auto-applied.")
            else:
                st.warning("No records saved - see the message above for details.")

    st.divider()
    st.subheader("Upload History")
    uploads = get_dataset_uploads()
    if not uploads.empty:
        st.table(uploads.set_index(uploads.columns[0]))
    else:
        info_text("No uploads yet.")

# ════════════════════════════════════════════════════════
# PAGE: DATA ENTRY
# ════════════════════════════════════════════════════════
def page_data_entry():
    st.markdown('<p class="page-title">Manual Data Entry</p>', unsafe_allow_html=True)
    subtitle("Enter daily sales and customer count")
    st.divider()

    items = get_all_food_items()
    if not items:
        for item in ["Biryani", "Chicken Karahi", "Naan", "Seekh Kebab", "Daal", "Raita"]:
            add_food_item(item, "Food", "units")
        items = get_all_food_items()

    item_names = [i[1] for i in items]
    tab1, tab2 = st.tabs(["Sales Entry", "Add Food Item"])

    with tab1:
        col1, col2, col3 = st.columns(3)
        with col1:
            entry_date = st.date_input("Date", value=date.today(), max_value=date.today())
        with col2:
            food_item = st.selectbox("Food Item", item_names)
        with col3:
            quantity = st.number_input("Quantity Sold", min_value=0, value=0)
        customer_count = st.number_input("Customer Count (for this date)", min_value=0, value=0)

        if st.button("Save Entry", use_container_width=True, type="primary"):
            item_id = get_food_item_by_name(food_item)
            if item_id:
                add_sale(item_id, str(entry_date), quantity)
                add_customer_count(str(entry_date), customer_count)
                st.success(f"Saved: {quantity}x {food_item}, {customer_count} customers on {entry_date}")
            else:
                st.error("Food item not found!")

    with tab2:
        new_item = st.text_input("New Food Item Name")
        new_cat  = st.text_input("Category", value="Food")
        new_unit = st.text_input("Unit", value="units")
        if st.button("Add Item"):
            if new_item:
                ok = add_food_item(new_item, new_cat, new_unit)
                if ok:
                    st.success(f"Added: {new_item}")
                    st.rerun()
                else:
                    st.error("Item already exists.")
            else:
                st.warning("Enter an item name.")

    st.divider()
    st.subheader("Recent Sales")
    sales_df = get_all_sales()
    if not sales_df.empty:
        st.table(sales_df.head(20).set_index(sales_df.columns[0]))
    else:
        info_text("No sales data yet.")

# ════════════════════════════════════════════════════════
# PAGE: PREDICTION MODEL
# ════════════════════════════════════════════════════════
def page_prediction_model():
    st.markdown('<p class="page-title">Prediction Model</p>', unsafe_allow_html=True)
    subtitle("Configure and run the AI demand forecasting model")
    st.divider()

    FORECAST_PERIOD_DAYS = {"Next 7 Days": 7, "Next 14 Days": 14, "Next 30 Days": 30}

    col1, col2 = st.columns(2)
    with col1:
        model_type = st.selectbox("Select Model", ["ARIMA", "XGBoost", "LSTM"])
    with col2:
        forecast_period = st.selectbox("Forecast Period", list(FORECAST_PERIOD_DAYS.keys()))
        forecast_days = FORECAST_PERIOD_DAYS[forecast_period]
        info_text(f"Model will be trained to forecast {forecast_days} days ahead.")

    st.markdown('<style>details summary p { color:#1a1a2e !important; font-weight:700 !important; font-size:1rem !important; }</style>', unsafe_allow_html=True)
    with st.expander("Data Preprocessing Details"):
        st.markdown("""
        <div style="background:#1a1a2e;padding:16px;border-radius:8px;border-left:4px solid #4a90d9;">
            <p style="color:#ffffff;font-size:0.95rem;margin-bottom:8px;font-weight:600;">Before training, the system automatically:</p>
            <ul style="color:#d0d8f0;font-size:0.9rem;line-height:1.8;margin:0;padding-left:20px;">
                <li>Extracts <strong style="color:#7eb8f7;">Day of Week</strong> feature from all dates</li>
                <li>Tags <strong style="color:#7eb8f7;">Pakistani public holidays</strong> (Eid ul-Fitr, Eid ul-Adha, Independence Day, Eid Milad-un-Nabi)</li>
                <li>Fills missing dates with <strong style="color:#7eb8f7;">0 values</strong> to create a regular time series</li>
                <li>Removes <strong style="color:#7eb8f7;">invalid or null</strong> records</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    if st.button("Generate Predictions", use_container_width=True, type="primary"):
        with st.spinner(f"Preprocessing data and training model for {forecast_days} days..."):
            try:
                results = generate_all_predictions(model_type, forecast_days)
                if results and results.get("customer_forecast"):
                    st.session_state.predictions = results
                    generate_demand_alerts(results, model_used=model_type)
                    saved_count = persist_predictions(results)

                    st.markdown(f'<div style="background-color:#059669; color:white; padding:16px; border-radius:8px; font-weight:700; font-size:1.1rem; box-shadow:0 4px 6px rgba(0,0,0,0.1); border-left:6px solid #047857; margin-bottom:15px;">Predictions generated for {forecast_days} days! {saved_count} forecast rows saved to database. Alerts updated. Go to View Predictions.</div>', unsafe_allow_html=True)
                    
                    st.subheader("Quick Preview")
                    
                    preview_df = pd.DataFrame({
                        "Date": results["dates"],
                        "Predicted Customers": results["customer_forecast"]
                    }).set_index("Date")
                    st.table(preview_df)
                else:
                    st.warning("Not enough data. Add more sales/customer data first.")
            except Exception as e:
                st.error(f"Error: {str(e)}")

    st.divider()
    st.subheader("Retrain Model")
    if st.session_state.user['role'] == 'Admin':
        if st.button("Retrain with New Data", use_container_width=True):
            with st.spinner(f"Retraining for {forecast_days} days..."):
                try:
                    results = generate_all_predictions(model_type, forecast_days)
                    if results and results.get("customer_forecast"):
                        st.session_state.predictions = results
                        generate_demand_alerts(results, model_used=model_type)
                        saved_count = persist_predictions(results)

                        st.markdown(f'<div style="background-color:#059669; color:white; padding:16px; border-radius:8px; font-weight:700; font-size:1.1rem; box-shadow:0 4px 6px rgba(0,0,0,0.1); border-left:6px solid #047857; margin-bottom:15px;">Model retrained and alerts refreshed! {saved_count} forecast rows saved.</div>', unsafe_allow_html=True)
                    else:
                        st.warning("Not enough data to retrain.")
                except Exception as e:
                    st.error(f"Error: {str(e)}")
    else:
        st.info("Retraining is restricted to Admins.")

    # ── Model Evaluation: train/test split + MAE/RMSE/MAPE vs Naive baseline ──
    st.divider()
    st.subheader("Model Evaluation (Backtest)")
    info_text(
        "Holds out the most recent days as a test set, retrains each model on the "
        "remaining history, forecasts the held-out window, and scores it against what "
        "actually happened - including a Naive 'same day last week' baseline so you can "
        "prove the ML models are actually adding value."
    )

    eval_col1, eval_col2 = st.columns(2)
    with eval_col1:
        test_days = st.slider("Test / holdout days", min_value=3, max_value=14, value=7)
    with eval_col2:
        eval_models = st.multiselect(
            "Models to backtest",
            ["ARIMA", "XGBoost", "LSTM"],
            default=["ARIMA", "XGBoost"],
            help="LSTM retrains a neural net per item/series, so it's the slowest to backtest."
        )

    if st.button("Run Backtest & Evaluation", use_container_width=True):
        if not eval_models:
            st.warning("Select at least one model to backtest.")
        else:
            with st.spinner(f"Backtesting {', '.join(eval_models)} + Naive baseline over the last {test_days} days..."):
                try:
                    eval_df = evaluate_models(model_types=eval_models, test_days=test_days, include_baseline=True)
                    if eval_df.empty:
                        st.warning(
                            "Not enough historical data to backtest yet. "
                            f"Each series needs at least {test_days + 3} days of history."
                        )
                    else:
                        st.session_state["eval_df"] = eval_df
                except Exception as e:
                    st.error(f"Error running evaluation: {str(e)}")

    if st.session_state.get("eval_df") is not None and not st.session_state["eval_df"].empty:
        eval_df = st.session_state["eval_df"]

        st.markdown("**Per-series results**")
        st.table(eval_df.set_index(["series", "model"]))

        st.markdown("**Average error by model (lower is better)**")
        model_avg = eval_df.groupby("model")[["MAE", "RMSE", "MAPE"]].mean().round(2)
        st.table(model_avg)

        if "Naive" in model_avg.index:
            naive_mae = model_avg.loc["Naive", "MAE"]
            beat_baseline = model_avg.drop(index="Naive")[model_avg.drop(index="Naive")["MAE"] < naive_mae]
            if not beat_baseline.empty:
                st.success(
                    "Beats the Naive baseline on average MAE: " +
                    ", ".join(beat_baseline.index.tolist())
                )
            else:
                st.warning(
                    "No model currently beats the Naive 'same day last week' baseline on average MAE. "
                    "This usually means more historical data or feature tuning is needed."
                )

        st.download_button(
            label="Download Evaluation Report (Excel)",
            data=df_to_excel_bytes({"Model Evaluation": eval_df, "Average by Model": model_avg.reset_index()}),
            file_name=f"model_evaluation_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

# ════════════════════════════════════════════════════════
# PAGE: VIEW PREDICTIONS
# ════════════════════════════════════════════════════════
def page_view_predictions():
    st.markdown('<p class="page-title">View Predictions</p>', unsafe_allow_html=True)

    if not st.session_state.predictions:
        subtitle("Demand Forecast")
        st.divider()
        st.info("No predictions yet. Go to Prediction Model to generate forecasts.")
        return

    preds       = st.session_state.predictions
    summary     = get_prediction_summary(preds)
    n_days      = len(preds.get('dates', []))
    subtitle(f"{n_days}-Day Demand Forecast")
    st.divider()

    c1, c2, c3 = st.columns(3)
    for col, label, key in [
        (c1, f"Total Customers ({n_days} days)", "total_customers_next_week"),
        (c2, "Avg Daily Customers",       "avg_daily_customers"),
        (c3, "Items Forecasted",          "items_with_forecast"),
    ]:
        with col:
            st.markdown(f"""
            <div style="background:#ffffff;padding:20px;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,0.1);">
                <div style="color:#555555;font-size:0.75rem;font-weight:600;text-transform:uppercase;letter-spacing:1px;">{label}</div>
                <div style="color:#1a1a2e;font-size:2.2rem;font-weight:700;margin-top:8px;">{summary.get(key, 0)}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f'<p style="color:#1a1a2e;font-weight:600;font-size:0.95rem;">Model used: {summary.get("model_used","N/A")}</p>', unsafe_allow_html=True)
    st.divider()

    st.subheader("Customer Count Forecast")
    date_labels = pd.to_datetime(preds['dates']).strftime("%a %d %b").tolist()
    fig_line = go.Figure()
    fig_line.add_trace(go.Scatter(
        x=date_labels, y=preds['customer_forecast'],
        mode='lines+markers',
        line=dict(color='#1a1a2e', width=2),
        marker=dict(size=8, color='#1a1a2e'),
        fill='tozeroy', fillcolor='rgba(26,26,46,0.08)'
    ))
    fig_line.update_layout(
        height=300, plot_bgcolor='#ffffff', paper_bgcolor='#ffffff',
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
        xaxis=dict(
            title="Date",
            title_font=dict(size=14, color='#1a1a2e', family='Arial Black'),
            tickfont=dict(size=12, color='#1a1a2e', family='Arial'),
            showgrid=False,
            linecolor='#333333', linewidth=2,
        ),
        yaxis=dict(
            title="Predicted Customers",
            title_font=dict(size=14, color='#1a1a2e', family='Arial Black'),
            tickfont=dict(size=12, color='#1a1a2e', family='Arial'),
            gridcolor='#bbbbbb', gridwidth=1,
            linecolor='#333333', linewidth=2,
            showgrid=True,
        ),
    )
    st.plotly_chart(fig_line, use_container_width=True, config={"displayModeBar": False})

    st.subheader("Item-wise Demand Forecast")
    if preds.get("item_forecasts"):
        items         = list(preds["item_forecasts"].keys())
        selected_item = st.selectbox("Select Item", items)

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            x=date_labels,
            y=preds["item_forecasts"][selected_item],
            marker_color='#333366',
            text=preds["item_forecasts"][selected_item],
            textposition='outside',
            textfont=dict(size=12, color='#1a1a2e')
        ))
        fig_bar.update_layout(
            height=300, plot_bgcolor='#ffffff', paper_bgcolor='#ffffff',
            margin=dict(l=10, r=10, t=10, b=10),
            showlegend=False,
            xaxis=dict(
                title="Date",
                title_font=dict(size=14, color='#1a1a2e', family='Arial Black'),
                tickfont=dict(size=12, color='#1a1a2e', family='Arial'),
                showgrid=False,
                linecolor='#333333', linewidth=2,
            ),
            yaxis=dict(
                title="Predicted Units",
                title_font=dict(size=14, color='#1a1a2e', family='Arial Black'),
                tickfont=dict(size=12, color='#1a1a2e', family='Arial'),
                gridcolor='#bbbbbb', gridwidth=1,
                linecolor='#333333', linewidth=2,
                showgrid=True,
            ),
        )
        st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})

        st.subheader("All Items Summary")
        summary_data = []
        for item, forecast in preds["item_forecasts"].items():
            avg_d  = sum(forecast) / len(forecast)
            status = "High" if avg_d > 50 else "Medium" if avg_d > 20 else "Low"
            summary_data.append({"Item": item, "Avg Daily Demand": int(avg_d),
                                  "Total Weekly": sum(forecast), "Demand Level": status})
        
        summary_df = pd.DataFrame(summary_data)
        if not summary_df.empty:
            summary_df = summary_df.set_index('Item')
        st.table(summary_df)
    else:
        st.info("No item-wise predictions. Add more sales data.")

    st.divider()
    st.subheader("Saved Predictions (from Database)")
    saved_preds = get_predictions()
    if not saved_preds.empty:
        info_text(f"{len(saved_preds)} prediction rows currently stored in the database.")
        st.table(saved_preds.tail(20).set_index(saved_preds.columns[0]))
    else:
        info_text("No predictions saved yet - generate a forecast on the Prediction Model page.")

    st.divider()
    st.subheader("Download Forecast Report")
    forecast_df = pd.DataFrame({"Date": preds['dates'], "Predicted Customers": preds['customer_forecast']})
    item_rows   = [{"Date": d, "Item": item, "Predicted Quantity": q}
                   for item, forecast in preds.get("item_forecasts", {}).items()
                   for d, q in zip(preds['dates'], forecast)]
    items_df    = pd.DataFrame(item_rows) if item_rows else pd.DataFrame(columns=["Date","Item","Predicted Quantity"])
    st.download_button(
        label="Download Forecast Report (Excel)",
        data=df_to_excel_bytes({"Customer Forecast": forecast_df, "Item Forecasts": items_df}),
        file_name=f"forecast_report_{date.today()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

# ════════════════════════════════════════════════════════
# PAGE: INVENTORY REPORT
# ════════════════════════════════════════════════════════
def page_inventory_report():
    st.markdown('<p class="page-title">Inventory Report</p>', unsafe_allow_html=True)
    subtitle("Raw material suggestions based on predicted demand")
    st.divider()

    preds          = st.session_state.predictions
    inventory_rows = []

    if preds and preds.get("item_forecasts"):
        raw_material_map = {
            "Biryani":        ("Basmati Rice", 0.3),
            "Chicken Karahi": ("Chicken",      0.5),
            "Naan":           ("Flour",        0.1),
            "Seekh Kebab":    ("Minced Meat",  0.2),
            "Daal":           ("Lentils",      0.15),
            "Raita":          ("Yogurt",       0.1),
        }
        for item, forecast in preds["item_forecasts"].items():
            weekly_total = sum(forecast)
            raw, mult    = raw_material_map.get(item, (f"{item} ingredient", 0.2))
            inventory_rows.append({
                "Food Item": item, "Raw Material": raw,
                "Predicted Weekly Demand (units)": weekly_total,
                "Suggested Order (kg/L)": round(weekly_total * mult, 1),
            })

    if inventory_rows:
        inv_df = pd.DataFrame(inventory_rows)
        st.table(inv_df.set_index('Food Item'))

        st.subheader("Raw Material Orders Needed")
        fig_inv = go.Figure()
        for i, row in inv_df.iterrows():
            fig_inv.add_trace(go.Bar(
                name=row["Food Item"],
                x=[row["Raw Material"]],
                y=[row["Suggested Order (kg/L)"]],
                text=[row["Suggested Order (kg/L)"]],
                textposition='outside',
                textfont=dict(size=12, color='#1a1a2e')
            ))
        fig_inv.update_layout(
            height=350, plot_bgcolor='#ffffff', paper_bgcolor='#ffffff',
            margin=dict(l=10, r=10, t=10, b=10),
            barmode='group',
            legend=dict(font=dict(size=12, color='#1a1a2e')),
            xaxis=dict(
                title="Raw Material",
                title_font=dict(size=14, color='#1a1a2e', family='Arial Black'),
                tickfont=dict(size=12, color='#1a1a2e', family='Arial'),
                showgrid=False,
                linecolor='#333333', linewidth=2,
            ),
            yaxis=dict(
                title="Suggested Order (kg/L)",
                title_font=dict(size=14, color='#1a1a2e', family='Arial Black'),
                tickfont=dict(size=12, color='#1a1a2e', family='Arial'),
                gridcolor='#bbbbbb', gridwidth=1,
                linecolor='#333333', linewidth=2,
                showgrid=True,
            ),
        )
        st.plotly_chart(fig_inv, use_container_width=True, config={"displayModeBar": False})

        st.download_button(
            label="Download Inventory Report (Excel)",
            data=df_to_excel_bytes({"Inventory Suggestions": inv_df}),
            file_name=f"inventory_report_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    else:
        st.info("Run the Prediction Model first to get AI-based inventory suggestions.")
        st.table(pd.DataFrame({
            "Raw Material":   ["Basmati Rice", "Chicken", "Flour", "Cooking Oil", "Spices Mix"],
            "Current Stock":  ["50 kg", "15 kg", "100 kg", "25 L", "5 kg"],
            "Suggested Order":["75 kg", "45 kg", "120 kg", "30 L", "8 kg"],
            "Status":         ["Low", "Critical", "OK", "Reorder", "Critical"]
        }).set_index("Raw Material"))

    saved = get_inventory_suggestions()
    if not saved.empty:
        st.divider()
        st.subheader("Saved Suggestions (from DB)")
        st.table(saved.set_index(saved.columns[0]))

# ════════════════════════════════════════════════════════
# PAGE: MANAGE USERS  (Admin only)
# ════════════════════════════════════════════════════════
def page_manage_users():
    require_admin()
    st.markdown('<p class="page-title">Manage Users</p>', unsafe_allow_html=True)
    subtitle("View, update roles, and delete user accounts.")
    st.divider()

    users = get_all_users()
    if not users:
        st.info("No users found.")
        return

    current_user_id = st.session_state.user['user_id']

    st.subheader("All Users")
    
    users_df = pd.DataFrame([
        {"ID": u[0], "Username": u[1], "Full Name": u[2], "Email": u[3], "Role": u[4], "Created At": u[5]}
        for u in users
    ]).set_index('ID')
    st.table(users_df)

    st.divider()
    st.subheader("Update Role")
    usernames = [u[1] for u in users if u[0] != current_user_id]
    if usernames:
        target_user = st.selectbox("Select User", usernames)
        new_role    = st.selectbox("New Role", ["Admin", "Staff"])
        if st.button("Update Role"):
            update_user_role(next(u[0] for u in users if u[1] == target_user), new_role)
            st.success(f"Updated {target_user} to {new_role}")
            st.rerun()
    else:
        info_text("No other users to update.")

    st.divider()
    st.subheader("Delete User")
    del_usernames = [u[1] for u in users if u[0] != current_user_id]
    if del_usernames:
        del_target = st.selectbox("Select User to Delete", del_usernames, key="del_user")
        if st.button("Delete User", type="primary"):
            delete_user(next(u[0] for u in users if u[1] == del_target))
            st.success(f"Deleted user: {del_target}")
            st.rerun()
    else:
        info_text("No other users to delete.")

# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════
def show_main_app():
    show_sidebar()
    {
        "Dashboard":        page_dashboard,
        "Upload Dataset":   page_upload_dataset,
        "Data Entry":       page_data_entry,
        "Prediction Model": page_prediction_model,
        "View Predictions": page_view_predictions,
        "Inventory Report": page_inventory_report,
        "Manage Users":     page_manage_users,
    }.get(st.session_state.page, page_dashboard)()

if st.session_state.logged_in:
    show_main_app()
else:
    show_login()