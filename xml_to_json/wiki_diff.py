#!/usr/bin/env python3
"""
Compare a wiki category against one of the generated data/json files.

    python xml_to_json/wiki_diff.py species        # one target
    python xml_to_json/wiki_diff.py --all          # every target in TARGETS
    python xml_to_json/wiki_diff.py --list         # show the targets

It reads the page titles of a category on the Star Wars FFG fandom wiki, reads
the Name of every row in the matching JSON, and writes a Markdown report to
xml_to_json/wiki_diff/<target>.md listing what each side has that the other
does not.

Adding a target
---------------
One line in TARGETS below. Nothing else is target-specific. A target may name
several wiki categories when one JSON file covers what the wiki splits up --
Vehicles.json holds both Category:Vehicles and Category:Starships -- in which
case the union of their pages is compared. For a one-off comparison that does
not deserve a permanent entry, pass the pieces directly:

    python xml_to_json/wiki_diff.py --category Talents --json data/json/Gear.json \\
                                    --type-key Gear --name adhoc

Matching
--------
Names rarely line up exactly, so a miss is retried with the relaxations in
RELAXATIONS (drop a subspecies suffix, drop a parenthetical, singularise).
Anything matched that way is reported in its own section with the rule that did
it, so a relaxation can never quietly hide a real difference. Add a rule by
appending one line to RELAXATIONS; combinations are handled automatically.

The wiki-only list is ordered official material first, homebrew after it, since
only the official half is worth importing.

What is left over is still noisy, because the two sides name things differently
("Arakyd Industries PX-11 Powered Armor" vs "PX-11 Powered Armor"). Those names
stay in the two _only lists -- they are genuinely unmatched -- and the report
additionally pairs each with its closest counterpart as a *suggestion* to check
by hand. Suggestions are never treated as matches.

This reads a third-party site over the network. It is a reporting tool only --
it never touches the XML sources, the JSON, or the app.
"""
import argparse
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict, namedtuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import convert                       # noqa: E402  (source_books, shared with the converter)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

API = 'https://star-wars-rpg-ffg.fandom.com/api.php'
USER_AGENT = 'sw-galaxy-wiki-diff/1.0 (+https://github.com/tilobuechsenschuss/sw-galaxy)'

Target = namedtuple('Target', 'category json_file type_key name_field')

# target name -> wiki category, JSON file under data/json/, its type key, and the
# field holding the display name. The type key is the one wrapping the array in
# the JSON -- note Weapons.json is keyed "Weapon". The category is one name, or a
# tuple of them when the wiki splits what one JSON file holds together.
TARGETS = OrderedDict([
    ('species',     Target('Species',     'Species.json',         'Species',         'Name')),
    ('armor',       Target('Armor',       'Armor.json',           'Armor',           'Name')),
    ('weapons',     Target('Weapon',      'Weapons.json',         'Weapon',          'Name')),
    ('gear',        Target('Gear',        'Gear.json',            'Gear',            'Name')),
    ('attachments', Target('Attachments', 'ItemAttachments.json', 'ItemAttachments', 'Name')),
    ('vehicles',    Target(('Vehicles', 'Starships'),
                                          'Vehicles.json',        'Vehicle',         'Name')),
])


def categories_of(target):
    """A target's wiki categories as a tuple -- one line may name several."""
    if isinstance(target.category, str):
        return (target.category,)
    return tuple(target.category)


# --------------------------------------------------------------------------
# Name matching
# --------------------------------------------------------------------------

def _key(text):
    """Comparison key: case, punctuation and spacing folded away."""
    return re.sub(r'[^a-z0-9]+', '', text.lower())


def _drop_subspecies(text):
    """'Aqualish - Aquala' -> 'Aqualish'. Species rows expand subspecies."""
    return text.split(' - ')[0] if ' - ' in text else None


def _drop_parenthetical(text):
    """'Human (Onderonian)' -> 'Human'."""
    stripped = re.sub(r'\s*\([^)]*\)', '', text).strip()
    return stripped if stripped and stripped != text else None


def _singularise(text):
    """'Toydarians' -> 'Toydarian'. Crude on purpose; the report shows its work."""
    return text[:-1] if len(text) > 3 and text.endswith('s') and not text.endswith('ss') else None


# Tried only after an exact match fails. Order is cosmetic; combinations of
# several rules are generated automatically.
RELAXATIONS = [
    ('subspecies', _drop_subspecies),
    ('parenthetical', _drop_parenthetical),
    ('plural', _singularise),
]


def variants(name):
    """
    {comparison key: tuple of rules applied} for one name.

    The exact key comes first with an empty rule tuple, then every key reachable
    by applying the relaxations, including combinations of them.
    """
    found = OrderedDict()
    queue = [(name, ())]
    while queue:
        text, rules = queue.pop(0)
        key = _key(text)
        if key and key not in found:
            found[key] = rules
            for rule_name, rule in RELAXATIONS:
                if rule_name in rules:
                    continue
                relaxed = rule(text)
                if relaxed and relaxed != text:
                    queue.append((relaxed, rules + (rule_name,)))
    return found


def compare(wiki_names, local_names):
    """
    Match two lists of names.

    Returns (exact, relaxed, wiki_only, local_only) where exact is a list of
    (wiki, local) pairs, relaxed is a list of (wiki, local, rules) and the two
    _only lists hold the names nothing matched.
    """
    local_index = OrderedDict()          # key -> [(local name, rules)]
    for name in local_names:
        for key, rules in variants(name).items():
            local_index.setdefault(key, []).append((name, rules))

    exact, relaxed, wiki_only = [], [], []
    matched_local = set()
    for wiki_name in wiki_names:
        hits = []
        for key, wiki_rules in variants(wiki_name).items():
            for local_name, local_rules in local_index.get(key, []):
                hits.append((len(wiki_rules) + len(local_rules),
                             wiki_rules + local_rules, local_name))
        if not hits:
            wiki_only.append(wiki_name)
            continue
        hits.sort(key=lambda h: (h[0], h[2]))
        best_cost = hits[0][0]
        for cost, rules, local_name in hits:
            if cost > best_cost:
                break
            matched_local.add(local_name)
            if cost == 0:
                exact.append((wiki_name, local_name))
            else:
                relaxed.append((wiki_name, local_name, rules))
    local_only = [n for n in local_names if n not in matched_local]
    return exact, relaxed, wiki_only, local_only


# A pair is worth a human look at or above this character-level similarity.
SIMILARITY_THRESHOLD = 0.80

# ... or when one name's significant words are a subset of the other's, which is
# what a dropped manufacturer prefix looks like. Below this many shared words the
# subset rule matches far too much ("Dart Launcher" / "Missile Launcher").
SUBSET_MIN_WORDS = 2


def _words(text):
    return {w for w in re.findall(r'[a-z0-9]+', text.lower()) if len(w) > 3}


def suggest(wiki_only, local_only):
    """
    Pair each unmatched wiki name with its most similar unmatched data name.

    These are hints for a human, not matches -- both names stay in their _only
    list. Returns [(wiki, local, score, why)] sorted strongest first.
    """
    import difflib
    out = []
    for wiki_name in wiki_only:
        wiki_key, wiki_words = _key(wiki_name), _words(wiki_name)
        best = None
        for local_name in local_only:
            local_words = _words(local_name)
            shared = wiki_words & local_words
            subset = (len(shared) >= SUBSET_MIN_WORDS
                      and (wiki_words <= local_words or local_words <= wiki_words))
            score = difflib.SequenceMatcher(None, wiki_key, _key(local_name)).ratio()
            if score < SIMILARITY_THRESHOLD and not subset:
                continue
            why = 'one name contains the other' if subset else 'similar spelling'
            if best is None or score > best[2]:
                best = (wiki_name, local_name, score, why)
        if best:
            out.append(best)
    out.sort(key=lambda p: -p[2])
    return out


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------

def fetch_category(category, api=API, verbose=True):
    """Every page title in a wiki category, following the API's continuation."""
    titles, params = [], {}
    while True:
        query = {'action': 'query', 'list': 'categorymembers',
                 'cmtitle': 'Category:' + category, 'cmlimit': '500',
                 'cmtype': 'page', 'format': 'json'}
        query.update(params)
        request = urllib.request.Request(api + '?' + urllib.parse.urlencode(query),
                                         headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
        if 'error' in payload:
            raise RuntimeError('wiki API: %s' % payload['error'].get('info', payload['error']))
        titles += [m['title'] for m in payload['query']['categorymembers']]
        if 'continue' not in payload:
            break
        params = payload['continue']
    if verbose:
        print('  wiki  Category:%-14s %4d pages' % (category, len(titles)))
    return sorted(titles)


def fetch_category_union(categories, api=API, verbose=True):
    """
    The page titles of one category or of several, merged.

    A page filed under two of them is one entry, so a target naming several
    categories compares against their union rather than a list with repeats.
    """
    titles = []
    for category in categories:
        titles += fetch_category(category, api=api, verbose=verbose)
    merged = sorted(OrderedDict.fromkeys(titles))
    if verbose and len(categories) > 1:
        print('  wiki  %-23s %4d pages' % ('union of %d categories' % len(categories),
                                           len(merged)))
    return merged


def load_names(json_file, type_key, name_field, repo_root=REPO_ROOT, verbose=True):
    """
    Every display name in one generated JSON file, plus {name: source books}
    taken straight from the row via the converter's own source_books().
    """
    path = json_file if os.path.isabs(json_file) else os.path.join(
        repo_root, 'data', 'json', os.path.basename(json_file))
    with open(path, encoding='utf-8') as handle:
        payload = json.load(handle)
    names, sources = [], {}
    for row in payload[type_key]:
        name = row.get(name_field)
        if not isinstance(name, str) or not name.strip():
            continue
        names.append(name)
        books = list(OrderedDict.fromkeys(convert.source_books(row)))
        sources[name] = ', '.join(books) if books else 'no source in the data'
    if verbose:
        print('  data  %-23s %4d rows' % (os.path.basename(path), len(names)))
    return names, sources, os.path.relpath(path, repo_root).replace('\\', '/')


# --------------------------------------------------------------------------
# Where a wiki page says its content came from
#
# The wiki classifies its own books: every official sourcebook category sits
# under Category:Source Book, every fan supplement under Category:Homebrew. So
# the two sets are read from the wiki rather than hardcoded here.
# --------------------------------------------------------------------------

_SUBCATEGORY_CACHE = {}


def fetch_subcategories(category, api=API):
    """The subcategory names of a category, fetched once per run."""
    if category in _SUBCATEGORY_CACHE:
        return _SUBCATEGORY_CACHE[category]
    names, params = [], {}
    while True:
        query = {'action': 'query', 'list': 'categorymembers',
                 'cmtitle': 'Category:' + category, 'cmlimit': '500',
                 'cmtype': 'subcat', 'format': 'json'}
        query.update(params)
        request = urllib.request.Request(api + '?' + urllib.parse.urlencode(query),
                                         headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
        names += [m['title'].split(':', 1)[1] for m in payload['query']['categorymembers']]
        if 'continue' not in payload:
            break
        params = payload['continue']
    _SUBCATEGORY_CACHE[category] = set(names)
    return _SUBCATEGORY_CACHE[category]


def fetch_categories(titles, api=API):
    """{page title: [category names]}, in batches of the API's 50-title limit."""
    found = OrderedDict((t, []) for t in titles)
    for start in range(0, len(titles), 50):
        batch, params = titles[start:start + 50], {}
        while True:
            query = {'action': 'query', 'prop': 'categories',
                     'titles': '|'.join(batch), 'cllimit': 'max', 'format': 'json'}
            query.update(params)
            request = urllib.request.Request(api + '?' + urllib.parse.urlencode(query),
                                             headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.load(response)
            for page in payload['query']['pages'].values():
                found.setdefault(page['title'], [])
                found[page['title']] += [c['title'].split(':', 1)[1]
                                         for c in page.get('categories', [])]
            if 'continue' not in payload:
                break
            params = payload['continue']
    return found


def wiki_sources(titles, own_categories, verbose=True):
    """
    {page title: readable source} for wiki pages.

    Official books are named plainly, fan material is prefixed 'homebrew:', so
    the report says at a glance whether an entry is worth importing.
    """
    if not titles:
        return {}
    official = fetch_subcategories('Source Book')
    fan_made = fetch_subcategories('Homebrew')
    categories = fetch_categories(titles)
    if verbose:
        print('  wiki  sources for %d pages (%d official books, %d homebrew known)'
              % (len(titles), len(official), len(fan_made)))
    labels = {}
    for title in titles:
        page = categories.get(title, [])
        books = sorted(c for c in page if c in official)
        fan = sorted(c for c in page if c in fan_made)
        bits = []
        if books:
            bits.append(', '.join(books))
        if fan:
            bits.append('homebrew: ' + ', '.join(fan))
        elif 'Homebrew' in page:
            bits.append('homebrew')
        if not bits:
            rest = sorted(c for c in page if c not in own_categories)
            bits.append(', '.join(rest) if rest else 'source not stated')
        labels[title] = ' / '.join(bits)
    return labels


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

def is_homebrew(source):
    """
    True when a source label names nothing but fan material.

    A page filed under an official book *and* a homebrew supplement counts as
    official: the importable half is what decides. An empty or unknown label
    counts as official too, so --no-sources leaves the order alphabetical.
    """
    parts = [p for p in (source or '').split(' / ') if p]
    return bool(parts) and all(p.startswith('homebrew') for p in parts)


def homebrew_last(titles, books):
    """Official material first, fan material after it, alphabetical within each."""
    return sorted(titles, key=lambda t: (is_homebrew(books.get(t)), t))


def render(name, target, source_label, wiki_names, local_names, result,
           wiki_books=None, local_books=None):
    """The Markdown report for one target."""
    exact, relaxed, wiki_only, local_only = result
    suggestions = suggest(wiki_only, local_only)
    wiki_books = wiki_books or {}
    local_books = local_books or {}

    official_only = [t for t in wiki_only if not is_homebrew(wiki_books.get(t))]

    def with_source(title, books):
        source = books.get(title)
        return '- %s (%s)' % (title, source) if source else '- %s' % title
    stamp = datetime.date.today().isoformat()
    out = []
    out.append('# %s: wiki vs. %s' % (name, source_label))
    out.append('')
    out.append('Generated %s by `xml_to_json/wiki_diff.py`.' % stamp)
    out.append('')
    out.append('| | count |')
    out.append('| --- | ---: |')
    on_the_wiki = ' + '.join('`Category:%s`' % c for c in categories_of(target))
    out.append('| %s on the wiki | %d |' % (on_the_wiki, len(wiki_names)))
    out.append('| rows in `%s` | %d |' % (source_label, len(local_names)))
    out.append('| matched exactly | %d |' % len(exact))
    out.append('| matched after normalisation | %d |' % len(relaxed))
    out.append('| **on the wiki only** | **%d** |' % len(wiki_only))
    out.append('| **in the data only** | **%d** |' % len(local_only))
    out.append('| of those, likely the same thing named differently | %d |' % len(suggestions))
    out.append('')

    out.append('## On the wiki, not in the data (%d)' % len(wiki_only))
    out.append('')
    out.append('The source in brackets is where the wiki files the page. Anything marked')
    out.append('`homebrew` is fan material, not an official FFG book.')
    if wiki_books:
        out.append('')
        out.append('Official material is listed first -- %d of these, then %d homebrew.'
                   % (len(official_only), len(wiki_only) - len(official_only)))
    out.append('')
    if wiki_only:
        for title in homebrew_last(wiki_only, wiki_books):
            out.append(with_source(title, wiki_books))
    else:
        out.append('_None._')
    out.append('')

    out.append('## In the data, not on the wiki (%d)' % len(local_only))
    out.append('')
    out.append('The source in brackets is the book on the row in the JSON.')
    out.append('')
    if local_only:
        for title in local_only:
            out.append(with_source(title, local_books))
    else:
        out.append('_None._')
    out.append('')

    out.append('## Matched only after normalisation (%d)' % len(relaxed))
    out.append('')
    out.append('Listed so a relaxation cannot quietly hide a real difference.')
    out.append('')
    if relaxed:
        out.append('| wiki | data | rule |')
        out.append('| --- | --- | --- |')
        for wiki_name, local_name, rules in relaxed:
            out.append('| %s | %s | %s |' % (wiki_name, local_name, ', '.join(rules)))
    else:
        out.append('_None._')
    out.append('')

    out.append('## Possibly the same, named differently (%d)' % len(suggestions))
    out.append('')
    out.append('Suggestions only, for checking by hand. Both names are still counted')
    out.append('as unmatched in the two lists above.')
    out.append('')
    if suggestions:
        out.append('| wiki | data | score | why |')
        out.append('| --- | --- | ---: | --- |')
        for wiki_name, local_name, score, why in suggestions:
            out.append('| %s | %s | %.2f | %s |' % (wiki_name, local_name, score, why))
    else:
        out.append('_None._')
    out.append('')
    return '\n'.join(out)


def run(name, target, out_dir, repo_root=REPO_ROOT, verbose=True, with_sources=True):
    """Compare one target and write its report. Returns the result tuple."""
    if verbose:
        print('%s' % name)
    categories = categories_of(target)
    wiki_names = fetch_category_union(categories, verbose=verbose)
    local_names, local_books, source_label = load_names(
        target.json_file, target.type_key, target.name_field, repo_root, verbose)
    result = compare(wiki_names, local_names)
    # Only the unmatched pages need a source, which keeps this to a handful of
    # extra requests rather than one per page in the category.
    wiki_books = wiki_sources(result[2], set(categories), verbose) if with_sources else {}
    report = render(name, target, source_label, wiki_names, local_names, result,
                    wiki_books, local_books if with_sources else {})

    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    path = os.path.join(out_dir, '%s.md' % name)
    with open(path, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(report)
    if verbose:
        print('  =>    %s  (%d wiki-only, %d data-only, %d relaxed)'
              % (os.path.relpath(path, repo_root).replace('\\', '/'),
                 len(result[2]), len(result[3]), len(result[1])))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('targets', nargs='*', help='targets to compare (see --list)')
    parser.add_argument('--all', action='store_true', help='compare every target')
    parser.add_argument('--list', action='store_true', help='list the targets and exit')
    parser.add_argument('--out', default=os.path.join(REPO_ROOT, 'xml_to_json', 'wiki_diff'),
                        help='directory for the reports')
    parser.add_argument('--category', help='ad-hoc: wiki category without the "Category:" '
                                           'prefix; several, comma separated, are compared '
                                           'as their union')
    parser.add_argument('--json', dest='json_file', help='ad-hoc: JSON file under data/json/')
    parser.add_argument('--type-key', help='ad-hoc: the key wrapping the array in that JSON')
    parser.add_argument('--name', default='adhoc', help='ad-hoc: name for the report file')
    parser.add_argument('--no-sources', action='store_true',
                        help='skip the per-page source lookup (fewer requests)')
    args = parser.parse_args(argv)

    if args.list:
        print('%-14s %-38s %s' % ('target', 'wiki category', 'json'))
        for name, target in TARGETS.items():
            print('%-14s %-38s %s'
                  % (name, ' + '.join('Category:' + c for c in categories_of(target)),
                     target.json_file))
        return 0

    if args.category or args.json_file or args.type_key:
        if not (args.category and args.json_file and args.type_key):
            parser.error('--category, --json and --type-key must be given together')
        categories = tuple(c.strip() for c in args.category.split(',') if c.strip())
        if not categories:
            parser.error('--category is empty')
        jobs = [(args.name, Target(categories, args.json_file, args.type_key, 'Name'))]
    elif args.all:
        jobs = list(TARGETS.items())
    elif args.targets:
        unknown = [t for t in args.targets if t not in TARGETS]
        if unknown:
            parser.error('unknown target(s): %s (see --list)' % ', '.join(unknown))
        jobs = [(t, TARGETS[t]) for t in args.targets]
    else:
        parser.error('name a target, or pass --all (see --list)')

    summary = []
    for name, target in jobs:
        try:
            result = run(name, target, args.out, with_sources=not args.no_sources)
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            print('  !     %s: could not reach the wiki (%s)' % (name, exc))
            return 2
        except (KeyError, ValueError) as exc:
            print('  !     %s: unexpected response or JSON (%r)' % (name, exc))
            return 2
        summary.append((name, len(result[2]), len(result[3])))

    if len(summary) > 1:
        print()
        print('%-14s %10s %10s' % ('target', 'wiki-only', 'data-only'))
        for name, wiki_only, local_only in summary:
            print('%-14s %10d %10d' % (name, wiki_only, local_only))
    return 0


if __name__ == '__main__':
    sys.exit(main())
