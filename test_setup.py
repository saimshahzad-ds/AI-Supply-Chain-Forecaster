# test_setup.py
import streamlit as st
import pandas as pd
import numpy as np
import sklearn
import xgboost
import plotly
import bcrypt
import sqlite3
import openpyxl

print("✅ All imports successful!")
print(f"Python version: {__import__('sys').version}")
print(f"Streamlit version: {st.__version__}")
print(f"Pandas version: {pd.__version__}")
print(f"NumPy version: {np.__version__}")
print(f"Scikit-learn version: {sklearn.__version__}")
print(f"XGBoost version: {xgboost.__version__}")