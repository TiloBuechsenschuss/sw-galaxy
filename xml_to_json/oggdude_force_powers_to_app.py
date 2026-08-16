#!/usr/bin/env python3
"""
Convert OggDude's per-force-power XML into the schema this app reads.

    python xml_to_json/oggdude_force_powers_to_app.py
    python xml_to_json/oggdude_force_powers_to_app.py --source oggdudes-data --dry-run

Reads  <source>/Force Powers/*.xml     (one file per power)
       <source>/Force Abilities.xml    (Key -> display name)
Writes xml_to_json/xml_sources/oggdude/ForcePowers.xml   (override with --out)

Then run convert.py to regenerate data/json/ForcePowers.json.

Why this exists
---------------
A force power is the same kind of thing as a specialization -- a grid of boxes
with connectors -- so it shares the layout code in
oggdude_specializations_to_app.py rather than restating it. Read that module's
docstring first: the grid, the union rule for one-sided links, and the fact that
each connector is written out once (a vertical link on the row above it, a
horizontal one on the left node of the pair) are all defined there.

WHAT IS DIFFERENT ABOUT A FORCE POWER

* THE GRID IS RAGGED, where all 123 specializations are a clean 5x4. Farsight
  and Heal/Harm have four rows, not five, and every row carries an
  <AbilitySpan>: a box may be up to four columns wide, so the four cells of a
  row are not four boxes. Move's first row is one Basic Power spanning all four.
* COST IS PER BOX, not per row. A specialization row is flatly 5/10/15/20/25 XP;
  a force power prices each upgrade separately, from 5 to 25. That makes the
  total cost of a tree a real number that differs between powers -- 20 of them
  spanning 65 to 185 XP -- so it is written out as <Experience> and reuses the
  slider the app already has for it. On a specialization it would be the
  constant 300 and worth nothing.
* THERE IS A PREREQUISITE. 14 powers state a <MinForceRating>; the other six
  omit it, and it is NOT defaulted to 1 here, for the reason FreeRanks is not
  defaulted to 4 in the careers importer -- that number is a rules claim the
  source does not make.
* THE ABILITIES ARE NOT TALENTS. They resolve against Force Abilities.xml, 177
  rows keyed to a power ("Magnitude", "Control: Sense Thoughts"), not against
  Talents.xml. All 177 are used and every reference resolves.

Two export bugs, both handled by layout_row() in the specializations module and
both worth knowing because they are what its rules were written for:

* WARDE'S FORESIGHT writes an empty <Key /> in its first row with a span of 1
  and a cost of 5 XP. A cell with no ability is a hole in the grid whatever its
  span and cost claim, so it is drawn blank and its cost is not counted.
* ENDURE and CONJURE have a last row whose spans sum to two, not four -- Endure
  as <Span>0</Span><Span>2</Span>..., a blank column before a double-width
  Mastery. A span of 0 that nothing covers is a hole, not a missing box.

Nine horizontal links sit INSIDE a spanning box (Suppress, Seek, Imbue, Alter,
Ebb and Flow), joining a cell to itself. There is no gap to draw them in and
they are not drawn; nothing is lost, since the box is already one box.
"""
import argparse
import glob
import os
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict

from oggdude_specializations_to_app import (
    COLUMNS, REPO_ROOT, collapse, layout_row, link_grid, load_key_names,
    read_directions, text_of, to_xml, write,
)

OUT_REL = os.path.join('xml_to_json', 'xml_sources', 'oggdude', 'ForcePowers.xml')


def int_or(text, default=0):
    try:
        return int((text or '').strip())
    except ValueError:
        return default


def transform(power, ability_names, warn):
    rec = OrderedDict()
    key = text_of(power.find('Key'))
    rec['Key'] = key
    rec['Name'] = text_of(power.find('Name'))

    # Left in OggDude's own shape -- expand_source_pages() in the converter
    # turns <Source Page="283">Book</Source> into <Source><Book/><Page/></Source>.
    rec['Sources'] = []
    single = power.find('Source')
    if single is not None and text_of(single):
        rec['Sources'].append((text_of(single), single.attrib.get('Page')))
    for s in power.findall('Sources/Source'):
        if text_of(s):
            rec['Sources'].append((text_of(s), s.attrib.get('Page')))

    rec['MinForceRating'] = text_of(power.find('MinForceRating'))
    # A force power belongs to no career and has no career skills; both lists
    # stay empty so the tab's Category and Skill dropdowns simply do not appear.
    rec['Categories'] = []
    rec['Skills'] = []

    rows = power.findall('AbilityRows/AbilityRow')
    dirs_by_row = [read_directions(r, warn, '%s row %d' % (key, i))
                   for i, r in enumerate(rows)]
    down, right = link_grid(dirs_by_row, warn, key)

    rec['Tree'] = []
    abilities = []
    total = 0
    for r, row_el in enumerate(rows):
        keys = [text_of(k) for k in row_el.findall('Abilities/Key')]
        spans = [int_or(text_of(s)) for s in row_el.findall('AbilitySpan/Span')]
        costs = [text_of(c) for c in row_el.findall('Costs/Cost')]
        # OggDude truncates the filler entries on a short row -- Conjure's last
        # row has two keys for four cells -- so every list is padded back out.
        while len(keys) < COLUMNS:
            keys.append(None)
        while len(spans) < COLUMNS:
            spans.append(0)
        while len(costs) < COLUMNS:
            costs.append(None)
        for code in keys:
            if code and code not in ability_names:
                warn.append('%s: unknown ability key %r -- kept as the name' % (key, code))
        names = dict((c, ability_names.get(c, c)) for c in keys if c)
        nodes = layout_row(keys, spans, costs, names, right[r], key, r, warn)
        width = sum(n['Span'] for n in nodes)
        if width != COLUMNS:
            warn.append('%s: row %d lays out %d columns wide, not %d'
                        % (key, r, width, COLUMNS))
        for n in nodes:
            if n['Name']:
                total += int_or(n['Cost'])
                if n['Name'] not in abilities:
                    abilities.append(n['Name'])
        rec['Tree'].append({
            'Cost': None,          # priced per box, not per row
            'Nodes': nodes,
            'Down': [c for c in range(COLUMNS) if down[r][c]],
        })

    rec['Experience'] = str(total) if total else None
    # Reuses the <Talents> block the specializations importer writes, so the two
    # tabs share one column and one dropdown. An "ability" is what a force power
    # has instead of a talent; the shape is identical.
    rec['Talents'] = sorted(abilities, key=lambda s: s.lower())
    rec['Description'] = collapse(power.findtext('Description')) or ''
    return rec


def build(source_dir, warn):
    ability_names = load_key_names(os.path.join(source_dir, 'Force Abilities.xml'),
                                   'ForceAbility')
    records = []
    for path in sorted(glob.glob(os.path.join(source_dir, 'Force Powers', '*.xml'))):
        root = ET.parse(path).getroot()
        rec = transform(root, ability_names, warn)
        if not rec['Key'] or not rec['Name']:
            warn.append('%s: no Key or no Name -- skipped' % os.path.basename(path))
            continue
        records.append(rec)
    # convert.py sorts again by source book; this keeps THIS file's diff stable.
    records.sort(key=lambda r: (r['Name'].strip().lower(), r['Key']))
    return records, len(ability_names)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', default='oggdudes-data',
                    help='folder holding "Force Powers/" and "Force Abilities.xml"')
    ap.add_argument('--out', default=OUT_REL,
                    help='repo-relative path of the ForcePowers.xml to write')
    ap.add_argument('--dry-run', action='store_true', help='write nothing')
    args = ap.parse_args(argv)

    source_dir = os.path.join(REPO_ROOT, args.source)
    if not os.path.isdir(os.path.join(source_dir, 'Force Powers')):
        print('no "Force Powers/" folder under %s' % source_dir, file=sys.stderr)
        return 1

    warn = []
    records, n_abilities = build(source_dir, warn)
    print('lookup: %d force abilities' % n_abilities)
    print('transformed %d force power rows' % len(records))
    nodes = sum(len(row['Nodes']) for r in records for row in r['Tree'])
    filled = sum(1 for r in records for row in r['Tree']
                 for n in row['Nodes'] if n['Name'])
    print('  tree rows            : %d' % sum(len(r['Tree']) for r in records))
    print('  ability boxes        : %d of %d cells' % (filled, nodes))
    print('  spanning boxes       : %d' % sum(1 for r in records for row in r['Tree']
                                              for n in row['Nodes']
                                              if n['Name'] and n['Span'] > 1))
    print('  distinct abilities   : %d'
          % len(set(n for r in records for n in r['Talents'])))
    print('  vertical links       : %d' % sum(len(row['Down']) for r in records
                                              for row in r['Tree']))
    print('  horizontal links     : %d' % sum(1 for r in records for row in r['Tree']
                                              for n in row['Nodes'] if n['LinkRight']))
    print('  stating a min rating : %d' % sum(1 for r in records if r['MinForceRating']))
    print('  total XP, low to high: %s'
          % ', '.join(sorted(set(r['Experience'] for r in records if r['Experience']),
                             key=int)))
    for w in warn:
        print('  WARNING: %s' % w)

    return write(records, args.out, args.dry_run,
                 'ForcePowerList', 'ForcePower', 'ForcePower')


if __name__ == '__main__':
    sys.exit(main())
