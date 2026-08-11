#!/usr/bin/env python3
"""
XML -> JSON converter for STAR WARS GALAXY.

A Python port of convert.php, for machines without PHP. Both converters produce
the same output; if you change one, change the other (see README.md).

    python xml_to_json/convert.py                # convert everything
    python xml_to_json/convert.py --only Species # just one type
    python xml_to_json/convert.py --check        # report, write nothing

It reads xml_to_json/xml_sources/<any folder>/<Type>.xml and writes
data/json/<Type>.json.

Merge rules
-----------
* Sources are read in alphabetical folder order and the first occurrence of a
  Key wins -- so a folder sorting earlier overrides later ones.
* A row whose every source book is in EXCLUDED_BOOKS is not imported at all, so
  neither the row nor the book name reaches the JSON.
* Rows are then sorted by their first Source book, then by Name, then by Key,
  so the committed JSON has a stable diff.

Output format matches the committed files: pretty-printed with 4 spaces,
forward slashes escaped the way PHP does it, ASCII-only, CRLF, no trailing
newline.
"""
import argparse
import json
import os
import re
import sys
import glob
from collections import OrderedDict
import xml.etree.ElementTree as ET

VALID_FILE_NAMES = OrderedDict([
    ('Armor', 'Armor.xml'),
    ('Weapon', 'Weapons.xml'),
    ('ItemAttachments', 'ItemAttachments.xml'),
    ('Gear', 'Gear.xml'),
    ('Species', 'Species.xml'),
])

# Books that are not imported at all. A row whose every source is one of these
# is skipped, so neither the row nor the book name reaches the JSON.
EXCLUDED_BOOKS = ('Unofficial Species Menagerie',)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_INT_RE = re.compile(r'^[+-]?\d+$')
_FLOAT_RE = re.compile(r'^[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?$')


# --------------------------------------------------------------------------
# PHP simplexml_load_string() + json_encode(JSON_NUMERIC_CHECK) emulation.
#
# Every rule below was derived by regenerating the committed JSON from the
# committed XML and diffing until it matched. Do not "simplify" them.
# --------------------------------------------------------------------------

def numeric_check(s):
    """
    JSON_NUMERIC_CHECK uses PHP 7 is_numeric(): leading whitespace is allowed,
    trailing whitespace is not. Weapons.xml has "<Count>4\\n        </Count>",
    which stays the string '4\\n        ' rather than becoming 4.
    """
    t = s.lstrip(' \t\n\r\v\f')
    if _INT_RE.match(t):
        try:
            return int(t)
        except ValueError:
            return s
    if _FLOAT_RE.match(t):
        try:
            return float(t)
        except ValueError:
            return s
    return s


def strip_ns(tag):
    return tag.split('}', 1)[1] if '}' in tag else tag


def node_name(c):
    return 'comment' if c.tag is ET.Comment else strip_ns(c.tag)


def sx_to_obj(el):
    """Convert an Element the way SimpleXML + json_encode would."""
    if el.tag is ET.Comment:
        # A comment exposes no content -> empty object. This is why convert.php
        # has to unset($data->comment); nested ones survive as "comment": {}.
        return OrderedDict()

    children = [c for c in el if c.tag is ET.Comment or isinstance(c.tag, str)]
    text = (el.text or '')

    if not children:
        # Attributes are dropped entirely: the XML sources carry 1677 Page="..."
        # attributes and the committed JSON contains no "@attributes" key.
        if text.strip() != '':
            return numeric_check(text)
        if text != '':
            return OrderedDict([('0', text)])   # whitespace-only element
        return OrderedDict()

    out = OrderedDict()
    grouped = OrderedDict()
    for c in children:
        grouped.setdefault(node_name(c), []).append(c)
    for name, els in grouped.items():
        vals = [sx_to_obj(c) for c in els]
        out[name] = vals[0] if len(vals) == 1 else vals
    return out


def expand_source_pages(root):
    """
    OggDude stores the page as an attribute: <Source Page="44">Forged in
    Battle</Source>. SimpleXML throws attributes away (see the quirks above), so
    those 1783 page numbers never reached the JSON and the item cards rendered a
    book with no page. Rewrite them into the <Book>/<Page> child shape before
    converting -- the shape Species already use and items.html already renders.
    convert.php does the same in expandSourcePages().
    """
    for src in list(root.iter('Source')):
        page = src.get('Page')
        if page is None or len(src):     # Species already have the children
            continue
        book = src.text or ''
        del src.attrib['Page']
        src.text = None
        ET.SubElement(src, 'Book').text = book
        ET.SubElement(src, 'Page').text = page
    return root


def load_xml(path):
    with open(path, 'rb') as fh:
        raw = fh.read()
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    parser.feed(raw)
    return expand_source_pages(parser.close())


# --------------------------------------------------------------------------
# Merge helpers
# --------------------------------------------------------------------------

def source_books(row):
    """Every book name attached to a row, across both Source shapes."""
    out = []
    srcs = row.get('Sources')
    if isinstance(srcs, dict):
        src = srcs.get('Source')
        if isinstance(src, list):
            for x in src:
                if isinstance(x, dict) and isinstance(x.get('Book'), str):
                    out.append(x['Book'])
                elif isinstance(x, str):
                    out.append(x)
        elif isinstance(src, dict) and isinstance(src.get('Book'), str):
            out.append(src['Book'])
        elif isinstance(src, str):
            out.append(src)
    single = row.get('Source')
    if isinstance(single, dict) and isinstance(single.get('Book'), str):
        out.append(single['Book'])
    elif isinstance(single, str):
        out.append(single)
    return out


def is_excluded(row):
    """
    True when the row has sources and every one of them is an excluded book, so
    the row can be dropped. A row with no source at all is kept -- seven generic
    Gear entries have none, and they are legitimate.
    """
    books = source_books(row)
    return bool(books) and all(b in EXCLUDED_BOOKS for b in books)


def mixes_excluded_book(row):
    """
    True when the row mixes an excluded book with a book that is kept. No row in
    the current data does, so such a row is reported rather than handled: keeping
    it would leak the excluded book name into the app's Source filter, dropping
    it would lose official content. Decide deliberately if this ever fires.
    """
    books = source_books(row)
    n = sum(1 for b in books if b in EXCLUDED_BOOKS)
    return 0 < n < len(books)


# --------------------------------------------------------------------------
# Output order
# --------------------------------------------------------------------------

_PHP_TRIM = ' \t\n\r\0\x0b'                 # exactly what PHP trim() strips
_ASCII_LOWER = str.maketrans('ABCDEFGHIJKLMNOPQRSTUVWXYZ',
                             'abcdefghijklmnopqrstuvwxyz')


def _fold(value):
    """
    PHP's strtolower(trim($s)). str.lower() would also fold non-ASCII letters,
    which PHP's byte-wise strtolower leaves alone -- keep the two converters
    ordering identically.
    """
    return str(value).strip(_PHP_TRIM).translate(_ASCII_LOWER)


def sort_book(row):
    """The book a row sorts under: its first source book, '' when it has none."""
    books = source_books(row)
    return books[0] if books else ''


def sort_key(row):
    """
    First Source book, then Name, then Key as tie-breaker. Comparing codepoints
    matches PHP's strcmp() on bytes, because UTF-8 preserves codepoint order.
    """
    return (_fold(sort_book(row)), _fold(row.get('Name', '')),
            str(row.get('Key', '')))


# --------------------------------------------------------------------------

def convert(repo_root=REPO_ROOT, only_types=None, verbose=True):
    """Return {type_key: (output_path, payload)} without writing anything."""
    results = OrderedDict()
    for type_key, file_name in VALID_FILE_NAMES.items():
        if only_types and type_key not in only_types:
            continue
        pattern = os.path.join(repo_root, 'xml_to_json', 'xml_sources', '*', file_name)
        xml_files = sorted(glob.glob(pattern))
        json_file = os.path.join(
            repo_root, 'data', 'json', re.sub(r'\.xml$', '.json', file_name))
        rows = OrderedDict()

        for xml_file in xml_files:
            data = sx_to_obj(load_xml(xml_file))
            data.pop('comment', None)          # convert.php: unset($data->comment)
            values = next(iter(data.values())) if data else []
            if isinstance(values, dict):
                values = [values]
            kept = excluded = 0
            for row in values:
                if not isinstance(row, dict):
                    continue
                key, name = row.get('Key'), row.get('Name')
                if key is None or not isinstance(name, str) or name.strip() == '':
                    continue
                key_s = key if isinstance(key, str) else str(key)
                if key_s == '' or isinstance(key, (int, float)):
                    key_s = 'MISSING_KEY_' + re.sub(r'["\' \-]', '_', str(name)).upper()
                    row['Key'] = key_s

                # Excluded before de-duplication, so an excluded row never takes
                # a Key that a kept row would otherwise have claimed.
                if is_excluded(row):
                    excluded += 1
                    continue
                if mixes_excluded_book(row):
                    print("  ! %s mixes an excluded book with a kept one"
                          " -- see mixes_excluded_book()" % key_s)
                if key_s in rows:
                    continue                   # first one wins
                kept += 1

                if not isinstance(row.get('Description'), str):
                    row['Description'] = ""
                if 'Descriptors' in row and not isinstance(row['Descriptors'], str):
                    del row['Descriptors']
                if type_key == 'Species':
                    src = row.get('Source')
                    if isinstance(src, dict) and 'Page' in src:
                        if not isinstance(src['Page'], (int, float)):
                            del src['Page']
                thumb = 'data/img/%s%s.png' % (type_key, key_s)
                row['Thumbnail'] = thumb if os.path.exists(
                    os.path.join(repo_root, thumb)) else 'img/no_image.png'
                rows[key_s] = row
            if verbose:
                extra = ', %d excluded' % excluded if excluded else ''
                print("Read %s (%d new%s)" % (xml_file, kept, extra))

        out_rows = sorted(rows.values(), key=sort_key)
        results[type_key] = (json_file, {type_key: out_rows})
        if verbose:
            print("=> %s (%d rows)" % (json_file, len(out_rows)))
    return results


def dump(payload):
    """Match the committed files: PHP JSON_PRETTY_PRINT, escaped slashes, CRLF."""
    text = json.dumps(payload, indent=4, ensure_ascii=True)
    return text.replace('/', '\\/').replace('\n', '\r\n')


def read_raw(path):
    """
    Read without newline translation. Opening in default text mode turns the
    committed CRLF into LF, which makes every file look changed.
    """
    with open(path, encoding='utf-8', newline='') as fh:
        return fh.read()


def write(path, payload):
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write(dump(payload))       # no trailing newline, as committed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--only', help='comma-separated type keys, e.g. Species')
    ap.add_argument('--check', action='store_true',
                    help='report what would change without writing')
    args = ap.parse_args(argv)

    only = args.only.split(',') if args.only else None
    results = convert(REPO_ROOT, only, verbose=True)

    print()
    changed = False
    for type_key, (path, payload) in results.items():
        new = dump(payload)
        old = read_raw(path) if os.path.exists(path) else None
        if old == new:
            print('%-16s unchanged' % type_key)
            continue
        changed = True
        if old is None:
            print('%-16s NEW FILE' % type_key)
        else:
            a = {r['Key'] for r in json.loads(old)[type_key]}
            b = {r['Key'] for r in payload[type_key]}
            print('%-16s +%d -%d keys, %d rows total'
                  % (type_key, len(b - a), len(a - b), len(payload[type_key])))
        if not args.check:
            write(path, payload)
    if args.check:
        print('\n--check: nothing written')
    elif not changed:
        print('\nnothing to do')
    return 0


if __name__ == '__main__':
    sys.exit(main())
