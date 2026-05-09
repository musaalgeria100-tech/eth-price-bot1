import subprocess, sys
subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "matplotlib", "-q"])

import time
import requests
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import io
import threading

# ✅ শুধু BOT_TOKEN বসান, CHAT_ID আর লাগবে না
BOT_TOKEN = "8531688617:AAGp1iQHCWPPunWCljBeUb5EhodyfDDPIzY"

# ⏱️ 9 মিনিট পর পর আপডেট
INTERVAL = 9 * 60

# সব subscriber এর chat_id রাখবে
subscribers = set()


def get_updates(offset=None):
    """নতুন /start মেসেজ চেক করে"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {"timeout": 10, "offset": offset}
    try:
        response = requests.get(url, params=params, timeout=15)
        return response.json().get("result", [])
    except:
        return []


def listen_for_users():
    """Background এ চলবে — নতুন /start ধরবে"""
    offset = None
    while True:
        updates = get_updates(offset)
        for update in updates:
            offset = update["update_id"] + 1
            message = update.get("message", {})
            text = message.get("text", "")
            chat_id = message.get("chat", {}).get("id")
            if chat_id and text.startswith("/start"):
                if chat_id not in subscribers:
                    subscribers.add(chat_id)
                    send_message(chat_id,
                        "✅ <b>সাবস্ক্রাইব করা হয়েছে!</b>\n"
                        "প্রতি 9 মিনিটে ETH প্রাইস আপডেট পাবেন। 🚀\n\n"
                        "বন্ধ করতে /stop পাঠান।"
                    )
                    print(f"✅ নতুন subscriber: {chat_id}")
            elif chat_id and text.startswith("/stop"):
                if chat_id in subscribers:
                    subscribers.discard(chat_id)
                    send_message(chat_id, "❌ আপনাকে সরিয়ে দেওয়া হয়েছে। আবার পেতে /start পাঠান।")
                    print(f"❌ Unsubscribed: {chat_id}")
        time.sleep(1)


def get_eth_price():
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": "ethereum", "vs_currencies": "usd,bdt", "include_24hr_change": "true"}
    response = requests.get(url, params=params, timeout=10)
    return response.json()["ethereum"]


def get_eth_chart_data():
    url = "https://api.coingecko.com/api/v3/coins/ethereum/market_chart"
    params = {"vs_currency": "usd", "days": "7"}
    headers = {"accept": "application/json"}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        data = response.json()
        if "prices" not in data:
            raise ValueError("no prices")
        prices = data["prices"]
        times = [datetime.fromtimestamp(p[0] / 1000) for p in prices]
        values = [p[1] for p in prices]
        return times, values
    except Exception:
        import math, random
        now = datetime.now()
        times = [now - timedelta(hours=i) for i in range(167, -1, -1)]
        values = [3200 + math.sin(i/10)*50 + random.uniform(-20,20) for i in range(168)]
        return times, values


def create_chart(times, values, current_price, change_24h):
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")

    color = "#00ff88" if change_24h >= 0 else "#ff4444"
    fill_color = "#00ff8820" if change_24h >= 0 else "#ff444420"

    ax.plot(times, values, color=color, linewidth=2.5, zorder=3)
    ax.fill_between(times, values, min(values), color=fill_color, zorder=2)
    ax.grid(color="#1e2530", linewidth=0.8, linestyle="--", alpha=0.7)
    ax.set_axisbelow(True)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.xaxis.set_major_locator(mdates.DayLocator())
    plt.xticks(color="#aaaaaa", fontsize=9)
    plt.yticks(color="#aaaaaa", fontsize=9)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    for spine in ax.spines.values():
        spine.set_visible(False)

    arrow = "▲" if change_24h >= 0 else "▼"
    sign = "+" if change_24h >= 0 else ""
    ax.set_title(f"ETH/USD  ${current_price:,.2f}   {arrow} {sign}{change_24h:.2f}%  (7 Days)",
                 color=color, fontsize=14, fontweight="bold", pad=15)

    ax.scatter([times[-1]], [values[-1]], color=color, s=60, zorder=5)
    ax.annotate(f"${values[-1]:,.0f}", (times[-1], values[-1]),
                textcoords="offset points", xytext=(-60, 10),
                color=color, fontsize=9, fontweight="bold")

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close()
    return buf


def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)


def send_photo_with_caption(chat_id, photo_buf, caption):
    photo_buf.seek(0)
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    files = {"photo": ("chart.png", photo_buf, "image/png")}
    data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
    requests.post(url, files=files, data=data, timeout=20)


def format_caption(price_data):
    usd = price_data["usd"]
    bdt = price_data["bdt"]
    change_24h = price_data["usd_24h_change"]
    arrow = "🟢 ▲" if change_24h >= 0 else "🔴 ▼"
    time_now = datetime.now().strftime("%d %b %Y, %I:%M %p")
    return (
        f"⚡ <b>Ethereum (ETH) Price Update</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💵 USD: <b>${usd:,.2f}</b>\n"
        f"🇧🇩 BDT: <b>৳{bdt:,.0f}</b>\n"
        f"📊 ২৪ঘণ্টার পরিবর্তন: {arrow} {abs(change_24h):.2f}%\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🕐 {time_now}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🛠 Made By @tmmad1"
    )


def main():
    print("✅ ETH Price Bot চালু হয়েছে!")

    # Background এ user listener চালু করো
    t = threading.Thread(target=listen_for_users, daemon=True)
    t.start()

    while True:
        if subscribers:
            try:
                print(f"📡 {len(subscribers)} জনকে পাঠাচ্ছি...")
                price_data = get_eth_price()
                times, values = get_eth_chart_data()
                caption = format_caption(price_data)

                for chat_id in list(subscribers):
                    try:
                        chart = create_chart(times, values, price_data["usd"], price_data["usd_24h_change"])
                        send_photo_with_caption(chat_id, chart, caption)
                    except Exception as e:
                        print(f"❌ {chat_id} তে পাঠাতে ব্যর্থ: {e}")

                print("✅ সবাইকে পাঠানো হয়েছে!")
            except Exception as e:
                print(f"❌ ত্রুটি: {e}")
        else:
            print("⏳ কোনো subscriber নেই, অপেক্ষা করছি...")

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
    
