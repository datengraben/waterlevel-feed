from datetime import datetime
import requests
import pandas as pd
import re

# Download latest csv
d = datetime.strftime(datetime.now(), '%d.%m.%Y')
url = "https://www.pegelonline.wsv.de/webservices/files/Wasserstand+Rohdaten/LAHN/GIESSEN+KL%C3%84RWERK/{}/down.txt".format(d)
rsp = requests.get(url)

with open('response.txt', 'w+') as fp:
    fp.write(rsp.text)

# Parse latest water level
data = rsp.text.split("\n")[12:-1]
data = list(map(lambda x: x.replace("\r", ""), data))
rows = list(map(lambda x: (x.split("#")[0], x.split("#")[1]), data))
_ = list(filter(lambda x: re.search("X", x[1]) == None, rows))
_ = _[-1]

# Write to result file
print(datetime.strftime(datetime.strptime(d, '%d.%m.%Y'), '%Y-%m-%d') + ' ' + _[0] + "," + _[1])

# Update rss feed (parameter with max level or max difference in %)
