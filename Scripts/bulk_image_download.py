import re
import requests
import urllib.request
import urllib3

from bs4 import BeautifulSoup

print('Beginning file download with urllib2...')
url = "https://www.aurora.nats.co.uk/htmlAIP/Publications/2020-04-09/html/eSUP/EG-eSUP-2020-017-en-GB.html"
"""Parse the given table into a beautifulsoup object"""
count = 0
http = urllib3.PoolManager()
error = http.request("GET", url)
if (error.status == 404):
    print("File not found")

page = requests.get(url)
soup = BeautifulSoup(page.content, "lxml")
searchData = soup.find_all("img")

for img in searchData:
    file = re.search(r"(ID_[\d]{7}\.gif)", str(img))

    if file:
        url = f'https://www.aurora.nats.co.uk/htmlAIP/Publications/2020-04-09/graphics/{file.group(1)}'
        urllib.request.urlretrieve(url, f'{count}.gif')
        count += 1