from sqlalchemy import create_engine, text

engine = create_engine("sqlite:///bot.db")
with engine.connect() as conn:
    result = conn.execute(text("SELECT trade_id, entry_price, stop_loss, take_profit, exit_reason FROM trades ORDER BY entry_time DESC LIMIT 3"))
    print("Latest 3 trades:")
    for row in result:
        print(f"  ID: {row[0]}, Entry: {row[1]}, SL: {row[2]}, TP: {row[3]}, Reason: {row[4]}")
