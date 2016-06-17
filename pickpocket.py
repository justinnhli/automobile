#!/usr/bin/env python3

import sys

from bs4 import BeautifulSoup

with open(sys.argv[1]) as fd:
    soup = BeautifulSoup(fd.read(), 'html.parser')
for tag in soup.find_all('ul')[0].find_all('a'):
    print(tag['href'])
