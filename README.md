# Mean Reversion Forex Bot

A Python trading bot for MetaTrader 5 (MT5) that scans a curated basket of FX pairs, evaluates mean-reversion setups, manages risk, and can send Telegram alerts for important trade events.

This project is designed for research, backtesting, and controlled demo or personal trading workflows. It is not a profit guarantee and should only be used with strict risk management.

## Why this project exists

The bot combines a few common building blocks used in algorithmic FX trading:

- MT5 data ingestion
- market/session filtering
- mean-reversion signal detection
- risk controls and position sizing
- order execution management
- SQLite trade persistence
- Telegram notifications

It is intentionally structured as a modular system so you can inspect, adjust, or replace components such as filters, strategies, risk rules, or execution logic without rewriting the whole project.

## Core features

- Multi-pair FX monitoring for major and cross pairs
- Mean-reversion signal generation using price and indicator logic
- Session and liquidity filters to reduce poor-quality setups
- Drawdown and daily-loss protection
- Position sizing based on configured account risk
- MT5 order management and partial exits
- SQLite-backed trade records
- Telegram alerts for startup, risk events, and trade signals
- Backtesting entry point for strategy validation

## Strategy profile

The current implementation focuses on a mean reversion approach for FX markets.

Typical flow:

1. Fetch recent OHLC data from MT5
2. Validate symbol, session, and liquidity conditions
3. Apply spread and market filters
4. Run the strategy logic on the selected pair
5. Check confidence and risk constraints
6. Calculate entry, stop-loss, and take-profit
7. Submit the order through MT5

The default configuration watches a small basket of pairs and restricts activity to specific market windows and trading days.

## Repository structure

```text
bot/
├── .env.example              # Example environment variables
├── .gitignore                # Git ignore rules
├── README.md                 # Project documentation
├── config.py                 # Runtime configuration
├── main.py                   # Bot entry point
├── requirements.txt          # Production dependencies
├── requirements-dev.txt     # Development dependencies
├── bot.db                   # SQLite database file
├── debug_signal_case.json    # Sample signal/debug case
├── run_backtest.py           # Backtesting workflow entry point
├── backtest/                 # Backtesting scripts and outputs
├── core/                     # Shared domain models
├── data/                    # Local data or generated artifacts
├── db/                      # Database models and repository layer
├── execution/               # MT5 client and order logic
├── filter/                  # Session, spread, and liquidity filters
├── indicators/              # Indicator implementations
├── notifications/           # Telegram and notification handling
├── risk/                    # Risk management logic
├── results/                 # Strategy/backtest results
├── strategies/              # Trading strategies
├── tests/                   # Test suite
├── utils/                   # Helpers and logging utilities
└── __pycache__/             # Python cache
```

## Prerequisites

Before running the bot, make sure you have:

- Python 3.10+ installed
- A working MetaTrader 5 installation
- A broker account connected to MT5
- Access to the MT5 terminal and login credentials
- A Telegram bot token and chat ID if you want notifications enabled

## Quick start

### 1) Clone the repository

```bash
git clone https://github.com/Matela-cyber/bot.git
cd bot
```

### 2) Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3) Install dependencies

```bash
pip install -r requirements.txt
```

### 4) Configure environment variables

Copy the example environment file and update the values:

```bash
cp .env.example .env
```

Then edit `.env` with your MT5 and Telegram settings.

Example:

```dotenv
MT5_PATH=C:/Program Files/MetaTrader 5/terminal64.exe
MT5_SERVER=ICMarkets-Demo
MT5_LOGIN=12345678
MT5_PASSWORD=your_password
TIMEFRAME=5m
RISK_PER_TRADE=0.03
MAX_DAILY_LOSS=0.05
DRAWDOWN_LIMIT=0.50
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
LOG_LEVEL=INFO
```

## Configuration

The bot reads configuration values from `config.py`, which loads environment variables from `.env`.

Key runtime settings include:

- `MT5_PATH`: local MT5 installation path
- `MT5_SERVER`: broker/server name
- `MT5_LOGIN`: MT5 account login
- `MT5_PASSWORD`: MT5 account password
- `TIMEFRAME`: chart timeframe used for signal generation
- `RISK_PER_TRADE`: percentage of account equity risked per trade
- `MAX_DAILY_LOSS`: daily risk limit
- `DRAWDOWN_LIMIT`: maximum acceptable drawdown
- `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`: Telegram notifications
- `DB_PATH`: SQLite database location
- `LOG_LEVEL`: logging verbosity

The bot currently uses a fixed list of FX pairs in `config.py`:

```python
["AUDCAD", "GBPJPY", "EURJPY", "EURUSD", "EURGBP", "USDJPY", "USDCAD"]
```

## Running the bot

Start the main trading loop:

```bash
python main.py
```

The bot will:

- initialize the database
- connect to MT5
- validate market/trading windows
- process each configured pair
- apply the strategy and filters
- size and submit trades
- persist execution data in SQLite
- send alerts through Telegram

## Backtesting

The project includes a backtesting entry point:

```bash
python run_backtest.py
```

This is useful for validating strategy behavior in a controlled setting before exposing any live account to real-market risk.

## Risk controls and warnings

This project includes several safety mechanisms, including:

- maximum daily loss limits
- drawdown monitoring
- pair and position caps
- spread and liquidity checks
- risk-based position sizing
- stop-loss and take-profit handling

It is important to understand that automated trading can behave differently in live markets than it does in backtests or demo environments.

## Important disclaimer

This software is for educational, research, and controlled personal testing use. It is not financial advice and does not guarantee profitability or performance.

Any live trading use is at your own risk. The author and contributors are not responsible for losses, execution issues, strategy failures, or account risk caused by using this project.

## Recommended usage

Use this project responsibly:

- test thoroughly in a demo account first
- validate the strategy with historical data
- confirm broker and MT5 settings before live trading
- keep risk limits conservative
- monitor the system regularly
- never assume a trading strategy will be profitable

## Future improvements

Possible next steps include:

- cleaner strategy configuration management
- richer backtest reporting and metrics
- better trade journaling and analytics
- improved Telegram alert formatting
- clearer deployment and operational documentation
- expanded test coverage

If you want to extend the project, the most natural next areas are strategy tuning, risk configuration, and observability.

---

This project is a trading prototype and should be treated as a research and automation tool, not a guaranteed income source or turnkey investment system.
