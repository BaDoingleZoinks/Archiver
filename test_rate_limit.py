import requests
import time
import concurrent.futures

url = "https://example.com"
api_url = f"https://archive.org/wayback/available?url={url}"

def check_wayback(i):
    start = time.time()
    try:
        resp = requests.get(api_url, timeout=10)
        return i, resp.status_code, time.time() - start
    except Exception as e:
        return i, str(e), time.time() - start

start_total = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    results = list(executor.map(check_wayback, range(20)))

for r in results:
    print(r)

print("Total time:", time.time() - start_total)
