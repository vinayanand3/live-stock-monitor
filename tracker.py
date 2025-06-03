import yfinance as yf
import time
import threading
from tkinter import Tk, Label, Entry, Button, Text, Scrollbar, END, VERTICAL, Frame, messagebox, font, StringVar, OptionMenu, filedialog
from datetime import datetime
import pandas as pd
import queue
import logging
from zoneinfo import ZoneInfo

# ----------------------
# Configuration Constants
# ----------------------
REFRESH_INTERVAL = 10  # Seconds between updates
COLUMN_WIDTH = 12      # Characters per stock column
MIN_WINDOW_WIDTH = 60  # Minimum window width in characters
MAX_ROWS = 500  # Cap for in-memory rows in export_data and output_text

# Store previous prices for percentage calculation
previous_prices = {}
# Store alerts for each stock
stock_alerts = {}
# Store alert trigger state for each stock and alert type
alert_triggered = {}
# Store all displayed data for export
export_data = []
# Store the current date string for display
current_display_date = None
# Initialize tracking list
stock_symbols = []
symbols_lock = threading.Lock()
stop_event = threading.Event()

# GUI update queue for thread safety
gui_queue = queue.Queue()

# --- Function Definitions ---
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
            percentage_change = (
                (current_price - previous_price) / previous_price) * 100
            return percentage_change
    return None

def check_alerts(symbol, current_price, percentage_change, collect_only=False):
    """Check if any alerts should be triggered only once until reset by price moving away and crossing again. If collect_only, return messages instead of showing popup."""
    if symbol not in stock_alerts:
        return [] if collect_only else None
    alerts = stock_alerts[symbol]
    assert isinstance(alerts['percent_high'], list)
    assert isinstance(alerts['percent_low'], list)
    triggered = alert_triggered.setdefault(symbol, {
        'price_high': {},  # dict of value: triggered
        'price_low': {},
        'percent_high': {},
        'percent_low': {}
    })
    messages = []
    # Price Above (multiple)
    for val in alerts['price_high']:
        if not triggered['price_high'].get(val, False) and current_price >= val:
            messages.append(f"Price above {val}")
            triggered['price_high'][val] = True
        elif triggered['price_high'].get(val, False) and current_price < val:
            triggered['price_high'][val] = False
    # Price Below (multiple)
    for val in alerts['price_low']:
        if not triggered['price_low'].get(val, False) and current_price <= val:
            messages.append(f"Price below {val}")
            triggered['price_low'][val] = True
        elif triggered['price_low'].get(val, False) and current_price > val:
            triggered['price_low'][val] = False
    # Percent Above (multiple)
    for val in alerts['percent_high']:
        if not triggered['percent_high'].get(val, False) and percentage_change is not None and percentage_change >= val:
            messages.append(f"Percentage change above {val}%")
            triggered['percent_high'][val] = True
        elif triggered['percent_high'].get(val, False) and percentage_change is not None and percentage_change < val:
            triggered['percent_high'][val] = False
    # Percent Below (multiple)
    for val in alerts['percent_low']:
        if not triggered['percent_low'].get(val, False) and percentage_change is not None and percentage_change <= val:
            messages.append(f"Percentage change below {val}%")
            triggered['percent_low'][val] = True
        elif triggered['percent_low'].get(val, False) and percentage_change is not None and percentage_change > val:
            triggered['percent_low'][val] = False
    if collect_only:
        return messages
    if messages:
        messagebox.showinfo(f"Alert for {symbol}", "\n".join(messages))

def monitor_stock_prices(stock_symbols, interval):
    """Background thread for price updates"""
    global current_display_date
    while True:
        if stock_symbols:
            now = datetime.now(ZoneInfo('America/New_York'))
            date_str = now.strftime("%Y-%m-%d")
            time_str = now.strftime("%H:%M:%S")
            # Show the date only once at the top
            if current_display_date != date_str:
                gui_queue.put(('text', f"Date: {date_str}\n"))
                current_display_date = date_str
            # Use yf.download for batch fetch
            try:
                data = yf.download(stock_symbols, period="1d", interval="1m", progress=False, threads=False, timeout=5)
                # data['Close'] is a DataFrame with columns as symbols
                last_row = data['Close'].iloc[-1] if not data['Close'].empty else {}
            except Exception as e:
                logging.exception("Error in monitor_stock_prices")
                last_row = {}
            price_strings = []
            percentage_strings = []
            alert_messages = []
            for symbol in stock_symbols:
                price = last_row[symbol] if symbol in last_row else None
                if price is None or pd.isna(price):
                    price_strings.append(f"{'N/A':>{COLUMN_WIDTH}}")
                    percentage_strings.append(f"{'N/A':>{COLUMN_WIDTH}}")
                    continue
                price_strings.append(f"{price:>{COLUMN_WIDTH}.2f}")
                percentage_change = calculate_percentage_change(symbol, price)
                if percentage_change is not None:
                    percentage_strings.append(f"{percentage_change:>{COLUMN_WIDTH}.2f}%")
                else:
                    percentage_strings.append(f"{'N/A':>{COLUMN_WIDTH}}")
                alert_msgs = check_alerts(symbol, price, percentage_change, collect_only=True)
                if alert_msgs:
                    alert_messages.append((symbol, alert_msgs))
                previous_prices[symbol] = price
                export_data.append({
                    'Time': now.strftime("%Y-%m-%d %H:%M:%S"),
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
            time_col = f"{time_str:10}"
            price_row = f"{time_col}  " + "  ".join(price_strings)
            percentage_row = f"{'':10}  " + "  ".join(percentage_strings)
            separator = "-" * (10 + (COLUMN_WIDTH + 2) * len(stock_symbols))
            gui_queue.put(('text', f"{price_row}\n{percentage_row}\n{separator}\n"))
            for symbol, msgs in alert_messages:
                gui_queue.put(('alert', symbol, msgs))
        time.sleep(interval)

def update_header():
    if not stock_symbols:
        return
    # Header row: stock symbols
    header = f"{'Time':10}  " + "  ".join([f"{s:>{COLUMN_WIDTH}}" for s in stock_symbols])
    # Second row: column labels (Price)
    subheader = f"{'':10}  " + "  ".join([f"{'Price':>{COLUMN_WIDTH}}" for _ in stock_symbols])
    # Third row: column labels (% Change)
    subheader2 = f"{'':10}  " + "  ".join([f"{'% Chg':>{COLUMN_WIDTH}}" for _ in stock_symbols])
    separator = "=" * (10 + (COLUMN_WIDTH + 2) * len(stock_symbols))
    output_text.insert(END, f"{header}\n{subheader}\n{subheader2}\n{separator}\n")

def export_to_excel():
    if not export_data:
        messagebox.showinfo("No Data", "No data to export yet.")
        return
    df = pd.DataFrame(export_data)
    file_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
    if not file_path:
        return
    try:
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            for symbol in df['Symbol'].unique():
                df_symbol = df[df['Symbol'] == symbol]
                df_symbol.to_excel(writer, sheet_name=symbol, index=False)
        messagebox.showinfo("Export Successful", f"Data exported to {file_path}")
    except Exception as e:
        logging.exception("Error in export_to_excel")
        messagebox.showerror("Export Failed", str(e))

def update_alert_display():
    global alert_dropdown
    for widget in alert_frame.winfo_children():
        widget.destroy()
    symbol = selected_stock.get()
    if not symbol or symbol not in stock_alerts:
        Label(alert_frame, text="No alerts set.").pack(anchor='w')
        return
    alerts = stock_alerts[symbol]
    alert_options = []
    alert_keys = []
    alert_values = []
    # Price Above
    for val in alerts['price_high']:
        alert_options.append(f"{symbol} - Price Above: {val}")
        alert_keys.append('price_high')
        alert_values.append(val)
    # Price Below
    for val in alerts['price_low']:
        alert_options.append(f"{symbol} - Price Below: {val}")
        alert_keys.append('price_low')
        alert_values.append(val)
    # Percent Above
    for val in alerts['percent_high']:
        alert_options.append(f"{symbol} - % Above: {val}")
        alert_keys.append('percent_high')
        alert_values.append(val)
    # Percent Below
    for val in alerts['percent_low']:
        alert_options.append(f"{symbol} - % Below: {val}")
        alert_keys.append('percent_low')
        alert_values.append(val)
    if alert_options:
        alert_dropdown_var.set(alert_options[0])
        alert_dropdown = OptionMenu(alert_frame, alert_dropdown_var, *alert_options)
        alert_dropdown.grid(row=0, column=0, padx=5, sticky='w')
        Button(alert_frame, text="Delete Alert", command=lambda: delete_selected_alert(symbol, alert_keys, alert_values, alert_options)).grid(row=0, column=1, padx=5)
    else:
        alert_dropdown = OptionMenu(alert_frame, alert_dropdown_var, "No alerts set")
        alert_dropdown.config(state='disabled')
        alert_dropdown.grid(row=0, column=0, padx=5, sticky='w')

def delete_selected_alert(symbol, alert_keys, alert_values, alert_options):
    selected = alert_dropdown_var.get()
    if selected not in alert_options:
        return
    idx = alert_options.index(selected)
    key = alert_keys[idx]
    value = alert_values[idx]
    if key in ['price_high', 'price_low']:
        if value in stock_alerts[symbol][key]:
            stock_alerts[symbol][key].remove(value)
        alert_triggered[symbol][key].pop(value, None)
    else:  # percent alerts
        if value in stock_alerts[symbol][key]:
            stock_alerts[symbol][key].remove(value)
        alert_triggered[symbol][key].pop(value, None)
    update_alert_display()

def set_price_above_alert():
    symbol = selected_stock.get()
    if not symbol:
        messagebox.showwarning("Input Error", "Please select a stock to set alert.")
        return
    try:
        price_above = float(price_above_entry.get())
    except ValueError:
        messagebox.showerror("Error", "Please enter a valid number for Price Above.")
        return
    if symbol in stock_alerts:
        if price_above not in stock_alerts[symbol]['price_high']:
            stock_alerts[symbol]['price_high'].append(price_above)
            alert_triggered[symbol]['price_high'][price_above] = False
            messagebox.showinfo("Alert Set", f"Price Above alert set for {symbol} at {price_above}")
        else:
            messagebox.showinfo("Info", f"Price Above alert {price_above} already set for {symbol}")
    price_above_entry.delete(0, END)
    update_alert_display()

def set_price_below_alert():
    symbol = selected_stock.get()
    if not symbol:
        messagebox.showwarning("Input Error", "Please select a stock to set alert.")
        return
    try:
        price_below = float(price_below_entry.get())
    except ValueError:
        messagebox.showerror("Error", "Please enter a valid number for Price Below.")
        return
    if symbol in stock_alerts:
        if price_below not in stock_alerts[symbol]['price_low']:
            stock_alerts[symbol]['price_low'].append(price_below)
            alert_triggered[symbol]['price_low'][price_below] = False
            messagebox.showinfo("Alert Set", f"Price Below alert set for {symbol} at {price_below}")
        else:
            messagebox.showinfo("Info", f"Price Below alert {price_below} already set for {symbol}")
    price_below_entry.delete(0, END)
    update_alert_display()

def update_dropdown():
    menu = stock_dropdown['menu']
    menu.delete(0, 'end')
    for s in stock_symbols:
        menu.add_command(label=s, command=lambda value=s: selected_stock.set(value))
    if stock_symbols:
        selected_stock.set(stock_symbols[-1])
    else:
        selected_stock.set("")
    update_alert_display()

def add_stock():
    symbol = stock_entry.get().strip().upper()
    if not symbol:
        messagebox.showwarning("Input Error", "Please enter a stock symbol")
        return
    if symbol in stock_symbols:
        messagebox.showinfo("Info", f"{symbol} is already being tracked")
        return
    # Validate symbol
    def validate_and_add():
        test_price = get_stock_price(symbol)
        if test_price is None:
            messagebox.showerror("Error", f"Invalid symbol: {symbol}")
            return
        with symbols_lock:
            stock_symbols.append(symbol)
            stock_alerts[symbol] = {
                'price_high': [],
                'price_low': [],
                'percent_high': [],
                'percent_low': []
            }
            # Initialize alert triggered state
            alert_triggered[symbol] = {
                'price_high': {},
                'price_low': {},
                'percent_high': {},
                'percent_low': {}
            }
            selected_stock.set(symbol)
            update_dropdown()
            stock_entry.delete(0, END)
            output_text.insert(END, f"Tracking started for {symbol}\n")
            update_header()
    threading.Thread(target=validate_and_add, daemon=True).start()

def process_queue():
    try:
        while True:
            item = gui_queue.get_nowait()
            if item[0] == 'text':
                output_text.insert(END, item[1])
                output_text.see(END)
                # Cap output_text lines
                lines = int(output_text.index('end-1c').split('.')[0])
                if lines > MAX_ROWS * 3:  # 3 lines per row approx
                    output_text.delete('1.0', f'{lines - MAX_ROWS * 3}.0')
            elif item[0] == 'alert':
                symbol, msgs = item[1], item[2]
                messagebox.showinfo(f"Alert for {symbol}", "\n".join(msgs))
    except queue.Empty:
        pass
    root.after(100, process_queue)

def clear_output():
    output_text.delete('1.0', END)
    export_data.clear()

def on_close():
    stop_event.set()
    monitor_thread.join(timeout=2)
    root.destroy()

# ----------------------
# GUI Setup
# ----------------------
root = Tk()
root.title("Live Stock Monitor")
root.minsize(MIN_WINDOW_WIDTH * 8, 400)  # Approximate character width

# Configure monospace font
mono_font = font.Font(root, family="Courier New", size=10)

# Now initialize selected_stock with root as master
selected_stock = StringVar(root)
selected_stock.set("")
# Add trace to update alert display when selected stock changes
selected_stock.trace_add('write', lambda *args: update_alert_display())

# Input Section
input_frame = Frame(root, padx=10, pady=10)
input_frame.pack(fill="x")

# Stock symbol input
Label(input_frame, text="Stock Symbol:").grid(row=0, column=0, padx=5, sticky='w')
stock_entry = Entry(input_frame, width=15, font=mono_font)
stock_entry.grid(row=0, column=1, padx=5, sticky='ew')
Button(input_frame, text="Track Stock", command=add_stock).grid(row=0, column=2, padx=5, sticky='ew')
Button(input_frame, text="Export to Excel", command=export_to_excel).grid(row=0, column=3, padx=5, sticky='ew')
Button(input_frame, text="Clear", command=clear_output).grid(row=0, column=4, padx=5, sticky='ew')

# Dropdown for selecting stock
Label(input_frame, text="Tracked Stock:").grid(row=1, column=0, padx=5, sticky='w')
stock_dropdown = OptionMenu(input_frame, selected_stock, "")
stock_dropdown.config(width=12, font=mono_font)
stock_dropdown.grid(row=1, column=1, padx=5, sticky='ew')

# Price Above/Below alert section moved to row 2
Label(input_frame, text="Price Above:").grid(row=2, column=0, padx=5, sticky='w')
price_above_entry = Entry(input_frame, width=10, font=mono_font)
price_above_entry.grid(row=2, column=1, padx=5, sticky='ew')
Button(input_frame, text="Set", command=set_price_above_alert).grid(row=2, column=2, padx=2, sticky='ew')

Label(input_frame, text="Price Below:").grid(row=2, column=3, padx=5, sticky='w')
price_below_entry = Entry(input_frame, width=10, font=mono_font)
price_below_entry.grid(row=2, column=4, padx=5, sticky='ew')
Button(input_frame, text="Set", command=set_price_below_alert).grid(row=2, column=5, padx=2, sticky='ew')

# Configure grid weights for responsiveness
for i in range(6):
    input_frame.grid_columnconfigure(i, weight=1)
for i in range(3):
    input_frame.grid_rowconfigure(i, weight=1)

# --- Alert Display Section ---
alert_frame = Frame(root, padx=10, pady=5)
alert_frame.pack(fill="x")

alert_dropdown_var = StringVar(alert_frame)
alert_dropdown = None

# Output Section
output_frame = Frame(root)
output_frame.pack(expand=True, fill="both")

output_text = Text(output_frame,
                   wrap="none",
                   font=mono_font,
                   height=15,
                   bg="white",
                   borderwidth=0,
                   highlightthickness=0)
output_text.pack(side="left", fill="both", expand=True)

scrollbar = Scrollbar(output_frame, orient=VERTICAL, command=output_text.yview)
scrollbar.pack(side="right", fill="y")
output_text.config(yscrollcommand=scrollbar.set)

# Start monitoring thread
monitor_thread = threading.Thread(
    target=monitor_stock_prices,
    args=(stock_symbols, REFRESH_INTERVAL),
    daemon=True
)
monitor_thread.start()

root.protocol("WM_DELETE_WINDOW", on_close)
root.after(100, process_queue)
root.mainloop()
