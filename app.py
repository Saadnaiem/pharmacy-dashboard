from flask import Flask, render_template, request
import pandas as pd
from sqlalchemy import create_engine
import json
import calendar
import os
import psycopg2

app = Flask(__name__)

# Connect to Supabase/PostgreSQL using individual environment variables
def connect_to_database():
    conn = psycopg2.connect(
        host=os.environ['DB_HOST'],
        database=os.environ['DB_NAME'],
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASSWORD'],
        port=os.environ['DB_PORT'],
        sslmode='require'  # Enforce SSL connection
    )
    return conn

def load_data():
    """
    Loads data from the Supabase/PostgreSQL 'sales' table into a Pandas DataFrame.
    Performs initial data cleaning and transformation:
    - Converts 'INVOICEDATE' to datetime objects.
    - Fills NaN values in 'LOCATIONNAME' and 'PHARMACISTNAME' with 'Unknown'.
    - Formats 'PHAMACISTNAME' to show only the first two words.
    - Adjusts 'NETREVENUEAMOUNT' for return invoices ('-R' in INVOICENUMBER).
    Returns the DataFrame or None if an error occurs during connection/query.
    """
    try:
        conn = connect_to_database()
        query = """
        SELECT
            INVOICEDATE,
            INVOICENUMBER,
            LOCATIONNAME,
            PHARMACISTNAME,
            NETREVENUEAMOUNT
        FROM sales
        """
        df = pd.read_sql_query(query, conn)

        # Data Cleaning and Preprocessing
        df['INVOICEDATE'] = pd.to_datetime(df['INVOICEDATE'])
        df['LOCATIONNAME'] = df['LOCATIONNAME'].fillna('Unknown').astype(str)
        df['PHARMACISTNAME'] = df['PHARMACISTNAME'].fillna('Unknown').astype(str)
        # Keep only the first two words of the pharmacist's name, if not 'Unknown'
        df['PHARMACISTNAME'] = df['PHARMACISTNAME'].apply(
            lambda x: ' '.join(x.split()[:2]) if x != 'Unknown' else x
        )
        # Adjust Net Revenue Amount for return invoices (marked with '-R')
        mask = df['INVOICENUMBER'].str.contains('-R', na=False)
        df.loc[mask, 'NETREVENUEAMOUNT'] = -df.loc[mask, 'NETREVENUEAMOUNT']

        return df
    except Exception as e:
        # Log the error for debugging
        print(f"Error loading data: {e}")
        print("Please check your database connection settings and ensure your Supabase/PostgreSQL database is running and accessible.")
        # Optionally, log error to a file or monitoring service here
        return None

def get_active_pharmacists(df):
    """
    Identifies active pharmacists based on the filtered DataFrame.
    A pharmacist is considered active if they have worked at least 15 unique days
    in the selected period and are not in the exclusion list.
    """
    exclude = ['Saad Saad', 'Tamer Elmorsi']
    # Count unique days worked for each pharmacist in the current filtered period
    days_worked = df.groupby('PHARMACISTNAME')['INVOICEDATE'].nunique().reset_index()
    # Filter for pharmacists who worked >= 15 days and are not in the exclusion list
    active = days_worked[
        (days_worked['INVOICEDATE'] >= 15) & (~days_worked['PHARMACISTNAME'].isin(exclude))
    ]['PHARMACISTNAME'].unique()
    return active

def filter_data(df, months, locations, pharmacists):
    """
    Applies filters to the DataFrame based on selected months, locations, and pharmacists.
    """
    if months:
        df = df[df['INVOICEDATE'].dt.month.isin(months)]
    if locations:
        df = df[df['LOCATIONNAME'].isin(locations)]
    if pharmacists:
        df = df[df['PHARMACISTNAME'].isin(pharmacists)]
    return df

def format_k_m(value):
    """
    Formats a numeric value into a more readable 'K' (thousands) or 'M' (millions) string.
    Returns the original value if it cannot be converted to float.
    """
    try:
        value = float(value)
        if abs(value) >= 1_000_000:
            return f"{value/1_000_000:.2f}M"
        elif abs(value) >= 1_000:
            return f"{value/1_000:.2f}K"
        else:
            # Format integers without decimal if they are whole numbers, otherwise two decimals
            return f"{value:.0f}" if value == int(value) else f"{value:.2f}"
    except (ValueError, TypeError):
        return value # Return original value if conversion fails

@app.route('/', methods=['GET', 'POST'])
def dashboard():
    df = load_data()
    if df is None:
        # Provide safe defaults for all required template variables
        all_months = list(range(1, 13))
        month_names = [calendar.month_name[m] for m in all_months]
        month_map = dict(zip(month_names, all_months))
        return render_template(
            'index.html',
            error="Failed to load data from Supabase/PostgreSQL. Please check your database connection settings.",
            years=[],
            selected_years=[],
            months=month_names,
            month_map=month_map,
            locations=[],
            pharmacists=[],
            selected_months=[],
            selected_locations=[],
            selected_pharmacists=[],
            total_active=0,
            total_net_sales=0,
            total_invoices=0,
            top_day='-',
            top_day_val=0,
            top_day_inv='-',
            top_day_inv_val=0,
            top_pharmacist='-',
            top_pharmacist_val=0,
            top_pharmacist_inv='-',
            top_pharmacist_inv_val=0,
            top_invoice_val=0,
            top_invoice_num='-',
            top_invoice_pharmacist='-',
            avg_daily_sales=0,
            avg_daily_tx=0
        )

    # --- Initialize filter options from the full dataset ---
    # All available months (1-12) for filter display
    all_months = list(range(1, 13))
    month_names = [calendar.month_name[m] for m in all_months]
    month_map = dict(zip(month_names, all_months)) # Map month names to numbers for form processing

    # All unique years present in the dataset
    all_years = sorted([int(y) for y in df['INVOICEDATE'].dt.year.dropna().unique()])
    # All unique pharmacists from the full dataset
    all_pharmacists = sorted(df['PHARMACISTNAME'].unique().tolist())
    # All unique locations from the full dataset
    all_locations = sorted(df['LOCATIONNAME'].unique().tolist())

    # --- Determine selected filter values from form submission or set defaults ---
    selected_years = all_years
    selected_months = all_months
    selected_locations = all_locations
    selected_pharmacists = all_pharmacists

    if request.method == 'POST':
        # Process selected years
        years_form = request.form.getlist('years')
        selected_years = ([int(y) for y in years_form]
                          if years_form and 'all' not in years_form else all_years)

        # Process selected months
        months_form = request.form.getlist('months')
        selected_months = ([int(m) for m in months_form]
                           if months_form and 'all' not in months_form else all_months)

        # Process selected locations
        locations_form = request.form.getlist('locations')
        selected_locations = ([str(l) for l in locations_form]
                              if locations_form and 'all' not in locations_form else all_locations)

        # Process selected pharmacists
        pharmacists_form = request.form.getlist('pharmacists')
        selected_pharmacists = ([str(p) for p in pharmacists_form]
                                if pharmacists_form and 'all' not in pharmacists_form else all_pharmacists)

    # --- Apply initial year filter to the DataFrame ---
    # This ensures subsequent filters and calculations are only on selected years.
    df_filtered_by_year = df[df['INVOICEDATE'].dt.year.isin(selected_years)]

    # --- Apply remaining filters to get the final filtered dataset ---
    filtered_data = filter_data(df_filtered_by_year, selected_months,
                                 selected_locations, selected_pharmacists)

    # --- Calculate Metrics ---
    # Calculate active pharmacists for the *currently filtered* period
    active_in_period = get_active_pharmacists(filtered_data)
    total_active = len(active_in_period)

    # Exclude Fridays for daily metrics (if needed, but not used in final metrics below)
    # filtered_no_friday = filtered_data[~filtered_data['INVOICEDATE'].dt.dayofweek.eq(4)]

    # Total Net Sales
    total_net_sales = filtered_data['NETREVENUEAMOUNT'].sum() if not filtered_data.empty else 0

    # Total Net Invoices (unique invoice numbers)
    total_net_invoices = filtered_data['INVOICENUMBER'].nunique() if not filtered_data.empty else 0

    # Average Daily Sales = sum(NETREVENUEAMOUNT) / count of unique days in selected period
    avg_daily_sales = 0
    avg_daily_tx = 0
    if not filtered_data.empty:
        unique_days = filtered_data['INVOICEDATE'].dt.date.nunique()
        total_sales = filtered_data['NETREVENUEAMOUNT'].sum()
        total_invoices = filtered_data['INVOICENUMBER'].nunique()
        if unique_days > 0:
            avg_daily_sales = total_sales / unique_days
            avg_daily_tx = total_invoices / unique_days
        else:
            avg_daily_sales = 0
            avg_daily_tx = 0

    # Top Day Sales (day with highest net sales, even if negative or zero)
    top_day, top_day_val = '-', 0
    # Debug printout for top day sales
    if not filtered_data.empty:
        daily_sales_sum = filtered_data.groupby(filtered_data['INVOICEDATE'].dt.date)['NETREVENUEAMOUNT'].sum()
        if not daily_sales_sum.empty:
            top_day_date = daily_sales_sum.idxmax()
            top_day_val = daily_sales_sum.max()
            top_day = pd.to_datetime(top_day_date).strftime('%d-%m-%Y')
            top_day_val = daily_sales_sum.max()
        else:
            top_day, top_day_val = '-', 0

    # Top Day Invoices
    top_day_inv, top_day_inv_val = '-', 0
    if not filtered_data.empty:
        daily_invoices_count = filtered_data.groupby(filtered_data['INVOICEDATE'].dt.date)['INVOICENUMBER'].nunique()
        if not daily_invoices_count.empty:
            top_day_inv_date = daily_invoices_count.idxmax()
            top_day_inv = pd.to_datetime(top_day_inv_date).strftime('%d-%m-%Y')
            top_day_inv_val = daily_invoices_count.max()

    # Top Pharmacist Sales
    top_pharmacist, top_pharmacist_val = '-', 0
    if not filtered_data.empty:
        pharmacist_sales = filtered_data.groupby('PHARMACISTNAME')['NETREVENUEAMOUNT'].sum()
        if not pharmacist_sales.empty:
            top_pharmacist = pharmacist_sales.idxmax()
            top_pharmacist_val = pharmacist_sales.max()

    # Top Pharmacist Invoices
    top_pharmacist_inv, top_pharmacist_inv_val = '-', 0
    if not filtered_data.empty:
        pharmacist_invoices = filtered_data.groupby('PHARMACISTNAME')['INVOICENUMBER'].nunique()
        if not pharmacist_invoices.empty:
            top_pharmacist_inv = pharmacist_invoices.idxmax()
            top_pharmacist_inv_val = pharmacist_invoices.max()

    # Top Invoice Value (the single invoice with the highest positive NETREVENUEAMOUNT)
    top_invoice_val, top_invoice_num, top_invoice_pharmacist = 0, 'N/A', 'N/A'
    if not filtered_data.empty and not filtered_data['NETREVENUEAMOUNT'].empty:
        # Ensure we only consider positive amounts for "top invoice value"
        positive_invoices = filtered_data[filtered_data['NETREVENUEAMOUNT'] > 0]
        if not positive_invoices.empty:
            # Use idxmax() only if the series is not empty
            top_invoice_row = positive_invoices.loc[positive_invoices['NETREVENUEAMOUNT'].idxmax()]
            top_invoice_val = top_invoice_row['NETREVENUEAMOUNT']
            top_invoice_num = top_invoice_row['INVOICENUMBER']
            top_invoice_pharmacist = top_invoice_row['PHARMACISTNAME']

    # Print total NETREVENUEAMOUNT for 24-05-2025 in terminal
    if not filtered_data.empty:
        date_to_check = pd.to_datetime('2025-05-24').date()
        total_net_for_day = filtered_data[filtered_data['INVOICEDATE'].dt.date == date_to_check]['NETREVENUEAMOUNT'].sum()
        # print(f"[DEBUG] NETREVENUEAMOUNT for 24-05-2025: {total_net_for_day}")

    # --- Render the template with all calculated metrics and filter options ---
    return render_template('index.html',
        # Filter options for the template
        years=all_years,
        selected_years=selected_years,
        months=month_names,
        month_map=month_map, # Used to convert month names back to numbers on POST
        locations=all_locations, # Use all_locations for filter options
        pharmacists=all_pharmacists, # Use all_pharmacists for filter options
        selected_months=selected_months,
        selected_locations=selected_locations,
        selected_pharmacists=selected_pharmacists,

        # Metrics for display
        total_active=total_active,
        total_net_sales=format_k_m(total_net_sales),
        total_invoices=format_k_m(total_net_invoices),
        avg_daily_sales=format_k_m(avg_daily_sales),
        avg_daily_tx=format_k_m(avg_daily_tx),
        top_day=top_day,
        top_day_val=format_k_m(top_day_val),
        top_day_inv=top_day_inv,
        top_day_inv_val=format_k_m(top_day_inv_val),
        top_pharmacist=top_pharmacist,
        top_pharmacist_val=format_k_m(top_pharmacist_val),
        top_pharmacist_inv=top_pharmacist_inv,
        top_pharmacist_inv_val=format_k_m(top_pharmacist_inv_val),
        top_invoice_val=format_k_m(top_invoice_val),
        top_invoice_num=top_invoice_num,
        top_invoice_pharmacist=top_invoice_pharmacist,
    )

if __name__ == '__main__':
    app.run(debug=True)
