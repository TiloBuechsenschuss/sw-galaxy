# Archive of ToDo's
This file lists previous todo's that are now finished.

## 2026-08-16

### Display missing

- [x] **Fix the Limits column on both attachment tabs.** Two bugs, not one. The
      template called `isString()`/`isObject()`, neither defined on the scope, so
      the `ng-if` was always false — but `fetchSource()` was also unwrapping
      `ItemLimit.Item` and `SkillLimit.Skill` when the child element in both is
      `Key`, so those arrays came out empty anyway. Both fixed; the nested case
      the template guarded never existed, so it is gone. 35 rows now show an
      "Item:" line and 17 a "Skill:" line (the 59/18 counted in the JSON include
      the `<ItemLimit>\n</ItemLimit>` whitespace-only elements, which carry no
      limit). `ItemLimit` holds item *keys* from other JSON files, so it got an
      `itemLimitFilter` name list; `SkillLimit` reuses `skillFilter`.
      `itemLimits`/`skillLimits`/`typeLimits` were also never declared and were
      leaking to `window` — now in the `var` list.
- [x] **Vehicle-attachment fit rules.** In the Limits cell, as an addition to it:
      `Silhouette: 3-10` / `5+` / `up to 2`, `Starship only`, `Needs a
      hyperdrive`, `Encum. capacity: 25+`. 23 rows get a silhouette line, 9
      starship-only, 1 each hyperdrive and capacity. The higher counts in the
      original note included the rows whose value is `0` or `"false"`, which is
      OggDude's "no bound" — two rows pair a real `MinSize` with a `MaxSize` of
      0, so a truthiness test would have printed "Silhouette 5-0".
- [x] **`Restricted`.** A floated `gavel` badge in the Name cell plus a
      "Legality" dropdown, on all five types that carry the field. Normalised in
      `fetchSource()` to `'Restricted'`/`'Unrestricted'`, which also defaults the
      rows where the field is *absent* (204 weapons, 235 gear, 218 attachments) —
      those mean the same as an explicit `"false"`, and without the default
      picking "Unrestricted" would have hidden two thirds of the tab.
- [x] **`Hidden` and `JuryRigged`** — checked and deliberately not shown. The
      data is not what this entry assumed. `Hidden` is OggDude's "don't offer
      this in the picker" flag, not a game rule: its 14 rows are the 11 Special
      Modifications crafting templates (Combat Plating, Ion Drive Array…),
      "Additional Cars", and two "Lessons" gear entries. `JuryRigged` is `"true"`
      on exactly two rows — the 100 counted are 98 `"false"` plus 2 `"true"` —
      and both are already named "Jury Rigged (Armor)" and "Jury Rigged
      (Weapon)", so the badge would restate the name.
- [x] **Species skill filter.** The `collectValues` gate is now `Career` **or**
      `Species`, and the dropdown is labelled just "Skill". 23 distinct skills
      across the 73 species that grant one; the Species tab already lists them in
      the Name cell, so the filter has something to point at.

### Console noise

All pre-existing, all now silent — zero `Please add base mod mapping for: …` and zero
`debugging!` against the committed data.

- [x] **The false "missing mapping" lines.** `descriptorFilter` and `talentFilter` each
      logged when *they* did not match, but a mod key is a descriptor or a talent, never
      both — so each reported every key the other resolved. That is why the console named
      *already-resolved display text* (`Please add base mod mapping for: Additional Damage
      Mod`). Neither has any caller but `modFilter`, which already reports the real case,
      so the two inner logs are gone. ~893 of the ~1003 lines.
- [x] **`debugging!`** was one row: the Glop Grenade has two `<MiscDesc>` siblings in one
      `<Mod>`, which SimpleXML makes an array. `infoFilter` read only the string shape, so
      both sentences were dropped and it fell through to a `<Key>` that does not exist.
- [x] **52 genuinely unmapped base-mod keys.** 16 mechanical ones (`REMQUAL*`, `SUBQUAL*`,
      `DAMADDCRYS`, `DAMSUBCRYS`, `DEFSET`, `DEFADDFORCE`, `SOAKSET`, `MOVEBASIC`,
      `RETRACTWEAPSYSTEM`) plus 36 skill and characteristic keys. The skills use FFG's own
      printed term, confirmed against the Strength Enhancing System entry — *"Modification
      Options: 2 Skill (Athletics) Mods"* for its `{"Key":"ATHL","Count":2}`, and
      *"Increases wearer's Brawn by one point"* for its `{"Key":"BR","Count":1}`. Names
      come from `oggdudes-data/Skills.xml`, the table the Careers and Species importers
      already use.
- [x] **`SkillIsCareer`.** 54 mods share those skill keys but carry no `Count` and grant no
      rank — they make the skill a career skill (all the Hologoggles and Holocrons). They
      would have claimed to grant a Skill Mod, so `infoFilter` renders them as
      "Athletics as a career skill". The flag is invisible to `descriptorFilter`, which
      only ever sees the bare key.

- [x] **Talent mods name themselves.** The books print modification options as "2 Innate
      Talent (Brace) Mods"; the app printed "2 x Brace". `modFilter` now wraps whatever
      `talentFilter` resolves, leaving its 474 lines alone — everything that list resolves
      *is* a talent the item grants, since it has no other caller. Checked: all 33 talent
      keys in the data are real rows on the Talents tab and each equals that talent's own
      `Key`; and over all 217 mod keys, exactly those 33 changed, the other 184 byte for
      byte identical. Demon Mask, Iron Fists and Meditation Focus sound like talents but
      are in `descriptorFilter` and stay unwrapped — none is in `Talents.json`, each is an
      artifact effect named after its own piece of gear.

### Rules text from the wiki

OggDude ships **no rules text** — almost every `Description` is "Please see page 132 of
the Edge of the Empire Core Rulebook for details". `xml_to_json/wiki_descriptions.py`
now fills that in for the four types where the prose *is* the content, from
<https://star-wars-rpg-ffg.fandom.com>. Full detail in `xml_to_json/README.md` under
*Rules text from the wiki*.

- [x] **Talents** — 588 of 601 rows carry the real text. The 13 with no wiki page keep
      their pointer and are listed in `xml_to_json/wiki_diff/talents-descriptions.md`.
- [x] **Careers** — all 20 carry the flavour paragraph from the wiki's career *category*
      page. A career is a category, not an article, which is why this did not work before.
- [x] **Force powers** — all 20, the lead paragraph of the power's page.
- [x] **Force abilities** — all 177, and the one type with **no page of its own**: they
      are paragraphs on their *power's* page under `===UPGRADES===`, labelled only by
      kind (`'''Control Upgrade:'''`), up to ten under the identical label. Matching them
      to keys is **not positional** — the wiki orders upgrades alphabetically by label and
      follows the book within them, while Enhance's keys run `CONT1` Coordination, `CONT2`
      Resilience, `CONT3` Force Leap against a page that runs Coordination, Piloting
      (Planetary), Piloting (Space), Agility… Pairing in order mis-describes seven of its
      ten. They are told apart instead by the distinctive words in each ability's own
      name, weighted by how many paragraphs of the group carry each word.

      Three things decided whether that was right, each of which got it wrong first:
      the power's own name is not a clue on its own page (*Sense* appeared in exactly one
      Sense paragraph — the wrong one — and the tie put three abilities out by one); the
      stop list has to stay short (*target* was on it and cost Seek the one paragraph that
      says *target*); and `prose()` has to keep `*'''Heal:'''` bullets here, since
      dropping them as talent-page headers left seven abilities holding nothing but
      "This Control upgrade has different effects for Heal and for Harm."

      166 of the 177 match on a word or are the only paragraph of their kind, 9 are
      settled by elimination, and **2 are a genuine guess** — Imbue's two upgrades are
      both named "Duration" and no content separates them; paired in order, which reading
      them confirms (the first commits two Force dice, the second reduces it to one).
      `wiki_diff/forceabilities-descriptions.md` names how every row matched.
- [x] **Where the text comes from, and whether it can be redistributed.** The FFG fandom
      wiki, Fandom's default **CC BY-SA 3.0** — redistributable with attribution and
      share-alike, though the underlying rules are FFG's copyright. The generated files
      carry an attribution header and `wiki_diff/<type>-descriptions.md` records the page
      and revision behind every line. *The deploy decision this raised is still open — see
      `todo.md`.*
- [x] **What shape it lands in.** `xml_to_json/xml_sources/fandom-wiki/`, a second source
      folder that sorts before `oggdude` and so wins the first-Key-wins merge. Each row is
      the oggdude row copied verbatim with only `<Description>` swapped, and
      `verify_convert.py` Check 6 proves it — including, now, that no two rows in one
      override file share a description, which is the offline shape of the bullet bug
      above.
- [x] **`wiki_diff.py` coverage targets.** `careers` and `talents` work now (careers are
      wiki *subcategories*, and a talent's page is titled "<Name> talent" — neither of
      which the tool used to know), and `specializations` and `forcepowers` were added.
      Both new targets report **0 data-only**: every row matches a wiki page. Note the
      categories are *singular* — `Category:Specialization`, `Category:Force Power`; the
      plurals do not exist.

### Talent trees and force trees

Two new tabs, and the first content in the app that is a *picture* rather than a row: a
grid of boxes with connectors, drawn in the row's expandable area. See *Talent trees and
force trees* in `AGENTS.md`.

- [x] **Specializations (123) and Force powers (20)** — the **Talent Trees** and **Force
      Trees** tabs. The geometry is computed at import time by
      `oggdude_specializations_to_app.py`, which `oggdude_force_powers_to_app.py` imports
      rather than restating; `readTree()` only unwraps SimpleXML shapes and the template
      only draws. `verify_convert.py` Check 7 asserts the invariant the CSS grid rests on:
      every row lays out exactly four columns wide, counting spans.

      What the data made hard: a box can span up to four columns and a cell can be a
      *hole* (a span of 0 that nothing covers, or a present-but-empty `<Key/>` that still
      claims a 5 XP cost), both of which break the width if mishandled. And links are
      undirected but stated twice, with **nine stated only once** — emitted on the union,
      which is not a coin toss: under the intersection two nodes in *Enhance* and
      *Farsight* become unreachable from the top row, which no printed tree does.
- [x] **Talent trees, the open question from the wiki work.** Solved from the data rather
      than the wiki: the 123 specialization files say which talents a tree offers and at
      what tier, so the tab draws the tree and the *Teaches* dropdown answers "which trees
      offer Grit?" directly. The wiki's `*'''Trees:'''` bullets stay dropped — the data
      says the same thing, per tier.
- [x] **What a box does: tooltip and popup.** Hovering a box gives its rules text;
      clicking or tapping it opens a `$mdDialog` (`app/components/tree-node.html`) with
      the name, XP price, activation, tags, full text and citation. Two ways in because a
      phone has no hover and the app is used at the table. The text comes from a lookup
      file the tab fetches once and keys into — `Talents.json` for talent trees, and
      `ForceAbilities.json`, generated for this and having no tab of its own, for force
      trees. Embedding the prose in the trees instead would repeat Grit's text in dozens
      of them.

      Two bugs found on the way: `readList()` silently dropped single *string* children,
      so a talent with exactly one category showed no tags (133 boxes → 1824); and the
      trees were being built for every row on screen, expanded or not, because the
      collapse row is `ng-show` — with a tooltip per box, "Show all" would have put 2460
      of them in the DOM unseen.