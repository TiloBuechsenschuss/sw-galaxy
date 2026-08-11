#!/usr/bin/env python3
"""
Convert OggDude's per-career XML into the schema this app reads.

    python xml_to_json/oggdude_careers_to_app.py
    python xml_to_json/oggdude_careers_to_app.py --source oggdudes-data --dry-run

Reads  <source>/Careers/*.xml           (one file per career, OggDude's format)
       <source>/Skills.xml              (Key -> display name)
       <source>/Specializations/*.xml   (Key -> display name)
Writes xml_to_json/xml_sources/oggdude/Careers.xml   (override with --out)

Then run convert.py (or convert.php) to regenerate data/json/Careers.json.

Why this exists
---------------
Same reason as oggdude_species_to_app.py: convert.php does a mechanical
XML->JSON conversion and never reshapes anything, so a source file has to
ALREADY be in the schema the app reads. OggDude ships 20 separate career files
that have to be merged into one, and both lists inside them are key references:

* CAREER SKILLS ARE KEYS. <CareerSkills><Key>ASTRO has to become "Astrogation"
  out of Skills.xml -- 146 references covering all 35 skills in the game --
  exactly like species skills and vehicle weapons. They are written as
  <Skills><Skill><Name>, the shape fetchSource() already unwraps for species.
* SPECIALIZATIONS ARE KEYS TOO. <Specializations><Key>DRIVER becomes "Driver"
  out of the 123 files under Specializations/ (118 references, 112 distinct --
  a handful are shared by two careers). Only the name is taken: the
  specialisation itself is a 4x5 talent TREE with directional links between its
  nodes, which is a renderer this app does not have. Listing which
  specialisations a career opens is still the single most useful thing about a
  career, so the names are carried and the trees are not.

Every key in the current data resolves; an unknown one is kept as its own name
and reported, the same call transform_weapon() makes in the vehicle importer.

Data OggDude carries that the app schema has no place for, and which is
therefore dropped:

* <Attributes> ZEROES AND <Requirement>. Seven Force careers carry a full
  attribute block that is all zeros except ForceRating, plus an empty
  <Requirement>. Only a non-zero ForceRating is written out -- that is the one
  thing a career actually grants, and fetchSource() already copies
  Attributes/ForceRating onto the row for the Force column. Those seven also get
  a <Categories><Category>Force, the same tag the talent importer writes, which
  is what makes "Force career" a filter rather than just a column.

<FreeRanks> is carried through as OggDude wrote it, which means it is present on
eight rows and absent on twelve: OggDude only states it when it differs from the
four free career-skill ranks the Edge of the Empire and Age of Rebellion careers
grant. It is NOT defaulted to 4 here -- inventing a number the source does not
state would put a rules claim in the data. The template shows the line only for
the rows that carry one.

<Source Page="64"> is left exactly as it is: the converter's
expand_source_pages() rewrites it into <Source><Book/><Page/></Source>, which is
the shape the app renders.
"""
import argparse
import glob
import os
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict
from xml.sax.saxutils import escape

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_REL = os.path.join('xml_to_json', 'xml_sources', 'oggdude', 'Careers.xml')


def load_key_names(path, item_tag):
    """Key -> display name, the same helper the species importer uses."""
    root = ET.parse(path).getroot()
    out = {}
    for el in root.iter(item_tag):
        k, n = el.findtext('Key'), el.findtext('Name')
        if k and n:
            out[k.strip()] = n.strip()
    return out


def load_folder_names(folder):
    """
    Key -> display name for a type OggDude ships one file per row, which is how
    Specializations/ is laid out. The root element of each file is the row.
    """
    out = {}
    for path in sorted(glob.glob(os.path.join(folder, '*.xml'))):
        root = ET.parse(path).getroot()
        k, n = root.findtext('Key'), root.findtext('Name')
        if k and n:
            out[k.strip()] = n.strip()
    return out


def text_of(el):
    return (el.text or '').strip() if el is not None else None


def collapse(s):
    """OggDude indents description blocks; keep the text, drop the padding."""
    if s is None:
        return None
    lines = [ln.strip() for ln in s.strip().splitlines()]
    return '\n'.join(ln for ln in lines if ln)


def resolve(keys, names, key, what, warn):
    """Key list -> display names, keeping and reporting anything unknown."""
    out = []
    for k in keys:
        if not k:
            continue
        if k not in names:
            warn.append('%s: unknown %s key %r -- kept as the name' % (key, what, k))
        out.append(names.get(k, k))
    return out


def transform(car, skill_names, spec_names, warn):
    rec = OrderedDict()
    key = text_of(car.find('Key'))
    rec['Key'] = key
    rec['Name'] = text_of(car.find('Name'))

    # Left in OggDude's own shape -- expand_source_pages() in the converter
    # turns <Source Page="64">Book</Source> into <Source><Book/><Page/></Source>.
    rec['Sources'] = []
    single = car.find('Source')
    if single is not None and text_of(single):
        rec['Sources'].append((text_of(single), single.attrib.get('Page')))
    for s in car.findall('Sources/Source'):
        if text_of(s):
            rec['Sources'].append((text_of(s), s.attrib.get('Page')))

    rec['Skills'] = resolve([text_of(k) for k in car.findall('CareerSkills/Key')],
                            skill_names, key, 'skill', warn)
    rec['Specializations'] = resolve(
        [text_of(k) for k in car.findall('Specializations/Key')],
        spec_names, key, 'specialization', warn)

    # Only a non-zero ForceRating: the rest of the block is zeros.
    force = text_of(car.find('Attributes/ForceRating'))
    rec['ForceRating'] = force if force and force != '0' else None
    # The same <Categories> tag talents carry, and for the same reason: the app
    # already renders that list under the name and already builds a multi-select
    # from it, so "Force career" is filterable for no new UI. The rating itself
    # stays in its own field, where the sortable Force column reads it.
    rec['Categories'] = ['Force'] if rec['ForceRating'] else []
    rec['FreeRanks'] = text_of(car.find('FreeRanks'))

    rec['Description'] = collapse(car.findtext('Description')) or ''
    return rec


def to_xml(rec, indent='  '):
    """Serialise one record in the app schema items.html binds against."""
    L = []
    p, q, r = indent, indent * 2, indent * 3
    L.append(p + '<Career>')
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

    # <Skills><Skill><Name> is the species shape, so fetchSource() unwraps these
    # without a line of new code.
    if rec['Skills']:
        L.append(q + '<Skills>')
        for name in rec['Skills']:
            L.append(r + '<Skill>')
            L.append(r + indent + '<Name>%s</Name>' % escape(name))
            L.append(r + '</Skill>')
        L.append(q + '</Skills>')

    if rec['Specializations']:
        L.append(q + '<Specializations>')
        for name in rec['Specializations']:
            L.append(r + '<Specialization>%s</Specialization>' % escape(name))
        L.append(q + '</Specializations>')

    if rec['Categories']:
        L.append(q + '<Categories>')
        for c in rec['Categories']:
            L.append(r + '<Category>%s</Category>' % escape(c))
        L.append(q + '</Categories>')

    if rec['ForceRating']:
        L.append(q + '<Attributes>')
        L.append(r + '<ForceRating>%s</ForceRating>' % escape(rec['ForceRating']))
        L.append(q + '</Attributes>')
    if rec['FreeRanks']:
        L.append(q + '<FreeRanks>%s</FreeRanks>' % escape(rec['FreeRanks']))

    if rec['Description']:
        L.append(q + '<Description>%s</Description>' % escape(rec['Description']))
    L.append(p + '</Career>')
    return L


def build(source_dir, warn):
    skill_names = load_key_names(os.path.join(source_dir, 'Skills.xml'), 'Skill')
    spec_names = load_folder_names(os.path.join(source_dir, 'Specializations'))
    records = []
    for path in sorted(glob.glob(os.path.join(source_dir, 'Careers', '*.xml'))):
        root = ET.parse(path).getroot()
        rec = transform(root, skill_names, spec_names, warn)
        if not rec['Key'] or not rec['Name']:
            warn.append('%s: no Key or no Name -- skipped' % os.path.basename(path))
            continue
        records.append(rec)
    # convert.py sorts again by source book; this keeps THIS file's diff stable.
    records.sort(key=lambda r: (r['Name'].strip().lower(), r['Key']))
    return records, len(skill_names), len(spec_names)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', default='oggdudes-data',
                    help='folder holding Careers/, Skills.xml, Specializations/')
    ap.add_argument('--out', default=OUT_REL,
                    help='repo-relative path of the Careers.xml to write')
    ap.add_argument('--dry-run', action='store_true', help='write nothing')
    args = ap.parse_args(argv)

    source_dir = os.path.join(REPO_ROOT, args.source)
    if not os.path.isdir(os.path.join(source_dir, 'Careers')):
        print('no Careers/ folder under %s' % source_dir, file=sys.stderr)
        return 1

    warn = []
    records, n_skills, n_specs = build(source_dir, warn)
    print('lookup: %d skills, %d specializations' % (n_skills, n_specs))
    print('transformed %d career rows' % len(records))
    print('  career skills resolved  : %d' % sum(len(r['Skills']) for r in records))
    print('  specializations resolved: %d'
          % sum(len(r['Specializations']) for r in records))
    print('  with a Force rating     : %d' % sum(1 for r in records if r['ForceRating']))
    print('  stating their free ranks: %d' % sum(1 for r in records if r['FreeRanks']))
    for w in warn:
        print('  WARNING: %s' % w)

    lines = ['<?xml version="1.0" ?>', '<CareerList>']
    for rec in records:
        lines += to_xml(rec)
    lines.append('</CareerList>')
    text = '\n'.join(lines) + '\n'

    out = os.path.join(REPO_ROOT, args.out)
    if args.dry_run:
        print('--dry-run: would write %s (%d bytes)' % (out, len(text)))
        return 0
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8', newline='\r\n') as fh:
        fh.write(text)
    print('wrote %s' % out)
    print('now run: python xml_to_json/convert.py --only Career')
    return 0


if __name__ == '__main__':
    sys.exit(main())
