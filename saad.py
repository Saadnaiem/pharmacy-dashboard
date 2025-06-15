import pandas as pd
from sqlalchemy import create_engine

# Database configuration for Windows Authentication
DB_CONFIG = {
    'driver': 'ODBC Driver 17 for SQL Server', # No curly braces for SQLAlchemy
    'server': 'DESKTOP-VOD4J60\SQLEXPRESS01',  # Change to your actual server name or instance
    'database': 'DashboardDB',
    'trusted_connection': 'yes'
}

def get_sqlalchemy_connection_string():
    # SQLAlchemy connection string for Windows Authentication
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
