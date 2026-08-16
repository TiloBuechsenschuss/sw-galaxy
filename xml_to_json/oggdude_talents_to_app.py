#!/usr/bin/env python3
"""
Convert OggDude's Talents.xml into the schema this app reads.

    python xml_to_json/oggdude_talents_to_app.py
    python xml_to_json/oggdude_talents_to_app.py --source oggdudes-data --dry-run

Reads  <source>/Talents.xml                          (one flat file, 604 rows)
Writes xml_to_json/xml_sources/oggdude/Talents.xml   (override with --out)

Then run convert.py to regenerate data/json/Talents.json.

Why this exists
---------------
Talents.xml is a single flat file, so unlike Species and Vehicles it could have
been copied straight across the way Armor and Gear are. It is not, for two
reasons -- one cosmetic and one that would have broken other tabs:

* ACTIVATION IS A CODE. <ActivationValue>taPassive is what OggDude's character
  builder switches on; the app would have shown "taPassive" in the Type column
  and in the Type dropdown. It becomes display text here (ACTIVATIONS below)
  rather than adding a mapping filter to SWApp.js, exactly the call
  oggdude_vehicles_to_app.py makes for the sr... sensor ranges.
* <Attributes> MEANS SOMETHING ELSE HERE. On a species it holds the starting
  wound threshold, strain threshold and experience, and fetchSource() copies
  those onto the row. Eight talents carry the same tag for what the talent
  GRANTS -- TOUGH has <WoundThreshold>2, FORCERAT has <ForceRating>1 -- so
  copying the file across would have put "2" in the Wound Thr. column of a
  talent and given the Talents tab a set of nonsense sliders. Dropped.

Ranked, ForceTalent and Conflict become <Categories>, the same tag vehicles use
for their Starship/Walker/... list: the app already renders that list under the
item name and already builds a multi-select from it, so the three flags are
filterable ("every ranked Force talent") for no new UI at all.

Data OggDude carries that the app schema has no place for, and which is
therefore dropped -- all of it drives the character builder rather than
describing the talent, and every one of them is spelled out in the talent's own
description anyway:

    Attributes, DieModifiers, SkillChars, SkillChoice, CharacteristicChoices,
    ChooseCareerSkills, ItemChanges, SelectedItem, RosterMods, JuryRigged,
    Rigger, Damage, ModPercentDiscount, LessStrain, AddlHP, HPPerItem,
    AddlCyber, SetForceRating

<Source Page="132"> is left exactly as it is: the converter's
expand_source_pages() rewrites it into <Source><Book/><Page/></Source>, which is
the shape the app renders.
"""
import argparse
import os
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict
from xml.sax.saxutils import escape

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_REL = os.path.join('xml_to_json', 'xml_sources', 'oggdude', 'Talents.xml')

# <ActivationValue>taPassive</ActivationValue> -> what the Type column shows.
# The wording is FFG's own: a talent is passive, or it is used as an action, a
# manoeuvre or an incidental.
ACTIVATIONS = OrderedDict([
    ('taPassive', 'Passive'),
    ('taActive', 'Active'),
    ('taAction', 'Action'),
    ('taManeuver', 'Maneuver'),
    ('taIncidental', 'Incidental'),
    ('taIncidentalOOT', 'Incidental (out of turn)'),
])

# Flag -> the category it becomes. Order is the order they are written, so every
# talent reads its tags the same way round.
CATEGORY_FLAGS = [
    # Ranked talents can be bought more than once, each rank stacking.
    ('Ranked', 'Ranked'),
    # A talent only a Force user can take.
    ('ForceTalent', 'Force'),
]


def text_of(el):
    return (el.text or '').strip() if el is not None else None


def collapse(s):
    """OggDude indents description blocks; keep the text, drop the padding."""
    if s is None:
        return None
    lines = [ln.strip() for ln in s.strip().splitlines()]
    return '\n'.join(ln for ln in lines if ln)


def activation(talent, key, warn):
    """The Type the app shows, out of OggDude's ta... code."""
    coded = text_of(talent.find('ActivationValue'))
    if not coded:
        warn.append('%s: no ActivationValue' % key)
        return None
    if coded not in ACTIVATIONS:
        warn.append('%s: unknown activation %r' % (key, coded))
        return None
    return ACTIVATIONS[coded]


def categories(talent):
    """The Ranked / Force / Conflict flags as the list vehicles use."""
    out = []
    for tag, label in CATEGORY_FLAGS:
        if (text_of(talent.find(tag)) or '').lower() == 'true':
            out.append(label)
    # <Conflict>1</Conflict>: using the talent costs Conflict, which is what
    # marks the dark side ones. The value is 1 on all fourteen that carry it, so
    # the tag alone says everything the number would.
    if text_of(talent.find('Conflict')):
        out.append('Conflict')
    return out


def transform(talent, warn):
    rec = OrderedDict()
    key = text_of(talent.find('Key'))
    rec['Key'] = key
    rec['Name'] = text_of(talent.find('Name'))

    # Left in OggDude's own shape -- expand_source_pages() in the converter
    # turns <Source Page="132">Book</Source> into <Source><Book/><Page/></Source>.
    rec['Sources'] = []
    single = talent.find('Source')
    if single is not None and text_of(single):
        rec['Sources'].append((text_of(single), single.attrib.get('Page')))
    for s in talent.findall('Sources/Source'):
        if text_of(s):
            rec['Sources'].append((text_of(s), s.attrib.get('Page')))

    rec['Type'] = activation(talent, key, warn)
    rec['Categories'] = categories(talent)
    rec['Description'] = collapse(talent.findtext('Description')) or ''
    return rec


def to_xml(rec, indent='  '):
    """Serialise one record in the app schema items.html binds against."""
    L = []
    p, q, r = indent, indent * 2, indent * 3
    L.append(p + '<Talent>')
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

    if rec['Type']:
        L.append(q + '<Type>%s</Type>' % escape(rec['Type']))

    if rec['Categories']:
        L.append(q + '<Categories>')
        for c in rec['Categories']:
            L.append(r + '<Category>%s</Category>' % escape(c))
        L.append(q + '</Categories>')

    if rec['Description']:
        L.append(q + '<Description>%s</Description>' % escape(rec['Description']))
    L.append(p + '</Talent>')
    return L


def merge_duplicate_keys(records, warn):
    """
    Fold the three talents OggDude's export lists twice into one row each,
    unioning their citations.

    FORCEWILL and WORKLIKECHARM are the same talent reprinted in a second book
    -- the two rows differ only in their Source and, for WORKLIKECHARM, in the
    capitalisation of "a" -- and ANALYZEDATA is written out twice verbatim. The
    converter's first-Key-wins merge would keep whichever came first and throw
    the other citation away, so "Force of Will" would vanish from the app the
    moment the Age of Rebellion line is switched off, despite also being in
    Collapse of the Republic. The first row still decides the name, type,
    categories and description; only the sources are added to.

    The two rows always disagree on the description, and that is the point
    rather than a problem: OggDude writes "Please see page 147 of the Age of
    Rebellion Core Rulebook for details", so each copy points at its own book.
    Only the mechanical fields are compared, and a disagreement there is
    reported rather than merged quietly, so a duplicate key that is really two
    different talents surfaces.
    """
    out = OrderedDict()
    for rec in records:
        first = out.get(rec['Key'])
        if first is None:
            out[rec['Key']] = rec
            continue
        for field in ('Type', 'Categories'):
            if first[field] != rec[field]:
                warn.append('%s: listed twice with a different %s -- kept the first'
                            % (rec['Key'], field))
        for src in rec['Sources']:
            if src not in first['Sources']:
                first['Sources'].append(src)
        print('  ~ %s: merged a second listing of %r' % (rec['Key'], rec['Name']))
    return list(out.values())


def build(source_dir, warn):
    root = ET.parse(os.path.join(source_dir, 'Talents.xml')).getroot()
    records = []
    for talent in root.findall('Talent'):
        rec = transform(talent, warn)
        if not rec['Key'] or not rec['Name']:
            warn.append('%r: no Key or no Name -- skipped' % rec['Name'])
            continue
        records.append(rec)
    records = merge_duplicate_keys(records, warn)
    # convert.py sorts again by source book; this keeps THIS file's diff stable.
    records.sort(key=lambda r: (r['Name'].strip().lower(), r['Key']))
    return records


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', default='oggdudes-data',
                    help='folder holding Talents.xml')
    ap.add_argument('--out', default=OUT_REL,
                    help='repo-relative path of the Talents.xml to write')
    ap.add_argument('--dry-run', action='store_true', help='write nothing')
    args = ap.parse_args(argv)

    source_dir = os.path.join(REPO_ROOT, args.source)
    if not os.path.isfile(os.path.join(source_dir, 'Talents.xml')):
        print('no Talents.xml under %s' % source_dir, file=sys.stderr)
        return 1

    warn = []
    records = build(source_dir, warn)
    print('transformed %d talent rows' % len(records))
    for label in ACTIVATIONS.values():
        n = sum(1 for r in records if r['Type'] == label)
        if n:
            print('  %-24s: %d' % (label, n))
    for _, label in CATEGORY_FLAGS + [(None, 'Conflict')]:
        print('  %-24s: %d' % (label,
                               sum(1 for r in records if label in r['Categories'])))
    for w in warn:
        print('  WARNING: %s' % w)

    lines = ['<?xml version="1.0" ?>', '<TalentList>']
    for rec in records:
        lines += to_xml(rec)
    lines.append('</TalentList>')
    text = '\n'.join(lines) + '\n'

    out = os.path.join(REPO_ROOT, args.out)
    if args.dry_run:
        print('--dry-run: would write %s (%d bytes)' % (out, len(text)))
        return 0
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8', newline='\r\n') as fh:
        fh.write(text)
    print('wrote %s' % out)
    print('now run: python xml_to_json/convert.py --only Talent')
    return 0


if __name__ == '__main__':
    sys.exit(main())
