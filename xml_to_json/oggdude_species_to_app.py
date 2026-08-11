#!/usr/bin/env python3
"""
Convert OggDude's per-species XML into the schema this app reads.

    python xml_to_json/oggdude_species_to_app.py
    python xml_to_json/oggdude_species_to_app.py --source oggdudes-data --dry-run

Reads  <source>/Species/*.xml        (one file per species, OggDude's own format)
       <source>/Skills.xml           (Key -> display name)
       <source>/Talents.xml          (Key -> display name)
Writes xml_to_json/xml_sources/species_from_oggdude/Species.xml

Then run convert.py (or convert.php) to regenerate data/json/Species.json.

Why this exists
---------------
convert.php does a mechanical XML->JSON conversion; it never reshapes anything.
So a source file has to ALREADY be in the schema the app reads -- the one
parsed_by_dutzen/Species.xml uses -- which is not the schema OggDude ships:

    app schema                        OggDude
    <Source><Book/><Page/></Source>   <Source Page="98">Nexus of Power</Source>
    <Characteristics>                 <StartingChars>
    <Attributes>                      <StartingAttrs>
    <Skills><Skill><Name>             <SkillModifiers><SkillModifier><Key>
    <Talents><Talent><Name>           <TalentModifiers><TalentModifier><Key>
    <SpecialAbilities>                <OptionChoices><OptionChoice><Options>

Skill and talent KEYS must be resolved to display names, because the template
renders {{skill.Name}} and would otherwise show "COORD".

Mapping rules, each verified against the 95 species that appear both here and in
the already-shipped parsed_by_dutzen data (see verify_convert.py):

* RankStart -> RankAdd. RankLimit is the career cap and has no home in the app
  schema, so it is dropped.
* An <OptionChoice> offering SEVERAL <Option>s is a character-creation pick
  ("one rank in Athletics OR Stealth", "Gearhead OR Solid Repairs"), not an
  innate trait, and is dropped. Only single-option choices become
  SpecialAbilities. This reproduces the shipped data for 70 of the 71
  overlapping species that have abilities.
* Species whose subspecies are already shipped as separate rows (Aqualish,
  Droid, Mustafarian, Nikto) are skipped, so the parent does not duplicate them.

Data OggDude carries that the app schema has no place for, and which is
therefore dropped: DieModifiers, StartingSkillTraining, per-option
SkillModifiers/TalentModifiers, and EncumbranceBonus.
"""
import argparse
import glob
import os
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict
from xml.sax.saxutils import escape

CHAR_ORDER = ['Brawn', 'Agility', 'Intellect', 'Cunning', 'Willpower', 'Presence']
ATTR_ORDER = ['WoundThreshold', 'StrainThreshold', 'Experience']

# Shipped as individual subspecies rows (AQUASUB1.., DROIDSUB1..,
# MUSTAFARIANSUB1.., NIKTOCH1OP1..), so the parent entry would be a duplicate.
SUBSPECIES_PARENTS = ('AQUA', 'DROID', 'MUSTAFARIAN', 'NIKTO')

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_REL = os.path.join('xml_to_json', 'xml_sources', 'species_from_oggdude', 'Species.xml')


def load_key_names(path, item_tag):
    root = ET.parse(path).getroot()
    out = {}
    for el in root.iter(item_tag):
        k, n = el.findtext('Key'), el.findtext('Name')
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


def parse_sources(sp):
    """[(book, page), ...] from either <Source> or <Sources><Source>."""
    out = []
    single = sp.find('Source')
    if single is not None and (single.text or '').strip():
        out.append(((single.text or '').strip(), single.attrib.get('Page')))
    multi = sp.find('Sources')
    if multi is not None:
        for s in multi.findall('Source'):
            if (s.text or '').strip():
                out.append(((s.text or '').strip(), s.attrib.get('Page')))
    return out


def transform(path, skill_names, talent_names, warn):
    sp = ET.parse(path).getroot()
    rec = OrderedDict()
    rec['Key'] = text_of(sp.find('Key'))
    rec['Name'] = text_of(sp.find('Name'))
    rec['Sources'] = parse_sources(sp)

    chars = OrderedDict()
    sc = sp.find('StartingChars')
    if sc is not None:
        for c in CHAR_ORDER:
            v = text_of(sc.find(c))
            if v is not None:
                chars[c] = v
    rec['Characteristics'] = chars

    attrs = OrderedDict()
    sa = sp.find('StartingAttrs')
    if sa is not None:
        for a in ATTR_ORDER:
            v = text_of(sa.find(a))
            if v is not None:
                attrs[a] = v
    rec['Attributes'] = attrs

    talents = []
    tm = sp.find('TalentModifiers')
    if tm is not None:
        for t in tm.findall('TalentModifier'):
            tk = text_of(t.find('Key'))
            if not tk:
                continue
            if tk not in talent_names:
                warn.append('%s: unknown talent key %r' % (rec['Key'], tk))
            talents.append((talent_names.get(tk, tk), text_of(t.find('RankAdd')) or '1'))
    rec['Talents'] = talents

    skills = []
    sm = sp.find('SkillModifiers')
    if sm is not None:
        for s in sm.findall('SkillModifier'):
            sk = text_of(s.find('Key'))
            if not sk:
                continue          # e.g. Cerean.xml carries an empty <Key/>
            rank = text_of(s.find('RankAdd')) or text_of(s.find('RankStart')) or '1'
            if sk not in skill_names:
                warn.append('%s: unknown skill key %r' % (rec['Key'], sk))
            skills.append((skill_names.get(sk, sk), rank))
    rec['Skills'] = skills

    abilities = []
    oc = sp.find('OptionChoices')
    if oc is not None:
        for choice in oc.findall('OptionChoice'):
            opts = choice.findall('Options/Option')
            if len(opts) != 1:
                continue          # a player choice, not an innate trait
            nm = text_of(opts[0].find('Name'))
            desc = collapse(opts[0].findtext('Description'))
            if nm or desc:
                abilities.append((nm or '', desc or ''))
    rec['SpecialAbilities'] = abilities

    rec['Description'] = collapse(sp.findtext('Description')) or ''
    return rec


def to_xml(rec, indent='  '):
    """Serialise one record in the app schema, mirroring parsed_by_dutzen."""
    L = []
    p, q = indent, indent * 2
    L.append(p + '<Species>')
    L.append(q + '<Key>%s</Key>' % escape(rec['Key']))
    L.append(q + '<Name>%s</Name>' % escape(rec['Name']))

    def src_block(pad, book, page):
        out = [pad + '<Source>', pad + indent + '<Book>%s</Book>' % escape(book)]
        if page:
            out.append(pad + indent + '<Page>%s</Page>' % escape(page))
        out.append(pad + '</Source>')
        return out

    srcs = rec['Sources']
    if len(srcs) == 1:
        L += src_block(q, *srcs[0])
    elif len(srcs) > 1:
        L.append(q + '<Sources>')
        for b, pg in srcs:
            L += src_block(q + indent, b, pg)
        L.append(q + '</Sources>')

    for tag, order, src in (('Characteristics', CHAR_ORDER, rec['Characteristics']),
                            ('Attributes', ATTR_ORDER, rec['Attributes'])):
        L.append(q + '<%s>' % tag)
        for k in order:
            if k in src:
                L.append(q + indent + '<%s>%s</%s>' % (k, escape(src[k]), k))
        L.append(q + '</%s>' % tag)

    for tag, inner, rows in (('Talents', 'Talent', rec['Talents']),
                             ('Skills', 'Skill', rec['Skills'])):
        if not rows:
            L.append(q + '<%s/>' % tag)
            continue
        L.append(q + '<%s>' % tag)
        for nm, ra in rows:
            L.append(q + indent + '<%s>' % inner)
            L.append(q + indent * 2 + '<Name>%s</Name>' % escape(nm))
            L.append(q + indent * 2 + '<RankAdd>%s</RankAdd>' % escape(ra))
            L.append(q + indent + '</%s>' % inner)
        L.append(q + '</%s>' % tag)

    L.append(q + '<OptionChoices/>')

    if rec['SpecialAbilities']:
        L.append(q + '<SpecialAbilities>')
        for nm, desc in rec['SpecialAbilities']:
            L.append(q + indent + '<SpecialAbility>')
            L.append(q + indent * 2 + '<Name>%s</Name>' % escape(nm))
            L.append(q + indent * 2 + '<Description>%s</Description>' % escape(desc))
            L.append(q + indent + '</SpecialAbility>')
        L.append(q + '</SpecialAbilities>')
    else:
        L.append(q + '<SpecialAbilities/>')

    if rec['Description']:
        L.append(q + '<Description>%s</Description>' % escape(rec['Description']))
    L.append(p + '</Species>')
    return L


def build(source_dir, warn):
    skill_names = load_key_names(os.path.join(source_dir, 'Skills.xml'), 'Skill')
    talent_names = load_key_names(os.path.join(source_dir, 'Talents.xml'), 'Talent')
    records = []
    for path in sorted(glob.glob(os.path.join(source_dir, 'Species', '*.xml'))):
        rec = transform(path, skill_names, talent_names, warn)
        if rec['Key'] in SUBSPECIES_PARENTS:
            continue
        records.append(rec)
    records.sort(key=lambda r: (r['Name'].strip().lower(), r['Key']))
    return records, len(skill_names), len(talent_names)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', default='oggdudes-data',
                    help='folder holding Species/, Skills.xml, Talents.xml')
    ap.add_argument('--dry-run', action='store_true', help='write nothing')
    args = ap.parse_args(argv)

    source_dir = os.path.join(REPO_ROOT, args.source)
    if not os.path.isdir(os.path.join(source_dir, 'Species')):
        print('no Species/ folder under %s' % source_dir, file=sys.stderr)
        return 1

    warn = []
    records, n_sk, n_tl = build(source_dir, warn)
    print('lookup: %d skills, %d talents' % (n_sk, n_tl))
    print('transformed %d species (skipped parents of shipped subspecies: %s)'
          % (len(records), ', '.join(SUBSPECIES_PARENTS)))
    for w in warn:
        print('  WARNING: %s' % w)

    lines = ['<?xml version="1.0" ?>', '<SpeciesList>']
    for rec in records:
        lines += to_xml(rec)
    lines.append('</SpeciesList>')
    text = '\n'.join(lines) + '\n'

    out = os.path.join(REPO_ROOT, OUT_REL)
    if args.dry_run:
        print('--dry-run: would write %s (%d bytes)' % (out, len(text)))
        return 0
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8', newline='\r\n') as fh:
        fh.write(text)
    print('wrote %s' % out)
    print('now run: python xml_to_json/convert.py --only Species')
    return 0


if __name__ == '__main__':
    sys.exit(main())
