# Data pipeline

How the JSON the app reads gets built, and how to add more of it.

```
oggdudes-data/                    raw OggDude export (any format)
        |
        |  oggdude_species_to_app.py      <- reshapes to the app's schema
        v
xml_to_json/xml_sources/<set>/*.xml       <- app-schema XML, one folder per set
        |
        |  convert.py  (or convert.php)   <- merges + emits JSON
        v
data/json/*.json                          <- what index.html actually loads
```

`Armor.xml`, `Weapons.xml`, `ItemAttachments.xml` and `Gear.xml` are already in
the app's schema and are copied straight into `xml_sources/oggdude/`. **Species
are the exception** — OggDude ships them one file per species in a different
schema, so they have to go through `oggdude_species_to_app.py` first.

Both the XML sources and the generated JSON are committed. A data change is
expected to include the regenerated JSON in the same commit.

---

## Scripts

| Script | What it does |
| --- | --- |
| `convert.php` | The original converter. Needs PHP 7. |
| `convert.py` | Python port of `convert.php`, for machines without PHP. **Must stay byte-identical in output.** |
| `oggdude_species_to_app.py` | Reshapes OggDude's per-species XML into the app's species schema. |
| `verify_convert.py` | Regression checks. Run after touching any of the above. |
| `wiki_diff.py` | Reports what a wiki category has that the JSON does not, and vice versa. Read-only. |

```bash
python xml_to_json/oggdude_species_to_app.py     # refresh the OggDude source set
python xml_to_json/convert.py --only Species     # rebuild one JSON file
python xml_to_json/convert.py --check            # report, write nothing
python xml_to_json/verify_convert.py             # prove nothing regressed
python xml_to_json/wiki_diff.py --all            # coverage against the fandom wiki
```

`php xml_to_json/convert.php` does the same job as `convert.py`. It can also be
triggered over HTTP if you are running Apache or nginx — but that is a note about
how the script *can* be used, not an invitation to start a server. Agents run the
converters from the command line and never serve anything; see *Verifying changes*
in `AGENTS.md`.

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
python xml_to_json/wiki_diff.py --all         # all six
```

Targets are one line each in `TARGETS` at the top of the script — wiki category,
JSON file, its type key. Nothing else is target-specific, so covering something
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

## Merge rules

`convert.php`/`convert.py` glob `xml_sources/*/<Type>.xml`, so **folders are read
in alphabetical order**, and:

1. **First occurrence of a `Key` wins.** A folder sorting earlier overrides later
   ones. There is currently only one folder, `oggdude`, so nothing collides —
   but this is what to reason about when adding a second.
2. **Excluded books are not imported at all.** A row whose every source book is
   in `$excludedBooks` / `EXCLUDED_BOOKS` is skipped, so neither the row nor the
   book name reaches the JSON or the app's Source filter. This drops 28 rows
   (27 species and one Gear entry). A row with *no* source is kept — seven
   generic Gear entries have none and are legitimate. A row that mixed an
   excluded book with a kept one would be ambiguous; none exists, so the
   converters print a warning instead of guessing.
3. **Every type is sorted before writing** — by the row's *first* `Source` book,
   then by `Name`, with `Key` as the tie-breaker (`compareRows` in `convert.php`,
   `sort_key` in `convert.py`). Source order in the XML is not preserved: OggDude
   regenerates its exports in an arbitrary order, and sorting is what keeps the
   committed JSON diffing cleanly across refreshes. Comparison is
   case-insensitive over ASCII only, matching PHP's byte-wise `strtolower()`.
   A row with no source book at all sorts first.
4. **Source pages are un-attributed first.** OggDude writes the page as an XML
   attribute — `<Source Page="44">Forged in Battle</Source>` — and SimpleXML
   drops attributes (quirk 1 below), so every page number was being thrown away
   for Armor, Weapons, Gear and ItemAttachments. `expandSourcePages()` /
   `expand_source_pages()` rewrite those into
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

`convert.php` is a *mechanical* XML→JSON conversion. Beyond the two repairs in
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

## PHP quirks the Python port has to reproduce

`convert.php` leans on `simplexml_load_string()` + `json_encode(JSON_NUMERIC_CHECK)`,
whose behaviour is surprising in four ways. All four were found by regenerating
the committed JSON and diffing until it matched — `verify_convert.py` still
checks all of them.

1. **Attributes are dropped.** `<Source Page="169">Edge…</Source>` becomes the
   plain string `"Edge…"`, not `{"@attributes":…}`. The XML carries 1783
   `Page="…"` attributes and the JSON contains no `@attributes` key at all.
   Page numbers therefore only survive when `<Page>` is a child element — which
   is why the converters rewrite `<Source Page="…">` into that shape up front
   (merge rule 4). Any *other* attribute added to the sources in future will
   still vanish silently.
2. **Whitespace-only elements keep their text** under a `"0"` key:
   `<BaseMods>\n    </BaseMods>` → `{"0":"\n    "}`, while a truly empty element
   gives `{}`.
3. **`JSON_NUMERIC_CHECK` uses PHP 7 `is_numeric()`** — leading whitespace is
   allowed, trailing whitespace is not. `<Count>4\n    </Count>` stays the
   *string* `"4\n    "`. (PHP 8 changed this; the committed data predates it.)
4. **Nested XML comments survive** as `"comment": {}`. `convert.php` only does
   `unset($data->comment)` at the root, which is what commit `23a8b4e` fixed —
   comments deeper in the tree still land in the JSON.

Output format, matched by both converters: pretty-printed with 4 spaces, PHP's
escaped forward slashes (`data\/img\/…`), ASCII-only, CRLF line endings, no
trailing newline.

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

`$excludedBooks` / `EXCLUDED_BOOKS` sit at the top of `convert.php` and
`convert.py`; the output order lives in `compareRows` / `sort_key` just below.
**Change both files**, then run `verify_convert.py`.

---

## What else could become a tab

Surveyed against `oggdudes-data/` while planning the Vehicles import. Volumes are
row counts for single-file exports, file counts for folder exports. The app-side
work is the same for all of them — see *Adding a new data type* in `AGENTS.md`;
what differs is the import.

| Candidate | Volume | Import effort |
| --- | --- | --- |
| **Vehicles** | 413 files | Done — `oggdude_vehicles_to_app.py`, see below |
| **Adversaries** | none | **Already half-built in `items.html`** (29 `name == 'Adversary'` conditions, full characteristic columns). OggDude ships no adversary export, so the UI exists and the data does not. Blocked on a data source, not on code. |
| Talents | 604 rows | Easy. Single `Talents.xml`, flat rows, and `talentFilter` in `SWApp.js` already maps every key to a display name. Best value per unit of work. |
| Vehicle attachments | 126 rows | Zero import work — they are already in `ItemAttachments.json` with `Type: Vehicle`. A filtered view or a split-out tab, not an import. |
| Specializations | 123 files | Talent *trees* — a 4×5 grid with directional links between nodes. Needs a renderer, not a table. |
| Force powers | 20 files | Same shape as specializations: upgrade trees, not rows. |
| Careers | 20 files | Small, but mostly cross-references into skills and specializations. |
| Signature abilities | 38 files | Same tree problem as specializations. |

The two single-file exports (Talents, and the vehicle attachments already
imported) are table-shaped and cheap. Everything under Specializations, Force
Powers and Signature Abilities is tree-shaped and would need UI this app does not
have yet.

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
