# AI-Driven Forecasting for Food Supply Chain Management

## Steps to Run

1. Create and activate virtual environment (Python 3.10 recommended)
python -m venv my_env
my_env\Scripts\activate

2. Upgrade pip and install dependencies
python -m pip install --upgrade pip
pip install streamlit
pip install plotly
pip install xgboost
pip install statsmodels
pip install tensorflow-cpu
pip install openpyxl
pip install bcrypt

3. Initialize the database (Required on first run to build tables)
python database/init_db.py

4. Run the application
streamlit run app.py

## Access the Application

* Open your web browser and navigate to: http://localhost:8501
* The system automatically creates a master admin account on the first run:
  * Username: Admin
  * Password: Admin123

(Standard Staff accounts can be created later using the "Sign Up" tab).

---
Troubleshooting: If the installation fails, verify that you are using Python 3.10 and that your virtual environment is actively running before executing the pip install command.