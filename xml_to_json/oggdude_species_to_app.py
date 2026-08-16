#!/usr/bin/env python3
"""
Convert OggDude's per-species XML into the schema this app reads.

    python xml_to_json/oggdude_species_to_app.py
    python xml_to_json/oggdude_species_to_app.py --source oggdudes-data --dry-run

Reads  <source>/Species/*.xml        (one file per species, OggDude's own format)
       <source>/Skills.xml           (Key -> display name)
       <source>/Talents.xml          (Key -> display name)
Writes xml_to_json/xml_sources/oggdude/Species.xml   (override with --out)

Then run convert.py to regenerate data/json/Species.json.

Why this exists
---------------
convert.py does a mechanical XML->JSON conversion; it never reshapes anything.
So a source file has to ALREADY be in the schema the app reads -- the one
items.html binds against -- which is not the schema OggDude ships:

    app schema                        OggDude
    <Source><Book/><Page/></Source>   <Source Page="98">Nexus of Power</Source>
    <Characteristics>                 <StartingChars>
    <Attributes>                      <StartingAttrs>
    <Skills><Skill><Name>             <SkillModifiers><SkillModifier><Key>
    <Talents><Talent><Name>           <TalentModifiers><TalentModifier><Key>
    <SpecialAbilities>                <OptionChoices><OptionChoice><Options>

Skill and talent KEYS must be resolved to display names, because the template
renders {{skill.Name}} and would otherwise show "COORD".

Mapping rules. These were originally derived by diffing against an independent,
hand-curated data set that has since been retired; verify_convert.py now checks
them as invariants against the OggDude source itself:

* RankStart -> RankAdd. RankLimit is the career cap and has no home in the app
  schema, so it is dropped.
* An <OptionChoice> with SEVERAL <Option>s is a character-creation pick ("one
  rank in Athletics OR Stealth") and becomes <OptionChoices><Option>, which
  items.html renders under "Choose one option:". An <OptionChoice> with a
  SINGLE <Option> is an innate trait and becomes a <SpecialAbility>.
  Checked against the shipped data: 122/126 and 116/126 respectively, and every
  exception is explained by subspecies inheritance (below) or by an entry that
  came from the fan-made Menagerie rather than OggDude.
* <SubSpeciesList> is expanded into one row per subspecies, keeping OggDude's
  own keys (AQUASUB1, DROIDSUB1, NIKTOCH1OP1...) so existing artwork still
  matches. A subspecies INHERITS the parent's source, characteristics,
  attributes, skills, talents, option choices and special abilities, then adds
  its own on top; its Name is prefixed with the parent's ("Aqualish - Aquala").
  The parent itself is not emitted when it has subspecies -- you cannot play a
  generic Aqualish.

Data OggDude carries that the app schema has no place for, and which is
therefore dropped: DieModifiers, StartingSkillTraining, per-option
SkillModifiers/TalentModifiers, WeaponModifiers, and EncumbranceBonus.
"""
import argparse
import copy
import glob
import os
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict
from xml.sax.saxutils import escape

CHAR_ORDER = ['Brawn', 'Agility', 'Intellect', 'Cunning', 'Willpower', 'Presence']
ATTR_ORDER = ['WoundThreshold', 'StrainThreshold', 'Experience']

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_REL = os.path.join('xml_to_json', 'xml_sources', 'oggdude', 'Species.xml')


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


def transform(sp, skill_names, talent_names, warn):
    """`sp` is a <Species> or <SubSpecies> element -- both carry the same tags."""
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

    # A choice between several options is a character-creation pick and belongs
    # in OptionChoices ("Choose one option:"); a choice with a single option is
    # an innate trait and belongs in SpecialAbilities.
    choices, abilities = [], []
    oc = sp.find('OptionChoices')
    if oc is not None:
        for choice in oc.findall('OptionChoice'):
            opts = choice.findall('Options/Option')
            bucket = choices if len(opts) > 1 else abilities
            for opt in opts:
                nm = text_of(opt.find('Name'))
                desc = collapse(opt.findtext('Description'))
                if nm or desc:
                    bucket.append((nm or '', desc or ''))
    rec['OptionChoices'] = choices
    rec['SpecialAbilities'] = abilities

    rec['Description'] = collapse(sp.findtext('Description')) or ''
    return rec


def merge_into_parent(parent, sub):
    """
    Build a subspecies row: the parent's record with the subspecies' own
    modifiers added on top, its own key and description, and a prefixed name.

    Verified against the shipped data -- e.g. Aqualish grants Brawl and Aquala
    adds Resilience, so "Aqualish - Aquala" ends up with both, and every Aqualish
    subspecies keeps the parent's "Underwater Breathing" ability.
    """
    rec = copy.deepcopy(parent)
    rec['Key'] = sub['Key']
    rec['Name'] = '%s - %s' % (parent['Name'], sub['Name'])
    rec['Description'] = sub['Description'] or parent['Description']
    for field in ('Talents', 'Skills', 'OptionChoices', 'SpecialAbilities'):
        for entry in sub[field]:
            if entry not in rec[field]:
                rec[field].append(entry)
    return rec


def to_xml(rec, indent='  '):
    """Serialise one record in the app schema that items.html binds against."""
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

    for tag, inner, rows in (('OptionChoices', 'Option', rec['OptionChoices']),
                             ('SpecialAbilities', 'SpecialAbility',
                              rec['SpecialAbilities'])):
        if not rows:
            L.append(q + '<%s/>' % tag)
            continue
        L.append(q + '<%s>' % tag)
        for nm, desc in rows:
            L.append(q + indent + '<%s>' % inner)
            L.append(q + indent * 2 + '<Name>%s</Name>' % escape(nm))
            L.append(q + indent * 2 + '<Description>%s</Description>' % escape(desc))
            L.append(q + indent + '</%s>' % inner)
        L.append(q + '</%s>' % tag)

    if rec['Description']:
        L.append(q + '<Description>%s</Description>' % escape(rec['Description']))
    L.append(p + '</Species>')
    return L


def build(source_dir, warn):
    skill_names = load_key_names(os.path.join(source_dir, 'Skills.xml'), 'Skill')
    talent_names = load_key_names(os.path.join(source_dir, 'Talents.xml'), 'Talent')
    records = []
    n_expanded = 0
    for path in sorted(glob.glob(os.path.join(source_dir, 'Species', '*.xml'))):
        root = ET.parse(path).getroot()
        parent = transform(root, skill_names, talent_names, warn)
        subs = root.findall('SubSpeciesList/SubSpecies')
        if not subs:
            records.append(parent)
            continue
        # The parent is a category, not something you can play -- emit only the
        # subspecies, each inheriting from it.
        for sub_el in subs:
            sub = transform(sub_el, skill_names, talent_names, warn)
            records.append(merge_into_parent(parent, sub))
        n_expanded += 1
    records.sort(key=lambda r: (r['Name'].strip().lower(), r['Key']))
    return records, len(skill_names), len(talent_names), n_expanded


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', default='oggdudes-data',
                    help='folder holding Species/, Skills.xml, Talents.xml')
    ap.add_argument('--out', default=OUT_REL,
                    help='repo-relative path of the Species.xml to write')
    ap.add_argument('--dry-run', action='store_true', help='write nothing')
    args = ap.parse_args(argv)

    source_dir = os.path.join(REPO_ROOT, args.source)
    if not os.path.isdir(os.path.join(source_dir, 'Species')):
        print('no Species/ folder under %s' % source_dir, file=sys.stderr)
        return 1

    warn = []
    records, n_sk, n_tl, n_expanded = build(source_dir, warn)
    print('lookup: %d skills, %d talents' % (n_sk, n_tl))
    print('transformed %d species rows (%d parents expanded into subspecies)'
          % (len(records), n_expanded))
    print('  with option choices   : %d'
          % sum(1 for r in records if r['OptionChoices']))
    print('  with special abilities: %d'
          % sum(1 for r in records if r['SpecialAbilities']))
    for w in warn:
        print('  WARNING: %s' % w)

    lines = ['<?xml version="1.0" ?>', '<SpeciesList>']
    for rec in records:
        lines += to_xml(rec)
    lines.append('</SpeciesList>')
    text = '\n'.join(lines) + '\n'

    out = os.path.join(REPO_ROOT, args.out)
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
