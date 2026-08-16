#!/usr/bin/env python3
"""
Fill in the rules text OggDude's export does not ship, from the FFG fandom wiki.

    python xml_to_json/wiki_descriptions.py --all        # all four types
    python xml_to_json/wiki_descriptions.py talents      # one type
    python xml_to_json/wiki_descriptions.py --all --dry-run
    python xml_to_json/wiki_descriptions.py --all --refresh   # re-download first

Then regenerate as usual:

    python xml_to_json/convert.py

The problem this solves
-----------------------
Almost every Description in OggDude's data is a pointer -- "Please see page 132
of the Edge of the Empire Core Rulebook for details". For most types the stats
carry the information, but a talent without its text is a name and an
activation type, which is why the Talents tab is the thinnest one in the app.
The fandom wiki writes that text out, in a strikingly regular format.

Where the text lands
--------------------
`xml_to_json/xml_sources/fandom-wiki/<Type>.xml` -- a **second source folder**,
not an edit of the oggdude one. convert.py reads source folders in alphabetical
order and the first Key wins, so `fandom-wiki` sorting before `oggdude` makes
its rows override. Nothing in the converter changes.

Each row written here is the oggdude row **copied verbatim** with only its
<Description> swapped, so a row can never lose its Key, Sources, Type or
Categories by being overridden. Rows with no wiki text are simply not written,
and oggdude's row stands. That is why the file is regenerated from both inputs:
re-run this after the oggdude importers, never instead of them.

How a row is matched to a page
------------------------------
Per type, in SOURCES below:

* **Talents** -- one page per talent, titled "<Name> talent". The Improved and
  Supreme versions are not pages of their own: they are `===Improved===`
  subsections of the base talent's page, which is exactly what the data's 67
  "X (Improved)" and 17 "X (Supreme)" rows need.
* **Careers** -- a career is a *category* on the wiki, not a page, so the text
  comes from the lead paragraph of "Category:<Name>". All 20 careers match by
  name with nothing to relax.
* **Force powers** -- one page per power, titled with its plain name; the lead
  paragraph, cut at the first <blockquote>, the way a career's is.
* **Force abilities** -- the hard one, and the only type with no page of its
  own: all 177 live on their power's page as paragraphs under `===UPGRADES===`,
  labelled by KIND ("'''Control Upgrade:'''") rather than by name, up to ten
  under the identical label. See the block comment above force_page_parts()
  for how they are told apart -- it is not by position.

Names are compared with punctuation and case folded away (`_key`), the same
normalisation wiki_diff.py uses.

Coverage today: 588 of 601 talents, 20 of 20 careers, 20 of 20 force powers and
177 of 177 force abilities.

Adding a type
-------------
One entry in SOURCES: an xml file name, the row tag, a function turning a row
into the wiki title(s) it could come from, and a function pulling the prose out
of the page. `to_markup()` and the XML writing are shared.

Markup
------
`to_markup()` turns wikitext into the OggDude inline markup the app's
`descriptionFilter` already renders: '''bold''' becomes [B]...[b], ''italic''
becomes [I]...[i], a blank line becomes [P], <br> becomes [BR], and links are
reduced to their display text. Dice references become the app's symbol tokens
where a symbol is unambiguous -- [[Narrative Dice#Advantage|advantage]] is
[ADVANTAGE] -- and stay as words where it is not: the wiki writes "Force
points" as two links, and [LIGHT][DARK] would be nonsense. An unrecognised
`Narrative Dice#` target is reported rather than guessed at, the way the app
reports an unmapped base mod.

The `*'''Activation:'''` / `*'''Ranked:'''` / `*'''Trees:'''` bullets above the
prose are deliberately dropped. The first two are already the row's Type and
its Ranked category; Trees is genuinely new information, but it is a list of
specializations that runs to 100 entries on Grit and belongs in a column of its
own, not glued to the front of the description.

Provenance and licence
----------------------
The wiki is Fandom, CC BY-SA 3.0, and this text describes FFG's copyrighted
rules. The generated file carries an attribution header, and the report written
alongside it names the page and revision every description came from. Read
xml_to_json/README.md before shipping it anywhere.
"""
import argparse
import datetime
import glob
import html
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict, namedtuple
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wiki                           # noqa: E402  (the shared wiki client)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_DIR = os.path.join('xml_to_json', 'xml_sources', 'fandom-wiki')
REPORT_DIR = os.path.join('xml_to_json', 'wiki_diff')

# No "--" anywhere in here: it is illegal inside an XML comment, and the
# converter parses this file with a strict parser.
ATTRIBUTION = (
    'Generated by xml_to_json/wiki_descriptions.py. Do not edit by hand.\n'
    '  Descriptions come from the Star Wars RPG (FFG) fandom wiki\n'
    '  (https://star-wars-rpg-ffg.fandom.com/), text available under CC BY-SA 3.0.\n'
    '  Every other field is copied verbatim from the oggdude source row.\n'
    '  See xml_to_json/wiki_diff/%s-descriptions.md for the page and revision\n'
    '  each description was taken from.'
)


# --------------------------------------------------------------------------
# wikitext -> the inline markup descriptionFilter renders
# --------------------------------------------------------------------------

# [[Narrative Dice#<target>|<display>]] -> the app's symbol token, but only when
# the display text is the bare symbol word. The wiki spells "Force points" as
# [[...Light Point|Force]] [[...Dark Point|points]], so those targets are left
# as words on purpose -- see DICE_AS_WORDS.
DICE_SYMBOLS = OrderedDict([
    ('Advantage',            'ADVANTAGE'),
    ('Boost',                'BOOST'),
    ('Boost (Blue)',         'BOOST'),
    ('Challenge (Red)',      'CHALLENGE'),
    ('Despair',              'DESPAIR'),
    ('Difficulty (Purple)',  'DIFFICULTY'),
    ('Failure',              'FAILURE'),
    ('Proficiency (Yellow)', 'PROFICIENCY'),
    ('Setback',              'SETBACK'),
    ('Setback (Black)',      'SETBACK'),
    ('Success',              'SUCCESS'),
    ('Threat',               'THREAT'),
    ('Triumph',              'TRIUMPH'),
])

# Targets that have no single symbol, or whose display text is a phrase. Kept as
# the words the wiki wrote: "a Force point", "Hard difficulty", "Force dice".
DICE_AS_WORDS = ('Force (White)', 'Light Point', 'Dark Point',
                 'Standard Difficulties', 'Defensive (Passive)')

_REF = re.compile(r'<ref\b[^>]*/>|<ref\b[^>]*>.*?</ref>', re.S | re.I)
_REFERENCES = re.compile(r'<references\s*/?>', re.I)
_CATEGORY_LINK = re.compile(r'\[\[\s*:?\s*Category:[^\]]*\]\]', re.I)
_FILE_LINK = re.compile(r'\[\[\s*(?:File|Image):[^\[\]]*(?:\[\[[^\]]*\]\][^\[\]]*)*\]\]', re.I)
_BLOCKQUOTE = re.compile(r'<blockquote\b.*?</blockquote>', re.S | re.I)
_LINK = re.compile(r'\[\[([^\[\]|]+)(?:\|([^\[\]]*))?\]\]')
# "[their]", "[they]", "[result]" -- and "Piloting [Space]" inside a link label on
# the Master Pilot page. The lookbehind is what keeps this off a [[wikilink]]:
# its inner "[" is always preceded by the outer one. No lookahead, so a bracket
# that ends up against a link's "]]" is still unwrapped.
_BRACKETED_WORD = re.compile(r"(?<!\[)\[([A-Za-z][A-Za-z' ]{0,24})\]")
_BR = re.compile(r'<br\s*/?>', re.I)
# Characters the wiki carries that the data should not. All four come from text
# pasted out of the PDFs:
#
# * SOFT HYPHENS split words at what used to be a line break -- "af<shy>fected",
#   "Leader<shy>ship", and "on<shy> going" with a space after it. They are
#   invisible, so they survive edits unnoticed and quietly break both the
#   rendered word and any attempt to match on it. The following whitespace goes
#   with them, which is what turns "on<shy> going" back into "ongoing".
# * A HALF-FILLED CIRCLE is the Force point pip. The wiki writes it as a
#   parenthetical after the words -- "spend a Force point (@)" -- in both of the
#   two glyphs it has used, and the app has a token that renders it in the FFG
#   symbol font. Unambiguous, unlike the Light/Dark point links DICE_AS_WORDS
#   deliberately leaves as words.
# * A NON-BREAKING SPACE and a TYPOGRAPHIC APOSTROPHE are just their ASCII
#   selves.
#
# An em dash is left alone: it is real punctuation and already in the data.
_SOFT_HYPHEN = re.compile('­\\s*')
_FORCE_PIP = re.compile('[◐◑]')


def clean_characters(text):
    """The four substitutions above, before anything else reads the text."""
    text = _SOFT_HYPHEN.sub('', text)
    return text.replace(' ', ' ').replace('’', "'")
# Stands in for a <br> while the tags are stripped. Deliberately not spelled with
# angle brackets: the last step of to_markup() removes every one of those.
_BR_MARK = '\x00BR\x00'
_TAG = re.compile(r'</?[a-zA-Z][^>]*>')
_SECTION = re.compile(r'(?m)^(=+)\s*(.*?)\s*\1\s*$')
_METADATA_BULLET = re.compile(r"^\*\s*'''[^']+:?'''")


def _depluralise(word):
    if word.endswith('es') and word[:-2].endswith(('s', 'x', 'ch', 'sh')):
        return word[:-2]
    return word[:-1] if word.endswith('s') else word


def _dice(target, display, unmapped):
    """One [[Narrative Dice#...]] link as either a symbol token or plain words."""
    target = re.sub(r'\s+', ' ', target).strip()
    plain = re.sub(r"'{2,}", '', display).strip()
    if target in DICE_AS_WORDS:
        return plain
    symbol = DICE_SYMBOLS.get(target)
    if symbol and _depluralise(plain.lower()) == symbol.lower():
        return '[%s]' % symbol
    if not symbol and target:
        unmapped.add(target)
    return plain


def _links(text, unmapped):
    """[[Target|display]] -> display, with the dice links handled specially."""
    def one(match):
        target, display = match.group(1).strip(), match.group(2)
        display = target if display is None else display
        head = target.split('#', 1)[0].strip()
        if head == 'Narrative Dice':
            return _dice(target.split('#', 1)[1] if '#' in target else '',
                         display, unmapped)
        return display.strip()
    return _LINK.sub(one, text)


def to_markup(text, unmapped=None):
    """
    Wikitext -> the inline markup app/module/SWApp.js already renders.

    Returns one line: paragraphs become [P] and explicit line breaks [BR], so
    the string survives XML, JSON and the app's <p> wrapper unchanged. Order
    matters -- refs and categories go before links, and the bracketed-pronoun
    unwrap goes before any symbol token is introduced, or [ADVANTAGE] would be
    unwrapped again.
    """
    if unmapped is None:
        unmapped = set()
    text = clean_characters(text)
    text = _REF.sub('', text)
    text = _REFERENCES.sub('', text)
    text = _BLOCKQUOTE.sub('', text)
    text = _FILE_LINK.sub('', text)
    text = _CATEGORY_LINK.sub('', text)
    # "[their]", "[they]", "[result]" -- the wiki brackets its own editorial
    # substitutions. Unwrapped here, while nothing else uses single brackets.
    text = _BRACKETED_WORD.sub(lambda m: m.group(1), text)
    text = _links(text, unmapped)
    # After the bracketed-pronoun unwrap, or [FORCEPOINT] would be unwrapped
    # again -- the same order the dice tokens in _links() depend on.
    text = _FORCE_PIP.sub('[FORCEPOINT]', text)
    text = _BR.sub('\n\n%s\n\n' % _BR_MARK, text)
    # Unescape BEFORE stripping tags, then strip again and drop any angle bracket
    # that is left. The app hands a Description to $sce.trustAsHtml, so a wiki
    # page writing "&lt;script&gt;" must not come out the other end as a tag.
    text = html.unescape(_TAG.sub('', text))
    text = _TAG.sub('', text).replace('<', '').replace('>', '')
    # '''''both''''' first, or the bold rule eats three of the five quotes.
    text = re.sub(r"'''''(.+?)'''''", r'[B][I]\1[i][b]', text, flags=re.S)
    text = re.sub(r"'''(.+?)'''", r'[B]\1[b]', text, flags=re.S)
    text = re.sub(r"''(.+?)''", r'[I]\1[i]', text, flags=re.S)

    # A wiki list item becomes its own line rather than being run into the
    # sentence before it. The app renders [BR] and has no list markup, so the
    # dash is the bullet -- two of Sense's basic power effects are a list, and
    # joined into one paragraph they read as a single run-on sentence.
    text = re.sub(r'(?m)^[*#]+\s*', '%s- ' % _BR_MARK, text)

    paragraphs = []
    for block in re.split(r'\n\s*\n', text):
        block = ' '.join(line.strip() for line in block.splitlines() if line.strip())
        block = re.sub(r'[ \t]{2,}', ' ', block).strip()
        if block:
            paragraphs.append(block)
    out = ('[P]'.join(paragraphs)
           .replace('[P]%s[P]' % _BR_MARK, '[BR]')
           .replace(_BR_MARK, '[BR]'))
    # A list opening a paragraph already has the paragraph's own break.
    out = out.replace('[P][BR]', '[P]').lstrip()
    if out.startswith('[BR]'):
        out = out[4:]
    return re.sub(r'\s+([.,;:!?])', r'\1', out).strip()


# --------------------------------------------------------------------------
# Reading a wiki page's sections
# --------------------------------------------------------------------------

Section = namedtuple('Section', 'level title body')


def sections(text):
    """
    A page split at its headings, refs already stripped.

    A talent page is one `==Name==` section plus an optional `===Improved===`
    and `===Supreme===`; the level is kept so a caller can tell a subsection
    from the page's own heading.
    """
    text = _REF.sub('', text)
    out, current = [], None
    for match in _SECTION.finditer(text):
        if current:
            out.append(Section(current[0], current[1], text[current[2]:match.start()]))
        current = (len(match.group(1)), match.group(2).strip(), match.end())
    if current:
        out.append(Section(current[0], current[1], text[current[2]:]))
    return out


def prose(body, keep_bullets=False):
    """
    A section body without its metadata bullets or category footer.

    The bullets are the `*'''Activation:''' Passive` block the wiki puts above
    every talent's text; see the module docstring for why they are dropped.

    `keep_bullets` is for the force powers, where a bullet of exactly that shape
    is the content rather than a header: every Control upgrade on the Heal/Harm
    and Protect/Unleash pages is written as one line of boilerplate followed by
    `*'''Heal:'''` and `*'''Harm:'''`, so dropping them left seven abilities
    with nothing but "This Control upgrade has different effects for Heal and
    for Harm."
    """
    keep = []
    for line in body.splitlines():
        stripped = line.strip()
        if not keep_bullets and _METADATA_BULLET.match(stripped):
            continue
        if _CATEGORY_LINK.match(stripped) or _REFERENCES.match(stripped):
            continue
        keep.append(line)
    return '\n'.join(keep)


# --------------------------------------------------------------------------
# The types
# --------------------------------------------------------------------------

def _key(text):
    """Comparison key: case, punctuation and spacing folded away."""
    return re.sub(r'[^a-z0-9]+', '', text.lower())


Source = namedtuple('Source', 'xml_file row_tag titles describe')

# "Parry (Improved)" -> the Improved subsection of the Parry page.
_VARIANT = re.compile(r'^(.*?)\s*\((Improved|Supreme)\)\s*$')


def talent_titles(rows):
    """Every wiki page the talent rows could come from, deduplicated."""
    out = []
    for row in rows:
        match = _VARIANT.match(row.findtext('Name') or '')
        base = match.group(1) if match else (row.findtext('Name') or '')
        out.append('%s talent' % base)
    return list(OrderedDict.fromkeys(out))


def talent_describe(row, pages, unmapped):
    """
    (description, page title, note) for one talent row, or None.

    The base talent is the page's own `==Name==` section; "X (Improved)" and
    "X (Supreme)" are subsections of that same page.
    """
    name = row.findtext('Name') or ''
    match = _VARIANT.match(name)
    base, variant = (match.group(1), match.group(2)) if match else (name, None)
    record = pages.get('%s talent' % base)
    if not record or record.get('missing') or not record.get('text'):
        return None
    wanted = _key(variant) if variant else _key(base)
    for section in sections(record['text']):
        if _key(section.title) != wanted:
            continue
        if variant and section.level < 3:
            continue           # a base section that happens to be named "Improved"
        text = to_markup(prose(section.body), unmapped)
        if text:
            return text, record['title'], 'section "%s"' % section.title
    return None


def career_titles(rows):
    """A career is a category page on the wiki, not an article."""
    return ['Category:%s' % (row.findtext('Name') or '') for row in rows]


def career_describe(row, pages, unmapped):
    """
    (description, page title, note) for one career row, or None.

    A career category opens with its flavour paragraph, then a <blockquote>
    naming the book and page, then the career skills, the specializations and
    the signature abilities -- all of which the app already shows from the data,
    and the whole of the sourcebook's contents after that.

    The flavour paragraph is the description; everything from the blockquote on
    is dropped. All 20 careers have that blockquote, so it is the cut. The
    first heading is a fallback for a page that ever loses it.
    """
    record = pages.get('Category:%s' % (row.findtext('Name') or ''))
    if not record or record.get('missing') or not record.get('text'):
        return None
    lead = _SECTION.split(record['text'], 1)[0]
    lead = re.split(r'<blockquote\b', lead, 1, flags=re.I)[0]
    text = to_markup(lead, unmapped)
    return (text, record['title'], 'lead paragraph') if text else None


# --------------------------------------------------------------------------
# Force powers, and the abilities inside them
# --------------------------------------------------------------------------
#
# A force ability is the one type whose text is NOT on a page of its own. All
# 177 live on their power's page, in an `===UPGRADES===` section, as paragraphs
# led by a bold label:
#
#     ===BASIC POWER===
#     At its most basic, Move allows the Force user to ...
#     ===UPGRADES===
#     '''Control Upgrade:''' The user gains the ability to move objects fast
#     '''Magnitude Upgrade:''' Spend a Force point to increase the number of ...
#
# So the label says only what KIND of upgrade a paragraph is, and a power has up
# to ten Control upgrades under the identical label. Matching them to
# MOVECONTROL1..3 is the whole problem, and it is not positional:
#
# ** THE WIKI ORDERS ITS UPGRADES ALPHABETICALLY BY LABEL, AND WITHIN THE
#    CONTROL UPGRADES IT FOLLOWS THE BOOK, NOT OGGDUDE'S KEY NUMBERING. **
#
# Enhance is the proof: its wiki page runs Coordination, Piloting (Planetary),
# Piloting (Space), Agility, Resilience, Brawl, Brawn, then the three Force
# Leaps, while the keys run ENHANCECONT1 Coordination, CONT2 Resilience, CONT3
# Force Leap... Pairing them off in order would mis-describe seven of the ten.
#
# What makes the match possible is that OggDude NAMES each ability for what it
# does -- "Control: Coordination", "Control: Force Leap (Vertical)" -- so the
# name's distinctive words are looked for in the paragraphs. A word is weighted
# by how many paragraphs of that group contain it, so a word in all of them
# counts for almost nothing and a word in exactly one settles the match. The
# best-scoring pair is taken first, then the next, until every ability has one
# paragraph and every paragraph one ability.
#
# The weighting is what gets the three Force Leaps right, and they are worth
# reading twice. The Vertical one is the paragraph that says "vertically as well
# as horizontally", so the word "horizontal" is in the VERTICAL paragraph and
# not in the horizontal one. Scoring alone would hand it to
# "Force Leap (Horizontal)"; because "vertical" and "horizontal" both appear in
# that one paragraph, "Force Leap (Vertical)" outscores it and takes it first,
# "(Maneuver)" takes the paragraph saying "maneuver", and "(Horizontal)" is left
# with the right one.
#
# Every row records in the report how it was matched, so a match made on a weak
# word or by position can be checked without re-running anything.

_FORCE_KINDS = ('Control', 'Duration', 'Magnitude', 'Range', 'Strength',
                'Mastery', 'Number')
# Only at the start of a line: paragraphs carry bold mid-sentence too
# ("'''Enhance power check'''"). "Upgrade" is optional because Ebb/Flow and
# Imbue write "'''Control:'''", and the colon is optional because one label on
# Protect/Unleash is missing it.
_FORCE_LABEL = re.compile(
    r"^'''\s*(%s)(?:\s+Upgrade)?\s*:?\s*'''\s*:?\s*(.*)$" % '|'.join(_FORCE_KINDS),
    re.I)
# "Control: Hurl", but Endure writes "Control - Additional Injuries".
_FORCE_NAME_SPLIT = re.compile(r'[:–-]')
_FORCE_BASIC = re.compile(r'\bBasic Power\b', re.I)
# Words too common in rules text to identify anything. Kept SHORT on purpose:
# the weighting already discounts a word by how many paragraphs carry it, so a
# common word costs little, while a word wrongly listed here costs a match
# outright. "Target" was in this list and cost Seek its "Control: Target",
# whose paragraph is the only one that says "target".
_FORCE_STOP = frozenset(
    'the and for a an of to with can may user power force point points '
    'this that their they check spend gains one two per its instead able '
    'make makes when'.split())

# power -> [(key, name)], filled by force_ability_titles() because that is the
# one hook handed every row at once. describe() sees a single row, and the
# match is a whole-group problem: which paragraph each ability gets depends on
# what the others took.
_FORCE_ROWS = {}
# (power, revid) -> {ability key: (paragraph, note)}. Keyed by revision so a
# --refresh that changes a page cannot serve a stale match.
_FORCE_MATCHED = {}


def _force_words(text):
    """
    Comparison words: links reduced to their display text, short words dropped,
    plurals folded. The wiki writes "emotions" where the ability says "Emotion"
    and "skills" where it says "Skill", which is enough to miss the match.
    """
    # Cleaned first: a soft hyphen inside "af<shy>fected" would otherwise make
    # two unmatchable fragments of a word the ability name is looking for.
    text = _LINK.sub(lambda m: m.group(2) or m.group(1), clean_characters(text))
    text = _TAG.sub(' ', text).lower()
    out = []
    for word in re.split(r'[^a-z0-9]+', text):
        if len(word) < 3:
            continue
        if word.endswith('ies') and len(word) > 4:
            word = word[:-3] + 'y'
        elif word.endswith('es') and len(word) > 4:
            word = word[:-2]
        elif word.endswith('s') and not word.endswith('ss') and len(word) > 3:
            word = word[:-1]
        out.append(word)
    return out


def _force_kind(name):
    """Which group of upgrades an ability belongs to, read off its name."""
    if _FORCE_BASIC.search(name):
        return 'Basic'
    head = _FORCE_NAME_SPLIT.split(name, 1)[0].strip().lower()
    for kind in _FORCE_KINDS:
        if head == kind.lower():
            return kind
    return head.title()


def force_page_parts(text):
    """
    (basic power prose, [(kind, paragraph)]) for one force power page.

    Heal/Harm and Protect/Unleash describe two halves of one power under their
    own headings between the basic power and the upgrades; both halves are part
    of what the basic power does, so they are kept and titled.
    """
    text = _REF.sub('', text)
    marks = [(m.start(), m.end(), _TAG.sub('', m.group(2)).strip().upper())
             for m in _SECTION.finditer(text)]
    basic, upgrades = [], ''
    for i, (start, end, title) in enumerate(marks):
        body = text[end:marks[i + 1][0]] if i + 1 < len(marks) else text[end:]
        if title.startswith('UPGRADE'):
            upgrades = body
        elif title.startswith('BASIC'):
            basic.append(body)
        elif basic and not upgrades:
            basic.append("'''%s'''\n%s" % (title.title(), body))
    paragraphs, current = [], None
    for line in upgrades.splitlines():
        match = _FORCE_LABEL.match(line.strip())
        if match:
            if current:
                paragraphs.append(current)
            current = [match.group(1).title(), match.group(2)]
        elif current is not None:
            current[1] += '\n' + line
    if current:
        paragraphs.append(current)
    return ('\n'.join(basic).strip(),
            [(kind, body.strip()) for kind, body in paragraphs])


def _force_assign(kind, abilities, paragraphs, power=''):
    """
    {ability key: (paragraph, note)} for one group of one kind.

    Greedy on the weighted score, highest pair first, which is what gets the
    Force Leaps right -- see the block comment above.

    THE POWER'S OWN NAME IS NOT A CLUE ON ITS OWN PAGE, and has to be ignored
    or it actively misleads. "Control: Sense Thoughts" contains "Sense", which
    happened to appear in exactly one Sense paragraph -- the wrong one -- and so
    scored as highly there as "thoughts" did in the right one. The tie went the
    wrong way and took the paragraph that "Control: Upgrade Difficulty" needed,
    putting three of Sense's abilities out by one.
    """
    if len(abilities) == 1 and len(paragraphs) == 1:
        return {abilities[0][0]: (paragraphs[0],
                                  'the only %s paragraph' % kind.lower())}
    stop = _FORCE_STOP.union(_force_words(power))
    words = [set(_force_words(p)) for p in paragraphs]
    seen = OrderedDict()
    for bag in words:
        for word in bag:
            seen[word] = seen.get(word, 0) + 1
    scored = []
    for ai, (_, name) in enumerate(abilities):
        wanted = [w for w in _force_words(_FORCE_NAME_SPLIT.split(name, 1)[-1])
                  if w not in stop]
        for pi, bag in enumerate(words):
            hit = [w for w in wanted if w in bag]
            scored.append((sum(1.0 / seen[w] for w in hit), ai, pi, hit))
    scored.sort(key=lambda row: -row[0])
    out, took_a, took_p = {}, set(), set()
    for score, ai, pi, hit in scored:
        if score <= 0 or ai in took_a or pi in took_p:
            continue
        took_a.add(ai)
        took_p.add(pi)
        out[abilities[ai][0]] = (paragraphs[pi],
                                 'matched on %s' % ', '.join('"%s"' % w for w in hit))
    # Whatever is left shares no distinctive word with any paragraph. One left
    # is settled by the others rather than guessed; more than one is a genuine
    # guess and says so, which is the line to read in the report.
    left_a = [i for i in range(len(abilities)) if i not in took_a]
    left_p = [i for i in range(len(paragraphs)) if i not in took_p]
    note = ('left over once the rest matched' if len(left_a) == 1
            else 'PAIRED BY POSITION, no distinctive word')
    for ai, pi in zip(left_a, left_p):
        out[abilities[ai][0]] = (paragraphs[pi], note)
    return out


def _force_match(power, record):
    """The whole power's assignment, computed once per page revision."""
    cached = _FORCE_MATCHED.get((power, record.get('revid')))
    if cached is not None:
        return cached
    basic, paragraphs = force_page_parts(record['text'])
    by_kind, by_kind_paras = OrderedDict(), OrderedDict()
    for key, name in _FORCE_ROWS.get(power, []):
        by_kind.setdefault(_force_kind(name), []).append((key, name))
    for kind, body in paragraphs:
        by_kind_paras.setdefault(kind, []).append(body)
    out = {}
    for kind, abilities in by_kind.items():
        if kind == 'Basic':
            for key, _ in abilities:
                if basic:
                    out[key] = (basic, 'the BASIC POWER section')
            continue
        out.update(_force_assign(kind, abilities, by_kind_paras.get(kind, []),
                                 power))
    _FORCE_MATCHED[(power, record.get('revid'))] = out
    return out


def force_ability_titles(rows):
    """
    The power pages, and -- see _FORCE_ROWS -- the grouping describe() needs.

    <Power> is written by oggdude_force_powers_to_app.py from the TREE that uses
    each ability, not from OggDude's own <Power> element: four rows leave that
    empty and the eight Foresee abilities spell it "Forsee", which is not the
    page's name.
    """
    _FORCE_ROWS.clear()
    for row in rows:
        power = (row.findtext('Power') or '').strip()
        if power:
            _FORCE_ROWS.setdefault(power, []).append(
                ((row.findtext('Key') or '').strip(),
                 (row.findtext('Name') or '').strip()))
    return list(_FORCE_ROWS)


def force_ability_describe(row, pages, unmapped):
    """(description, page title, note) for one force ability, or None."""
    power = (row.findtext('Power') or '').strip()
    record = pages.get(power)
    if not record or record.get('missing') or not record.get('text'):
        return None
    found = _force_match(power, record).get((row.findtext('Key') or '').strip())
    if not found:
        return None
    # keep_bullets: on a force power page a `*'''Heal:'''` bullet is the rules
    # text, not a header -- see prose().
    text = to_markup(prose(found[0], keep_bullets=True), unmapped)
    return (text, record['title'], '%s: %s' % (power, found[1])) if text else None


def force_power_titles(rows):
    """A force power's page is titled with its plain name."""
    return [(row.findtext('Name') or '').strip() for row in rows]


def force_power_describe(row, pages, unmapped):
    """
    The lead paragraph of the power's page: what the power is, before the
    mechanics. The same cut career_describe() makes -- everything from the first
    <blockquote> on is the book-and-page citation and the contents after it.
    """
    record = pages.get((row.findtext('Name') or '').strip())
    if not record or record.get('missing') or not record.get('text'):
        return None
    lead = _SECTION.split(record['text'], 1)[0]
    lead = re.split(r'<blockquote\b', lead, 1, flags=re.I)[0]
    text = to_markup(lead, unmapped)
    return (text, record['title'], 'lead paragraph') if text else None


SOURCES = OrderedDict([
    ('talents', Source('Talents.xml', 'Talent', talent_titles, talent_describe)),
    ('careers', Source('Careers.xml', 'Career', career_titles, career_describe)),
    ('forcepowers', Source('ForcePowers.xml', 'ForcePower',
                           force_power_titles, force_power_describe)),
    ('forceabilities', Source('ForceAbilities.xml', 'ForceAbility',
                              force_ability_titles, force_ability_describe)),
])


# --------------------------------------------------------------------------
# Reading the rows this folder overrides
# --------------------------------------------------------------------------

def base_rows(xml_file, row_tag, repo_root=REPO_ROOT):
    """
    The rows of every *other* source folder, first Key wins.

    Deliberately the same rule convert.py merges by, and deliberately not a
    hardcoded path to the oggdude folder: whatever the converter would use as
    the row is what gets copied and re-described here.
    """
    pattern = os.path.join(repo_root, 'xml_to_json', 'xml_sources', '*', xml_file)
    rows = OrderedDict()
    for path in sorted(glob.glob(pattern)):
        if os.path.dirname(path) == os.path.join(repo_root, SOURCE_DIR):
            continue
        for row in ET.parse(path).getroot().findall(row_tag):
            key = (row.findtext('Key') or '').strip()
            if key and key not in rows:
                rows[key] = row
    return rows


# --------------------------------------------------------------------------
# Writing the override folder
# --------------------------------------------------------------------------

def serialise(element, indent, level=1):
    """
    One element and its children, in the 2-space style the importers write.

    Generic rather than per-type: a Career carries nested <Skills><Skill><Name>
    that has to survive being copied. Attributes are kept, because <Source
    Page="132"> is where the page numbers live until the converter expands it.
    """
    pad = indent * level
    attrs = ''.join(' %s="%s"' % (k, escape(v, {'"': '&quot;'}))
                    for k, v in element.attrib.items())
    children = list(element)
    if not children:
        text = (element.text or '').strip()
        if not text:
            return ['%s<%s%s />' % (pad, element.tag, attrs)]
        return ['%s<%s%s>%s</%s>' % (pad, element.tag, attrs, escape(text), element.tag)]
    lines = ['%s<%s%s>' % (pad, element.tag, attrs)]
    for child in children:
        lines += serialise(child, indent, level + 1)
    lines.append('%s</%s>' % (pad, element.tag))
    return lines


def set_description(row, text):
    """A copy of the row with its Description replaced (or added)."""
    import copy
    out = copy.deepcopy(row)
    node = out.find('Description')
    if node is None:
        node = ET.SubElement(out, 'Description')
        node.tail = None
    node.text = text
    for child in out.iter():
        child.tail = None
    return out


def build(name, source, repo_root=REPO_ROOT, refresh=False, verbose=True):
    """
    Fetch, match and describe one type.

    Returns (written rows, report lines, unmapped dice targets).
    """
    rows = base_rows(source.xml_file, source.row_tag, repo_root)
    if verbose:
        print('%s' % name)
        print('  data  %-23s %4d rows' % (source.xml_file, len(rows)))
    titles = source.titles(list(rows.values()))
    pages = wiki.wikitext(titles, refresh=refresh, verbose=verbose)

    unmapped = set()
    described, missed = [], []
    for key, row in rows.items():
        found = source.describe(row, pages, unmapped)
        if not found:
            missed.append((key, row.findtext('Name') or ''))
            continue
        text, title, note = found
        described.append((key, row.findtext('Name') or '', title, note,
                          pages[title].get('revid'), set_description(row, text)))
    if verbose:
        print('  =>    %d described, %d without wiki text' % (len(described), len(missed)))
    return described, missed, unmapped


def write_xml(name, source, described, repo_root=REPO_ROOT):
    """The override source file for one type."""
    out_dir = os.path.join(repo_root, SOURCE_DIR)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    path = os.path.join(out_dir, source.xml_file)
    root_tag = source.row_tag + 'List'
    lines = ['<?xml version="1.0" ?>',
             '<!--', ATTRIBUTION % name, '-->',
             '<%s>' % root_tag]
    for _, _, _, _, _, row in described:
        lines += serialise(row, '  ')
    lines.append('</%s>' % root_tag)
    with open(path, 'w', encoding='utf-8', newline='\r\n') as handle:
        handle.write('\n'.join(lines) + '\n')
    return path


def write_report(name, source, described, missed, unmapped, repo_root=REPO_ROOT):
    """Which row took its text from which page and revision, and what did not."""
    out_dir = os.path.join(repo_root, REPORT_DIR)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    path = os.path.join(out_dir, '%s-descriptions.md' % name)
    out = ['# %s: descriptions taken from the wiki' % name, '',
           'Generated %s by `xml_to_json/wiki_descriptions.py`.'
           % datetime.date.today().isoformat(), '',
           'Text from the Star Wars RPG (FFG) fandom wiki, CC BY-SA 3.0.', '',
           '| | count |', '| --- | ---: |',
           '| rows in `%s` | %d |' % (source.xml_file, len(described) + len(missed)),
           '| **described from the wiki** | **%d** |' % len(described),
           '| **left as the page pointer** | **%d** |' % len(missed), '']
    if unmapped:
        out += ['## Unmapped dice references (%d)' % len(unmapped), '',
                'A `Narrative Dice#` link target that is neither in `DICE_SYMBOLS` nor',
                'in `DICE_AS_WORDS`. Its display text was used as written.', '']
        out += ['- `%s`' % t for t in sorted(unmapped)] + ['']
    out += ['## Without wiki text (%d)' % len(missed), '',
            'These keep OggDude\'s page pointer -- the row is not written to the',
            'override folder at all.', '']
    out += ['- %s (`%s`)' % (n, k) for k, n in missed] if missed else ['_None._']
    out += ['', '## Described (%d)' % len(described), '',
            '| name | key | wiki page | rev | from |',
            '| --- | --- | --- | ---: | --- |']
    for key, row_name, title, note, revid, _ in described:
        out.append('| %s | `%s` | %s | %s | %s |' % (row_name, key, title, revid, note))
    out.append('')
    with open(path, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write('\n'.join(out))
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('types', nargs='*', help='types to import (%s)'
                                             % ', '.join(SOURCES))
    ap.add_argument('--all', action='store_true', help='every type in SOURCES')
    ap.add_argument('--refresh', action='store_true',
                    help='re-download the pages instead of using the cache')
    ap.add_argument('--dry-run', action='store_true', help='write nothing')
    args = ap.parse_args(argv)

    if args.all:
        jobs = list(SOURCES.items())
    elif args.types:
        unknown = [t for t in args.types if t not in SOURCES]
        if unknown:
            ap.error('unknown type(s): %s (known: %s)'
                     % (', '.join(unknown), ', '.join(SOURCES)))
        jobs = [(t, SOURCES[t]) for t in args.types]
    else:
        ap.error('name a type (%s), or pass --all' % ', '.join(SOURCES))

    for name, source in jobs:
        try:
            described, missed, unmapped = build(name, source, refresh=args.refresh)
        except wiki.WikiError as exc:
            print('  !     %s: wiki API: %s' % (name, exc))
            return 2
        except OSError as exc:
            print('  !     %s: %s' % (name, exc))
            return 2
        for target in sorted(unmapped):
            print('  WARNING: please add a dice mapping for: %s' % target)
        if args.dry_run:
            print('  --dry-run: would write %d rows to %s/%s'
                  % (len(described), SOURCE_DIR.replace('\\', '/'), source.xml_file))
            continue
        for path in (write_xml(name, source, described),
                     write_report(name, source, described, missed, unmapped)):
            print('  wrote %s' % os.path.relpath(path, REPO_ROOT).replace('\\', '/'))

    if not args.dry_run:
        print('\nnow run: python xml_to_json/convert.py')
    return 0


if __name__ == '__main__':
    sys.exit(main())
