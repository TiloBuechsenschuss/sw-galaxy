#!/usr/bin/env python3
"""
Convert OggDude's per-vehicle XML into the schema this app reads.

    python xml_to_json/oggdude_vehicles_to_app.py
    python xml_to_json/oggdude_vehicles_to_app.py --source oggdudes-data --dry-run

Reads  <source>/Vehicles/*.xml          (one file per vehicle, OggDude's format)
       <source>/Weapons.xml             (Key -> display name, for vehicle weapons)
       <source>/ItemAttachments.xml     (Key -> display name, for built-ins)
Writes xml_to_json/xml_sources/oggdude/Vehicles.xml   (override with --out)

Then run convert.py (or convert.php) to regenerate data/json/Vehicles.json.

Why this exists
---------------
Same reason as oggdude_species_to_app.py: convert.php does a mechanical
XML->JSON conversion and never reshapes anything, so a source file has to
ALREADY be in the schema the app reads. Armor, Weapons, Gear and
ItemAttachments ship as one file each and are copied straight across. Vehicles
do not -- OggDude ships 413 separate files that have to be merged into one, and
three things in them need resolving on the way.

Mapping rules, each derived from a census of all 413 files:

* VEHICLE WEAPONS ARE KEY REFERENCES. <VehicleWeapon><Key>BLASTCANLT has to
  become a display name out of Weapons.xml -- 860 references across 48 distinct
  keys -- exactly like species skills and talents. MINCONCLNCH is referenced by
  two vehicles and does not exist in Weapons.xml; the key is kept as the name
  and a warning printed, rather than dropping the weapon.
* SENSOR RANGE COMES IN TWO SHAPES. 380 vehicles carry <SensorRangeValue>srClose
  and 165 also carry a plain-text <SensorRange>Close. rangeFilter in SWApp.js
  only maps the wr... weapon-range prefixes, so the sr... values are resolved
  here instead of adding a second mapping to the app.
* FIRING ARCS ARE SIX BOOLEANS. <Fore>true</Fore><Aft>true</Aft>... becomes the
  display-ready "Fore, Aft, Port, Starboard", the way Crew is already free text.

Everything else is passed through as OggDude wrote it, including the four
separate DefFore/DefAft/DefPort/DefStarboard fields. They are NOT grouped into a
<Defense> block on purpose: the app's min/max filters and md-order-by both index
a flat field name, so grouping them would cost sorting and filtering. The
template composes the "F/A/P/S" display instead.

Data OggDude carries that the app schema has no place for, and which is
therefore dropped:

* WeaponModifiers (24 vehicles) -- turns an unarmed vehicle into an armed one
  with its own skill and qualities; a second weapon shape the template would
  have to render separately.
* EraPricing (3 vehicles) -- alternate price/rarity/restricted per era
  ("Clone Wars"). There is one price column, not one per era.

<Source Page="50"> is left exactly as it is: the converter's
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
OUT_REL = os.path.join('xml_to_json', 'xml_sources', 'oggdude', 'Vehicles.xml')

# <SensorRangeValue>srClose</SensorRangeValue> -> what items.html should show.
# rangeFilter in SWApp.js covers the wr... weapon ranges only.
SENSOR_RANGES = OrderedDict([
    # "No Sensors", not "None": that is the wording OggDude itself uses on the 19
    # srNone vehicles that spell the range out, and one wording means one entry
    # in the sidenav dropdown rather than two that mean the same thing.
    ('srNone', 'No Sensors'),
    ('srClose', 'Close'),
    ('srShort', 'Short'),
    ('srMedium', 'Medium'),
    ('srLong', 'Long'),
    ('srExtreme', 'Extreme'),
])

# Canonical order, so every vehicle reads its arcs the same way round.
FIRING_ARCS = ['Fore', 'Aft', 'Port', 'Starboard', 'Dorsal', 'Ventral']

# Straight copies, in the order they are written to the row. Grouped the way the
# item card reads: what it is, how it fights, what it costs, what it carries,
# how far it goes.
PLAIN_FIELDS = [
    'Type',
    'Silhouette', 'Speed', 'Handling',
    'DefFore', 'DefAft', 'DefPort', 'DefStarboard',
    'Armor', 'HullTrauma', 'SystemStrain',
    'Price', 'Rarity', 'Restricted', 'HP', 'Encumbrance',
    'Crew', 'Passengers', 'EncumbranceCapacity', 'Consumables', 'SinglePilot',
    'HyperdrivePrimary', 'HyperdriveBackup', 'NaviComputer', 'MaxAltitude',
    'StarFighters', 'Starship', 'Massive',
]


def load_key_names(path, item_tag):
    """Key -> display name, the same helper oggdude_species_to_app.py uses."""
    root = ET.parse(path).getroot()
    out = {}
    for el in root.iter(item_tag):
        k, n = el.findtext('Key'), el.findtext('Name')
        if k and n:
            out[k.strip()] = n.strip()
    return out


def text_of(el):
    return (el.text or '').strip() if el is not None else None


def field_text(veh, name):
    """
    Read a field, tolerating the one case-variant tag OggDude's export contains:
    241 vehicles carry <StarFighters>, EF76 alone carries <Starfighters>. Both
    are written out under the canonical name so the JSON has one key, not two.
    """
    value = text_of(veh.find(name))
    if value:
        return value
    lowered = name.lower()
    for child in veh:
        if child.tag != name and child.tag.lower() == lowered:
            return text_of(child)
    return None


def dedupe_sources(srcs):
    """
    Fold a book cited twice on the same vehicle into one entry.

    Five vehicles do this, in two shapes: ATTE and CONSLTCRUIS repeat
    "Forged in Battle" p57 verbatim, while T47ALLIANCE, T47AIRSPEEDER and
    HWK1000LTFREIGHT cite the same book once with a page and once without --
    which would render as two source lines for one citation. The entry carrying
    the page wins.

    A book cited twice with two DIFFERENT pages is left alone: that is a real
    two-page citation, the same call the converter makes for CONCMISSILEMK10.
    """
    out = []
    for book, page in srcs:
        match = None
        for i, (seen_book, seen_page) in enumerate(out):
            if seen_book == book and (seen_page == page
                                      or seen_page is None or page is None):
                match = i
                break
        if match is None:
            out.append((book, page))
        elif out[match][1] is None and page is not None:
            out[match] = (book, page)
    return out


def collapse(s):
    """OggDude indents description blocks; keep the text, drop the padding."""
    if s is None:
        return None
    lines = [ln.strip() for ln in s.strip().splitlines()]
    return '\n'.join(ln for ln in lines if ln)


def sensor_range(veh, key, warn):
    """
    Prefer the plain-text <SensorRange> when OggDude wrote one, map
    <SensorRangeValue> otherwise. Warn when a vehicle carries both and they
    disagree -- that would mean the two fields cannot be used interchangeably.
    """
    literal = text_of(veh.find('SensorRange'))
    coded = text_of(veh.find('SensorRangeValue'))
    mapped = SENSOR_RANGES.get(coded) if coded else None
    if coded and mapped is None:
        warn.append('%s: unknown sensor range %r' % (key, coded))
    if literal and mapped and literal != mapped:
        warn.append('%s: SensorRange %r disagrees with SensorRangeValue %r'
                    % (key, literal, coded))
    return literal or mapped


def firing_arcs(weapon):
    """The six <FiringArcs> booleans as "Fore, Aft, Port"."""
    arcs = weapon.find('FiringArcs')
    if arcs is None:
        return None
    on = [a for a in FIRING_ARCS if (text_of(arcs.find(a)) or '').lower() == 'true']
    return ', '.join(on) or None


def transform_weapon(weapon, weapon_names, key, warn):
    wk = text_of(weapon.find('Key'))
    if not wk:
        return None
    if wk not in weapon_names:
        warn.append('%s: unknown weapon key %r -- kept as the name' % (key, wk))
    rec = OrderedDict()
    rec['Key'] = wk
    rec['Name'] = weapon_names.get(wk, wk)
    count = text_of(weapon.find('Count'))
    if count:
        rec['Count'] = count
    arcs = firing_arcs(weapon)
    if arcs:
        rec['FiringArcs'] = arcs
    for flag in ('Turret', 'Retractable'):
        if (text_of(weapon.find(flag)) or '').lower() == 'true':
            rec[flag] = 'true'
    where = text_of(weapon.find('Location'))
    if where and where != 'Unspecified':
        rec['Location'] = where
    quals = []
    for q in weapon.findall('Qualities/Quality'):
        qk = text_of(q.find('Key'))
        if qk:
            quals.append((qk, text_of(q.find('Count'))))
    rec['Qualities'] = quals
    return rec


def transform(veh, weapon_names, attachment_names, warn):
    rec = OrderedDict()
    key = text_of(veh.find('Key'))
    rec['Key'] = key
    rec['Name'] = text_of(veh.find('Name'))

    # Left in OggDude's own shape -- expand_source_pages() in the converter
    # turns <Source Page="50">Book</Source> into <Source><Book/><Page/></Source>.
    rec['Sources'] = []
    single = veh.find('Source')
    if single is not None and text_of(single):
        rec['Sources'].append((text_of(single), single.attrib.get('Page')))
    for s in veh.findall('Sources/Source'):
        if text_of(s):
            rec['Sources'].append((text_of(s), s.attrib.get('Page')))
    rec['Sources'] = dedupe_sources(rec['Sources'])

    rec['Categories'] = [c.text.strip() for c in veh.findall('Categories/Category')
                         if (c.text or '').strip()]

    for field in PLAIN_FIELDS:
        value = field_text(veh, field)
        if value:
            rec[field] = value

    sensors = sensor_range(veh, key, warn)
    if sensors:
        rec['SensorRange'] = sensors

    weapons = []
    for w in veh.findall('VehicleWeapons/VehicleWeapon'):
        one = transform_weapon(w, weapon_names, key, warn)
        if one:
            weapons.append(one)
    rec['VehicleWeapons'] = weapons

    built_in = []
    for a in veh.findall('BuiltInAttachments/Key'):
        ak = (a.text or '').strip()
        if not ak:
            continue
        if ak not in attachment_names:
            warn.append('%s: unknown attachment key %r' % (key, ak))
        built_in.append(attachment_names.get(ak, ak))
    rec['BuiltInAttachments'] = built_in

    # Same <Mod><Count><MiscDesc> shape the other types already use, so the
    # app's modFilter renders these unchanged.
    rec['BaseMods'] = []
    for mod in veh.findall('BaseMods/Mod'):
        rec['BaseMods'].append((text_of(mod.find('Key')),
                                text_of(mod.find('Count')),
                                collapse(mod.findtext('MiscDesc'))))

    rec['Description'] = collapse(veh.findtext('Description')) or ''
    return rec


def to_xml(rec, indent='  '):
    """Serialise one record in the app schema items.html will bind against."""
    L = []
    p, q, r = indent, indent * 2, indent * 3
    L.append(p + '<Vehicle>')
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

    if rec['Categories']:
        L.append(q + '<Categories>')
        for c in rec['Categories']:
            L.append(r + '<Category>%s</Category>' % escape(c))
        L.append(q + '</Categories>')

    for field in PLAIN_FIELDS:
        if field in rec:
            L.append(q + '<%s>%s</%s>' % (field, escape(rec[field]), field))
    if 'SensorRange' in rec:
        L.append(q + '<SensorRange>%s</SensorRange>' % escape(rec['SensorRange']))

    if rec['VehicleWeapons']:
        L.append(q + '<VehicleWeapons>')
        for w in rec['VehicleWeapons']:
            L.append(r + '<VehicleWeapon>')
            for field in ('Key', 'Name', 'Count', 'FiringArcs', 'Turret',
                          'Retractable', 'Location'):
                if field in w:
                    L.append(r + indent + '<%s>%s</%s>'
                             % (field, escape(w[field]), field))
            if w['Qualities']:
                L.append(r + indent + '<Qualities>')
                for qk, qc in w['Qualities']:
                    L.append(r + indent * 2 + '<Quality>')
                    L.append(r + indent * 3 + '<Key>%s</Key>' % escape(qk))
                    if qc:
                        L.append(r + indent * 3 + '<Count>%s</Count>' % escape(qc))
                    L.append(r + indent * 2 + '</Quality>')
                L.append(r + indent + '</Qualities>')
            L.append(r + '</VehicleWeapon>')
        L.append(q + '</VehicleWeapons>')

    if rec['BuiltInAttachments']:
        L.append(q + '<BuiltInAttachments>')
        for name in rec['BuiltInAttachments']:
            L.append(r + '<Attachment>%s</Attachment>' % escape(name))
        L.append(q + '</BuiltInAttachments>')

    if rec['BaseMods']:
        L.append(q + '<BaseMods>')
        for mk, count, desc in rec['BaseMods']:
            L.append(r + '<Mod>')
            if mk:
                L.append(r + indent + '<Key>%s</Key>' % escape(mk))
            if count:
                L.append(r + indent + '<Count>%s</Count>' % escape(count))
            if desc:
                L.append(r + indent + '<MiscDesc>%s</MiscDesc>' % escape(desc))
            L.append(r + '</Mod>')
        L.append(q + '</BaseMods>')

    if rec['Description']:
        L.append(q + '<Description>%s</Description>' % escape(rec['Description']))
    L.append(p + '</Vehicle>')
    return L


def build(source_dir, warn):
    weapon_names = load_key_names(os.path.join(source_dir, 'Weapons.xml'), 'Weapon')
    attachment_names = load_key_names(os.path.join(source_dir, 'ItemAttachments.xml'),
                                      'ItemAttachment')
    records = []
    for path in sorted(glob.glob(os.path.join(source_dir, 'Vehicles', '*.xml'))):
        root = ET.parse(path).getroot()
        rec = transform(root, weapon_names, attachment_names, warn)
        if not rec['Key'] or not rec['Name']:
            warn.append('%s: no Key or no Name -- skipped' % os.path.basename(path))
            continue
        records.append(rec)
    # convert.py sorts again by source book; this keeps THIS file's diff stable.
    records.sort(key=lambda r: (r['Name'].strip().lower(), r['Key']))
    return records, len(weapon_names), len(attachment_names)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', default='oggdudes-data',
                    help='folder holding Vehicles/, Weapons.xml, ItemAttachments.xml')
    ap.add_argument('--out', default=OUT_REL,
                    help='repo-relative path of the Vehicles.xml to write')
    ap.add_argument('--dry-run', action='store_true', help='write nothing')
    args = ap.parse_args(argv)

    source_dir = os.path.join(REPO_ROOT, args.source)
    if not os.path.isdir(os.path.join(source_dir, 'Vehicles')):
        print('no Vehicles/ folder under %s' % source_dir, file=sys.stderr)
        return 1

    warn = []
    records, n_weapons, n_attachments = build(source_dir, warn)
    print('lookup: %d weapons, %d attachments' % (n_weapons, n_attachments))
    print('transformed %d vehicle rows' % len(records))
    print('  with weapons     : %d' % sum(1 for r in records if r['VehicleWeapons']))
    print('  weapons resolved : %d'
          % sum(len(r['VehicleWeapons']) for r in records))
    print('  with base mods   : %d' % sum(1 for r in records if r['BaseMods']))
    print('  with built-ins   : %d' % sum(1 for r in records if r['BuiltInAttachments']))
    for w in warn:
        print('  WARNING: %s' % w)

    lines = ['<?xml version="1.0" ?>', '<VehicleList>']
    for rec in records:
        lines += to_xml(rec)
    lines.append('</VehicleList>')
    text = '\n'.join(lines) + '\n'

    out = os.path.join(REPO_ROOT, args.out)
    if args.dry_run:
        print('--dry-run: would write %s (%d bytes)' % (out, len(text)))
        return 0
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8', newline='\r\n') as fh:
        fh.write(text)
    print('wrote %s' % out)
    print('now run: python xml_to_json/convert.py --only Vehicle')
    return 0


if __name__ == '__main__':
    sys.exit(main())
