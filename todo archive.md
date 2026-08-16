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