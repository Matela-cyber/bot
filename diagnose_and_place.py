from __future__ import annotations

import json
import sys
import traceback

from execution.mt5_client import MT5Client
from config import settings


def main() -> None:
    client = MT5Client(settings.mt5_account, settings.mt5_password, settings.mt5_server)
    try:
        print("Connecting to MT5...")
        client.connect()
        print("Connected")

        try:
            balance = client.get_balance()
            print(f"Balance: {balance}")
        except Exception as e:
            print(f"Warning: could not fetch balance: {e}")

        symbol = "EURUSD"
        try:
            tick = client.get_price(symbol)
            print(f"Tick for {symbol}: {tick}")
        except Exception as e:
            print(f"Warning: could not fetch tick for {symbol}: {e}")

        print("Placing order: EURUSD buy 0.01 lots (no SL/TP)")
        result = client.place_order(symbol=symbol, order_type="buy", lots=0.01, comment="diagnostic:place")
        print("Order result:")
        print(json.dumps(result, default=str, indent=2))

    except Exception as exc:
        print("ERROR during MT5 operation:")
        print(str(exc))
        traceback.print_exc()
        sys.exit(1)
    finally:
        try:
            client.disconnect()
            print("Disconnected MT5")
        except Exception:
            pass


if __name__ == "__main__":
    main()
