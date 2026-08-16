# TODO

Roughly in the order they are worth doing. Finished work moves to
[todo archive.md](todo%20archive.md), newest date first.

## Fill in missing details in

OggDude's export ships **no rules text**. Almost every `Description` in the data
is a pointer — "Please see page 132 of the Edge of the Empire Core Rulebook for
details". Where it stands now:

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
| Force powers | 20 | 0% (was 100%) |
| Force abilities | 177 | 0% (was 100%) |

Species is the one type that already read well without help, because its text
comes from `OptionChoices` and `SpecialAbilities` rather than from
`Description`.

- [ ] **The other six types are still page pointers.** The wiki has pages for
      most of them and the same machinery would cover them — one `SOURCES` entry
      in `wiki_descriptions.py` each, plus a `wiki_diff.py` target to see the
      coverage first. Lower value than the four already done, since for those
      six the stats carry the information and the prose is colour.
- [ ] **193 talents and 4 careers exist on the wiki but not in the data** — see
      `xml_to_json/wiki_diff/talents.md`. Much of it is homebrew (the report
      sorts official material first), but not all.

## Could become a tab

Surveyed against `oggdudes-data/`; the full table with volumes lives in
`xml_to_json/README.md` under *What else could become a tab*.

- [ ] **Signature abilities** (38) — the third and last tree type. Structurally
      the force powers again — 3 rows of 4, spans and per-box costs, names out of
      a separate `SigAbilityNodes.xml` the way abilities come from
      `Force Abilities.xml` — so the renderer and the layout code already fit.
      **One export quirk to handle first: 26 of its 114 rows write 16 `<Span>`
      entries for 4 cells**, all four rows' spans flattened into the first row's
      element, which `layout_row()` would read the first four of and quietly
      mislay the rest.
- [ ] **Skills** — 35 rows, flat single file, trivially table-shaped. Cheap, but
      thin: at 35 rows it is a reference list rather than something the
      sliders-and-filters table earns its keep on. Its one real draw is the
      characteristic each skill keys off (`CharKey`).
- [ ] **Adversaries** — the UI is *already built*: 29 `name == 'Adversary'`
      conditions in `items.html`, with Soak, both thresholds, all six
      characteristics and Force rating wired. OggDude ships no adversary export,
      so this is blocked on a data source, not on code. Do not treat those
      `ng-if`s as dead code.

## Get missing books

Can be compared to wiki, for instance. Or pdf files.
