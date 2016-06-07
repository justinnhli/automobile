#!/usr/bin/env python3

from bs4 import BeautifulSoup

with open('/Users/justinnhli/Desktop/ril_export.html') as fd:
    soup = BeautifulSoup(fd.read(), 'html.parser')
for tag in soup.find_all('ul')[0].find_all('a'):
    print(tag['href'])
