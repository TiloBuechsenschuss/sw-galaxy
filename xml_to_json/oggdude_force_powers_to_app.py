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

from xml.sax.saxutils import escape

from oggdude_specializations_to_app import (
    COLUMNS, REPO_ROOT, collapse, layout_row, link_grid, load_key_names,
    read_directions, text_of, to_xml, write,
)

OUT_REL = os.path.join('xml_to_json', 'xml_sources', 'oggdude', 'ForcePowers.xml')
ABILITIES_OUT_REL = os.path.join('xml_to_json', 'xml_sources', 'oggdude',
                                 'ForceAbilities.xml')


def int_or(text, default=0):
    try:
        return int((text or '').strip())
    except ValueError:
        return default


def abilities_to_xml(rec, indent='  '):
    """
    One <ForceAbility> row for the lookup file. Kept in OggDude's own shape --
    <Source Page="280"> included, which the converter expands -- because nothing
    here needs reshaping: the app looks a row up by Key and reads its Name,
    Description and Sources.
    """
    L = []
    p, q, r = indent, indent * 2, indent * 3
    L.append(p + '<ForceAbility>')
    L.append(q + '<Key>%s</Key>' % escape(rec['Key']))
    L.append(q + '<Name>%s</Name>' % escape(rec['Name']))
    srcs = rec['Sources']
    if len(srcs) == 1:
        attr = ' Page="%s"' % escape(srcs[0][1], {'"': '&quot;'}) if srcs[0][1] else ''
        L.append(q + '<Source%s>%s</Source>' % (attr, escape(srcs[0][0])))
    elif len(srcs) > 1:
        L.append(q + '<Sources>')
        for b, pg in srcs:
            attr = ' Page="%s"' % escape(pg, {'"': '&quot;'}) if pg else ''
            L.append(r + '<Source%s>%s</Source>' % (attr, escape(b)))
        L.append(q + '</Sources>')
    if rec['Power']:
        L.append(q + '<Power>%s</Power>' % escape(rec['Power']))
    if rec['Description']:
        L.append(q + '<Description>%s</Description>' % escape(rec['Description']))
    L.append(p + '</ForceAbility>')
    return L


def build_abilities(source_dir, powers=None, warn=None):
    """
    The 177 force abilities as their own rows, so the app can look up what a box
    in a force tree is when it is hovered or opened.

    They are NOT embedded in the tree the way a node's name and cost are: an
    ability appears in several trees, the file is fetched once per tab rather
    than per row, and it is where wiki_descriptions.py writes the rules text.

    <Power> IS TAKEN FROM THE TREE THAT USES THE ABILITY, not from OggDude's own
    <Power> element, when the transformed powers are passed in. The element is
    unreliable in two ways and both matter here, because wiki_descriptions.py
    groups abilities by power and looks the power's page up by that name:

    * four rows have no <Power> at all -- BATMEDBASIC, BINDBASIC, BINDMASTERY
      and SENSECONTROL3;
    * the eight Foresee abilities spell it "Forsee", which is the KEY's spelling,
      not the power's name. The wiki page is "Foresee".

    Every one of the 177 is referenced by exactly one tree, so the trees settle
    both. A disagreement with OggDude's own element is reported, never silent.
    """
    owner = {}
    for power in (powers or []):
        for row in power['Tree']:
            for node in row['Nodes']:
                if node['Key']:
                    owner.setdefault(node['Key'], set()).add(power['Name'])
    root = ET.parse(os.path.join(source_dir, 'Force Abilities.xml')).getroot()
    records = []
    for el in root.iter('ForceAbility'):
        rec = OrderedDict()
        rec['Key'] = text_of(el.find('Key'))
        rec['Name'] = text_of(el.find('Name'))
        if not rec['Key'] or not rec['Name']:
            continue
        rec['Sources'] = []
        single = el.find('Source')
        if single is not None and text_of(single):
            rec['Sources'].append((text_of(single), single.attrib.get('Page')))
        for s in el.findall('Sources/Source'):
            if text_of(s):
                rec['Sources'].append((text_of(s), s.attrib.get('Page')))
        stated = text_of(el.find('Power'))
        trees = sorted(owner.get(rec['Key'], []))
        if trees:
            rec['Power'] = trees[0]
            if len(trees) > 1 and warn is not None:
                warn.append('%s: used by %d trees (%s) -- filed under the first'
                            % (rec['Key'], len(trees), ', '.join(trees)))
            if stated != rec['Power'] and warn is not None:
                warn.append('%s: <Power> says %r, the %s tree uses it'
                            % (rec['Key'], stated, rec['Power']))
        else:
            rec['Power'] = stated
            if powers and warn is not None:
                warn.append('%s: no tree uses it -- <Power> %r kept as it stands'
                            % (rec['Key'], stated))
        rec['Description'] = collapse(el.findtext('Description')) or ''
        records.append(rec)
    records.sort(key=lambda r: (r['Name'].strip().lower(), r['Key']))
    return records


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
    ap.add_argument('--abilities-out', default=ABILITIES_OUT_REL,
                    help='repo-relative path of the ForceAbilities.xml to write')
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

    rc = write(records, args.out, args.dry_run,
               'ForcePowerList', 'ForcePower', 'ForcePower')
    if rc:
        return rc

    # The companion lookup, written from the same source file in the same run so
    # the two can never drift apart.
    awarn = []
    abilities = build_abilities(source_dir, records, awarn)
    pointers = sum(1 for a in abilities if 'lease see page' in a['Description'])
    print()
    print('%d force abilities, %d of them still a page pointer'
          % (len(abilities), pointers))
    print('  filed under %d powers by the tree that uses them'
          % len(set(a['Power'] for a in abilities)))
    for w in awarn:
        print('  WARNING: %s' % w)
    lines = ['<?xml version="1.0" ?>', '<ForceAbilityList>']
    for rec in abilities:
        lines += abilities_to_xml(rec)
    lines.append('</ForceAbilityList>')
    text = '\n'.join(lines) + '\n'
    out = os.path.join(REPO_ROOT, args.abilities_out)
    if args.dry_run:
        print('--dry-run: would write %s (%d bytes)' % (out, len(text)))
        return 0
    with open(out, 'w', encoding='utf-8', newline='\r\n') as fh:
        fh.write(text)
    print('wrote %s' % out)
    print('now run: python xml_to_json/convert.py --only ForcePower --only ForceAbility')
    return 0


if __name__ == '__main__':
    sys.exit(main())
