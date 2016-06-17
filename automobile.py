#!/usr/bin/env python3

import re
from argparse import ArgumentParser
from ast import literal_eval
from collections import namedtuple
from datetime import datetime
from os import mkdir, getcwd as pwd
from os.path import dirname, exists as file_exists, expanduser, join as join_path, realpath
from shutil import copy, copytree
from subprocess import run
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import requests
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

SRC_DIR = dirname(realpath(expanduser(__file__)))

CACHE_FILE = join_path(SRC_DIR, 'article-cache')
GET_PARAMETERS = set((
    '_r',
    'emc',
    'partner',
    'referer',
    'smid',
    'smprod',
    'smtyp',
    'utm_campaign',
    'utm_content',
    'utm_medium',
    'utm_source',
    'utm_term',
))

MOBI_SCRIPT = join_path(SRC_DIR, 'make-mobi')
TEMPLATES_ROOT = join_path(SRC_DIR, 'templates')

Article = namedtuple('Article', ('order_id', 'title', 'content'))

def save_cache(cache):
    with open(CACHE_FILE, 'w') as fd:
        fd.write('{\n')
        for key, value in cache.items():
            minicache = {key:value}
            fd.write('\t' + repr(minicache)[1:-1] + ',\n')
        fd.write('}')

def load_cache():
    if file_exists(CACHE_FILE):
        with open(CACHE_FILE) as fd:
            return literal_eval(fd.read())
    else:
        return {}

def clean_url(url):
    scheme, netloc, path, query, fragment = urlsplit(url)
    query = urlencode(sorted((k, v) for k, v in parse_qsl(query) if k not in GET_PARAMETERS), doseq=True)
    url = urlunsplit((scheme, netloc, path, query, fragment))
    return url

def minimize_html(html):
    return ''.join(line.strip() for line in html.splitlines())

def clean_html(html):
    html = html.replace('\t', ' ')
    html = html.replace('\n', ' ')
    html = re.sub(' +', ' ', html)
    soup = BeautifulSoup(html, 'html.parser')
    # remove images (TODO)
    for name in ('img', 'figure'):
        for tag in soup.find_all(name):
            tag.extract()
    # remove empty tags
    for tag in soup.find_all((lambda t: t.get_text().strip() == '')):
        tag.extract()
    # remove CSS attributes
    for tag in soup.find_all(True):
        for attr in ('class', 'id', 'name', 'style'):
            if tag.has_attr(attr):
                del tag[attr]
    return minimize_html(soup.encode('ascii').decode('ascii'))

def download_article(url):
    parser_api = 'https://readability.com/api/content/v1/parser'
    params = {
        'token': '100252f25bc5a22b97caa5ed694ef3e67239fb28',
        'url': url,
    }
    r = requests.get(parser_api, params=params)
    if r.status_code != 200:
        raise IOError('Readability received status code {}'.format(r.status_code))
    json = r.json()
    title = json['title'].strip()
    html = clean_html(json['content'].strip())
    return title, html

def get_article(cache, url):
    if url in cache:
        title, html = cache[url]
        return title, html
    else:
        print('downloading URL: {}'.format(url))
        title, html = download_article(url)
        cache[url] = (title, html)
        return title, html

def get_articles(urls_file):
    cache = load_cache()
    articles = []
    with open(urls_file) as fd:
        for index, url in enumerate(reversed(fd.read().splitlines()), start=1):
            url = clean_url(url)
            title, html = get_article(cache, url)
            articles.append(Article('{:03d}'.format(index), title, html))
    save_cache(cache)
    return articles

def make_magazine(articles, title=None):
    now = datetime.now()
    context = {
        'identifier': 'justinnhli.com/automobile/{}'.format(now.strftime("%Y%m%d%H%M%S")),
        'modified': now.isoformat(),
        'chapters': tuple(articles),
    }
    if title is None:
        context['title'] = 'Article Collection {}'.format(now.strftime("%Y-%m-%d %H:%M:%S")),
    else:
        context['title'] = title
    jinja_env = Environment(
        loader=FileSystemLoader(TEMPLATES_ROOT),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    with TemporaryDirectory() as temp_dir:
        if title is None:
            mobi_name = 'magazine'
        else:
            mobi_name = re.sub('[^0-9A-Za-z]', ' ', title)
            mobi_name = re.sub(' +', ' ', mobi_name)
            mobi_name = mobi_name.replace(' ', '-').lower()
        epub_dir = join_path(temp_dir, mobi_name)
        mkdir(epub_dir)
        copytree(join_path(TEMPLATES_ROOT, 'META-INF'), join_path(epub_dir, 'META-INF'))
        copy(join_path(TEMPLATES_ROOT, 'mimetype'), epub_dir)
        for file in ('content.opf', 'toc.ncx'):
            with open(join_path(epub_dir, file), 'w') as fd:
                fd.write(jinja_env.get_template(file).render(context))
        mkdir(join_path(epub_dir, 'xhtml'))
        with open(join_path(epub_dir, 'xhtml', 'toc.xhtml'), 'w') as fd:
            xml = minimize_html(jinja_env.get_template('xhtml/toc.xhtml').render(context))
            fd.write(xml)
        order_id = 1
        for article in articles:
            article_context = {
                'title': article.title,
                'content': '<h1>{}</h1>'.format(article.title) + article.content,
            }
            with open(join_path(epub_dir, 'xhtml', '{:03d}.xhtml'.format(order_id)), 'w') as fd:
                xml = minimize_html(jinja_env.get_template('xhtml/chapter.xhtml').render(article_context))
                fd.write(xml)
            order_id += 1
        run(['/bin/sh', MOBI_SCRIPT, epub_dir])
        copy(join_path(temp_dir, '{}.mobi'.format(mobi_name)), realpath(expanduser(pwd())))

def main():
    arg_parser = ArgumentParser()
    arg_parser.add_argument('file')
    arg_parser.add_argument('--title')
    args = arg_parser.parse_args()
    articles = get_articles(realpath(expanduser(args.file)))
    make_magazine(articles, title=args.title)

if __name__ == '__main__':
    main()
