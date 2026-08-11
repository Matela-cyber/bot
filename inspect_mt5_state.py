from __future__ import annotations

import json
import sys
import traceback

import MetaTrader5 as mt5  # type: ignore[import]
from config import settings


def dump(obj):
    try:
        return json.dumps(obj, default=lambda o: o.__dict__ if hasattr(o, '__dict__') else str(o), indent=2)
    except Exception:
        return str(obj)


def main():
    try:
        print("Initializing MT5 connection for inspection...")
        if not mt5.initialize(login=settings.mt5_account, password=settings.mt5_password, server=settings.mt5_server):
            print("MT5 initialize failed:", mt5.last_error())
            sys.exit(1)
        print("MT5 initialized")

        print("Open positions:")
        positions = mt5.positions_get()
        if positions is None:
            print("positions_get returned None")
        else:
            for p in positions:
                print(dump(p))

        print("Open orders:")
        orders = mt5.orders_get()
        if orders is None:
            print("orders_get returned None")
        else:
            for o in orders:
                print(dump(o))

        import time

        print("Recent deals (last 50):")
        now_ts = int(time.time())
        deals = mt5.history_deals_get(0, now_ts, 50)
        if deals is None:
            print("history_deals_get returned None or no recent deals")
        else:
            for d in deals:
                print(dump(d))

        print("History orders (last 50):")
        orders_hist = mt5.history_orders_get(0, now_ts, 50)
        if orders_hist is None:
            print("history_orders_get returned None or no recent orders")
        else:
            for o in orders_hist:
                print(dump(o))

    except Exception as exc:
        print("ERROR:", exc)
        traceback.print_exc()
    finally:
        try:
            mt5.shutdown()
            print("MT5 shutdown")
        except Exception:
            pass


if __name__ == '__main__':
    main()
