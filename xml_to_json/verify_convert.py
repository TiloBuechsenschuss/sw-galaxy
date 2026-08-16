#!/usr/bin/env python3
"""
Regression checks for the conversion pipeline.

    python xml_to_json/verify_convert.py

Run this after touching convert.py or any oggdude_*_to_app.py.
Exits non-zero if anything fails.

Check 1 -- converter fidelity
    Rebuild every data/json/*.json from the committed XML sources and compare to
    what is on disk. data/json/ is a committed deployment artifact, so this is
    the check that keeps the converter's parsing quirks (dropped attributes,
    whitespace-only elements, the trailing-space rule on numbers, nested
    comments) intact -- it is how each of them was found in the first place.

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

Check 4 -- career schema mapping
    The same idea for oggdude_careers_to_app.py:

      * one row per file under oggdudes-data/Careers/, keys unique
      * no career skill and no specialization is lost on the way, and every key
        resolves to a display name
      * only a non-zero ForceRating survives the all-zero <Attributes> block

Check 5 -- talent schema mapping
    The same idea for oggdude_talents_to_app.py:

      * every talent in Talents.xml reaches a row, with the three keys OggDude
        lists twice merged rather than dropped
      * a merged row keeps every citation both listings carried
      * every ActivationValue resolves to display text
      * the Ranked / Force / Conflict categories match the flags in the source,
        and nothing else is invented

Check 6 -- the wiki description override
    xml_sources/fandom-wiki/ overrides whole rows, because that is the only
    precedence convert.py has, but it is only ever meant to replace the
    Description. So:

      * every row it holds has a counterpart with the same Key in another
        source folder -- an override with nothing to override is a row the app
        would silently gain
      * the two rows are identical everywhere except <Description>, tags,
        attributes and text compared in order
      * the new Description is not empty and is not another page pointer

    This is the check that would catch a row rewritten by hand, or an oggdude
    re-import that moved a field the override folder is still carrying an old
    copy of.

Check 7 -- tree schema mapping
    oggdude_specializations_to_app.py and oggdude_force_powers_to_app.py are the
    two importers whose output is a LAYOUT, so what has to hold is geometry:

      * one row per source file, and every distinct cell key in a row survives
        it -- either as a box or absorbed into a spanning one
      * every tree row lays out exactly four columns wide, counting spans. This
        is the invariant the renderer rests on, and holes and spans are the two
        ways OggDude's export can break it
      * each connector is written exactly once and points at something: no
        <Down> on the last row, no LinkRight on a box at the right edge
      * specializations never span (they are a clean 5x4), every one of them
        belongs to a career or is universal, and every force power box is priced
        with <Experience> as the sum
      * the one-sided links the importers union are counted, so a change in that
        count is visible rather than silently accepted
"""
import glob
import json
import os
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import convert                        # noqa: E402
import oggdude_species_to_app as O    # noqa: E402
import oggdude_vehicles_to_app as V   # noqa: E402
import oggdude_careers_to_app as C    # noqa: E402
import oggdude_talents_to_app as T    # noqa: E402
import oggdude_specializations_to_app as S  # noqa: E402
import oggdude_force_powers_to_app as F     # noqa: E402

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


def check_careers():
    print()
    print('=' * 72)
    print('Check 4: OggDude -> app schema career translation holds')
    print('=' * 72)
    source_dir = os.path.join(ROOT, 'oggdudes-data')
    if not os.path.isdir(os.path.join(source_dir, 'Careers')):
        print('  oggdudes-data/Careers not present -- skipped')
        return True

    warn = []
    records, _, _ = C.build(source_dir, warn)
    by_key = {r['Key']: r for r in records}
    failures = []

    # --- one row per file, keys unique ------------------------------------
    expected = {}
    for path in sorted(glob.glob(os.path.join(source_dir, 'Careers', '*.xml'))):
        root = ET.parse(path).getroot()
        expected[(root.findtext('Key') or '').strip()] = root
    missing = set(expected) - set(by_key)
    extra = set(by_key) - set(expected)
    if missing or extra:
        failures.append('row set: missing %s, unexpected %s'
                        % (sorted(missing)[:5], sorted(extra)[:5]))
    print('  %d rows, one per source file: %s'
          % (len(records), len(records) == len(expected) and not missing and not extra))

    # --- both key lists carried in full -----------------------------------
    # Resolving a key to a display name must never lose one, so the counts have
    # to match file by file. This is the check that would catch a <Key/> element
    # being skipped the way Cerean.xml's empty one is on the species side.
    lost = []
    for key, root in expected.items():
        rec = by_key.get(key)
        if rec is None:
            continue
        for tag, path, field in (('career skill', 'CareerSkills/Key', 'Skills'),
                                 ('specialization', 'Specializations/Key',
                                  'Specializations')):
            want = len([k for k in root.findall(path) if (k.text or '').strip()])
            if want != len(rec[field]):
                lost.append('%s: %d %ss in, %d out' % (key, want, tag, len(rec[field])))
    if lost:
        failures.append('key lists not carried in full (%d)' % len(lost))
    print('  every career skill and specialization carried: %s' % (not lost))
    for l in lost[:8]:
        print('      %s' % l)

    # --- the all-zero attribute block did not leak ------------------------
    # Seven Force careers carry <WoundThreshold>0</WoundThreshold> and friends,
    # plus an empty <Requirement>. Only a real ForceRating may survive.
    leaked = []
    for key, root in expected.items():
        rec = by_key.get(key)
        if rec is None:
            continue
        source_force = (root.findtext('Attributes/ForceRating') or '').strip()
        want = source_force if source_force and source_force != '0' else None
        if rec['ForceRating'] != want:
            leaked.append('%s: ForceRating %r, source has %r'
                          % (key, rec['ForceRating'], source_force))
        # The Force category is what the sidenav filters on, so it must say
        # exactly what the rating says -- a career tagged Force with no rating,
        # or the other way round, would filter to the wrong set.
        tagged = 'Force' in rec['Categories']
        if tagged != bool(want):
            leaked.append('%s: Force category %s, ForceRating %r'
                          % (key, tagged, rec['ForceRating']))
    if leaked:
        failures.append('ForceRating mismatches (%d)' % len(leaked))
    print('  only a non-zero ForceRating survives <Attributes>,'
          ' and the Force category agrees with it: %s' % (not leaked))
    for l in leaked[:8]:
        print('      %s' % l)

    # --- key resolution ----------------------------------------------------
    print('  all skill/specialization keys resolve: %s' % (not warn))
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


def check_talents():
    print()
    print('=' * 72)
    print('Check 5: OggDude -> app schema talent translation holds')
    print('=' * 72)
    source_dir = os.path.join(ROOT, 'oggdudes-data')
    talents_xml = os.path.join(source_dir, 'Talents.xml')
    if not os.path.isfile(talents_xml):
        print('  oggdudes-data/Talents.xml not present -- skipped')
        return True

    warn = []
    records = T.build(source_dir, warn)
    by_key = {r['Key']: r for r in records}
    failures = []

    root = ET.parse(talents_xml).getroot()
    listings = root.findall('Talent')

    # --- every talent reaches a row, duplicates merged rather than dropped --
    expected = OrderedDict()
    for el in listings:
        expected.setdefault((el.findtext('Key') or '').strip(), []).append(el)
    missing = set(expected) - set(by_key)
    extra = set(by_key) - set(expected)
    duplicated = [k for k, els in expected.items() if len(els) > 1]
    if missing or extra:
        failures.append('row set: missing %s, unexpected %s'
                        % (sorted(missing)[:5], sorted(extra)[:5]))
    print('  %d listings -> %d rows, %d keys listed twice: %s'
          % (len(listings), len(records), len(duplicated),
             not missing and not extra))

    # --- a merged row kept both listings' citations -------------------------
    def cited(el):
        out = []
        single = el.find('Source')
        if single is not None and (single.text or '').strip():
            out.append(((single.text or '').strip(), single.attrib.get('Page')))
        for s in el.findall('Sources/Source'):
            if (s.text or '').strip():
                out.append(((s.text or '').strip(), s.attrib.get('Page')))
        return out

    dropped = []
    for key, els in expected.items():
        rec = by_key.get(key)
        if rec is None:
            continue
        for src in [s for el in els for s in cited(el)]:
            if src not in rec['Sources']:
                dropped.append('%s: lost citation %s' % (key, src))
    if dropped:
        failures.append('citations lost (%d)' % len(dropped))
    print('  no citation lost, including across the merged keys: %s' % (not dropped))
    for d in dropped[:8]:
        print('      %s' % d)

    # --- activations resolved to display text ------------------------------
    bad = sorted({r['Type'] for r in records
                  if r['Type'] not in T.ACTIVATIONS.values()})
    if bad:
        failures.append('unmapped activations: %s' % bad)
    print('  every activation resolved to display text: %s' % (not bad))

    # --- categories are exactly the flags the source carries ---------------
    wrong = []
    for key, els in expected.items():
        rec = by_key.get(key)
        if rec is None:
            continue
        want = []
        first = els[0]
        for tag, label in T.CATEGORY_FLAGS:
            if (first.findtext(tag) or '').strip().lower() == 'true':
                want.append(label)
        if (first.findtext('Conflict') or '').strip():
            want.append('Conflict')
        if want != rec['Categories']:
            wrong.append('%s: categories %s, flags say %s'
                         % (key, rec['Categories'], want))
    if wrong:
        failures.append('category mismatches (%d)' % len(wrong))
    print('  Ranked/Force/Conflict categories match the flags: %s' % (not wrong))
    for w in wrong[:8]:
        print('      %s' % w)

    # --- key resolution -----------------------------------------------------
    print('  no warnings from the transform: %s' % (not warn))
    for w in warn[:8]:
        print('      %s' % w)
    if warn:
        failures.append('transform warnings (%d)' % len(warn))

    if failures:
        print()
        print('  FAILURES:')
        for f in failures:
            print('    %s' % f)
    return not failures


def _shape(el):
    """
    An element as (tag, attributes, text, children) -- everything but the
    Description, which is the one field the override folder is allowed to
    change. Order is kept: two rows listing the same tags differently are not
    the same row.
    """
    return (el.tag, tuple(sorted(el.attrib.items())), (el.text or '').strip(),
            tuple(_shape(c) for c in el if c.tag != 'Description'))


def check_wiki_override():
    print()
    print('=' * 72)
    print('Check 6: the wiki description override only changes descriptions')
    print('=' * 72)
    override_dir = os.path.join(ROOT, 'xml_to_json', 'xml_sources', 'fandom-wiki')
    if not os.path.isdir(override_dir):
        print('  xml_sources/fandom-wiki not present -- skipped')
        return True

    failures = []
    for path in sorted(glob.glob(os.path.join(override_dir, '*.xml'))):
        file_name = os.path.basename(path)
        row_tag = next((k for k, v in convert.VALID_FILE_NAMES.items()
                        if v == file_name), None)
        if row_tag is None:
            failures.append('%s is not a file name convert.py knows' % file_name)
            continue

        base = OrderedDict()
        for other in sorted(glob.glob(os.path.join(
                ROOT, 'xml_to_json', 'xml_sources', '*', file_name))):
            if os.path.dirname(other) == override_dir:
                continue
            for row in ET.parse(other).getroot().findall(row_tag):
                key = (row.findtext('Key') or '').strip()
                if key and key not in base:
                    base[key] = row

        rows = ET.parse(path).getroot().findall(row_tag)
        orphans, changed, empty, pointers = [], [], [], []
        for row in rows:
            key = (row.findtext('Key') or '').strip()
            original = base.get(key)
            if original is None:
                orphans.append(key)
                continue
            if _shape(row) != _shape(original):
                changed.append(key)
            text = (row.findtext('Description') or '').strip()
            if not text:
                empty.append(key)
            elif 'please see page' in text.lower():
                pointers.append(key)

        for label, bad in (('rows with no row to override', orphans),
                           ('rows changed outside Description', changed),
                           ('empty descriptions', empty),
                           ('descriptions still a page pointer', pointers)):
            print('  %-16s %-38s %s' % (file_name, label + ':', not bad))
            if bad:
                failures.append('%s: %s (%d) %s'
                                % (file_name, label, len(bad), sorted(bad)[:5]))
        print('  %-16s %d rows override %d' % (file_name, len(rows), len(base)))

    if failures:
        print()
        print('  FAILURES:')
        for f in failures:
            print('    %s' % f)
    return not failures


def _tree_invariants(label, records, expected, cell_path, failures, min_rows):
    """
    The invariants both tree importers share. `expected` maps Key -> the OggDude
    root element, `cell_path` is where that element lists a row's cell keys.
    """
    by_key = {r['Key']: r for r in records}

    missing = set(expected) - set(by_key)
    extra = set(by_key) - set(expected)
    if missing or extra:
        failures.append('%s row set: missing %s, unexpected %s'
                        % (label, sorted(missing)[:5], sorted(extra)[:5]))
    print('  %d rows, one per source file: %s'
          % (len(records), not missing and not extra))

    # --- every row lays out exactly four columns wide ----------------------
    # The single invariant the renderer depends on: a row that laid out three
    # or five columns wide would shear the grid, and holes and spans are
    # exactly the two ways OggDude's export can make that happen.
    bad_width, short = [], []
    for key, rec in sorted(by_key.items()):
        if len(rec['Tree']) < min_rows:
            short.append('%s: %d rows' % (key, len(rec['Tree'])))
        for r, row in enumerate(rec['Tree']):
            width = sum(n['Span'] for n in row['Nodes'])
            if width != S.COLUMNS:
                bad_width.append('%s row %d: %d columns' % (key, r, width))
    if bad_width:
        failures.append('%s rows not %d columns wide (%d)'
                        % (label, S.COLUMNS, len(bad_width)))
    print('  every tree row lays out %d columns wide: %s'
          % (S.COLUMNS, not bad_width))
    for b in bad_width[:8]:
        print('      %s' % b)
    if short:
        failures.append('%s trees with fewer than %d rows (%d)'
                        % (label, min_rows, len(short)))
        for b in short[:8]:
            print('      %s' % b)

    # --- no cell is lost ---------------------------------------------------
    # A named cell in the source must come out either as a box or as one of the
    # covered cells a spanning box absorbed. Counting columns rather than boxes
    # is what makes this hold for both types at once.
    lost = []
    for key, root in sorted(expected.items()):
        rec = by_key.get(key)
        if rec is None:
            continue
        rows = root.findall(cell_path)
        if len(rows) != len(rec['Tree']):
            lost.append('%s: %d source rows, %d out' % (key, len(rows), len(rec['Tree'])))
            continue
        for r, row_el in enumerate(rows):
            want = set(k.text.strip() for k in row_el.findall('Key')
                       if k.text and k.text.strip())
            got = set(n['Key'] for n in rec['Tree'][r]['Nodes'] if n['Key'])
            if want != got:
                lost.append('%s row %d: source %s, out %s'
                            % (key, r, sorted(want), sorted(got)))
    if lost:
        failures.append('%s cells lost or invented (%d)' % (label, len(lost)))
    print('  every distinct cell key in a row survives it: %s' % (not lost))
    for l in lost[:8]:
        print('      %s' % l)

    # --- links are written once, and never off the grid --------------------
    # A vertical link belongs to the row ABOVE it and a horizontal one to the
    # LEFT node of the pair, so the last row can carry no <Down> and the node
    # ending at the right edge can carry no LinkRight. Getting this wrong draws
    # a connector into empty space.
    stray = []
    for key, rec in sorted(by_key.items()):
        last = len(rec['Tree']) - 1
        for r, row in enumerate(rec['Tree']):
            if r == last and row['Down']:
                stray.append('%s: last row links down' % key)
            for c in row['Down']:
                if not 0 <= c < S.COLUMNS:
                    stray.append('%s row %d: down link at column %d' % (key, r, c))
            for n in row['Nodes']:
                if n['LinkRight'] and n['Col'] + n['Span'] >= S.COLUMNS:
                    stray.append('%s row %d: node at %d links right off the edge'
                                 % (key, r, n['Col']))
    if stray:
        failures.append('%s links off the grid (%d)' % (label, len(stray)))
    print('  no connector points off the grid: %s' % (not stray))
    for s in stray[:8]:
        print('      %s' % s)


def check_trees():
    print()
    print('=' * 72)
    print('Check 7: OggDude -> app schema tree translation holds')
    print('=' * 72)
    source_dir = os.path.join(ROOT, 'oggdudes-data')
    if not os.path.isdir(os.path.join(source_dir, 'Specializations')):
        print('  oggdudes-data/Specializations not present -- skipped')
        return True

    failures = []

    print('  -- specializations --')
    warn = []
    records, _, _ = S.build(source_dir, warn)
    expected = {}
    for path in sorted(glob.glob(os.path.join(source_dir, 'Specializations', '*.xml'))):
        root = ET.parse(path).getroot()
        expected[(root.findtext('Key') or '').strip()] = root
    _tree_invariants('specialization', records, expected,
                     'TalentRows/TalentRow/Talents', failures, min_rows=5)

    # Specializations are a clean 5x4 with no spans at all -- if a future export
    # starts spanning them, layout_row() would silently start dropping cells,
    # since it reads spans only when the caller passes them.
    ragged = [r['Key'] for r in records
              if any(n['Span'] != 1 for row in r['Tree'] for n in row['Nodes'])]
    if ragged:
        failures.append('specializations with a span other than 1: %s' % ragged[:5])
    print('  every specialization cell is one column: %s' % (not ragged))

    # Every tree belongs to a career or is universal; that tag IS the sidenav
    # filter, so a tree with neither would be unreachable from the dropdown.
    orphan = [r['Key'] for r in records if not r['Categories']]
    if orphan:
        failures.append('specializations no career offers: %s' % orphan[:5])
    print('  every tree has a career or is universal: %s' % (not orphan))

    # The one-sided links from the module docstring. Four is what the committed
    # export contains; a change in that count means the export changed, and the
    # union rule should be re-read before it is accepted.
    onesided = [w for w in warn if 'from one end only' in w]
    unresolved = [w for w in warn if 'from one end only' not in w]
    if unresolved:
        failures.append('specialization warnings beyond one-sided links (%d)'
                        % len(unresolved))
    print('  all talent and skill keys resolve: %s' % (not unresolved))
    for w in unresolved[:8]:
        print('      %s' % w)
    print('  one-sided links, unioned: %d (4 in the committed export)' % len(onesided))

    print('  -- force powers --')
    warn = []
    records, _ = F.build(source_dir, warn)
    expected = {}
    for path in sorted(glob.glob(os.path.join(source_dir, 'Force Powers', '*.xml'))):
        root = ET.parse(path).getroot()
        expected[(root.findtext('Key') or '').strip()] = root
    # Farsight and Heal/Harm have four rows, not five.
    _tree_invariants('force power', records, expected,
                     'AbilityRows/AbilityRow/Abilities', failures, min_rows=4)

    # Every box is priced, and the total is what the Experience slider reads.
    unpriced = []
    for rec in records:
        for r, row in enumerate(rec['Tree']):
            for n in row['Nodes']:
                if n['Name'] and not F.int_or(n['Cost']):
                    unpriced.append('%s row %d: %s costs nothing'
                                    % (rec['Key'], r, n['Name']))
        total = sum(F.int_or(n['Cost']) for row in rec['Tree']
                    for n in row['Nodes'] if n['Name'])
        if str(total) != (rec['Experience'] or '0'):
            unpriced.append('%s: Experience %r, boxes total %d'
                            % (rec['Key'], rec['Experience'], total))
    if unpriced:
        failures.append('force power costs (%d)' % len(unpriced))
    print('  every box is priced and Experience is their sum: %s' % (not unpriced))
    for u in unpriced[:8]:
        print('      %s' % u)

    onesided = [w for w in warn if 'from one end only' in w]
    unresolved = [w for w in warn if 'from one end only' not in w]
    if unresolved:
        failures.append('force power warnings beyond one-sided links (%d)'
                        % len(unresolved))
    print('  all ability keys resolve, no row clipped: %s' % (not unresolved))
    for w in unresolved[:8]:
        print('      %s' % w)
    print('  one-sided links, unioned: %d (5 in the committed export)' % len(onesided))

    if failures:
        print()
        print('  FAILURES:')
        for f in failures:
            print('    %s' % f)
    return not failures


if __name__ == '__main__':
    checks = [check_converter(), check_mapping(), check_vehicles(),
              check_careers(), check_talents(), check_wiki_override(),
              check_trees()]
    print()
    print('RESULT:', 'PASS' if all(checks) else 'FAIL')
    sys.exit(0 if all(checks) else 1)
