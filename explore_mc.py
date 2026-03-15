# explore_mc.py として保存して実行
import requests, re

r = requests.get("https://metalcharts.org/shfe/copper", timeout=15, headers={"User-Agent": "Mozilla/5.0"})
text = r.text

# RSC data chunks with inventory/stock keywords
for i, chunk in enumerate(text.split("self.__next_f.push")):
    lower = chunk.lower()
    if "inventory" in lower or "warrant" in lower or "326" in lower:
        if len(chunk) < 5000:
            print(f"=== RSC chunk #{i} ===")
            print(chunk[:1000])
            print("...\n")

# Try fetching with RSC header (Next.js server component data)
r2 = requests.get(
    "https://metalcharts.org/shfe/copper",
    timeout=15,
    headers={
        "User-Agent": "Mozilla/5.0",
        "RSC": "1",
        "Next-Router-State-Tree": "%5B%22%22%2C%7B%22children%22%3A%5B%22(dashboard)%22%2C%7B%22children%22%3A%5B%22shfe%22%2C%7B%22children%22%3A%5B%22copper%22%2C%7B%22children%22%3A%5B%22__PAGE__%22%2C%7B%7D%5D%7D%5D%7D%5D%7D%5D%7D%5D",
    }
)
print(f"\nRSC request: {r2.status_code}, {len(r2.text)} chars")
# Look for data in RSC response
lines = r2.text.split("\n")
for line in lines:
    if len(line) > 200 and any(x in line for x in ["date", "inventory", "stock", "2024", "2025", "2026"]):
        print(f"Data line ({len(line)} chars): {line[:500]}")
        print("...")