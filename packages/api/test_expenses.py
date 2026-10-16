import json
import ssl
import urllib.request

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

r = urllib.request.urlopen('https://127.0.0.1:8444/api/expenses?limit=50&offset=0', context=ctx)
data = json.loads(r.read())
print('Status OK')
print(f'Total: {data["total"]} | Items returned: {len(data["items"])}')
if data["items"]:
    print("Sample item:", json.dumps(data["items"][0], indent=2))
