import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
from zoneinfo import ZoneInfo
import threading
import queue
import logging

# ----------------------
# Configuration Constants
# ----------------------
REFRESH_INTERVAL = 10  # Seconds between updates
MAX_ROWS = 500  # Cap for in-memory rows

# Store previous prices for percentage calculation
previous_prices = {}
# Store alerts for each stock
stock_alerts = {}
# Store alert trigger state for each stock and alert type
alert_triggered = {}
# Store all displayed data
export_data = []
# Initialize tracking list
stock_symbols = []
symbols_lock = threading.Lock()
stop_event = threading.Event()

# GUI update queue for thread safety
gui_queue = queue.Queue()

def get_stock_price(symbol):
    """Fetch current stock price using Yahoo Finance"""
    try:
        stock = yf.Ticker(symbol)
        price = stock.history(period="1d", prepost=True)["Close"].iloc[-1]
        return price
    except Exception as e:
        logging.exception("Error in get_stock_price")
        return None

def calculate_percentage_change(symbol, current_price):
    """Calculate percentage change from previous price"""
    if symbol in previous_prices:
        previous_price = previous_prices[symbol]
        if previous_price != 0:  # Avoid division by zero
            percentage_change = ((current_price - previous_price) / previous_price) * 100
            return percentage_change
    return None

def check_alerts(symbol, current_price, percentage_change):
    """Check if any alerts should be triggered"""
    if symbol not in stock_alerts:
        return []
    alerts = stock_alerts[symbol]
    triggered = alert_triggered.setdefault(symbol, {
        'price_high': {},
        'price_low': {},
        'percent_high': {},
        'percent_low': {}
    })
    messages = []
    
    # Price Above
    for val in alerts['price_high']:
        if not triggered['price_high'].get(val, False) and current_price >= val:
            messages.append(f"Price above {val}")
            triggered['price_high'][val] = True
        elif triggered['price_high'].get(val, False) and current_price < val:
            triggered['price_high'][val] = False
            
    # Price Below
    for val in alerts['price_low']:
        if not triggered['price_low'].get(val, False) and current_price <= val:
            messages.append(f"Price below {val}")
            triggered['price_low'][val] = True
        elif triggered['price_low'].get(val, False) and current_price > val:
            triggered['price_low'][val] = False
            
    # Percent Above
    for val in alerts['percent_high']:
        if not triggered['percent_high'].get(val, False) and percentage_change is not None and percentage_change >= val:
            messages.append(f"Percentage change above {val}%")
            triggered['percent_high'][val] = True
        elif triggered['percent_high'].get(val, False) and percentage_change is not None and percentage_change < val:
            triggered['percent_high'][val] = False
            
    # Percent Below
    for val in alerts['percent_low']:
        if not triggered['percent_low'].get(val, False) and percentage_change is not None and percentage_change <= val:
            messages.append(f"Percentage change below {val}%")
            triggered['percent_low'][val] = True
        elif triggered['percent_low'].get(val, False) and percentage_change is not None and percentage_change > val:
            triggered['percent_low'][val] = False
            
    return messages

def monitor_stock_prices():
    """Background thread for price updates"""
    while not stop_event.is_set():
        if stock_symbols:
            try:
                data = yf.download(stock_symbols, period="1d", interval="1m", progress=False, threads=False, timeout=5)
                last_row = data['Close'].iloc[-1] if not data['Close'].empty else {}
                
                for symbol in stock_symbols:
                    price = last_row[symbol] if symbol in last_row else None
                    if price is None or pd.isna(price):
                        continue
                        
                    percentage_change = calculate_percentage_change(symbol, price)
                    alert_msgs = check_alerts(symbol, price, percentage_change)
                    
                    if alert_msgs:
                        for msg in alert_msgs:
                            st.toast(f"{symbol}: {msg}")
                            
                    previous_prices[symbol] = price
                    export_data.append({
                        'Time': datetime.now(ZoneInfo('America/New_York')).strftime("%Y-%m-%d %H:%M:%S"),
                        'Symbol': symbol,
                        'Price': price,
                        '% Change': percentage_change,
                        'Price Above': stock_alerts[symbol]['price_high'][:],
                        'Price Below': stock_alerts[symbol]['price_low'][:],
                        '% Above': stock_alerts[symbol]['percent_high'][:],
                        '% Below': stock_alerts[symbol]['percent_low'][:]
                    })
                    
                    # Cap export_data
                    if len(export_data) > MAX_ROWS:
                        export_data[:] = export_data[-MAX_ROWS:]
                        
            except Exception as e:
                logging.exception("Error in monitor_stock_prices")
                
        time.sleep(REFRESH_INTERVAL)

def create_price_chart(symbol):
    """Create an interactive price chart using Plotly"""
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="1d", interval="1m")
        
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=hist.index,
            open=hist['Open'],
            high=hist['High'],
            low=hist['Low'],
            close=hist['Close'],
            name='Price'
        ))
        
        # Add alert lines if they exist
        if symbol in stock_alerts:
            for price in stock_alerts[symbol]['price_high']:
                fig.add_hline(y=price, line_dash="dash", line_color="green",
                            annotation_text=f"Alert Above: {price}")
            for price in stock_alerts[symbol]['price_low']:
                fig.add_hline(y=price, line_dash="dash", line_color="red",
                            annotation_text=f"Alert Below: {price}")
        
        fig.update_layout(
            title=f"{symbol} Price Chart",
            yaxis_title="Price",
            xaxis_title="Time",
            template="plotly_dark"
        )
        
        return fig
    except Exception as e:
        logging.exception("Error creating price chart")
        return None

def main():
    st.set_page_config(
        page_title="Tracker Dashboard",
        page_icon="📈",
        layout="wide"
    )
    
    st.title("📈 Tracker Dashboard")
    
    # Sidebar for stock management
    with st.sidebar:
        st.header("Material Management")
        
        # Add new stock
        new_symbol = st.text_input("Add Stock Symbol", key="new_stock").strip().upper()
        if st.button("Add Stock"):
            if new_symbol and new_symbol not in stock_symbols:
                test_price = get_stock_price(new_symbol)
                if test_price is not None:
                    stock_symbols.append(new_symbol)
                    stock_alerts[new_symbol] = {
                        'price_high': [],
                        'price_low': [],
                        'percent_high': [],
                        'percent_low': []
                    }
                    alert_triggered[new_symbol] = {
                        'price_high': {},
                        'price_low': {},
                        'percent_high': {},
                        'percent_low': {}
                    }
                    st.success(f"Added {new_symbol}")
                else:
                    st.error(f"Invalid symbol: {new_symbol}")
            elif new_symbol in stock_symbols:
                st.warning(f"{new_symbol} is already being tracked")
        
        # Stock selection
        if stock_symbols:
            selected_stock = st.selectbox("Select Stock", stock_symbols)
            
            # Alert management
            st.subheader("Alert Management")
            
            # Price alerts
            col1, col2 = st.columns(2)
            with col1:
                price_above = st.number_input("Price Above", key="price_above")
                if st.button("Set Price Above Alert"):
                    if price_above not in stock_alerts[selected_stock]['price_high']:
                        stock_alerts[selected_stock]['price_high'].append(price_above)
                        alert_triggered[selected_stock]['price_high'][price_above] = False
                        st.success(f"Price Above alert set at {price_above}")
            
            with col2:
                price_below = st.number_input("Price Below", key="price_below")
                if st.button("Set Price Below Alert"):
                    if price_below not in stock_alerts[selected_stock]['price_low']:
                        stock_alerts[selected_stock]['price_low'].append(price_below)
                        alert_triggered[selected_stock]['price_low'][price_below] = False
                        st.success(f"Price Below alert set at {price_below}")
            
            # Percentage alerts
            col3, col4 = st.columns(2)
            with col3:
                percent_above = st.number_input("Percent Above", key="percent_above")
                if st.button("Set Percent Above Alert"):
                    if percent_above not in stock_alerts[selected_stock]['percent_high']:
                        stock_alerts[selected_stock]['percent_high'].append(percent_above)
                        alert_triggered[selected_stock]['percent_high'][percent_above] = False
                        st.success(f"Percent Above alert set at {percent_above}%")
            
            with col4:
                percent_below = st.number_input("Percent Below", key="percent_below")
                if st.button("Set Percent Below Alert"):
                    if percent_below not in stock_alerts[selected_stock]['percent_low']:
                        stock_alerts[selected_stock]['percent_low'].append(percent_below)
                        alert_triggered[selected_stock]['percent_low'][percent_below] = False
                        st.success(f"Percent Below alert set at {percent_below}%")
            
            # Display current alerts
            st.subheader("Current Alerts")
            alerts = stock_alerts[selected_stock]
            for alert_type, values in alerts.items():
                if values:
                    st.write(f"{alert_type.replace('_', ' ').title()}: {', '.join(map(str, values))}")
            
            # Delete alerts
            if any(alerts.values()):
                alert_to_delete = st.selectbox(
                    "Select Alert to Delete",
                    [f"{k}: {v}" for k, v in alerts.items() if v]
                )
                if st.button("Delete Alert"):
                    alert_type, value = alert_to_delete.split(": ")
                    alert_type = alert_type.lower().replace(" ", "_")
                    value = float(value)
                    if value in stock_alerts[selected_stock][alert_type]:
                        stock_alerts[selected_stock][alert_type].remove(value)
                        alert_triggered[selected_stock][alert_type].pop(value, None)
                        st.success(f"Deleted {alert_type} alert at {value}")
    
    # Main content area
    if stock_symbols:
        # Create tabs for different views
        tab1, tab2, tab3 = st.tabs(["Price Charts", "Data Table", "Export"])
        
        with tab1:
            # Display price charts in a grid
            cols = st.columns(min(3, len(stock_symbols)))
            for idx, symbol in enumerate(stock_symbols):
                with cols[idx % 3]:
                    fig = create_price_chart(symbol)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
        
        with tab2:
            # Display data table
            if export_data:
                df = pd.DataFrame(export_data)
                st.dataframe(df, use_container_width=True)
        
        with tab3:
            # Export functionality
            if export_data:
                df = pd.DataFrame(export_data)
                csv = df.to_csv(index=False)
                st.download_button(
                    "Download CSV",
                    csv,
                    "stock_data.csv",
                    "text/csv",
                    key='download-csv'
                )
                
                # Excel export
                if st.button("Export to Excel"):
                    try:
                        with pd.ExcelWriter("stock_data.xlsx", engine='openpyxl') as writer:
                            for symbol in df['Symbol'].unique():
                                df_symbol = df[df['Symbol'] == symbol]
                                df_symbol.to_excel(writer, sheet_name=symbol, index=False)
                        st.success("Data exported to stock_data.xlsx")
                    except Exception as e:
                        st.error(f"Export failed: {str(e)}")
    else:
        st.info("Add stocks using the sidebar to start tracking")

if __name__ == "__main__":
    # Start monitoring thread
    monitor_thread = threading.Thread(target=monitor_stock_prices, daemon=True)
    monitor_thread.start()
    
    try:
        main()
    finally:
        stop_event.set()
        monitor_thread.join(timeout=2) 