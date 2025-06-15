import pandas as pd
from sqlalchemy import create_engine
import os

# Use environment variables for DB config in production
DB_CONFIG = {
    'driver': os.environ.get('DB_DRIVER', 'ODBC Driver 17 for SQL Server'),
    'server': os.environ.get('DB_SERVER', 'localhost'),
    'database': os.environ.get('DB_NAME', 'DashboardDB'),
    'trusted_connection': os.environ.get('DB_TRUSTED', 'yes')
}

def get_sqlalchemy_connection_string():
    user = os.environ.get('DB_USER')
    password = os.environ.get('DB_PASSWORD')
    if user and password:
        return (
            f"mssql+pyodbc://{user}:{password}@{DB_CONFIG['server']}/{DB_CONFIG['database']}"
            f"?driver={DB_CONFIG['driver'].replace(' ', '+')}"
        )
    else:
        return (
            f"mssql+pyodbc://@{DB_CONFIG['server']}/{DB_CONFIG['database']}"
            f"?driver={DB_CONFIG['driver'].replace(' ', '+')}"
            f"&trusted_connection={DB_CONFIG['trusted_connection']}"
        )

def load_data():
    conn_str = get_sqlalchemy_connection_string()
    try:
        engine = create_engine(conn_str)
        query = """
        SELECT
            INVOICEDATE,
            INVOICENUMBER,
            LOCATIONNAME,
            PHAMACISTNAME,
            NETREVENUEAMOUNT
        FROM Dashboard
        """
        df = pd.read_sql_query(query, engine)
        return df
    except Exception as e:
        print(f"Error loading data: {e}\nCheck your DB_CONFIG settings and ensure the SQL Server is running and accessible.")
        return None

df = load_data()
if df is not None:
    print("Data loaded successfully.")
    print(df.head())
    print(f"Number of rows in DataFrame: {len(df)}")
    # Show the invoice with the highest NETREVENUEAMOUNT
    idx = df['NETREVENUEAMOUNT'].idxmax()
    print("Invoice with highest NETREVENUEAMOUNT:")
    print(df.loc[idx])
else:
    print("Failed to load data.")
