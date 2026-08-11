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

```bash
python xml_to_json/oggdude_species_to_app.py     # refresh the OggDude source set
python xml_to_json/convert.py --only Species     # rebuild one JSON file
python xml_to_json/convert.py --check            # report, write nothing
python xml_to_json/verify_convert.py             # prove nothing regressed
```

`php xml_to_json/convert.php` does the same job as `convert.py`. It can also be
triggered over HTTP if you are running Apache or nginx.

---

## Merge rules

`convert.php`/`convert.py` glob `xml_sources/*/<Type>.xml`, so **folders are read
in alphabetical order**, and:

1. **First occurrence of a `Key` wins.** A folder sorting earlier overrides later
   ones. There is currently only one folder, `oggdude`, so nothing collides —
   but this is what to reason about when adding a second.
2. **…except that fan-made data always loses.** An entry whose every source book
   is in `$deprioritisedBooks` / `DEPRIORITISED_BOOKS` (currently just
   *Unofficial Species Menagerie*) is replaced by any entry carrying an official
   book, whatever the folder order. 27 species are Menagerie-only and have no
   official version, so they stay; the app hides them by default via
   `defaultDisabledSources` in `SWApp.js`.
3. **Species are sorted by `Name`** before writing (`$sortByName` / `SORT_BY_NAME`),
   so the committed JSON has a stable diff. Other types keep source order.
4. Recognised file names are fixed in `$validFileNames`: `Armor.xml`,
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

`convert.php` is a *mechanical* XML→JSON conversion. It never reshapes anything.
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
   plain string `"Edge…"`, not `{"@attributes":…}`. The XML carries 1677
   `Page="…"` attributes and the JSON contains no `@attributes` key at all.
   *This is why page numbers only survive when `<Page>` is a child element.*
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

`$deprioritisedBooks` / `DEPRIORITISED_BOOKS` and `$sortByName` / `SORT_BY_NAME`
sit at the top of `convert.php` and `convert.py`. **Change both**, then run
`verify_convert.py`.
