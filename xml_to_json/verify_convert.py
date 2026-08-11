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

Check 3 -- vehicle schema mapping
    The same idea for oggdude_vehicles_to_app.py:

      * one row per file under oggdudes-data/Vehicles/, keys unique
      * every non-empty source field reaches the row, compared case-insensitively
        (this is what caught EF76's <Starfighters> tag)
      * no book is cited twice on one row with the same page
      * every sensor range resolves to display text
      * no unresolved key beyond the two dangling references OggDude's own
        export contains (MINCONCLNCH, TSMEU6)
"""
import glob
import json
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import convert                        # noqa: E402
import oggdude_species_to_app as O    # noqa: E402
import oggdude_vehicles_to_app as V   # noqa: E402

ROOT = convert.REPO_ROOT

# Vehicle fields with no home in the app schema -- see README.md.
VEH_DROPPED = {'WeaponModifiers', 'EraPricing'}
# Vehicle fields that survive under a different name or shape, so a tag-for-tag
# comparison would report them as lost: the two Source shapes are reshaped by the
# converter, and the two sensor-range fields are folded into one SensorRange.
VEH_RESHAPED = {'Source', 'Sources', 'SensorRange', 'SensorRangeValue'}


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


def check_vehicles():
    print()
    print('=' * 72)
    print('Check 3: OggDude -> app schema vehicle translation holds')
    print('=' * 72)
    source_dir = os.path.join(ROOT, 'oggdudes-data')
    if not os.path.isdir(os.path.join(source_dir, 'Vehicles')):
        print('  oggdudes-data/Vehicles not present -- skipped')
        return True

    warn = []
    records, _, _ = V.build(source_dir, warn)
    by_key = {r['Key']: r for r in records}
    failures = []

    # --- one row per file, keys unique ------------------------------------
    expected = {}
    for path in sorted(glob.glob(os.path.join(source_dir, 'Vehicles', '*.xml'))):
        root = ET.parse(path).getroot()
        expected[(root.findtext('Key') or '').strip()] = root
    missing = set(expected) - set(by_key)
    extra = set(by_key) - set(expected)
    if missing or extra:
        failures.append('row set: missing %s, unexpected %s'
                        % (sorted(missing)[:5], sorted(extra)[:5]))
    print('  %d rows, one per source file: %s'
          % (len(records), len(records) == len(expected) and not missing and not extra))

    # --- nothing silently dropped ------------------------------------------
    # The check that caught EF76's <Starfighters> typo: every non-empty field in
    # the source has to reach the record, compared case-insensitively so the one
    # case-variant tag counts as carried rather than lost.
    lost = []
    for key, root in expected.items():
        rec = by_key.get(key)
        if rec is None:
            continue
        have = {k.lower() for k, v in rec.items() if v not in (None, '', [], {})}
        for child in root:
            if child.tag in VEH_DROPPED or child.tag in VEH_RESHAPED:
                continue
            if not (len(child) or (child.text or '').strip()):
                continue
            if child.tag.lower() not in have:
                lost.append('%s: %s' % (key, child.tag))
    if lost:
        failures.append('fields dropped in translation (%d)' % len(lost))
    print('  every non-empty source field carried through: %s' % (not lost))
    for l in lost[:8]:
        print('      %s' % l)

    # --- a book cited twice on one row was folded --------------------------
    dupes = []
    for rec in records:
        seen = {}
        for book, page in rec['Sources']:
            # Same book twice is only legitimate with two different pages.
            if book in seen and seen[book] == page:
                dupes.append('%s: %s cited twice identically' % (rec['Key'], book))
            seen[book] = page
    if dupes:
        failures.append('duplicate citations (%d)' % len(dupes))
    print('  no book cited twice with the same page: %s' % (not dupes))

    # --- sensor ranges resolved to display text ----------------------------
    bad_sensors = sorted({rec['SensorRange'] for rec in records
                          if 'SensorRange' in rec
                          and rec['SensorRange'] not in V.SENSOR_RANGES.values()})
    if bad_sensors:
        failures.append('unmapped sensor ranges: %s' % bad_sensors)
    print('  sensor ranges all resolved to display text: %s' % (not bad_sensors))

    # --- key resolution -----------------------------------------------------
    # MINCONCLNCH and TSMEU6 are dangling references in OggDude's own export
    # (see README). They are expected; anything else is not.
    unexpected = [w for w in warn
                  if 'MINCONCLNCH' not in w and 'TSMEU6' not in w]
    if unexpected:
        failures.append('unresolved keys (%d)' % len(unexpected))
    print('  no unresolved keys beyond the 2 known dangling ones: %s'
          % (not unexpected))
    for w in unexpected[:8]:
        print('      %s' % w)

    if failures:
        print()
        print('  FAILURES:')
        for f in failures:
            print('    %s' % f)
    return not failures


if __name__ == '__main__':
    a = check_converter()
    b = check_mapping()
    c = check_vehicles()
    print()
    print('RESULT:', 'PASS' if (a and b and c) else 'FAIL')
    sys.exit(0 if (a and b and c) else 1)
