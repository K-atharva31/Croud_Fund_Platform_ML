import urllib.request, json
data = open("/tmp/payload.json","rb").read()
req = urllib.request.Request("http://127.0.0.1:5005/admin/api/fraud/score_campaign", data=data, headers={"Content-Type":"application/json"})
resp = urllib.request.urlopen(req).read().decode()
print(json.dumps(json.loads(resp), indent=2))
