# TODO

Roughly in the order they are worth doing. Everything under *Display missing* is
already in `data/json/` and needs no import at all.

## Fill in missing details in

OggDude's export ships **no rules text**. Almost every `Description` in the data
is a pointer — "Please see page 132 of the Edge of the Empire Core Rulebook for
details":

| Type | Rows | Descriptions that are just a page pointer |
| --- | --- | --- |
| Armor | 111 | 100% |
| Vehicles | 413 | 98% |
| Weapons | 469 | 98% |
| Gear | 584 | 97% |
| Attachments | 357 | 97% |
| Species | 102 | 58% |
| Talents | 601 | ~2% (was 91%) |
| Careers | 20 | 0% (was 100%) |

For most types the stats carry the information and the missing prose costs
little. For these two it was the whole content, and both are now done:

- [x] **Talents** — 588 of 601 rows now carry the real rules text, taken from
      the fandom wiki by `xml_to_json/wiki_descriptions.py`. The 13 without a
      wiki page keep their pointer; they are listed in
      `xml_to_json/wiki_diff/talents-descriptions.md`.
- [x] **Career** — all 20 carry the flavour paragraph from the wiki's career
      category page.

Species is the one type that already read well, because its text comes from
`OptionChoices` and `SpecialAbilities` rather than from `Description`.

Still open on this front:

- [ ] **Talent trees.** The wiki lists, per talent, which specializations offer
      it and at what tier (`*'''Trees:'''`). That is real information the data
      does not have, and `wiki_descriptions.py` deliberately drops it — it needs
      a column of its own, not a paragraph glued to the description.
- [ ] The other six types are still pointers. The wiki has pages for most of
      them; the same machinery would cover them, one `SOURCES` entry each. Lower
      value, since the stats already carry those rows.

## Get Missing Data from books

- [x] **Where the text comes from, and whether it can be redistributed.** It
      comes from the FFG fandom wiki, which is Fandom's default **CC BY-SA
      3.0** — redistributable with attribution and share-alike, though the
      underlying rules are FFG's copyright. The generated files carry an
      attribution header and `wiki_diff/<type>-descriptions.md` records the page
      and revision behind every line. **Worth a deliberate decision before the
      next public deploy** — the repo now ships prose it did not before.
- [x] **What shape it lands in.** `xml_to_json/xml_sources/fandom-wiki/`, a
      second source folder that sorts before `oggdude` and so wins the
      first-Key-wins merge. Each row is the oggdude row copied verbatim with
      only `<Description>` swapped, and `verify_convert.py` Check 6 proves it.
- [x] `wiki_diff.py` reports what the wiki has that the data does not. The
      `careers` and `talents` targets work now: careers are wiki
      *subcategories* rather than pages, and a talent's page is titled
      "<Name> talent", neither of which the tool used to know.

Left over from the survey, for whoever wants more content:

- [ ] 193 talents and 4 careers exist on the wiki but not in the data — see
      `xml_to_json/wiki_diff/talents.md`. Much of it is homebrew (the report
      sorts official material first), but not all.

## Could become a tab

Surveyed against `oggdudes-data/`; the full table with volumes lives in
`xml_to_json/README.md` under *What else could become a tab*.

- [ ] **Skills** — 35 rows, flat single file, trivially table-shaped. Cheap, but
      thin: at 35 rows it is a reference list rather than something the
      sliders-and-filters table earns its keep on. Its one real draw is the
      characteristic each skill keys off (`CharKey`).
- [ ] **Adversaries** — the UI is *already built*: 29 `name == 'Adversary'`
      conditions in `items.html`, with Soak, both thresholds, all six
      characteristics and Force rating wired. OggDude ships no adversary export,
      so this is blocked on a data source, not on code. Do not treat those
      `ng-if`s as dead code.
- [ ] **Specializations** (123), **Force powers** (20), **Signature abilities**
      (38) — all talent *trees*: a 4x5 grid with directional links between
      nodes. These need a renderer, not a table, which is UI this app does not
      have. Specialization **names** already appear on the Careers tab, which is
      most of the value for a fraction of the work.

## Get misising books

Can be compared to wiki, for instance. Or pdf files.