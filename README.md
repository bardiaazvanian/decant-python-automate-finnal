# Decant Price Updater

Automated price calculator for perfume decants. When the price of a main perfume (tester) changes in the Sepidar ERP database, this script detects the change and recalculates all linked decant prices using a volume-based formula with profit margins.

## How It Works

1. **First run** — reads all main product prices from the Sepidar database, calculates every decant price, updates them, and saves a snapshot locally
2. **Subsequent runs** — compares current prices against the local snapshot. Only recalculates and updates decants for products whose main price has changed. If nothing changed, does nothing.

### Price Formula

```
PricePerMl = MainProductPrice / MainProductVolume(ml)
DecantPrice = PricePerMl × DecantVolume × ProfitMargin
```

| Decant Size | Profit Margin |
|-------------|---------------|
| 3 ml        | × 1.20        |
| 5 ml        | × 1.15        |
| 10 ml       | × 1.10        |
| 20 ml       | × 1.05        |

Final prices are rounded up to the nearest 500,000.

### Database Architecture

| Database | Type | Purpose |
|----------|------|---------|
| Sepidar ERP (`Sepidar01-change-angel`) | MSSQL | Main source — reads main product prices, writes updated decant prices |
| `decant_local.db` | SQLite | Local snapshot — tracks last-known prices to detect changes between runs |

### Product Relationship

- **Main product (tester)**: identified by `Code`, volume extracted from `Title` (e.g. `"Chanel Allure 100ml"`)
- **Decant product**: its `Description` field matches the main product's `Code`, volume in `Title` (e.g. `"Chanel Allure decant 5ml"`)

## Requirements

- Python 3.10+
- MSSQL Server with Windows Authentication
- ODBC Driver 17 for SQL Server

## Setup

1. Install the dependency:
   ```
   pip install pyodbc
   ```

2. Edit the config at the top of `decant_price_updater.py` if needed:
   ```python
   MSSQL_SERVER = r"."              # "." for local, or "SERVER\INSTANCE"
   MSSQL_DATABASE = "Sepidar01-change-angel"
   ```

3. Run it:
   ```
   python decant_price_updater.py
   ```
   Or double-click `run_updater.bat`.

## Scheduling (Windows Task Scheduler)

1. Open **Task Scheduler** > Create Basic Task
2. Set trigger to repeat every **2 days**
3. Action: **Start a program** > browse to `run_updater.bat`
4. Set **"Start in"** to the project directory

## Output

- **Console + log file** (`decant_updater.log`) — timestamped entries showing every price change
- **Local database** (`decant_local.db`) — contains:
  - `price_snapshot` — current main product prices
  - `update_log` — history of all price changes with timestamps

### Example Output

```
Decant price updater started
Found 226 main products with decants
3 product(s) need decant updates
  080169 (Kilian Angels share decant 5ml): 40,500,000 -> 42,000,000
  080168 (Kilian Angels share decant 10ml): 77,000,000 -> 80,000,000
  Main [01970002]  726,500,000 ->  750,000,000  (2 decants updated)
Done. 2 decant price(s) updated total.
```

```
No price changes detected. Nothing to do.
```

## Project Structure

```
decant-query-automate-finnal/
  decant_price_updater.py   # Main script
  run_updater.bat           # Windows batch wrapper for Task Scheduler
  requirements.txt          # Python dependencies
  decant_local.db           # Auto-created local SQLite database
  decant_updater.log        # Auto-created log file
```
