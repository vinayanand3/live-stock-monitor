# Live Stock Monitor 📈

Real-time desktop application that tracks multiple stock symbols, displays rolling prices & percentage moves, and fires one-time alerts when your custom price or %-change thresholds are hit. Built with **Tkinter**, **yfinance**, and **pandas**; exports history to Excel in one click.

<p align="center">
  <a href="https://github.com/vinayanand3/live-stock-monitor/releases">
    <img alt="GitHub release" src="https://img.shields.io/github/v/release/vinayanand3/live-stock-monitor?logo=github">
  </a>
  <a href="https://github.com/vinayanand3/live-stock-monitor/blob/main/LICENSE">
    <img alt="MIT License" src="https://img.shields.io/github/license/vinayanand3/live-stock-monitor">
  </a>
</p>

---

## ✨ Key Features

| Feature                      | Description |
|-----------------------------|-------------|
| **Live quotes**             | Fetches all tracked symbols in a single Yahoo Finance batch call every few seconds. |
| **% change calculation**    | Displays real-time percentage change next to price. |
| **Custom alerts**           | Set one-time alerts for price above/below or % change above/below. |
| **Excel export**            | Export all monitored data to a multi-sheet `.xlsx` file. |
| **Responsive GUI**          | Thread-safe Tkinter interface with background fetching. |
| **Lightweight dependencies**| Uses only `yfinance`, `pandas`, and `openpyxl`. |

---

## 🖥️ Demo

<p align="center">
  <img src="stock%20monitor.png" width="600" alt="Live Stock Monitor GUI">
</p>

---

## 🚀 Quick Start

```bash
# 1. Clone this repo
git clone https://github.com/vinayanand3/live-stock-monitor.git
cd live-stock-monitor

# 2. (Optional) Create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the application
python stock_monitor.py
```
## Requirements

| Package    | Tested Version |
|------------|----------------|
| Python     | 3.9+           |
| yfinance   | ^0.2           |
| pandas     | ^2.2           |
| openpyxl   | ^3.1           |

*If you're using Python < 3.9, make sure* `backports.zoneinfo` *is installed — this is handled automatically in* `requirements.txt`.

---

## 🕹️ How to Use

| Action             | Instructions                                                                 |
|--------------------|------------------------------------------------------------------------------|
| **Track stock**    | Enter a stock symbol (e.g., `AAPL`) and click **Track Stock**.               |
| **Set alerts**     | Choose a tracked stock, input alert values (Price Above, Price Below), and click **Set**. |
| **Delete alert**   | Use the alert dropdown and click **Delete Alert** to remove it.              |
| **Export to Excel**| Click **Export to Excel** to download historical data.                       |
| **Clear display**  | Click **Clear** to reset the GUI log display.                                |

---

## 🛠️ Project Structure

```text
live-stock-monitor/
│
├── stock_monitor.py       # Main script (GUI + logic)
├── requirements.txt       # Python dependencies
├── README.md              # This file
├── LICENSE                # MIT license
└── docs/
    └── demo_screenshot.png
```

---

## 🎯 Roadmap

- [ ] Add sound alerts (e.g. `winsound` or `playsound`)
- [ ] Save/load alert settings to file
- [ ] Add broker integration or trade ticket prototype
- [ ] Package as standalone `.exe` using PyInstaller

---

## 🤝 Contributing

Pull requests are welcome!  
Before submitting:
- Open an issue to discuss any major feature or bugfix.
- Run linting with `ruff` or `flake8`.
- Validate basic functionality if possible (`pytest` or manual check).

---

## 📝 License

Licensed under the [MIT License](LICENSE).

---

## 🙏 Acknowledgements

- [yfinance](https://github.com/ranaroussi/yfinance) – Yahoo Finance Python API  
- [Heroicons](https://heroicons.dev/) – Icons under MIT license  
- GUI and logic designed by **Vinay Anand Bhaskarla**
