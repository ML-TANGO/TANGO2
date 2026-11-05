import requests

url = "http://192.168.0.20:32767/v1/resource/workspace/4"
payload = {"interval": "1h"}

response = requests.post(url, json=payload) #, json=payload
# print(response.json())
print({'timeline': response.json()})