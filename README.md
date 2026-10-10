# Mean Reversion Forex Bot

A Python-based automated trading system for MetaTrader 5 (MT5) that monitors a curated basket of FX pairs, evaluates mean-reversion opportunities, applies risk controls, and executes trades with operational safeguards.

This project is built for research, experimentation, and controlled live testing. It is not a guarantee of profitability and should only be used with disciplined risk management.

![Bot running 24/7 on AWS EC2 with Windows Remote Desktop](./Screenshot%20%28175%29.png)

## Overview

The bot is designed around a repeatable cycle:

- connect to MT5 and retrieve market data
- validate symbol, session, and liquidity conditions
- evaluate mean-reversion setups across multiple FX pairs
- size positions based on account risk
- manage open trades and partial exits
- persist trade and operational state locally
- send Telegram alerts for key events and risk conditions

This repository is structured as a modular trading system, so the strategy, filters, risk logic, execution layer, and notifications can be reviewed and adjusted independently.

## Why this project exists

The goal is to create a transparent, testable FX automation prototype that focuses on:

- disciplined risk management
- reproducible signal generation
- MT5 integration and workflow automation
- stateful trade logging in SQLite
- operational monitoring through Telegram alerts
- backtesting support before live deployment

## Key features

- Multi-pair FX monitoring across a defined basket of symbols
- Mean-reversion signal generation using price and indicator logic
- Market, spread, and liquidity filters to reduce poor-quality entries
- Daily loss and drawdown protections
- Risk-based position sizing
- MT5 order execution and trade management
- Partial exit logic and stop-loss management
- SQLite-backed trade persistence
- Telegram notifications for startup, trade signals, and risk events
- Backtesting workflow to validate strategy behavior

## Strategy profile

The current implementation is centered on a mean reversion approach for FX markets.

Typical execution flow:

1. Fetch recent OHLC data for the target symbol
2. Run market and session validation checks
3. Apply filter logic for spread, liquidity, and volatility conditions
4. Generate a trade signal from the strategy engine
5. Confirm risk and confidence thresholds
6. Calculate entry, stop-loss, and take-profit levels
7. Submit the trade via MT5

The default setup focuses on active macro trading windows and a limited set of major and cross FX pairs.

## Repository structure

```text
bot/
├── .env.example              # Example environment variables
├── .gitignore                # Git ignore rules
├── README.md                 # Project documentation
├── Screenshot (175).png      # Live bot deployment screenshot
├── config.py                 # Runtime configuration
├── main.py                   # Bot entry point
├── requirements.txt          # Runtime dependencies
├── requirements-dev.txt      # Development dependencies
├── bot.db                    # SQLite database
├── debug_signal_case.json    # Sample signal/debug case
├── run_backtest.py           # Backtesting entry point
├── backtest/                 # Backtesting engine and reports
├── core/                     # Shared domain models
├── data/                     # Data loading and historical data
├── db/                       # SQLite models and repositories
├── execution/                # MT5 client and order logic
├── filter/                   # Session, spread, and liquidity filters
├── indicators/               # Indicator implementations
├── notifications/            # Telegram integration
├── risk/                     # Risk management logic
├── results/                  # Strategy outputs and summaries
├── strategies/               # Trading strategy implementations
├── tests/                   # Automated tests
├── utils/                    # Logger and helper utilities
└── __pycache__/              # Python bytecode cache
```

## Prerequisites

Before running the bot, ensure you have:

- Python 3.10 or newer
- MetaTrader 5 installed and configured
- A valid broker account with MT5 access
- Correct MT5 login credentials and server details
- Telegram bot token and chat ID if notifications are enabled
- A Windows or Linux environment capable of running the bot continuously

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

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3) Install dependencies

```bash
pip install -r requirements.txt
```

### 4) Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your environment-specific settings.

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

### 5) Run the bot

```bash
python main.py
```

## Configuration

The bot loads runtime settings from `config.py` and reads the environment variables from `.env`.

Key configuration values include:

- `MT5_PATH`: local MT5 installation path
- `MT5_SERVER`: broker or server identifier
- `MT5_LOGIN`: account login
- `MT5_PASSWORD`: account password
- `TIMEFRAME`: chart timeframe used in the strategy loop
- `RISK_PER_TRADE`: risk percentage per trade
- `MAX_DAILY_LOSS`: maximum allowed daily loss
- `DRAWDOWN_LIMIT`: hard drawdown cutoff
- `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID`: notification settings
- `DB_PATH`: database file location
- `LOG_LEVEL`: log verbosity

Current default trading pairs:

```python
["AUDCAD", "GBPJPY", "EURJPY", "EURUSD", "EURGBP", "USDJPY", "USDCAD"]
```

## Operational behavior

When running, the bot will:

- initialize the database and MT5 client
- check trading-day and active-hour windows
- process each configured FX pair
- apply safety filters and signal logic
- size and submit trades according to risk rules
- manage open positions and partial exits
- log activity and send Telegram alerts

## Risk controls

The project includes several built-in protections, including:

- maximum daily loss checks
- drawdown monitoring
- pair and position caps
- spread and liquidity validation
- risk-based position sizing
- stop-loss and take-profit control
- operational alerting for risk events

These safeguards are intended to reduce the chance of uncontrolled execution, but they do not eliminate market risk.

## Backtesting

The project includes a backtesting entry point for validating strategy behavior before high-risk deployment:

```bash
python run_backtest.py
```

This is useful for checking logic, reviewing outputs, and validating assumptions under historical data before placing real trades.

## Deployment notes

This repository includes a live runtime screenshot showing the bot running continuously in a remote Windows environment. That is a practical example of how the system can be kept online in a persistent environment for unattended operation.

A typical deployment model is:

- EC2 or another cloud virtual machine for persistent execution
- Windows Remote Desktop or remote access for operational oversight
- MT5 installed and logged into the broker account
- script launched through a persistent session or service workflow

## Important disclaimer

This software is intended for educational, research, and controlled personal testing use.

It is not financial advice, and it does not guarantee performance or profitability. Any live trading use is at your own risk. The author and contributors are not responsible for losses, strategy failures, execution issues, or account outcomes related to using this project.

## Recommended usage

- test in a demo account before any live deployment
- validate the strategy using historical data
- keep risk limits conservative
- monitor the bot regularly
- verify MT5 connectivity and credentials before each session
- never assume a strategy is profitable based on a single setup or market regime

## Future improvements

Possible enhancements include:

- better configuration management
- richer backtest reporting and analytics
- improved trade journaling and strategy evaluation
- cleaner Telegram formatting and daily summaries
- expanded automated testing
- more robust deployment and monitoring documentation

## License and usage notice

This project is provided as-is for experimentation and automation research. Use responsibly and always validate system behavior in a safe environment before exposing real capital.

---

Built for automated FX research, controlled execution, and risk-aware MT5 trading.
