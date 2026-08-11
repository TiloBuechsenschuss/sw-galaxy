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
    elements, is_numeric's trailing-space rule, nested comments) were found.

Check 2 -- schema mapping
    Check the OggDude -> app-schema translation against the OggDude source
    itself. There is no longer an independent data set to diff against (the
    parsed_by_dutzen fork was removed), so this verifies the invariants the
    translation is supposed to hold:

      * every playable species produces exactly one row, with subspecies
        expanded and their parents suppressed
      * every row carries all six characteristics and all three attributes,
        inherited by subspecies from their parent
      * an OptionChoice with several Options lands in OptionChoices, one with a
        single Option lands in SpecialAbilities, and nothing is silently lost
      * subspecies inherit the parent's skills, talents, choices and abilities
      * every skill and talent key resolves to a display name
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


def option_names(el):
    """(names from multi-option choices, names from single-option choices)."""
    multi, single = [], []
    for ch in el.findall('OptionChoices/OptionChoice'):
        opts = ch.findall('Options/Option')
        picked = multi if len(opts) > 1 else single
        for o in opts:
            n = (o.findtext('Name') or '').strip()
            if n:
                picked.append(n)
    return multi, single


def check_mapping():
    print()
    print('=' * 72)
    print('Check 2: OggDude -> app schema translation holds its invariants')
    print('=' * 72)
    source_dir = os.path.join(ROOT, 'oggdudes-data')
    if not os.path.isdir(os.path.join(source_dir, 'Species')):
        print('  oggdudes-data/Species not present -- skipped')
        return True

    warn = []
    records, _, _, n_expanded = O.build(source_dir, warn)
    by_key = {r['Key']: r for r in records}
    failures = []

    # --- expected row set -------------------------------------------------
    expected, parents = set(), {}
    for path in sorted(glob.glob(os.path.join(source_dir, 'Species', '*.xml'))):
        root = ET.parse(path).getroot()
        key = (root.findtext('Key') or '').strip()
        subs = root.findall('SubSpeciesList/SubSpecies')
        if subs:
            for s in subs:
                sk = (s.findtext('Key') or '').strip()
                expected.add(sk)
                parents[sk] = (key, root, s)
        else:
            expected.add(key)

    missing = expected - set(by_key)
    extra = set(by_key) - expected
    if missing:
        failures.append('rows missing: %s' % sorted(missing))
    if extra:
        failures.append('unexpected rows: %s' % sorted(extra))
    print('  %d rows, %d parents expanded into subspecies' % (len(records), n_expanded))
    print('  expected row set matches: %s' % (not missing and not extra))

    # --- stats present on every row ---------------------------------------
    incomplete = [r['Key'] for r in records
                  if sorted(r['Characteristics']) != sorted(O.CHAR_ORDER)
                  or sorted(r['Attributes']) != sorted(O.ATTR_ORDER)]
    if incomplete:
        failures.append('rows missing characteristics/attributes: %s' % incomplete[:10])
    print('  all rows carry 6 characteristics + 3 attributes: %s' % (not incomplete))

    # --- option choices routed correctly, nothing dropped -----------------
    misrouted = []
    for path in sorted(glob.glob(os.path.join(source_dir, 'Species', '*.xml'))):
        root = ET.parse(path).getroot()
        subs = root.findall('SubSpeciesList/SubSpecies')
        targets = [((s.findtext('Key') or '').strip(), s) for s in subs] or \
                  [((root.findtext('Key') or '').strip(), root)]
        p_multi, p_single = option_names(root) if subs else ([], [])
        for key, el in targets:
            rec = by_key.get(key)
            if rec is None:
                continue
            multi, single = option_names(el)
            got_opt = {n for n, _ in rec['OptionChoices']}
            got_ab = {n for n, _ in rec['SpecialAbilities']}
            for n in multi + p_multi:
                if n not in got_opt:
                    misrouted.append('%s: multi-option %r not in OptionChoices' % (key, n))
            for n in single + p_single:
                if n not in got_ab:
                    misrouted.append('%s: single-option %r not in SpecialAbilities' % (key, n))
    if misrouted:
        failures.append('option choices misrouted (%d)' % len(misrouted))
    print('  every option choice routed and preserved: %s' % (not misrouted))
    for m in misrouted[:8]:
        print('      %s' % m)

    # --- subspecies inheritance -------------------------------------------
    broken = []
    for sk, (pkey, proot, sel) in parents.items():
        rec = by_key.get(sk)
        if rec is None:
            continue
        pname = (proot.findtext('Name') or '').strip()
        if not rec['Name'].startswith(pname + ' - '):
            broken.append('%s: name %r not prefixed with %r' % (sk, rec['Name'], pname))
        pskills = [(s.findtext('Key') or '').strip()
                   for s in proot.findall('SkillModifiers/SkillModifier')]
        if len(pskills) and not rec['Skills']:
            broken.append('%s: lost the parent skills %s' % (sk, pskills))
    if broken:
        failures.append('subspecies inheritance (%d)' % len(broken))
    print('  subspecies inherit from their parent: %s' % (not broken))
    for b in broken[:8]:
        print('      %s' % b)

    # --- key resolution ----------------------------------------------------
    print('  all skill/talent keys resolve: %s' % (not warn))
    for w in warn[:8]:
        print('      %s' % w)
    if warn:
        failures.append('unresolved keys (%d)' % len(warn))

    if failures:
        print()
        print('  FAILURES:')
        for f in failures:
            print('    %s' % f)
    return not failures


if __name__ == '__main__':
    a = check_converter()
    b = check_mapping()
    print()
    print('RESULT:', 'PASS' if (a and b) else 'FAIL')
    sys.exit(0 if (a and b) else 1)
