from flask import Flask, render_template, request
import pandas as pd
import plotly
import plotly.express as px
import json
import calendar
import os

app = Flask(__name__)

# Load and preprocess data
def load_data():
    df = pd.read_excel(os.path.join('data', 'sales.xlsx'))
    df['INVOICEDATE'] = pd.to_datetime(df['INVOICEDATE'])
    df['LOCATIONNAME'] = df['LOCATIONNAME'].fillna('Unknown').astype(str)
    df['PHAMACISTNAME'] = df['PHAMACISTNAME'].fillna('Unknown').astype(str)
    # Only keep first and second name
    df['PHAMACISTNAME'] = df['PHAMACISTNAME'].apply(lambda x: ' '.join(x.split()[:2]) if x != 'Unknown' else x)
    df['IS_RETURN'] = df['INVOICENUMBER'].astype(str).str.contains('-R-')
    return df

def get_active_pharmacists(df):
    exclude = ['Saad Saad', 'Tamer Elmorsi']
    # Count unique days worked in the selected period (not per month)
    days_worked = df.groupby('PHAMACISTNAME')['INVOICEDATE'].nunique().reset_index()
    # Exclude those who worked less than 15 days
    active = days_worked[(days_worked['INVOICEDATE'] >= 15) & (~days_worked['PHAMACISTNAME'].isin(exclude))]['PHAMACISTNAME'].unique()
    return active

def filter_data(df, months, locations, pharmacists):
    if months:
        df = df[df['INVOICEDATE'].dt.month.isin(months)]
    if locations:
        df = df[df['LOCATIONNAME'].isin(locations)]
    if pharmacists:
        df = df[df['PHAMACISTNAME'].isin(pharmacists)]
    return df

def format_k_m(value):
    try:
        value = float(value)
        if abs(value) >= 1_000_000:
            return f"{value/1_000_000:.2f}M"
        elif abs(value) >= 1_000:
            return f"{value/1_000:.2f}K"
        else:
            return f"{value:.0f}"
    except:
        return value

@app.route('/', methods=['GET', 'POST'])
def dashboard():
    df = load_data()
    years = sorted(df['INVOICEDATE'].dt.year.unique())
    months = sorted(df['INVOICEDATE'].dt.month.unique())
    month_names = [calendar.month_name[m] for m in months]
    month_map = dict(zip(month_names, months))
    locations = sorted([str(l) for l in df['LOCATIONNAME'].unique()])
    pharmacists = sorted([str(p) for p in df['PHAMACISTNAME'].unique()])

    # Default filter values
    selected_years = years
    selected_months = months
    selected_locations = locations
    selected_pharmacists = pharmacists

    if request.method == 'POST':
        years_form = request.form.getlist('years')
        selected_years = years if 'all' in years_form else [int(y) for y in years_form] if years_form else years
        months_form = request.form.getlist('months')
        selected_months = months if 'all' in months_form else [int(m) for m in months_form] if months_form else months
        locations_form = request.form.getlist('locations')
        selected_locations = locations if 'all' in locations_form else locations_form if locations_form else locations
        pharmacists_form = request.form.getlist('pharmacists')
        selected_pharmacists = pharmacists if 'all' in pharmacists_form else pharmacists_form if pharmacists_form else pharmacists

    # Filter by year
    df = df[df['INVOICEDATE'].dt.year.isin(selected_years)]
    filtered = filter_data(df, selected_months, selected_locations, selected_pharmacists)

    # Calculate active pharmacists for the selected period
    active_in_period = get_active_pharmacists(filtered)
    total_active = len(active_in_period)

    # Average daily sales: use all filtered data (all pharmacists)
    filtered_no_friday_all = filtered[~filtered['INVOICEDATE'].dt.dayofweek.eq(4)]
    if not filtered_no_friday_all.empty and 'NETREVENUEAMOUNT' in filtered_no_friday_all.columns:
        avg_daily_sales = filtered_no_friday_all[~filtered_no_friday_all['IS_RETURN']].groupby('INVOICEDATE')['NETREVENUEAMOUNT'].sum().mean()
    else:
        avg_daily_sales = 0

    # Average daily transactions: use only active pharmacists
    filtered_active = filtered[filtered['PHAMACISTNAME'].isin(active_in_period)]
    filtered_no_friday_active = filtered_active[~filtered_active['INVOICEDATE'].dt.dayofweek.eq(4)]
    if not filtered_no_friday_active.empty and 'INVOICENUMBER' in filtered_no_friday_active.columns:
        avg_daily_tx = filtered_no_friday_active[~filtered_no_friday_active['IS_RETURN']].groupby('INVOICEDATE')['INVOICENUMBER'].nunique().mean()
    else:
        avg_daily_tx = 0

    # Calculate Total Net Sales and Total Net Invoices
    total_net_sales = filtered['NETREVENUEAMOUNT'].sum()
    total_net_invoices = filtered[~filtered['INVOICENUMBER'].str.contains('-R-')]['INVOICENUMBER'].nunique()

    # By pharmacist
    net_sales_by_pharmacist = filtered.groupby('PHAMACISTNAME')['NETREVENUEAMOUNT'].sum()
    net_invoices_by_pharmacist = filtered[~filtered['INVOICENUMBER'].str.contains('-R-')].groupby('PHAMACISTNAME')['INVOICENUMBER'].nunique()

    # By day
    net_sales_by_day = filtered.groupby('INVOICEDATE')['NETREVENUEAMOUNT'].sum()
    net_invoices_by_day = filtered[~filtered['INVOICENUMBER'].str.contains('-R-')].groupby('INVOICEDATE')['INVOICENUMBER'].nunique()

    # By month
    filtered['Month'] = filtered['INVOICEDATE'].dt.to_period('M').astype(str)
    net_sales_by_month = filtered.groupby('Month')['NETREVENUEAMOUNT'].sum()
    net_invoices_by_month = filtered[~filtered['INVOICENUMBER'].str.contains('-R-')].groupby('Month')['INVOICENUMBER'].nunique()

    # All other metrics use all pharmacists' data (filtered)
    total_invoices = filtered[~filtered['INVOICENUMBER'].str.contains('-R-')]['INVOICENUMBER'].nunique()
    total_return_invoices = filtered[filtered['IS_RETURN']]['INVOICENUMBER'].nunique()
    day_sales = filtered[~filtered['IS_RETURN']].groupby('INVOICEDATE')['NETREVENUEAMOUNT'].sum()
    if not day_sales.empty:
        top_day = day_sales.idxmax().strftime('%d-%m-%Y')
        top_day_val = day_sales.max()
    else:
        top_day, top_day_val = '-', 0
    day_invoices = filtered[~filtered['IS_RETURN']].groupby('INVOICEDATE')['INVOICENUMBER'].nunique()
    if not day_invoices.empty:
        top_day_inv = day_invoices.idxmax().strftime('%d-%m-%Y')
        top_day_inv_val = day_invoices.max()
    else:
        top_day_inv, top_day_inv_val = '-', 0
    if not net_sales_by_pharmacist.empty:
        top_pharmacist = net_sales_by_pharmacist.idxmax()
        top_pharmacist_val = net_sales_by_pharmacist.max()
    else:
        top_pharmacist, top_pharmacist_val = '-', 0
    pharmacist_invoices = filtered[~filtered['IS_RETURN']].groupby('PHAMACISTNAME')['INVOICENUMBER'].nunique()
    if not pharmacist_invoices.empty:
        top_pharmacist_inv = pharmacist_invoices.idxmax()
        top_pharmacist_inv_val = pharmacist_invoices.max()
    else:
        top_pharmacist_inv, top_pharmacist_inv_val = '-', 0
    if not filtered[~filtered['IS_RETURN']].empty:
        top_invoice = filtered[~filtered['IS_RETURN']].loc[filtered[~filtered['IS_RETURN']]['NETREVENUEAMOUNT'].idxmax()]
        top_invoice_val = top_invoice['NETREVENUEAMOUNT']
        top_invoice_num = top_invoice['INVOICENUMBER']
        top_invoice_pharmacist = top_invoice['PHAMACISTNAME']
    else:
        top_invoice_val, top_invoice_num, top_invoice_pharmacist = 0, '', ''
    # Average daily sales (exclude Fridays, only active pharmacists)
    filtered_no_friday = filtered[~filtered['INVOICEDATE'].dt.dayofweek.eq(4)]
    filtered_no_friday = filtered_no_friday[filtered_no_friday['PHAMACISTNAME'].isin(active_in_period)]
    if not filtered_no_friday.empty and 'NETREVENUEAMOUNT' in filtered_no_friday.columns:
        avg_daily_sales = filtered_no_friday[~filtered_no_friday['IS_RETURN']].groupby('INVOICEDATE')['NETREVENUEAMOUNT'].sum().mean()
    else:
        avg_daily_sales = 0
    if not filtered_no_friday.empty and 'INVOICENUMBER' in filtered_no_friday.columns:
        avg_daily_tx = filtered_no_friday[~filtered_no_friday['IS_RETURN']].groupby('INVOICEDATE')['INVOICENUMBER'].nunique().mean()
    else:
        avg_daily_tx = 0

    # Bar chart: sales by month (default)
    filtered['Month'] = filtered['INVOICEDATE'].dt.to_period('M').astype(str)
    sales_time = filtered[~filtered['IS_RETURN']].groupby('Month')['NETREVENUEAMOUNT'].sum().reset_index()
    fig = px.bar(sales_time, x='Month', y='NETREVENUEAMOUNT', title='Monthly Sales')
    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    # Use net values for all card metrics
    # Top day sales (net)
    net_sales_by_day = filtered.groupby('INVOICEDATE')['NETREVENUEAMOUNT'].sum()
    if not net_sales_by_day.empty:
        top_day_date = net_sales_by_day.idxmax()
        top_day = top_day_date.strftime('%d-%m-%Y')
        top_day_weekday = top_day_date.strftime('%A')
        top_day_val = net_sales_by_day.max()
    else:
        top_day, top_day_weekday, top_day_val = '-', '-', 0
    # Top day invoices (net)
    net_invoices_by_day = filtered[~filtered['INVOICENUMBER'].str.contains('-R-')].groupby('INVOICEDATE')['INVOICENUMBER'].nunique()
    if not net_invoices_by_day.empty:
        top_day_inv_date = net_invoices_by_day.idxmax()
        top_day_inv = top_day_inv_date.strftime('%d-%m-%Y')
        top_day_inv_weekday = top_day_inv_date.strftime('%A')
        top_day_inv_val = net_invoices_by_day.max()
    else:
        top_day_inv, top_day_inv_weekday, top_day_inv_val = '-', '-', 0
    # Top pharmacist sales (net)
    if not net_sales_by_pharmacist.empty:
        top_pharmacist = net_sales_by_pharmacist.idxmax()
        top_pharmacist_val = net_sales_by_pharmacist.max()
    else:
        top_pharmacist, top_pharmacist_val = '-', 0
    # Top pharmacist invoices (net)
    if not net_invoices_by_pharmacist.empty:
        top_pharmacist_inv = net_invoices_by_pharmacist.idxmax()
        top_pharmacist_inv_val = net_invoices_by_pharmacist.max()
    else:
        top_pharmacist_inv, top_pharmacist_inv_val = '-', 0
    # Top invoice value (net, not return)
    if not filtered[~filtered['INVOICENUMBER'].str.contains('-R-')].empty:
        top_invoice = filtered[~filtered['INVOICENUMBER'].str.contains('-R-')].loc[filtered[~filtered['INVOICENUMBER'].str.contains('-R-')]['NETREVENUEAMOUNT'].idxmax()]
        top_invoice_val = top_invoice['NETREVENUEAMOUNT']
        top_invoice_num = top_invoice['INVOICENUMBER']
        top_invoice_pharmacist = top_invoice['PHAMACISTNAME']
    else:
        top_invoice_val, top_invoice_num, top_invoice_pharmacist = 0, '', ''

    return render_template('index.html',
        years=years,
        selected_years=selected_years,
        months=month_names,
        month_map=month_map,
        locations=locations,
        pharmacists=pharmacists,
        selected_months=selected_months,
        selected_locations=selected_locations,
        selected_pharmacists=selected_pharmacists,
        total_active=total_active,
        total_net_sales=format_k_m(total_net_sales),
        total_invoices=format_k_m(total_net_invoices),
        total_return_invoices=format_k_m(total_return_invoices),
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
        avg_daily_sales=format_k_m(avg_daily_sales),
        avg_daily_tx=format_k_m(avg_daily_tx),
        graphJSON=graphJSON,
        top_day_weekday=top_day_weekday,
        top_day_inv_weekday=top_day_inv_weekday
    )

#if __name__ == '__main__':
    app.run(debug=True)
