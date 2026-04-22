
import time
import requests
import os
from collections import defaultdict

# ---------------------- إعدادات عامة ----------------------
BASE_CURRENCY = "USDT"
TRADE_AMOUNT = 50.0
MIN_PROFIT_PERCENT = 0.10
MIN_PRICE_THRESHOLD = 0.00001

# ---------------------- إعدادات تيليجرام ----------------------
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# ---------------------- هياكل البيانات ----------------------
SYMBOLS_INFO = []
ALL_TRIANGLES = []
PRICE_CACHE = {}
UNIQUE_SYMBOLS_NEEDED = set()

# ---------------------- إرسال تنبيه تيليجرام ----------------------
def send_telegram_alert(sym1, sym2, sym3, profit, percent, final):
    """إرسال إشعار فوري إلى تيليجرام"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    message = f"""
✨ *فرصة مراجحة مثلثية مكتشفة!*
```

المثلث: {sym1} → {sym2} → {sym3}
الربح: {profit:.4f} USDT
النسبة: {percent:.4f}%
المبلغ النهائي: {final:.4f} USDT

```
"""
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"},
            timeout=10
        )
    except Exception as e:
        print(f"⚠️ فشل إرسال تنبيه تيليجرام: {e}")

# ---------------------- تحميل الأزواج من Binance ----------------------
def load_symbols():
    global SYMBOLS_INFO
    print("⏳ تحميل أزواج Binance...")
    try:
        resp = requests.get("https://api.binance.com/api/v3/exchangeInfo", timeout=10)
        data = resp.json()
        for s in data.get("symbols", []):
            if s.get("status") == "TRADING":
                SYMBOLS_INFO.append((s["symbol"], s["baseAsset"], s["quoteAsset"]))
        print(f"✅ تم تحميل {len(SYMBOLS_INFO)} زوج نشط.")
        return True
    except Exception as e:
        print(f"❌ خطأ: {e}")
    return False

# ---------------------- بناء مثلثات المراجحة ----------------------
def build_triangles():
    global ALL_TRIANGLES, UNIQUE_SYMBOLS_NEEDED
    graph = defaultdict(list)
    for sym, base, quote in SYMBOLS_INFO:
        graph[base].append((quote, sym))
        graph[quote].append((base, sym))
    
    for first_coin, sym1 in graph[BASE_CURRENCY]:
        for second_coin, sym2 in graph[first_coin]:
            if second_coin == BASE_CURRENCY: continue
            for third_coin, sym3 in graph[second_coin]:
                if third_coin == BASE_CURRENCY:
                    ALL_TRIANGLES.append((sym1, sym2, sym3))
                    UNIQUE_SYMBOLS_NEEDED.update([sym1, sym2, sym3])
    print(f"✅ تم توليد {len(ALL_TRIANGLES)} مثلث.")
    print(f"✅ الأزواج المطلوبة للأسعار: {len(UNIQUE_SYMBOLS_NEEDED)}")

# ---------------------- تحديث الأسعار (أفضل Bid/Ask) ----------------------
def update_prices():
    global PRICE_CACHE
    session = requests.Session()
    new_cache = {}
    for symbol in UNIQUE_SYMBOLS_NEEDED:
        try:
            resp = session.get(
                "https://api.binance.com/api/v3/depth",
                params={"symbol": symbol, "limit": 1},
                timeout=2
            )
            data = resp.json()
            asks = data.get("asks", [])
            bids = data.get("bids", [])
            if asks and bids:
                ask = float(asks[0][0])
                bid = float(bids[0][0])
                if ask >= MIN_PRICE_THRESHOLD and bid >= MIN_PRICE_THRESHOLD:
                    new_cache[symbol] = (bid, ask)
        except Exception:
            pass
    if len(new_cache) >= len(UNIQUE_SYMBOLS_NEEDED) * 0.9:
        PRICE_CACHE = new_cache
        return True
    return False

# ---------------------- حساب الربح للمثلث ----------------------
def calculate(sym1, sym2, sym3):
    if sym1 not in PRICE_CACHE or sym2 not in PRICE_CACHE or sym3 not in PRICE_CACHE:
        return None
    bid1, ask1 = PRICE_CACHE[sym1]
    bid2, ask2 = PRICE_CACHE[sym2]
    bid3, ask3 = PRICE_CACHE[sym3]
    
    fee = 0.001
    try:
        amount = (TRADE_AMOUNT / ask1) * (1 - fee)
        amount = (amount / ask2) * (1 - fee)
        final_amount = amount * bid3 * (1 - fee)
        profit = final_amount - TRADE_AMOUNT
        percent = (profit / TRADE_AMOUNT) * 100
        if percent > 10.0:  # فلترة الأرباح غير الواقعية
            return None
        return profit, percent, final_amount
    except:
        return None

# ---------------------- عرض وإرسال الفرصة ----------------------
def print_opportunity(sym1, sym2, sym3, profit, percent, final):
    print("\n" + "="*80)
    print(f"✨ فرصة مراجحة مثلثية مكتشفة!")
    print(f"   المثلث: {sym1} → {sym2} → {sym3}")
    print(f"   💰 الربح: {profit:.4f} USDT")
    print(f"   📈 النسبة: {percent:.4f}%")
    print(f"   💵 المبلغ النهائي: {final:.4f} USDT")
    print("="*80)
    send_telegram_alert(sym1, sym2, sym3, profit, percent, final)

# ---------------------- فحص جميع المثلثات ----------------------
def scan_and_display():
    if not PRICE_CACHE:
        return 0
    found_count = 0
    for sym1, sym2, sym3 in ALL_TRIANGLES:
        res = calculate(sym1, sym2, sym3)
        if res:
            profit, percent, final = res
            if percent >= MIN_PROFIT_PERCENT:
                print_opportunity(sym1, sym2, sym3, profit, percent, final)
                found_count += 1
    return found_count

# ---------------------- نمط GitHub Actions (دورة واحدة) ----------------------
def run_single_cycle():
    """دورة واحدة فقط (مناسبة لـ GitHub Actions)"""
    if not load_symbols():
        exit(1)
    build_triangles()
    print(f"\n🔍 المبلغ={TRADE_AMOUNT} USDT | الحد الأدنى={MIN_PROFIT_PERCENT}%")
    print("⏳ جاري جلب الأسعار وفحص الفرص...\n")
    if update_prices():
        count = scan_and_display()
        if count == 0:
            print(f"🔍 لا توجد فرص ≥{MIN_PROFIT_PERCENT}%")
        else:
            print(f"\n✅ تم العثور على {count} فرصة خلال هذه الدورة\n")
    else:
        print("⚠️ فشل تحديث الأسعار")

# ---------------------- نمط التشغيل المستمر (محلي / VPS) ----------------------
def run_continuous():
    """حلقة مستمرة (للتشغيل المحلي أو السيرفر)"""
    print("🚀 بوت المراجحة الفوري - Binance (تشغيل مستمر)\n")
    if not load_symbols():
        exit(1)
    build_triangles()
    print(f"\n🔍 المبلغ={TRADE_AMOUNT} USDT | الحد الأدنى={MIN_PROFIT_PERCENT}%")
    print("⏳ جاري جلب الأسعار وفحص الفرص بشكل مستمر... (CTRL+C للإيقاف)\n")
    try:
        while True:
            start_scan = time.time()
            if update_prices():
                count = scan_and_display()
                elapsed = time.time() - start_scan
                if count == 0:
                    print(f"🔍 لا توجد فرص ≥{MIN_PROFIT_PERCENT}% (المسح استغرق {elapsed:.2f} ثانية)", end="\r")
                else:
                    print(f"\n✅ تم العثور على {count} فرصة خلال هذه الدورة (استغرقت {elapsed:.2f} ثانية)\n")
            else:
                print("⚠️ فشل تحديث الأسعار - إعادة المحاولة...")
            time.sleep(2)
    except KeyboardInterrupt:
        print("\n👋 تم إيقاف البوت.")

# ---------------------- نقطة البداية ----------------------
if __name__ == "__main__":
    # إذا تم تعيين متغير البيئة GITHUB_ACTIONS فإننا نعمل دورة واحدة فقط
    if os.environ.get("GITHUB_ACTIONS") == "true":
        run_single_cycle()
    else:
        run_continuous()
