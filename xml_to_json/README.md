# Data pipeline

How the JSON the app reads gets built, and how to add more of it.

```
oggdudes-data/                    raw OggDude export (any format)
        |                                          fandom wiki (network)
        |  oggdude_<type>_to_app.py                        |
        |    <- reshapes to the app's schema               |  wiki.py
        v                                                  v  wiki_descriptions.py
xml_to_json/xml_sources/oggdude/*.xml     xml_to_json/xml_sources/fandom-wiki/*.xml
        |                                                  |   <- rules text only
        +--------------------------+-----------------------+
                                   |  convert.py
                                   v     merges, first Key wins
                          data/json/*.json    <- what index.html actually loads
```

`Armor.xml`, `Weapons.xml`, `ItemAttachments.xml` and `Gear.xml` are already in
the app's schema and are copied straight into `xml_sources/oggdude/`. **Everything
else goes through its own `oggdude_*_to_app.py` first.** Species, Vehicles,
Careers, Specializations and Force Powers ship one file per row in a different
schema; Talents ships flat but with two fields the app would misread; and the
last two go further still, since what the app renders from them is a grid rather
than a row — see *Specializations and force powers*.

Both the XML sources and the generated JSON are committed. A data change is
expected to include the regenerated JSON in the same commit.

---

## Scripts

| Script | What it does |
| --- | --- |
| `convert.py` | The XML -> JSON converter. **Its output must stay byte-identical to the committed JSON.** |
| `oggdude_species_to_app.py` | Reshapes OggDude's per-species XML into the app's species schema. |
| `oggdude_vehicles_to_app.py` | The same for the 413 per-vehicle files. |
| `oggdude_careers_to_app.py` | The same for the 20 per-career files, resolving skill and specialization keys. |
| `oggdude_talents_to_app.py` | Reshapes the single flat `Talents.xml` — see *Talents* below for why it is not just copied. |
| `oggdude_specializations_to_app.py` | The 123 talent trees. Lays the grid out; see *Specializations and force powers*. |
| `oggdude_force_powers_to_app.py` | The 20 force trees. Imports the layout code from the one above. |
| `verify_convert.py` | Regression checks, one per importer. Run after touching any of the above. |
| `wiki.py` | The shared, cached client for the fandom wiki. Imported by the two below; nothing else opens a connection. |
| `wiki_diff.py` | Reports what a wiki category has that the JSON does not, and vice versa. Read-only. |
| `wiki_descriptions.py` | Writes the rules text OggDude does not ship into `xml_sources/fandom-wiki/`. |

```bash
python xml_to_json/oggdude_species_to_app.py     # refresh the OggDude source set
python xml_to_json/wiki_descriptions.py --all    # refresh the wiki descriptions
python xml_to_json/convert.py --only Species     # rebuild one JSON file
python xml_to_json/convert.py --check            # report, write nothing
python xml_to_json/verify_convert.py             # prove nothing regressed
python xml_to_json/wiki_diff.py --all            # coverage against the fandom wiki
```

Everything here is Python 3 with the standard library only — nothing to install.
Agents run these from the command line and never serve anything; see *Verifying
changes* in `AGENTS.md`.

---

## Talking to the fandom wiki

Three scripts share one client. **`wiki.py` is the only place that opens a
connection** — anything fetching more content later should import it rather than
reaching for `urllib`.

```bash
python xml_to_json/wiki.py members Talents          # titles in a category
python xml_to_json/wiki.py subcats "Source Book"    # its subcategories
python xml_to_json/wiki.py search "Bounty Hunter"   # what does the wiki call it?
python xml_to_json/wiki.py page "Parry talent"      # one page's wikitext
python xml_to_json/wiki.py cache Talents            # download a whole category
```

It offers `members()`, `subcategories()`, `page_categories()`, `search()` and
`wikitext()`, each following the API's continuation cursor and batching to the
50-title limit, with a descriptive User-Agent and a pause between requests.

`wikitext()` **caches every page** as JSON under `xml_to_json/wiki_cache/`, with
the revision id and timestamp. That directory is gitignored: it is a download,
not a source. The cache is what makes writing a parser bearable — the
edit-and-rerun loop over 700 talent pages costs no requests at all. Pass
`--refresh` to re-download.

Two wiki facts are worth knowing before writing anything against it, because
neither is guessable:

- **A talent's page is titled `<Name> talent`**, not `<Name>`. There is no
  `Grit` page; there is a `Grit talent` page.
- **A career is a category, not a page.** `Category:Careers` has *no* page
  members at all — the 24 careers are its subcategories, and the prose lives on
  the category page itself.

---

## Coverage against the fandom wiki

`wiki_diff.py` compares a category on
<https://star-wars-rpg-ffg.fandom.com> against one generated JSON file and writes
a Markdown report to `xml_to_json/wiki_diff/<target>.md`. It is a **reporting tool
only** — it never touches the XML, the JSON or the app, and it is the one script
here that needs network access.

```bash
python xml_to_json/wiki_diff.py --list        # the configured targets
python xml_to_json/wiki_diff.py species       # one target
python xml_to_json/wiki_diff.py --all         # all ten
```

Targets are one line each in `TARGETS` at the top of the script — wiki category,
JSON file, its type key, and two optional fields for the categories that are not
a plain list of items: `strip`, a regex removed from every wiki title before
comparing (`\s+talent$`, `^Category:`), and `kind`, the API's member type
(`subcat` for careers). Nothing else is target-specific, so covering something
new is a one-line change. A target may name **several categories** where the wiki
splits what one JSON file holds together — `vehicles` compares `Vehicles.json`
against the union of `Category:Vehicles` and `Category:Starships` — and a page
filed under both is still one entry. For a throwaway comparison, skip the
registry (`--category` takes a comma-separated list too):

```bash
python xml_to_json/wiki_diff.py --category Talents --json data/json/Gear.json \
                                --type-key Gear --name talents-scratch
```

Names rarely line up, so each report sorts its findings into four buckets:

1. **matched exactly** after folding case, punctuation and spacing;
2. **matched after normalisation** — one of the `RELAXATIONS` applied (drop a
   `Aqualish - Aquala` subspecies suffix, drop a `Human (Onderonian)`
   parenthetical, singularise `Toydarians`). Always listed with the rule that did
   it, so a relaxation cannot quietly hide a real difference. New rules are one
   line in `RELAXATIONS`; combinations are generated automatically;
3. **the actual diff** — what only the wiki has, and what only the data has,
   each entry annotated with where it came from (below);
4. **possibly the same, named differently** — leftovers paired by similarity
   (`Adverse Environment Gear` / `Adverse Environmental Gear`). Suggestions for a
   human, never counted as matches, and both names stay in the diff above.

Expect a large wiki-only count on every target: the wiki carries homebrew and
material OggDude does not cover. The number to watch is *data-only*, and bucket 4,
which is where typos surface.

### The source in brackets

Every entry in the two diff lists is annotated so it can be triaged without
opening anything:

- **data-only** rows show the book on the row itself, via the converter's own
  `source_books()` — `Mk I Nightstalker Suit (Cyphers and Masks)`;
- **wiki-only** pages show where the wiki files them. The wiki classifies its own
  books: official sourcebook categories sit under `Category:Source Book`, fan
  supplements under `Category:Homebrew`, so `wiki_sources()` reads both sets from
  the wiki instead of hardcoding them. Fan material is prefixed, which is the
  whole point of the annotation — `Ewok (Allies)` is worth importing,
  `Abednedo (homebrew: Sequels)` is not.

That prefix also sets the order: the wiki-only list puts **official material
first**, homebrew after it, alphabetical within each half, with the split counted
under the heading. A page filed under both an official book and a fan supplement
(`Quadnoculars (Beginner Sequel / homebrew: Andor)`) counts as official — the
importable half is what decides. With `--no-sources` there is nothing to sort by
and the list stays plain alphabetical.

Two things to know when reading them. The wiki names books after the **career**
(`Hired Gun`, `Guardian`, `Ace`), while the data uses the **title**
(*Dangerous Covenants*, *Keeping the Peace*, *Stay on Target*) — so the same book
looks different on the two sides. And `Extra Stuff` is a catch-all that sits under
`Source Book` despite not being one book.

Only the *unmatched* pages are looked up, which keeps this to a few extra requests
rather than one per page in the category. `--no-sources` skips it entirely.

---

## Rules text from the wiki

OggDude's export ships **no rules text**. Almost every `Description` is a pointer
— *"Please see page 132 of the Edge of the Empire Core Rulebook for details"* —
and for talents that is the whole content of the row. `wiki_descriptions.py`
fills those in from the wiki, which writes the text out in a strikingly regular
format.

```bash
python xml_to_json/wiki_descriptions.py --all              # talents and careers
python xml_to_json/wiki_descriptions.py talents --dry-run  # one type, write nothing
python xml_to_json/wiki_descriptions.py --all --refresh    # re-download first
python xml_to_json/convert.py                              # then regenerate
```

Coverage today: **588 of 601 talents** and **20 of 20 careers**. The 13 talents
with no wiki page keep their pointer.

### It writes a second source folder

The output is `xml_sources/fandom-wiki/<Type>.xml`, **not** an edit of the
oggdude folder. Source folders are read in alphabetical order and the first
`Key` wins, so `fandom-wiki` sorting before `oggdude` overrides it. Nothing in
the converter changes.

Whole-row override is the only precedence `convert.py` has, so each row written
here is **the oggdude row copied verbatim with only its `<Description>`
swapped** — a row can never lose its `Key`, `Sources`, `Type` or `Categories` by
being overridden. Rows with no wiki text are not written at all and oggdude's
row stands, which is why the file holds 588 rows and not 601.

That makes it a *derived* file with two inputs. **Re-run it after the oggdude
importers, never instead of them**, or the override folder will keep serving an
old copy of a row the import has since changed. `verify_convert.py` Check 6
enforces exactly that: every row has a counterpart to override, the two are
identical outside `<Description>`, and the new description is neither empty nor
another page pointer.

### Where the text comes from

| Type | Page | Section |
| --- | --- | --- |
| Talents | `<Name> talent` | the page's own `==Name==` heading |
| Talents, `X (Improved)` / `X (Supreme)` | `X talent` | the `===Improved===` / `===Supreme===` subsection |
| Careers | `Category:<Name>` | the lead paragraph, everything above the first `<blockquote>` |

The Improved and Supreme variants are the reason this works at all: they are not
pages of their own, which is exactly what the data's 67 `(Improved)` and 17
`(Supreme)` rows need.

Everything above the prose on a talent page — the `*'''Activation:'''`,
`*'''Ranked:'''` and `*'''Trees:'''` bullets — is dropped. The first two are
already the row's `Type` and its `Ranked` category. **Trees is genuinely new
information** (which specializations offer the talent, and at what tier), but it
runs to a hundred entries on Grit and belongs in a column of its own rather than
glued to the front of a description.

### Markup

`to_markup()` turns wikitext into the inline markup `descriptionFilter` in
`SWApp.js` already renders: `'''bold'''` → `[B]…[b]`, `''italic''` → `[I]…[i]`,
a blank line → `[P]`, `<br>` → `[BR]`, and a link down to its display text.

Dice references become the app's **symbol tokens** where a symbol is
unambiguous — `[[Narrative Dice#Advantage|advantage]]` is `[ADVANTAGE]` — and
stay as words where it is not. That distinction is not fussiness: the wiki
spells "Force points" as *two* links, `[[…Light Point|Force]] [[…Dark
Point|points]]`, and mapping both would produce `[LIGHT][DARK]`. The targets
left as words are listed in `DICE_AS_WORDS`; an unrecognised `Narrative Dice#`
target is reported rather than guessed at, the way the app reports an unmapped
base mod.

The app hands a `Description` to `$sce.trustAsHtml`, so `to_markup()` unescapes
entities *before* stripping tags and then drops every remaining angle bracket. A
wiki page writing `&lt;script&gt;` must not come out the other end as a tag.

### Licence

The wiki is Fandom, **CC BY-SA 3.0**, and the text describes FFG's copyrighted
rules. Each generated file carries an attribution header, and
`wiki_diff/<type>-descriptions.md` names the page and revision every description
came from. That report is the thing to read before shipping this anywhere.

### Adding a type

One entry in `SOURCES`: the XML file name, the row tag, a function turning a row
into the wiki title(s) it could come from, and a function pulling the prose out
of the page. `to_markup()`, the row copying, the XML writing and the report are
shared.

---

## Merge rules

`convert.py` globs `xml_sources/*/<Type>.xml`, so **folders are read in
alphabetical order**, and:

1. **First occurrence of a `Key` wins.** A folder sorting earlier overrides later
   ones. There is currently only one folder, `oggdude`, so nothing collides —
   but this is what to reason about when adding a second.
2. **Excluded books are not imported at all.** A row whose every source book is
   in `EXCLUDED_BOOKS` is skipped, so neither the row nor the
   book name reaches the JSON or the app's Source filter. This drops 28 rows
   (27 species and one Gear entry). A row with *no* source is kept — seven
   generic Gear entries have none and are legitimate. A row that mixed an
   excluded book with a kept one would be ambiguous; none exists, so the
   converter prints a warning instead of guessing.
3. **Every type is sorted before writing** — by the row's *first* `Source` book,
   then by `Name`, with `Key` as the tie-breaker (`sort_key` in `convert.py`).
   Source order in the XML is not preserved: OggDude regenerates its exports in
   an arbitrary order, and sorting is what keeps the committed JSON diffing
   cleanly across refreshes. Comparison is case-insensitive **over ASCII only** —
   folding non-ASCII letters too would reorder the committed rows. A row with no
   source book at all sorts first.
4. **Source pages are un-attributed first.** OggDude writes the page as an XML
   attribute — `<Source Page="44">Forged in Battle</Source>` — and the converter
   drops attributes (quirk 1 below), so every page number was being thrown away
   for Armor, Weapons, Gear and ItemAttachments. `expand_source_pages()` rewrites
   those into
   `<Source><Book>…</Book><Page>44</Page></Source>` before the conversion runs,
   which is the shape Species already use and the one `items.html` renders as
   *"Source: <book> page N"*. Sources that already have `<Book>`/`<Page>`
   children are left alone.
5. **Duplicated fields are collapsed.** OggDude's export sometimes writes the
   same field twice on one row, and SimpleXML turns repeated siblings into an
   array — `THONTIIN`, `ZOPHIS` and `PROTTORPHVY` reached the JSON with
   `"Type": ["Weapon","Weapon"]`, `DATABRBO` with
   `"Restricted": ["true","true"]`, which `items.html` rendered as the array.
   `dropDuplicateSiblings()` / `drop_duplicate_siblings()` keep the first copy
   and drop the rest, printing a `~` line for each so a new export bug is
   visible. The rule is narrow on purpose: only *childless* elements whose tag,
   attributes **and** text all match. `<Mod>`, `<Skill>` and `<Option>` blocks
   have children and are untouched; so are `CONCMISSILEMK10`'s two
   `Dangerous Covenants` sources, which differ by page and both belong in the
   JSON; so are whitespace-only elements, which quirk 2 below depends on.
   Whole duplicated rows (`SYNTHEROPE`, `ENCRYCOMP`, `SHISBLADE`, `ASHMALA`)
   are not this rule's job — the first-`Key`-wins merge already handles them.
6. Recognised file names are fixed in `$validFileNames`: `Armor.xml`,
   `Weapons.xml`, `ItemAttachments.xml`, `Gear.xml`, `Species.xml`. Adding a new
   data type means touching the converter, `index.html` and usually `items.html`.

Thumbnails are wired up automatically: a row gets `data/img/<TypeKey><Key>.png`
if that file exists, otherwise `img/no_image.png`. Artwork sits in
`oggdudes-data/SpeciesImages/` etc. named by bare `Key`, so it only needs the
type prefix adding:

```bash
cp oggdudes-data/SpeciesImages/VURK.png data/img/SpeciesVURK.png
```

---

## The two species schemas

`convert.py` is a *mechanical* XML→JSON conversion. Beyond the two repairs in
merge rules 4 and 5, it never reshapes anything.
So a source file must already be in the schema the app reads — the one
`xml_sources/oggdude/Species.xml` uses, and which `items.html` binds against.
That is **not** the schema OggDude ships:

| app schema (`xml_sources/oggdude/Species.xml`) | raw OggDude (`oggdudes-data/Species/*.xml`) |
| --- | --- |
| `<Source><Book/><Page/></Source>` | `<Source Page="98">Nexus of Power</Source>` |
| `<Characteristics>` | `<StartingChars>` |
| `<Attributes>` | `<StartingAttrs>` |
| `<Skills><Skill><Name>Coordination` | `<SkillModifiers><SkillModifier><Key>COORD` |
| `<Talents><Talent><Name>Durable` | `<TalentModifiers><TalentModifier><Key>DURA` |
| `<SpecialAbilities><SpecialAbility>` | `<OptionChoices><OptionChoice><Options><Option>` |

`oggdude_species_to_app.py` does that translation. The rules it encodes, each
derived by diffing against the already-shipped data:

- **Skill and talent keys must be resolved to display names** via
  `oggdudes-data/Skills.xml` and `Talents.xml`. The template renders
  `{{skill.Name}}`, so an unresolved key shows up as literal `COORD`.
- `RankStart` → `RankAdd`. `RankLimit` is the career cap; the app schema has no
  place for it.
- **Option choices are routed by how many options they offer.** An
  `<OptionChoice>` with *several* `<Option>`s is a character-creation pick ("one
  rank in Athletics *or* Stealth") and becomes `<OptionChoices><Option>`, which
  `items.html` renders under *"Choose one option:"*. An `<OptionChoice>` with a
  *single* `<Option>` is an innate trait and becomes a `<SpecialAbility>`.
  35 species have option choices and 71 options depend on this; routing them all
  into `SpecialAbilities` invents traits like "One Rank in Stealth", and dropping
  them loses real data.
- **`<SubSpeciesList>` is expanded into one row per subspecies**, keeping
  OggDude's keys (`AQUASUB1`, `DROIDSUB1`, `NIKTOCH1OP1`…) so existing artwork
  still matches. A subspecies **inherits** the parent's source, characteristics,
  attributes, skills, talents, option choices and special abilities, then adds
  its own; its name is prefixed with the parent's ("Aqualish - Aquala"). The
  parent is *not* emitted when it has subspecies — you cannot play a generic
  Aqualish. This affects Aqualish (3), Droid (7), Mustafarian (2) and Nikto (5).
- Dropped for want of anywhere to put it: `DieModifiers`,
  `StartingSkillTraining`, per-option `SkillModifiers`/`TalentModifiers`,
  `WeaponModifiers`, `EncumbranceBonus`.

---

## Four parsing quirks the output depends on

`data/json/*.json` is a **committed deployment artifact**, so the converter's job
is to reproduce it exactly, not to parse XML the most sensible way. Four of its
rules look arbitrary and are load-bearing. All four were found by regenerating
the committed JSON and diffing until it matched — `verify_convert.py` Check 1
still enforces every one of them.

They are inherited: the original converter was a PHP script, `convert.php`, and
these are the behaviours of `simplexml_load_string()` +
`json_encode(JSON_NUMERIC_CHECK)`. **That script has been deleted and the
pipeline is Python only** — but the quirks stay, because the data does.
"Simplifying" one of them turns into several hundred lines of spurious diff
across files nobody touched.

1. **Attributes are dropped.** `<Source Page="169">Edge…</Source>` becomes the
   plain string `"Edge…"`, not `{"@attributes":…}`. The XML carries 1783
   `Page="…"` attributes and the JSON contains no `@attributes` key at all.
   Page numbers therefore only survive when `<Page>` is a child element — which
   is why the converter rewrites `<Source Page="…">` into that shape up front
   (merge rule 4). Any *other* attribute added to the sources in future will
   still vanish silently.
2. **Whitespace-only elements keep their text** under a `"0"` key:
   `<BaseMods>\n    </BaseMods>` → `{"0":"\n    "}`, while a truly empty element
   gives `{}`.
3. **A number keeps leading whitespace but not trailing whitespace.** `" 4"`
   becomes `4`; `<Count>4\n    </Count>` stays the *string* `"4\n    "`.
4. **Nested XML comments survive** as `"comment": {}`. Only the root-level
   `comment` key is dropped, which is what commit `23a8b4e` fixed — comments
   deeper in the tree still land in the JSON.

Output format: pretty-printed with 4 spaces, escaped forward slashes
(`data\/img\/…`), ASCII-only, CRLF line endings, no trailing newline.

---

## Recipes

### Add or refresh species from an OggDude export

```bash
python xml_to_json/oggdude_species_to_app.py    # rebuild the app-schema source
python xml_to_json/convert.py --only Species    # rebuild data/json/Species.json
python xml_to_json/verify_convert.py            # confirm nothing else moved
```

Then copy in any missing artwork and re-run `convert.py` so the `Thumbnail`
paths pick it up.

### Add a whole new data set

Create `xml_to_json/xml_sources/<your-folder>/`, drop app-schema XML in, and
re-run the converter. Name the folder with the precedence rules above in mind:
alphabetically earlier means higher priority.

### Change how conflicts resolve

`EXCLUDED_BOOKS` sits at the top of `convert.py`; the output order lives in
`sort_key` just below. Then run `verify_convert.py`.

---

## What else could become a tab

Surveyed against `oggdudes-data/` while planning the Vehicles import. Volumes are
row counts for single-file exports, file counts for folder exports. The app-side
work is the same for all of them — see *Adding a new data type* in `AGENTS.md`;
what differs is the import.

| Candidate | Volume | Import effort |
| --- | --- | --- |
| **Vehicles** | 413 files | Done — `oggdude_vehicles_to_app.py`, see below |
| **Talents** | 604 rows | Done — `oggdude_talents_to_app.py`, see below. Not the copy job this table first estimated. |
| **Careers** | 20 files | Done — `oggdude_careers_to_app.py`, see below |
| **Vehicle attachments** | 125 rows | Done — no import at all, a second tab over `ItemAttachments.json` split by `attachmentClass`, the way Starships split off Vehicles. |
| **Adversaries** | none | **Already half-built in `items.html`** (29 `name == 'Adversary'` conditions, full characteristic columns). OggDude ships no adversary export, so the UI exists and the data does not. Blocked on a data source, not on code. |
| **Specializations** | 123 files | Done — `oggdude_specializations_to_app.py`, see below. The tree renderer this table said the app did not have now exists. |
| **Force powers** | 20 files | Done — `oggdude_force_powers_to_app.py`, which imports the layout code from the specializations importer. |
| Skills | 35 rows | Trivially table-shaped: flat single file, `Key`/`Name`/`Description`/`Sources`/`CharKey`/`TypeValue`. At 35 rows it is a reference list rather than something the sliders-and-filters table earns its keep on. |
| Signature abilities | 38 files | The third tree type, and the only one left. Structurally the force powers again — 3 rows of 4, spans and per-box costs, names out of a separate `SigAbilityNodes.xml` the way abilities come from `Force Abilities.xml` — so the renderer and the layout code are already in place. **One export quirk to handle first: 26 of the 114 rows write 16 `<Span>` entries for 4 cells**, all four rows' spans flattened into the first row's element. `layout_row()` would read the first four and quietly mislay the rest. |

What is left is Skills, which is table-shaped and cheap but thin, and Signature
Abilities, which is tree-shaped and now has a renderer waiting for it.

The Talents row is worth reading twice. It was estimated here as a straight copy —
"single file, flat rows" — and it is not: `<ActivationValue>taPassive` would have
reached the Type column as a code, and eight talents use `<Attributes>` for what
the talent *grants* while `fetchSource()` reads that tag as a species' *starting
stats*. **A flat single file is not by itself evidence that a type can be copied
straight across.** Check what the app already does with each tag name first.

---

## Vehicles

413 vehicles, one file each under `oggdudes-data/Vehicles/`, in OggDude's own
schema — so, like Species, they go through a translation script before the
converter sees them:

```bash
python xml_to_json/oggdude_vehicles_to_app.py    # rebuild the app-schema source
python xml_to_json/convert.py --only Vehicle     # rebuild data/json/Vehicles.json
```

Most of the schema already matches what the app reads. What the script has to
resolve, each derived from a census of all 413 files:

- **Vehicle weapons are key references.** `<VehicleWeapon><Key>BLASTCANLT` has to
  become a display name out of `Weapons.xml`, the same way species skills and
  talents do — 860 references across 48 distinct keys. **`MINCONCLNCH` does not
  exist in `Weapons.xml`**; the key is kept verbatim and a warning printed rather
  than dropping the weapon. Each weapon also carries `FiringArcs`, `Turret`,
  `Count` and `Qualities` (`LINKED` ×415, `LIMITEDAMMO` ×44, `BREACH`…), and the
  existing `qualityFilter` already renders those keys.
- **Sensor range comes in two shapes.** 380 vehicles carry
  `<SensorRangeValue>srClose`, 165 also carry a plain-text `<SensorRange>Close`.
  `rangeFilter` in `SWApp.js` only maps the `wr…` weapon-range prefixes, so the
  `sr…` values are resolved here instead of adding a second mapping to the app.
  The two agree everywhere except `srNone`, which the data itself spells
  **"No Sensors"** on the 19 vehicles that write it out — so that is the wording
  the mapping uses, and all 48 `srNone` vehicles land on one dropdown entry
  rather than two meaning the same thing. `sensor_range()` warns on any *other*
  disagreement, so the check stays live.
- **Firing arcs are six booleans** and become the display-ready
  "Fore, Aft, Port, Starboard", the way `Crew` is already free text.
- **Booleans arrive as the strings `"true"`/`"false"`** — `Starship`,
  `NaviComputer`, `Restricted`, `SinglePilot`, `Massive`.
- `<Source Page="50">` needs no work: the converter's `expand_source_pages()`
  already rewrites it, and the `<Sources>` shape 69 vehicles use is what it emits.

Three export bugs the script works around, all found by checking the output
field-by-field against the 413 source files:

- **`EF76` spells the tag `<Starfighters>`** where 241 other vehicles use
  `<StarFighters>`. It is the only case-variant tag in the whole vehicle export.
  `field_text()` falls back to a case-insensitive match and writes the canonical
  name, so the JSON has one key rather than two.
- **Five vehicles cite the same book twice.** `ATTE` and `CONSLTCRUIS` repeat
  *Forged in Battle* p57 verbatim; `T47ALLIANCE`, `T47AIRSPEEDER` and
  `HWK1000LTFREIGHT` cite one book once with a page and once without, which would
  render as two source lines for one citation. `dedupe_sources()` folds them,
  keeping the entry that carries the page. Two *different* pages for one book is
  left alone — that is a real two-page citation.
- **Two dangling key references**, both kept verbatim with a warning rather than
  dropped: `MC-2CMMNDSPDR` mounts weapon `MINCONCLNCH`, which is not in
  `Weapons.xml`, and `TSMEU6` lists a built-in attachment whose key is the
  vehicle's own and matches no `ItemAttachment`.

Field coverage worth knowing before binding a template to it: `Key`, `Name`,
`Description`, `Type`, `Rarity`, `Silhouette` and `SystemStrain` are on all 413.
`Price` 412, `HullTrauma` 410, `Speed` 409, `HP` 401, `EncumbranceCapacity` 395,
`Armor` 386, `Source` 385, `Handling` 375, `Passengers` 369, `VehicleWeapons` 290
non-empty, `MaxAltitude` only 114. **`Handling` runs −6 to +3 and is the only
signed stat in the app** — no existing field exercises a negative, so both the
display and the min/max sliders need checking against it.

`Categories` has 12 clean values (Starship, Land Vehicle, Capital Ship, Walker…)
and makes a far better sidenav filter than `Type`, which has 91.

Artwork: `oggdudes-data/VehicleImages/` covers 327 of 413 (79%), named by bare
`Key`, so `cp VehicleImages/<KEY>.png data/img/Vehicle<KEY>.png`.

---

## Careers

20 careers, one file each under `oggdudes-data/Careers/`, in OggDude's own
schema — so, like Species and Vehicles, they go through a translation script
before the converter sees them:

```bash
python xml_to_json/oggdude_careers_to_app.py    # rebuild the app-schema source
python xml_to_json/convert.py --only Career     # rebuild data/json/Careers.json
```

A career is almost entirely cross-references, so almost all the work is
resolving them:

- **Career skills are keys.** `<CareerSkills><Key>ASTRO` becomes "Astrogation"
  out of `Skills.xml` — 146 references covering all 35 skills in the game. They
  are written as `<Skills><Skill><Name>`, which is deliberately the shape
  Species already use, so `fetchSource()` unwraps them with no new app code.
- **Specializations are keys too.** `<Specializations><Key>DRIVER` becomes
  "Driver" out of the 123 files under `Specializations/` — 118 references, 112
  distinct, since a few specializations belong to two careers. **Only the name is
  taken.** The specialization itself is a 4×5 talent tree with directional links
  between its nodes; listing which ones a career opens is the useful part and
  needs no renderer.
- **The `<Attributes>` block is almost all zeros.** Seven Force careers carry
  `WoundThreshold`, `StrainThreshold`, `DefenseRanged`, `DefenseMelee`,
  `SoakValue` and `Experience` set to `0`, plus an empty `<Requirement>`. Only a
  non-zero `ForceRating` is written out — that is the one thing a career actually
  grants, and `fetchSource()` already copies `Attributes/ForceRating` onto the
  row, so it reuses the `Adversary` Force column.
- **Those same seven get a `<Categories><Category>Force`**, the tag the talent
  importer already writes, which is what makes "Force career" a *filter* rather
  than just a column — the app builds its Category multi-select from it. The tag
  and the rating are two views of one fact, so `verify_convert.py` asserts they
  never disagree.

**`FreeRanks` is deliberately left incomplete.** OggDude writes it on eight rows
(3 for the Force and Destiny careers, 4 for Clone Soldier) and omits it on the
other twelve, because those grant the standard four. It is *not* defaulted to 4
here: that number is a rules claim the source does not make, and inventing it
would put it in the data rather than in the rulebook. The template shows the line
only for the rows that carry one.

`CLONE` is the only career citing two books (*Rise of the Separatists* and
*Collapse of the Republic*, both p18); the other 19 cite one.

Artwork: none. OggDude ships no career images, so every row falls back to
`img/no_image.png` and the tab has no image column.

---

## Talents

604 listings in a single flat `oggdudes-data/Talents.xml` — and still an
importer, not a copy:

```bash
python xml_to_json/oggdude_talents_to_app.py    # rebuild the app-schema source
python xml_to_json/convert.py --only Talent     # rebuild data/json/Talents.json
```

- **Activation is a code.** `<ActivationValue>taPassive` is what OggDude's
  character builder switches on; copied straight across it would have shown
  "taPassive" in the Type column *and* in the Type dropdown. It becomes display
  text here — Passive (248), Incidental (161), Action (99), Maneuver (49),
  Incidental (out of turn) (44) — the same call the vehicle importer makes for
  the `sr…` sensor ranges.
- **`<Attributes>` means something else here.** On a species it holds the
  starting wound threshold, strain threshold and experience, and `fetchSource()`
  copies those onto the row. Eight talents carry the same tag for what the talent
  *grants*: `TOUGH` has `<WoundThreshold>2`, `FORCERAT` has `<ForceRating>1`,
  `GRIT` has `<StrainThreshold>1`. Copying the file across would have put "2" in
  a talent's Wound Thr. column and given the tab a set of nonsense sliders.
  Dropped — every one of them is spelled out in the talent's own description.
- **Three keys are listed twice.** `FORCEWILL` and `WORKLIKECHARM` are the same
  talent reprinted in a second book, `ANALYZEDATA` is written out verbatim twice.
  The converter's first-Key-wins merge would keep whichever came first and throw
  the other citation away, so "Force of Will" would have vanished from the app
  the moment the Age of Rebellion line was switched off, despite also being in
  *Collapse of the Republic*. `merge_duplicate_keys()` folds them and unions the
  citations; the first listing still decides name, type and description. The two
  listings always disagree on the description — each says "please see page N of
  *its own book*" — so only the mechanical fields are compared, and a
  disagreement there is reported rather than merged quietly.
- **Ranked, ForceTalent and Conflict become `<Categories>`**: Ranked (162),
  Force (131), Conflict (14). That is the same tag vehicles use for their
  Starship/Walker/… list, so the app already renders it under the talent name and
  already builds a multi-select from it — three filterable flags for no new UI.
  `<Conflict>` is `1` on all fourteen rows that carry it, so the tag alone says
  everything the number would.

Everything else OggDude carries drives the character builder rather than
describing the talent, and is dropped: `DieModifiers` (31 rows), `SkillChars`,
`SkillChoice`, `CharacteristicChoices`, `ChooseCareerSkills`, `ItemChanges`,
`SelectedItem`, `RosterMods`, `JuryRigged`, `Rigger`, `Damage`,
`ModPercentDiscount`, `LessStrain`, `AddlHP`, `HPPerItem`, `AddlCyber`,
`SetForceRating`.

Artwork: none, same as careers.

---

## Specializations and force powers

The two tree types: 123 specializations under `oggdudes-data/Specializations/`
and 20 force powers under `oggdudes-data/Force Powers/`, one file each.

```bash
python xml_to_json/oggdude_specializations_to_app.py   # rebuild the app-schema source
python xml_to_json/oggdude_force_powers_to_app.py
python xml_to_json/convert.py --only Specialization --only ForcePower
```

These two importers differ from the others in kind, not just in detail: **their
output is a layout**. A specialization is not a row of stats, it is a picture —
a grid of boxes with connectors between them — and the app draws it in the row's
expandable detail area rather than in a cell. Everything geometric is decided
here, so `SWApp.js` only unwraps SimpleXML shapes and `items.html` only draws.
`oggdude_force_powers_to_app.py` imports the layout functions from the
specializations importer rather than restating them.

The rules, each derived from a census of all 143 files:

- **Every row lays out to exactly four columns**, counting spans. That is the
  invariant the renderer rests on, and `verify_convert.py` Check 7 tests it on
  every row of every tree.
- **A box can span up to four columns.** Only force powers do; Move's first row
  is one Basic Power four wide. The covered cells repeat the same key as filler
  and are dropped. Specializations are a clean 5×4 and never span — Check 7
  asserts that too, since `layout_row()` reads spans only when passed them.
- **A cell can be a hole.** A `<Span>` of 0 that nothing covers is a blank
  column, not a missing box: Endure's last row is `0, 2, 0, 0` — a gap, a
  double-wide Mastery, a gap. Warde's Foresight writes an empty `<Key />` with
  a span of 1 and a cost of 5 XP. Both render blank and keep their column.
- **Links are undirected and stated twice** — `Down` on the upper cell, `Up` on
  the lower — and **nine of them are stated only once**. A link is emitted when
  *either* end declares it. That is not a coin toss: under the intersection two
  nodes in *Enhance* and *Farsight* become unreachable from the top row, which
  no printed tree does. Every one-sided flag is reported and Check 7 counts them
  (4 and 5 today), so a changed export surfaces instead of being absorbed.
- **Each connector is written out once**, from the end that owns it: a vertical
  link as `<Down><Col>` on the row *above*, a horizontal one as `<LinkRight>` on
  the *left* box. Vertical links stay **per column** rather than per box,
  because a four-wide box can be joined downward in all four.

Nine horizontal links sit *inside* a spanning box, joining a cell to itself.
There is nowhere to draw them and they are dropped; the box is already one box.

Key resolution is the familiar part: talent keys against `Talents.xml` (591
distinct, all resolve), force ability keys against `Force Abilities.xml` (all
177 used), skill keys against `Skills.xml`. A specialization's careers are a
**reverse lookup** — a specialization file never names its career, so
`Careers/*.xml` is read backwards — and land in `<Categories>`, the tag the app
already builds a multi-select from.

Force powers alone carry `<MinForceRating>`, stated by 14 of 20 and **not
defaulted** for the other six, and `<Experience>`, the summed cost of every box
(90 to 215 XP). On a specialization that total is the constant 300 and is not
written.

Dropped: `<AddlCareerSkills>` (empty on 9 of the 10 specializations that have
it), and the `<Attributes>` / `<Requirements>` blocks, which are all zeros on
every one of the 123 files.

Artwork: none, same as careers and talents. Descriptions are still OggDude's
page pointers for both types — the tree is the content, so it costs far less
here than it did for talents, but `wiki_descriptions.py` would cover them with
one `SOURCES` entry each.

Both have a `wiki_diff.py` target, and both report **0 data-only**: every
specialization and force power in the data matches a wiki page. Note that the
categories are **singular** — `Category:Specialization` and `Category:Force
Power`; the plural forms do not exist and come back empty — and that their pages
are titled with the bare name, so unlike talents there is nothing to `strip`.
