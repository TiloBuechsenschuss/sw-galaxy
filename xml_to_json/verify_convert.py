#!/usr/bin/env python3
"""
Regression checks for the conversion pipeline.

    python xml_to_json/verify_convert.py

Run this after touching convert.py, convert.php or oggdude_species_to_app.py.
Exits non-zero if anything fails.

Check 1 -- converter fidelity
    Rebuild every data/json/*.json from the committed XML sources and compare to
    what is on disk. This is what proves the Python port behaves like the PHP
    one; it is how the SimpleXML quirks (dropped attributes, whitespace-only
    elements, is_numeric's trailing-space rule, nested comments) were found in
    the first place.

Check 2 -- schema mapping
    For every species present BOTH in oggdudes-data and in the shipped
    parsed_by_dutzen set, transform the OggDude file and compare against the
    shipped entry. Characteristics, attributes, skills, talents and abilities
    must agree, except where the two sets describe genuinely different versions
    of the species (the shipped entry is fan-made and OggDude has the official
    one). Those are listed, not failed.
"""
import glob
import json
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import convert                       # noqa: E402
import oggdude_species_to_app as O   # noqa: E402

ROOT = convert.REPO_ROOT
MEN = 'Unofficial Species Menagerie'


def check_converter():
    print('=' * 72)
    print('Check 1: converter reproduces the committed JSON')
    print('=' * 72)
    ok = True
    for type_key, (path, payload) in convert.convert(ROOT, verbose=False).items():
        if not os.path.exists(path):
            print('  %-16s MISSING %s' % (type_key, path))
            ok = False
            continue
        on_disk = json.load(open(path, encoding='utf-8'))
        rebuilt = json.loads(convert.dump(payload))
        if on_disk == rebuilt:
            print('  %-16s ok (%d rows)' % (type_key, len(payload[type_key])))
            continue
        ok = False
        a = {r['Key']: r for r in on_disk[type_key]}
        b = {r['Key']: r for r in payload[type_key]}
        print('  %-16s MISMATCH  +%d -%d changed=%d'
              % (type_key, len(set(b) - set(a)), len(set(a) - set(b)),
                 sum(1 for k in set(a) & set(b) if a[k] != b[k])))
        for k in sorted(set(a) & set(b)):
            if a[k] != b[k]:
                for f in sorted(set(a[k]) | set(b[k])):
                    if a[k].get(f) != b[k].get(f):
                        print('      %s.%s\n        on disk : %s\n        rebuilt : %s'
                              % (k, f, repr(a[k].get(f))[:90], repr(b[k].get(f))[:90]))
                break
    return ok


def as_list(node, inner):
    if not isinstance(node, dict):
        return []
    v = node.get(inner)
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def names(node, inner):
    return sorted(x.get('Name') for x in as_list(node, inner)
                  if isinstance(x, dict) and x.get('Name'))


def check_mapping():
    print()
    print('=' * 72)
    print('Check 2: OggDude -> app schema mapping matches the shipped data')
    print('=' * 72)
    source_dir = os.path.join(ROOT, 'oggdudes-data')
    if not os.path.isdir(source_dir):
        print('  oggdudes-data not present -- skipped')
        return True

    shipped = {}
    for path in glob.glob(os.path.join(
            ROOT, 'xml_to_json', 'xml_sources', 'parsed_by_dutzen', 'Species.xml')):
        for sp in ET.parse(path).getroot():
            k = (sp.findtext('Key') or '').strip()
            if k:
                shipped[k] = sp
    if not shipped:
        print('  parsed_by_dutzen/Species.xml not found -- skipped')
        return True

    warn = []
    records, _, _ = O.build(source_dir, warn)
    compared = agreed = 0
    version_diffs = {}
    real = []

    for rec in records:
        sp = shipped.get(rec['Key'])
        if sp is None:
            continue
        compared += 1

        def obj(tag):
            el = sp.find(tag)
            if el is None:
                return {}
            return {c.tag: (c.text or '').strip() for c in el}

        problems = []
        for tag, order, mine in (('Characteristics', O.CHAR_ORDER, rec['Characteristics']),
                                 ('Attributes', O.ATTR_ORDER, rec['Attributes'])):
            theirs = obj(tag)
            for f in order:
                if f in mine and f in theirs and int(mine[f]) != int(theirs[f]):
                    problems.append('%s.%s %s!=%s' % (tag, f, mine[f], theirs[f]))

        their_books = [(e.findtext('Book') or '').strip()
                       for e in sp.iter('Source') if e.findtext('Book')]
        my_books = [b for b, _ in rec['Sources']]
        if their_books and my_books and their_books[0] != my_books[0]:
            problems.append('Source %s!=%s' % (my_books[0], their_books[0]))

        def node(tag):
            el = sp.find(tag)
            if el is None:
                return {}
            inner = {'Skills': 'Skill', 'Talents': 'Talent',
                     'SpecialAbilities': 'SpecialAbility'}[tag]
            return {inner: [{c.tag: (c.text or '').strip() for c in item}
                            for item in el.findall(inner)]}

        for tag, inner, mine in (('Skills', 'Skill', rec['Skills']),
                                 ('Talents', 'Talent', rec['Talents']),
                                 ('SpecialAbilities', 'SpecialAbility',
                                  rec['SpecialAbilities'])):
            theirs = names(node(tag), inner)
            mine_n = sorted(n for n, _ in mine) if tag != 'SpecialAbilities' \
                else sorted(n for n, _ in mine)
            if theirs and mine_n != theirs:
                problems.append('%s %s!=%s' % (tag, mine_n, theirs))

        if not problems:
            agreed += 1
        elif MEN in their_books:
            version_diffs[rec['Key']] = (my_books[0] if my_books else '?', len(problems))
        else:
            real.append((rec['Key'], problems))

    print('  compared %d species: %d agree, %d differ only because the shipped'
          % (compared, agreed, len(version_diffs)))
    print('  entry is fan-made, %d genuine mismatches' % len(real))
    if version_diffs:
        print()
        print('  shipped as "%s", OggDude has the official version:' % MEN)
        for k, (book, n) in sorted(version_diffs.items()):
            print('    %-14s -> %-26s (%d field(s) differ)' % (k, book, n))
    if real:
        print()
        print('  GENUINE MISMATCHES:')
        for k, ps in real[:15]:
            print('    %-14s %s' % (k, '; '.join(ps)))
    for w in warn:
        print('  WARNING: %s' % w)
    return not real


if __name__ == '__main__':
    a = check_converter()
    b = check_mapping()
    print()
    print('RESULT:', 'PASS' if (a and b) else 'FAIL')
    sys.exit(0 if (a and b) else 1)
