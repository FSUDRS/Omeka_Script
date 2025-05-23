import requests

api_key = "751d0352ade25f08a50eab3324d96eec5a8aee04"
url = "https://fsucardarchive.create.fsu.edu/api/users/current"
headers = {"Authorization": f"Bearer {api_key}"}

response = requests.get(url, headers=headers, verify=False)
print("Status Code:", response.status_code)
print("Response:", response.text)