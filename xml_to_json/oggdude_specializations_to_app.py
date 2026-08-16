#!/usr/bin/env python3
"""
Convert OggDude's per-specialization XML into the schema this app reads.

    python xml_to_json/oggdude_specializations_to_app.py
    python xml_to_json/oggdude_specializations_to_app.py --source oggdudes-data --dry-run

Reads  <source>/Specializations/*.xml   (one file per specialization)
       <source>/Talents.xml             (Key -> display name)
       <source>/Skills.xml              (Key -> display name)
       <source>/Careers/*.xml           (reverse lookup: who offers this tree)
Writes xml_to_json/xml_sources/oggdude/Specializations.xml   (override with --out)

Then run convert.py to regenerate data/json/Specializations.json.

Why this exists
---------------
The same reason as every other oggdude_*_to_app.py: convert.py is a mechanical
XML->JSON conversion, so a source file must ALREADY be in the app's schema. On
top of merging 123 files and resolving key references, this one has to turn a
TREE into something a template can render, which the other importers never had
to do. The layout rules it encodes are below; they were derived by a census of
all 123 files, and oggdude_force_powers_to_app.py encodes the same ones.

THE GRID. Every specialization is exactly 5 rows of 4 talents, and the rows cost
5/10/15/20/25 XP -- all 123, with no exceptions, so nothing here is defensive
about ragged trees. Force powers are the ragged ones.

LINKS ARE UNDIRECTED, AND THE EXPORT IS NOT ALWAYS SYMMETRIC. OggDude writes
four booleans per cell (Up/Down/Left/Right). A connector between two boxes is
therefore stated twice -- once from each end -- and four of the 615 rows state
it only once (Ambassador, Protector, Scoundrel, Sharpshooter). Those are export
slips, not one-way links: the printed trees draw a line or they do not.

** A link is emitted when EITHER end declares it. ** The union is what the force
power trees prove is right -- under the intersection two nodes in Enhance and
Farsight become unreachable from row 0, which no printed tree does. Every
one-sided flag is reported so the count stays visible if a future export changes.

WHAT IS EMITTED. Each connector is written ONCE, from the end that owns it, so
the renderer never has to de-duplicate:

* a vertical link is a <Link><Col>n</Col><Down>true</Down> on the row ABOVE it.
  Per column, not per node -- a node spanning several columns can be joined
  downward in each of them (Force powers do exactly that), and collapsing them
  to one bar under the middle of the box would drop connectors that are printed.
* a horizontal link is <LinkRight>true</LinkRight> on the LEFT node of the pair.

TALENT AND SKILL KEYS ARE RESOLVED to display names, the way career skills and
vehicle weapons are: the template renders {{node.Name}}, so an unresolved key
would show as literal GRIT. All 591 distinct talent keys resolve today.

CAREERS ARE A REVERSE LOOKUP. A specialization does not name its career; the
career names its specializations. Reading Careers/*.xml backwards gives each
tree the careers that open it, and those names are written as <Categories>, the
tag the app already builds its multi-select from -- so "show me the Guardian
trees" is a filter for no new UI, exactly the trick oggdude_careers_to_app.py
plays with 'Force'. The 11 <Universal>true</Universal> trees, which every career
may take, get a 'Universal' category the same way.

Dropped, as character-builder data with nowhere to go in the app schema:
<AddlCareerSkills> (empty on 9 of the 10 rows that have it, and a "choose one
Knowledge skill" instruction on the tenth), and the <Attributes>/<Requirements>
blocks, which are all zeros on every one of the 123 files.
"""
import argparse
import glob
import os
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict
from xml.sax.saxutils import escape

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_REL = os.path.join('xml_to_json', 'xml_sources', 'oggdude', 'Specializations.xml')

COLUMNS = 4


def load_key_names(path, item_tag):
    """Key -> display name, the same helper the careers importer uses."""
    root = ET.parse(path).getroot()
    out = {}
    for el in root.iter(item_tag):
        k, n = el.findtext('Key'), el.findtext('Name')
        if k and n:
            out[k.strip()] = n.strip()
    return out


def load_career_specializations(folder):
    """
    Specialization key -> the careers offering it, read out of the career files.
    A specialization file never names its career, so this is the only direction
    the link exists in. A dozen trees belong to two careers.
    """
    out = {}
    for path in sorted(glob.glob(os.path.join(folder, '*.xml'))):
        root = ET.parse(path).getroot()
        career = (root.findtext('Name') or '').strip()
        if not career:
            continue
        for k in root.findall('Specializations/Key'):
            key = (k.text or '').strip()
            if key:
                out.setdefault(key, []).append(career)
    return out


def text_of(el):
    return (el.text or '').strip() if el is not None else None


def collapse(s):
    """OggDude indents description blocks; keep the text, drop the padding."""
    if s is None:
        return None
    lines = [ln.strip() for ln in s.strip().splitlines()]
    return '\n'.join(ln for ln in lines if ln)


def read_directions(row_el, warn, where):
    """
    The four booleans per cell, padded to COLUMNS. A missing <Direction> means
    no links, which is what the empty <Direction /> elements in the force power
    export say explicitly.
    """
    dirs = []
    holder = row_el.find('Directions')
    for d in (holder.findall('Direction') if holder is not None else []):
        dirs.append(dict((c.tag, (c.text or '').strip() == 'true') for c in d))
    if len(dirs) > COLUMNS:
        warn.append('%s: %d <Direction> entries for %d columns -- extras ignored'
                    % (where, len(dirs), COLUMNS))
        dirs = dirs[:COLUMNS]
    while len(dirs) < COLUMNS:
        dirs.append({})
    return dirs


def link_grid(dirs_by_row, warn, key):
    """
    Fold OggDude's two statements of each connector into one, and report the
    ones stated only from one end.

    Returns (down, right): down[r][c] is a link from row r column c to the row
    below it; right[r][c] joins column c to column c+1 in row r. See the module
    docstring on why this is the union.
    """
    n = len(dirs_by_row)
    down = [[False] * COLUMNS for _ in range(n)]
    right = [[False] * COLUMNS for _ in range(n)]
    for r in range(n):
        for c in range(COLUMNS):
            here = dirs_by_row[r][c]
            if r + 1 < n:
                below = dirs_by_row[r + 1][c].get('Up', False)
                if here.get('Down', False) != below:
                    warn.append('%s: row %d col %d states a vertical link from one '
                                'end only -- linked' % (key, r, c))
                down[r][c] = here.get('Down', False) or below
            elif here.get('Down', False):
                warn.append('%s: row %d col %d links down off the bottom of the '
                            'tree -- dropped' % (key, r, c))
            if c + 1 < COLUMNS:
                nxt = dirs_by_row[r][c + 1].get('Left', False)
                if here.get('Right', False) != nxt:
                    warn.append('%s: row %d col %d states a horizontal link from one '
                                'end only -- linked' % (key, r, c))
                right[r][c] = here.get('Right', False) or nxt
            elif here.get('Right', False):
                warn.append('%s: row %d col %d links right off the edge of the '
                            'tree -- dropped' % (key, r, c))
    return down, right


def layout_row(keys, spans, costs, names, right_row, key, r, warn):
    """
    One row of the grid, as the renderer wants it.

    `spans` is OggDude's per-cell colspan, and is None for specializations,
    which have no spanning nodes. Its rules, from the force power export:

    * a cell with a span of N draws one box N columns wide and the N-1 cells it
      covers are dropped -- they repeat the same key as filler;
    * a cell with a span of 0 that nothing covers is a genuine HOLE in the grid.
      Endure's last row is <Span>0</Span><Span>2</Span><Span>0</Span><Span>0</Span>:
      a blank, then a double-width Mastery, then a blank. It still has to occupy
      a column or the row would come out three wide;
    * a cell with no key is a hole too, whatever its span says. Warde's Foresight
      writes an empty <Key /> with a span of 1 and a cost of 5.

    Every row therefore comes out exactly COLUMNS wide, counting spans.
    """
    nodes = []
    c = 0
    while c < COLUMNS:
        span = spans[c] if spans else 1
        name = names.get(keys[c]) if c < len(keys) and keys[c] else None
        if span < 1 or not name:
            # A hole: one blank column, so the row keeps its width.
            nodes.append({'Col': c, 'Span': 1, 'Key': None, 'Name': None,
                          'Cost': None, 'LinkRight': False})
            c += 1
            continue
        if c + span > COLUMNS:
            warn.append('%s: row %d col %d spans %d past the edge -- clipped'
                        % (key, r, c, span))
            span = COLUMNS - c
        nodes.append({
            'Col': c,
            'Span': span,
            'Key': keys[c],
            'Name': name,
            'Cost': costs[c] if costs else None,
            # The connector to the node on its right, which is the one at the
            # box's right edge. A horizontal link INSIDE a spanning box joins a
            # cell to itself -- nine of those exist, all in force powers, and
            # they are silently not drawn because there is no gap to draw in.
            'LinkRight': right_row[c + span - 1] if c + span - 1 < COLUMNS else False,
        })
        c += span
    return nodes


def transform(spec, talent_names, skill_names, careers_by_spec, warn):
    rec = OrderedDict()
    key = text_of(spec.find('Key'))
    rec['Key'] = key
    rec['Name'] = text_of(spec.find('Name'))

    # Left in OggDude's own shape -- expand_source_pages() in the converter
    # turns <Source Page="81">Book</Source> into <Source><Book/><Page/></Source>.
    rec['Sources'] = []
    single = spec.find('Source')
    if single is not None and text_of(single):
        rec['Sources'].append((text_of(single), single.attrib.get('Page')))
    for s in spec.findall('Sources/Source'):
        if text_of(s):
            rec['Sources'].append((text_of(s), s.attrib.get('Page')))

    # <Skills><Skill><Name> is the shape species and careers already use, so
    # fetchSource() unwraps it and the shared "Skill" dropdown picks it up.
    rec['Skills'] = []
    for k in spec.findall('CareerSkills/Key'):
        code = text_of(k)
        if not code:
            continue
        if code not in skill_names:
            warn.append('%s: unknown skill key %r -- kept as the name' % (key, code))
        rec['Skills'].append(skill_names.get(code, code))

    # The careers that open this tree, plus Universal, as <Categories>: the tag
    # the app's multi-select is already built from.
    rec['Categories'] = list(careers_by_spec.get(key, []))
    if text_of(spec.find('Universal')) == 'true':
        rec['Categories'].append('Universal')

    rows = spec.findall('TalentRows/TalentRow')
    dirs_by_row = [read_directions(r, warn, '%s row %d' % (key, i))
                   for i, r in enumerate(rows)]
    down, right = link_grid(dirs_by_row, warn, key)

    rec['Tree'] = []
    talents = []
    for r, row_el in enumerate(rows):
        keys = [text_of(k) for k in row_el.findall('Talents/Key')]
        while len(keys) < COLUMNS:
            keys.append(None)
        for code in keys:
            if code and code not in talent_names:
                warn.append('%s: unknown talent key %r -- kept as the name' % (key, code))
        names = dict((c, talent_names.get(c, c)) for c in keys if c)
        cost = text_of(row_el.find('Cost'))
        nodes = layout_row(keys, None, None, names, right[r], key, r, warn)
        for n in nodes:
            if n['Name'] and n['Name'] not in talents:
                talents.append(n['Name'])
        rec['Tree'].append({
            'Cost': cost,
            'Nodes': nodes,
            # Only the row above owns a vertical connector, so it is written once.
            'Down': [c for c in range(COLUMNS) if down[r][c]],
        })

    # The distinct talents in the tree, sorted, for the "which tree teaches
    # this?" dropdown. A talent appearing twice in one tree is common.
    rec['Talents'] = sorted(talents, key=lambda s: s.lower())
    rec['Description'] = collapse(spec.findtext('Description')) or ''
    return rec


def to_xml(rec, row_tag='Specialization', indent='  '):
    """Serialise one record in the app schema items.html binds against."""
    L = []
    p, q, r, s = indent, indent * 2, indent * 3, indent * 4
    L.append(p + '<%s>' % row_tag)
    L.append(q + '<Key>%s</Key>' % escape(rec['Key']))
    L.append(q + '<Name>%s</Name>' % escape(rec['Name']))

    def src_line(pad, book, page):
        # Left in OggDude's Page-as-attribute shape; the converter expands it.
        attr = ' Page="%s"' % escape(page, {'"': '&quot;'}) if page else ''
        return pad + '<Source%s>%s</Source>' % (attr, escape(book))

    srcs = rec['Sources']
    if len(srcs) == 1:
        L.append(src_line(q, *srcs[0]))
    elif len(srcs) > 1:
        L.append(q + '<Sources>')
        for b, pg in srcs:
            L.append(src_line(r, b, pg))
        L.append(q + '</Sources>')

    if rec.get('MinForceRating'):
        L.append(q + '<MinForceRating>%s</MinForceRating>' % escape(rec['MinForceRating']))
    if rec.get('Experience'):
        L.append(q + '<Experience>%s</Experience>' % escape(rec['Experience']))

    if rec.get('Skills'):
        L.append(q + '<Skills>')
        for name in rec['Skills']:
            L.append(r + '<Skill>')
            L.append(r + indent + '<Name>%s</Name>' % escape(name))
            L.append(r + '</Skill>')
        L.append(q + '</Skills>')

    if rec['Categories']:
        L.append(q + '<Categories>')
        for c in rec['Categories']:
            L.append(r + '<Category>%s</Category>' % escape(c))
        L.append(q + '</Categories>')

    # Every repeated element below carries children on purpose. convert.py's
    # drop_duplicate_siblings() collapses repeated CHILDLESS siblings whose text
    # matches, so a bare <Down>2</Down><Down>2</Down> or an empty <Node /> would
    # silently lose entries. <Col> is always written for the same reason: it
    # keeps two otherwise identical cells distinct, and the renderer wants it.
    if rec['Tree']:
        L.append(q + '<Tree>')
        for row in rec['Tree']:
            L.append(r + '<Row>')
            if row['Cost']:
                L.append(s + '<Cost>%s</Cost>' % escape(row['Cost']))
            L.append(s + '<Nodes>')
            for n in row['Nodes']:
                L.append(s + indent + '<Node>')
                pad = s + indent * 2
                L.append(pad + '<Col>%d</Col>' % n['Col'])
                L.append(pad + '<Span>%d</Span>' % n['Span'])
                if n['Name']:
                    L.append(pad + '<Key>%s</Key>' % escape(n['Key']))
                    L.append(pad + '<Name>%s</Name>' % escape(n['Name']))
                if n['Cost']:
                    L.append(pad + '<Cost>%s</Cost>' % escape(n['Cost']))
                if n['LinkRight']:
                    L.append(pad + '<LinkRight>true</LinkRight>')
                L.append(s + indent + '</Node>')
            L.append(s + '</Nodes>')
            for c in row['Down']:
                L.append(s + '<Down>')
                L.append(s + indent + '<Col>%d</Col>' % c)
                L.append(s + '</Down>')
            L.append(r + '</Row>')
        L.append(q + '</Tree>')

    if rec['Talents']:
        L.append(q + '<Talents>')
        for name in rec['Talents']:
            L.append(r + '<Talent>')
            L.append(r + indent + '<Name>%s</Name>' % escape(name))
            L.append(r + '</Talent>')
        L.append(q + '</Talents>')

    if rec['Description']:
        L.append(q + '<Description>%s</Description>' % escape(rec['Description']))
    L.append(p + '</%s>' % row_tag)
    return L


def build(source_dir, warn):
    talent_names = load_key_names(os.path.join(source_dir, 'Talents.xml'), 'Talent')
    skill_names = load_key_names(os.path.join(source_dir, 'Skills.xml'), 'Skill')
    careers_by_spec = load_career_specializations(os.path.join(source_dir, 'Careers'))
    records = []
    for path in sorted(glob.glob(os.path.join(source_dir, 'Specializations', '*.xml'))):
        root = ET.parse(path).getroot()
        rec = transform(root, talent_names, skill_names, careers_by_spec, warn)
        if not rec['Key'] or not rec['Name']:
            warn.append('%s: no Key or no Name -- skipped' % os.path.basename(path))
            continue
        if not rec['Categories']:
            warn.append('%s: no career offers it and it is not universal' % rec['Key'])
        records.append(rec)
    # convert.py sorts again by source book; this keeps THIS file's diff stable.
    records.sort(key=lambda r: (r['Name'].strip().lower(), r['Key']))
    return records, len(talent_names), len(skill_names)


def report(records, warn, n_talents, n_skills):
    print('lookup: %d talents, %d skills' % (n_talents, n_skills))
    print('transformed %d specialization rows' % len(records))
    nodes = sum(len(row['Nodes']) for r in records for row in r['Tree'])
    filled = sum(1 for r in records for row in r['Tree']
                 for n in row['Nodes'] if n['Name'])
    print('  tree rows            : %d' % sum(len(r['Tree']) for r in records))
    print('  talent nodes         : %d of %d cells' % (filled, nodes))
    print('  distinct talents used: %d'
          % len(set(n for r in records for n in r['Talents'])))
    print('  vertical links       : %d' % sum(len(row['Down']) for r in records
                                              for row in r['Tree']))
    print('  horizontal links     : %d' % sum(1 for r in records for row in r['Tree']
                                              for n in row['Nodes'] if n['LinkRight']))
    print('  career skills        : %d' % sum(len(r['Skills']) for r in records))
    print('  universal trees      : %d'
          % sum(1 for r in records if 'Universal' in r['Categories']))
    for w in warn:
        print('  WARNING: %s' % w)


def write(records, out_rel, dry_run, root_tag, row_tag, next_type):
    lines = ['<?xml version="1.0" ?>', '<%s>' % root_tag]
    for rec in records:
        lines += to_xml(rec, row_tag)
    lines.append('</%s>' % root_tag)
    text = '\n'.join(lines) + '\n'

    out = os.path.join(REPO_ROOT, out_rel)
    if dry_run:
        print('--dry-run: would write %s (%d bytes)' % (out, len(text)))
        return 0
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8', newline='\r\n') as fh:
        fh.write(text)
    print('wrote %s' % out)
    print('now run: python xml_to_json/convert.py --only %s' % next_type)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', default='oggdudes-data',
                    help='folder holding Specializations/, Talents.xml, Skills.xml, Careers/')
    ap.add_argument('--out', default=OUT_REL,
                    help='repo-relative path of the Specializations.xml to write')
    ap.add_argument('--dry-run', action='store_true', help='write nothing')
    args = ap.parse_args(argv)

    source_dir = os.path.join(REPO_ROOT, args.source)
    if not os.path.isdir(os.path.join(source_dir, 'Specializations')):
        print('no Specializations/ folder under %s' % source_dir, file=sys.stderr)
        return 1

    warn = []
    records, n_talents, n_skills = build(source_dir, warn)
    report(records, warn, n_talents, n_skills)
    return write(records, args.out, args.dry_run,
                 'SpecializationList', 'Specialization', 'Specialization')


if __name__ == '__main__':
    sys.exit(main())
