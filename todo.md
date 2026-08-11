# TODO

Roughly in the order they are worth doing. Everything under *Display missing* is
already in `data/json/` and needs no import at all.

## Display missing

- [ ] **Fix the Limits column on both attachment tabs.** `items.html:1186-1193`
      calls `isString()` and `isObject()`, and neither is defined on the scope,
      so `ng-if` is always false and the **"Item:" and "Skill:" limits have never
      rendered on any build**. 59 attachments carry a non-empty `ItemLimit` and
      18 a `SkillLimit`; the `CategoryLimit` (139) and `TypeLimit` (58) lines
      beside them render fine, which is why it has gone unnoticed. Two lines on
      `$scope`; check both shapes, since the normalisation makes these arrays of
      strings and the template also handles a nested case.
- [ ] **Vehicle-attachment fit rules.** Now that the vehicle attachments have
      their own tab, the fields that decide whether a mod actually fits are the
      ones missing from it. Of the 125 rows on that tab: `MaxSize` (18),
      `MustBeStarship` (11), `MinSize` (10), `MustHaveHyperdrive` (3),
      `MinEncumCap` (3).
      "Silhouette 3-5, starship only, needs a hyperdrive" belongs in the Limits
      column next to the category and type limits — an addition to that cell,
      not a new column.
- [ ] **`Restricted`.** Flagged on 117 weapons, 132 gear, 105 vehicles, 62
      attachments and 42 armor, and shown nowhere. It is a one-glyph badge next
      to the name, and a plausible filter. Note the field is the *string*
      `"true"`/`"false"`, not a boolean — `"false"` is truthy in JS, so it needs
      `== 'true'` rather than a truthiness test.
- [ ] **`Hidden` and `JuryRigged`** on attachments (14 and 100 rows). Same
      zero-import story, smaller payoff.
- [ ] **Species skill filter.** Dropping the `Career` gate on the one
      `collectValues` line at `SWApp.js:2224` would let species be filtered by
      the skill they grant, reusing the multi-select the Careers tab now has.
      The dropdown label would need to stop saying "Career skill".

## Fill in missing details in

OggDude's export ships **no rules text**. Almost every `Description` in the data
is a pointer — "Please see page 132 of the Edge of the Empire Core Rulebook for
details":

| Type | Rows | Descriptions that are just a page pointer |
| --- | --- | --- |
| Armor | 111 | 100% |
| Careers | 20 | 100% |
| Vehicles | 413 | 98% |
| Weapons | 469 | 98% |
| Gear | 584 | 97% |
| Attachments | 357 | 97% |
| Talents | 601 | 91% |
| Species | 102 | 58% |

For most types the stats carry the information and the missing prose costs
little. For these two it is the whole content:

- [ ] **Talents** — 601 rows, ~547 of them a page pointer. Without the text a
      talent is a name, an activation type and three flags; there is nothing to
      tell you what it *does*. The worst offender in the app.
- [ ] **Career** — 20 of 20 are pointers. Less painful, because the career
      skills and specializations now shown on the tab are the substance, and the
      description is mostly flavour.

Species is the one type that reads well today, because its text comes from
`OptionChoices` and `SpecialAbilities` rather than from `Description`.

## Get Missing Data from books

The source for the above. Worth deciding before starting:

- [ ] Where the text comes from, and whether it can be redistributed. The
      descriptions are FFG's copyrighted rules text; the current data set only
      ever points at a page number, which may be exactly why.
- [ ] What shape it lands in. It has to go into the **XML sources**, never into
      `data/json/*.json` — those are generated, and hand-edits are lost on the
      next `convert.py` run. A hand-written set is a second folder under
      `xml_to_json/xml_sources/` that merges by `Key`, which the pipeline already
      supports: folders are read in alphabetical order and the first `Key` wins,
      so a folder sorting before `oggdude` overrides it per row.
- [ ] `wiki_diff.py` already reports what the fandom wiki has that the data does
      not, per type, including the new `careers` and `talents` targets. That is
      the cheapest survey of what is missing before anyone starts transcribing.

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