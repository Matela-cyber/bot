import os

import MetaTrader5 as mt5
from dotenv import load_dotenv


def main() -> int:
    load_dotenv()

    account = os.getenv("MT5_ACCOUNT")
    password = os.getenv("MT5_PASSWORD")
    server = os.getenv("MT5_SERVER")

    if account is None or password is None or server is None:
        print("❌ MT5 credentials are not fully configured.")
        return 1

    try:
        account_id = int(account)
    except ValueError:
        print("❌ MT5_ACCOUNT must be an integer.")
        return 1

    print(f"🔌 Connecting to MT5...")
    print(f"   Account: {account_id}")
    print(f"   Server: {server}")

    if not mt5.initialize():
        print(f"❌ MT5 initialization failed. Error: {mt5.last_error()}")
        mt5.shutdown()
        return 1

    print("✅ MT5 initialized.")

    if not mt5.login(login=account_id, password=password, server=server):
        print(f"❌ Login failed. Error: {mt5.last_error()}")
        mt5.shutdown()
        return 1

    print("✅ Login successful!")

    info = mt5.account_info()
    if info:
        print(f"\n📊 Account Details:")
        print(f"   Balance:   ${info.balance:.2f}")
        print(f"   Equity:    ${info.equity:.2f}")
        print(f"   Profit:    ${info.profit:.2f}")
        print(f"   Leverage:  1:{info.leverage}")
        print(f"   Currency:  {info.currency}")
    else:
        print("❌ Failed to fetch MT5 account info.")

    symbol = "EURUSD"
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 1)
    if rates is not None and len(rates) > 0:
        price = rates[0][4]
        print(f"\n💱 {symbol} Price: {price:.5f}")
    else:
        print(f"\n❌ Failed to get {symbol} price.")

    mt5.shutdown()
    print("\n✅ MT5 connection closed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
