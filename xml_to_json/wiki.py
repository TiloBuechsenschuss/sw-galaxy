#!/usr/bin/env python3
"""
Read-only client for the Star Wars FFG fandom wiki.

    python xml_to_json/wiki.py members Talents          # titles in a category
    python xml_to_json/wiki.py subcats "Source Book"    # its subcategories
    python xml_to_json/wiki.py page "Parry talent"      # one page's wikitext
    python xml_to_json/wiki.py cache Talents            # every page of a category
    python xml_to_json/wiki.py cache Talents --refresh  # ... ignoring the cache

This is the one place that talks to the wiki. `wiki_diff.py` (coverage reports)
and `wiki_descriptions.py` (rules text for the XML sources) both import it, and
anything fetching more content later should too rather than opening its own
urllib connection.

What it offers
--------------
* `members()` / `subcategories()` -- category listings, continuation followed.
* `page_categories()` -- the categories of many pages, in batches.
* `wikitext()` -- the raw source of many pages, in batches, **cached on disk**.
* `search()` -- full-text search, for finding what a thing is called.

The cache
---------
`wikitext()` writes one JSON file per page under `xml_to_json/wiki_cache/`,
holding the text, the revision id and the revision timestamp. It is not
committed (see .gitignore): it is a download, not a source. A second run over
the same pages costs no requests at all, which matters because parsing 700
talent pages is an edit-and-rerun loop. Pass `refresh=True` (`--refresh`) to
re-download.

Being polite
------------
One request at a time, a descriptive User-Agent, and `PAUSE` seconds between
requests. Fandom's API is generous but this walks whole categories, so it asks
for the API's maximum per request rather than hammering it with small ones.
Transient network errors are retried `RETRIES` times with a growing backoff;
anything else is raised.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

API = 'https://star-wars-rpg-ffg.fandom.com/api.php'
USER_AGENT = 'sw-galaxy-wiki/1.0 (+https://github.com/tilobuechsenschuss/sw-galaxy)'
CACHE_DIR = os.path.join(REPO_ROOT, 'xml_to_json', 'wiki_cache')

TIMEOUT = 30
RETRIES = 3
PAUSE = 0.1                # seconds between requests
BATCH = 50                 # the API's title limit for anonymous callers


class WikiError(RuntimeError):
    """The API answered, and said no."""


# --------------------------------------------------------------------------
# Transport
# --------------------------------------------------------------------------

def request(params, api=API):
    """One API call. Returns the decoded payload, retrying transient failures."""
    query = dict(params)
    query.setdefault('format', 'json')
    query.setdefault('formatversion', '2')
    url = api + '?' + urllib.parse.urlencode(query)
    last = None
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                payload = json.load(response)
            break
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError) as exc:
            last = exc
            if attempt == RETRIES - 1:
                raise
            time.sleep(2 ** attempt)
    else:                                                   # pragma: no cover
        raise last
    if 'error' in payload:
        raise WikiError(payload['error'].get('info', payload['error']))
    time.sleep(PAUSE)
    return payload


def query_all(params, api=API):
    """
    Yield every payload of a query, following the API's `continue` cursor.

    MediaWiki answers a large query in slices and hands back the parameters for
    the next one. Every listing here is potentially longer than one slice --
    Category:Talents alone is 702 pages -- so nothing calls request() directly
    for a list.
    """
    params = dict(params)
    while True:
        payload = request(params, api)
        yield payload
        if 'continue' not in payload:
            return
        params.update(payload['continue'])


def batched(items, size=BATCH):
    """Slice a list into the chunks the API's 50-title limit allows."""
    for start in range(0, len(items), size):
        yield items[start:start + size]


# --------------------------------------------------------------------------
# Categories
# --------------------------------------------------------------------------

def members(category, kind='page', api=API):
    """
    The titles in a category, sorted.

    `kind` is the API's cmtype: 'page' for articles, 'subcat' for
    subcategories, 'file' for images, or several comma separated. Careers are
    the reason 'subcat' matters here -- the wiki files each career as a
    *category*, not a page, so Category:Careers has no page members at all.
    """
    titles = []
    for payload in query_all({'action': 'query', 'list': 'categorymembers',
                              'cmtitle': 'Category:' + category, 'cmlimit': 'max',
                              'cmtype': kind}, api):
        titles += [m['title'] for m in payload['query']['categorymembers']]
    return sorted(titles)


def subcategories(category, api=API):
    """Subcategory names of a category, without the 'Category:' prefix."""
    return [t.split(':', 1)[1] for t in members(category, kind='subcat', api=api)]


def page_categories(titles, api=API):
    """{page title: [category names]} for many pages, in batches."""
    found = OrderedDict((t, []) for t in titles)
    for batch in batched(list(titles)):
        for payload in query_all({'action': 'query', 'prop': 'categories',
                                  'titles': '|'.join(batch), 'cllimit': 'max'}, api):
            for page in payload['query']['pages']:
                found.setdefault(page['title'], [])
                found[page['title']] += [c['title'].split(':', 1)[1]
                                         for c in page.get('categories', [])]
    return found


def search(text, limit=20, api=API):
    """Full-text search. For finding out what the wiki calls something."""
    payload = request({'action': 'query', 'list': 'search',
                       'srsearch': text, 'srlimit': str(limit)}, api)
    return [hit['title'] for hit in payload['query']['search']]


# --------------------------------------------------------------------------
# Page content, cached
# --------------------------------------------------------------------------

def cache_path(title, cache_dir=CACHE_DIR):
    """
    Where one page is cached.

    The title is percent-escaped rather than slugified, so it round-trips and
    two pages can never collide on one file: "Parry talent" and "Parry Talent"
    are different pages on a case-sensitive wiki.
    """
    return os.path.join(cache_dir, urllib.parse.quote(title, safe='') + '.json')


def read_cache(title, cache_dir=CACHE_DIR):
    """The cached record for one page, or None."""
    path = cache_path(title, cache_dir)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding='utf-8') as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None            # a truncated cache file is a miss, not a crash


def write_cache(record, cache_dir=CACHE_DIR):
    if not os.path.isdir(cache_dir):
        os.makedirs(cache_dir)
    path = cache_path(record['title'], cache_dir)
    with open(path, 'w', encoding='utf-8', newline='\n') as handle:
        json.dump(record, handle, indent=1, ensure_ascii=False, sort_keys=True)


def wikitext(titles, refresh=False, cache_dir=CACHE_DIR, api=API, verbose=False):
    """
    {title: record} for many pages, reading and filling the on-disk cache.

    A record is {'title', 'text', 'revid', 'revtime', 'missing'}. A page that
    does not exist is cached too, with `missing` True and `text` None -- so a
    name that is simply not on the wiki costs one request ever, not one per run.

    The returned mapping is keyed by the title as *asked for*, and each
    record's 'title' is that same name. MediaWiki answers under its own
    spelling -- it normalises titles and follows redirects, so asking for
    "Center Of Being talent" comes back as "Center of Being talent" -- and both
    hops are walked back so the caller gets its own name. The wiki's spelling
    is kept as 'wiki_title'.
    """
    titles = list(OrderedDict.fromkeys(titles))
    out = OrderedDict()
    wanted = []
    for title in titles:
        record = None if refresh else read_cache(title, cache_dir)
        if record is None:
            wanted.append(title)
        else:
            # The cache file is keyed by the asked-for title, but the record in
            # it was written under whatever name that run asked for -- the same
            # page reached as "Center of Being talent" and as a redirect from
            # "Center Of Being talent". Key and record must agree.
            record = dict(record, title=title)
            out[title] = record

    if verbose and titles:
        print('  wiki  %d page(s): %d cached, %d to fetch'
              % (len(titles), len(titles) - len(wanted), len(wanted)))

    for batch in batched(wanted):
        # 'normalized' and 'redirects' each map a name we asked for to the name
        # the wiki answered under. Walking them back is what lets a caller look
        # a page up by the name in its own data.
        hops, pages = {}, {}
        for payload in query_all({'action': 'query', 'prop': 'revisions',
                                  'rvprop': 'content|ids|timestamp',
                                  'rvslots': 'main', 'redirects': '1',
                                  'titles': '|'.join(batch)}, api):
            block = payload['query']
            for hop in block.get('normalized', []) + block.get('redirects', []):
                hops.setdefault(hop['to'], hop['from'])
            for page in block['pages']:
                pages.setdefault(page['title'], page)

        def asked_for(title, hops=hops):
            """Follow the normalise/redirect hops back, without looping."""
            seen = set()
            while title in hops and title not in seen:
                seen.add(title)
                title = hops[title]
            return title

        # A redirect means several asked-for names can share one answer, so the
        # page is looked up per requested title rather than iterated over.
        answers = {asked_for(t): p for t, p in pages.items()}
        for title in batch:
            page = answers.get(title, {'missing': True})
            revisions = page.get('revisions') or [{}]
            slots = revisions[0].get('slots', {})
            record = {
                'title': title,
                'wiki_title': page.get('title', title),
                'missing': bool(page.get('missing')),
                'text': slots.get('main', {}).get('content'),
                'revid': revisions[0].get('revid'),
                'revtime': revisions[0].get('timestamp'),
            }
            write_cache(record, cache_dir)
            out[title] = record

    return OrderedDict((t, out[t]) for t in titles)


def cache_category(category, refresh=False, cache_dir=CACHE_DIR, api=API,
                   verbose=True):
    """Download every page of a category into the cache. Returns the records."""
    titles = members(category, api=api)
    if verbose:
        print('  wiki  Category:%-16s %4d pages' % (category, len(titles)))
    return wikitext(titles, refresh=refresh, cache_dir=cache_dir, api=api,
                    verbose=verbose)


# --------------------------------------------------------------------------
# CLI -- for looking at the wiki by hand before writing an importer against it
# --------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', choices=['members', 'subcats', 'page', 'cache', 'search'])
    ap.add_argument('args', nargs='+', help='category, page title or search text')
    ap.add_argument('--refresh', action='store_true', help='ignore the cache')
    ap.add_argument('--cache-dir', default=CACHE_DIR)
    args = ap.parse_args(argv)

    try:
        if args.command == 'members':
            for title in members(args.args[0]):
                print(title)
        elif args.command == 'subcats':
            for name in subcategories(args.args[0]):
                print(name)
        elif args.command == 'search':
            for title in search(' '.join(args.args)):
                print(title)
        elif args.command == 'page':
            found = wikitext(args.args, refresh=args.refresh, cache_dir=args.cache_dir)
            for title, record in found.items():
                print('=' * 70)
                print('%s  (rev %s, %s)%s' % (title, record['revid'], record['revtime'],
                                              '  MISSING' if record['missing'] else ''))
                print('=' * 70)
                print(record['text'] or '')
        elif args.command == 'cache':
            for category in args.args:
                found = cache_category(category, refresh=args.refresh,
                                       cache_dir=args.cache_dir)
                missing = sum(1 for r in found.values() if r['missing'])
                print('  =>    %d cached under %s%s'
                      % (len(found) - missing,
                         os.path.relpath(args.cache_dir, REPO_ROOT).replace('\\', '/'),
                         ', %d missing' % missing if missing else ''))
    except WikiError as exc:
        print('wiki API: %s' % exc, file=sys.stderr)
        return 2
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        print('could not reach the wiki (%s)' % exc, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
