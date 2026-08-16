var App = angular.module('SWApp', [
    'ngMaterial',
    'ngSanitize',
    'md.data.table',
    'fixed.table.header'
]);

App.config(function ($mdThemingProvider) {
    $mdThemingProvider.theme('default')
        .primaryPalette('red');
});

/**
 * Sources that are not selected when the app starts or when the filters are cleared.
 * They stay available in the "Source" filter, so they can be switched on by choice.
 * Names must match the Book name in the data exactly.
 *
 * Empty on purpose: the only entry this ever held was excluded from the import
 * instead, so no data carries it any more. See EXCLUDED_BOOKS in convert.py.
 */
App.constant('defaultDisabledSources', []);

/**
 * The tabs, in the order they appear in the app.
 *
 * One entry per tab: the tab label, the type key wrapping the array inside the
 * JSON (the itemList directive's source-name) and the file to load.
 * index.html repeats over this list, so this array is the tab order: reordering
 * the tabs means moving lines here, and a new tab is one more line. Nothing
 * refers to a tab by position.
 *
 * Two entries may share a file and a type key. Vehicles.json feeds both the
 * Vehicles and the Starships tab, split by the optional vehicleClass, and
 * ItemAttachments.json feeds both Attachments and Vehicle Attachments, split by
 * the optional attachmentClass. vehicleClassFilter and attachmentClassFilter
 * read them; leave one off and the tab shows the whole file.
 */
App.constant('tabs', [
    {label: 'Weapons', name: 'Weapon', url: 'data/json/Weapons.json'},
    {label: 'Armors', name: 'Armor', url: 'data/json/Armor.json'},
    {label: 'Gear', name: 'Gear', url: 'data/json/Gear.json'},
    {label: 'Attachments', name: 'ItemAttachments', url: 'data/json/ItemAttachments.json', attachmentClass: 'item'},
    {label: 'Vehicles', name: 'Vehicle', url: 'data/json/Vehicles.json', vehicleClass: 'land'},
    {label: 'Starships', name: 'Vehicle', url: 'data/json/Vehicles.json', vehicleClass: 'space'},
    {label: 'Vehicle Attachments', name: 'ItemAttachments', url: 'data/json/ItemAttachments.json', attachmentClass: 'vehicle'},
    {label: 'Species', name: 'Species', url: 'data/json/Species.json'},
    {label: 'Careers', name: 'Career', url: 'data/json/Careers.json'},
    {label: 'Talents', name: 'Talent', url: 'data/json/Talents.json'},
    {label: 'Talent Trees', name: 'Specialization', url: 'data/json/Specializations.json'},
    {label: 'Force Trees', name: 'ForcePower', url: 'data/json/ForcePowers.json'},
]);

/**
 * The four lines a source book can belong to, in the order they appear in the
 * menu at the right of the tab strip. Every Book name in the data belongs to
 * exactly one of them.
 *
 * "Extended Material" is the catch-all for everything published outside the three
 * core lines: the Clone Wars era books, and OggDude's "User Data" placeholder for
 * hand-entered rows.
 *
 * A book missing from these lists is reported once by sourceLineFilter, and items
 * carrying it stay visible -- a new book must never disappear because nobody has
 * filed it yet. Adding one means adding its name to the right list, in the
 * existing style. The lists are alphabetical.
 */
App.constant('sourceLines', [
    {
        key: 'eote', label: 'Edge of the Empire', books: [
            'Beyond the Rim',
            'Dangerous Covenants',
            'Edge of the Empire Core Rulebook',
            'Enter the Unknown',
            'Far Horizons',
            'Fly Casual',
            'Jewel of Yavin',
            'Long Arm of the Hutt',
            'Lords of Nal Hutta',
            'Mask of the Pirate Queen',
            'No Disintegrations',
            'Special Modifications',
            'Suns of Fortune',
            'Under a Black Sun'
        ]
    },
    {
        key: 'aor', label: 'Age of Rebellion', books: [
            'Age of Rebellion Beta Rulebook',
            'Age of Rebellion Core Rulebook',
            'Cyphers and Masks',
            'Desperate Allies',
            'Forged in Battle',
            'Friends Like These',
            'Fully Operational',
            'Lead by Example',
            'Onslaught at Arda I',
            'Stay on Target',
            'Strongholds of Resistance'
        ]
    },
    {
        key: 'fad', label: 'Force and Destiny', books: [
            'Chronicles of the Gatekeeper',
            'Disciples of Harmony',
            'Endless Vigil',
            'Force and Destiny Beta Rulebook',
            'Force and Destiny Core Rulebook',
            'Force and Destiny Game Master\'s Kit',
            'Keeping the Peace',
            'Knights of Fate',
            'Nexus of Power',
            'Savage Spirits',
            'Unlimited Power'
        ]
    },
    {
        key: 'extended', label: 'Extended Material', books: [
            'Collapse of the Republic',
            'Rise of the Separatists',
            'User Data'
        ]
    }
]);

/**
 * Which source lines are switched on. One object for the whole app: the menu
 * lives in the tab strip, every tab filters by it, and it outlives a reload.
 *
 * Stored as the list of lines that are *off*, so a line added to the constant
 * later starts on rather than being silently hidden by an old saved selection.
 * The stamp expires the selection after STORAGE_MAX_AGE_DAYS -- switching a line
 * off is meant to last a while, not forever.
 *
 * Every localStorage call is guarded: Safari's private mode throws on setItem,
 * and a browser that refuses to store simply forgets the selection on reload.
 */
App.factory('sourceLineSelection', function ($rootScope, $window, sourceLines) {
    var STORAGE_KEY = 'sw-galaxy.sourceLines',
        STORAGE_MAX_AGE_DAYS = 30,
        enabled = {};

    function store() {
        try {
            return $window.localStorage;
        } catch (e) {
            return null;
        }
    }

    function enableAll() {
        var i, l = sourceLines.length;
        for (i = 0; i < l; i++) {
            enabled[sourceLines[i].key] = true;
        }
    }

    function read() {
        var storage = store(), raw, payload, i, l;
        enableAll();
        if (!storage) {
            return;
        }
        try {
            raw = storage.getItem(STORAGE_KEY);
            payload = raw ? angular.fromJson(raw) : null;
        } catch (e) {
            payload = null;
        }
        if (!payload || typeof payload.saved != 'number' ||
            $window.Date.now() - payload.saved > STORAGE_MAX_AGE_DAYS * 24 * 60 * 60 * 1000) {
            return;
        }
        if (payload.off && typeof payload.off.length == 'number') {
            for (i = 0, l = payload.off.length; i < l; i++) {
                if (enabled.hasOwnProperty(payload.off[i])) {
                    enabled[payload.off[i]] = false;
                }
            }
        }
    }

    function write() {
        var storage = store(), off = [], i, l = sourceLines.length;
        if (!storage) {
            return;
        }
        for (i = 0; i < l; i++) {
            if (!enabled[sourceLines[i].key]) {
                off.push(sourceLines[i].key);
            }
        }
        try {
            storage.setItem(STORAGE_KEY, angular.toJson({saved: $window.Date.now(), off: off}));
        } catch (e) {
            // Out of quota, or storage denied. The selection still works for this
            // page view; it just will not be there after a reload.
        }
    }

    read();

    return {
        enabled: enabled,
        isEnabled: function (key) {
            return enabled[key] === true;
        },
        toggle: function (key) {
            enabled[key] = !enabled[key];
            write();
            // Every tab re-filters, including the ones the user is not looking at.
            $rootScope.$broadcast('sourceLinesChanged');
        }
    };
});

App.controller('TabsController', function ($scope, tabs, sourceLines, sourceLineSelection) {
    $scope.tabs = tabs;
    $scope.sourceLines = sourceLines;
    $scope.isSourceLineEnabled = sourceLineSelection.isEnabled;
    $scope.toggleSourceLine = sourceLineSelection.toggle;
    // Colours the menu button while a line is switched off: an icon in the tab
    // strip is the only hint that items are being held back.
    $scope.allSourceLinesOn = function () {
        var i, l = sourceLines.length;
        for (i = 0; i < l; i++) {
            if (!sourceLineSelection.isEnabled(sourceLines[i].key)) {
                return false;
            }
        }
        return true;
    };
});

App.filter('searchFilter', function () {
    return function (items, search, ctrl) {
        if (!search) {
            return items;
        }
        search = search.replace(/[\-\[\]\/\{\}\(\)\*\+\?\.\\\^\$\|]/g, "\\$&");
        var searchItems = search.split(' ');
        return items.filter(function (item) {
            var i, l = searchItems.length, pattern, found;
            for (i = 0; i < l; i++) {
                pattern = new RegExp(searchItems[i], "i");
                found = pattern.test(item.Name) ||
                pattern.test(item.Description) ||
                pattern.test(item.Damage) ||
                pattern.test(item.Crit) ||
                pattern.test(item.Rarity) ||
                pattern.test(item.Encumbrance) ||
                pattern.test(item.HP) ||
                pattern.test(item.Type) ||
                pattern.test(item.SkillKey) ||
                pattern.test(item.RangeValue) ||
                (typeof item.Qualities == 'object' && pattern.test(JSON.stringify(item.Qualities))) ||
                // What a talent or force tree teaches. The tree itself is the
                // content of those two tabs, so a search that could not see
                // into it would only ever match a specialization's own name.
                (typeof item.Talents == 'object' && pattern.test(JSON.stringify(item.Talents)));
                if (!found) {
                    return false;
                }
            }
            return true;
        });
    };
});

App.filter('fulltextFilter', function () {
    return function (items, search, attribute) {
        if (!search || typeof items.filter != 'function') {
            return items;
        }
        return items.filter(function (item) {
            return item[attribute] == search;
        });
    };
});

App.filter('trustAsHtmlFilter', function ($sce) {
    return function (text) {
        return $sce.trustAsHtml(text);
    };
});

App.filter('arrayFulltextFilter', function () {
    return function (items, searchItems, attribute, key) {
        if (!searchItems || searchItems.length == 0) {
            return items;
        }
        var i, l = searchItems.length, search;
        for (i = 0; i < l; i++) {
            search = searchItems[i];
            items = items.filter(function (item) {
                var i2, l2 = item[attribute].length;
                for (i2 = 0; i2 < l2; i2++) {
                    if (item[attribute][i2][key] == search) {
                        return true;
                    }
                }
                return false;
            });
        }
        return items;
    }
});

App.filter('arrayFulltextFilterOr', function () {
    return function (items, searchItems, attribute, key) {
        if (!searchItems || searchItems.length == 0) {
            return items;
        }
        items = items.filter(function (item) {
            var i2, l2 = item[attribute].length;
            for (i2 = 0; i2 < l2; i2++) {
                if (searchItems.indexOf(item[attribute][i2][key]) != -1) {
                    return true;
                }
            }
            return false;
        });
        return items;
    }
});
App.filter('nameFilter', function ($sce, $filter) {
 return function (item) {
        var html = '', mods = '', count;
        if (typeof item.Name == 'string') {
            html += "<div><strong>" + item.Name + "</strong></div>";
        }
	if (html.length > 0) {
            html = html.replace("[H3]" + item.Name + "[h3]", "");
            html = html.replace(/\[H3\]/g, "<div><em>");
            html = html.replace(/\[h3\]/g, "</em></div>");
            html = html.replace("[H4]" + item.Name + "[h4]", "");
            html = html.replace(/\[I\]/g, "<em>");
            html = html.replace(/\[i\]/g, "</em>");
            html = html.replace(/\[B\]/g, "<strong>");
            html = html.replace(/\[b\]/g, "</strong>");
            html = html.replace(/\[P\]/g, "</p><p>");
            html = html.replace(/\[BR\]/g, "<br/>");
            html = $filter('symbolFilter')(html);
            return $sce.trustAsHtml(html);
        } else {
            return null;
        }
    };
});

App.filter('descriptionFilter', function ($sce, $filter) {
    return function (item) {
        var html = '', mods = '', count;


        if (typeof item.Description == 'string') {
           html += "<p>" + item.Description + "</p>";
        }

        if (html.length > 0) {
            html = html.replace("[H3]" + item.Name + "[h3]", "");
            html = html.replace("[H4]" + item.Name + "[h4]", "");
            html = html.replace(/\[H3\]/g, "<div><em>");
            html = html.replace(/\[h3\]/g, "</em></div>");
            html = html.replace(/\[H4\]/g, "<div><em>");
            html = html.replace(/\[h4\]/g, "</em></div>");
            html = html.replace(/\[I\]/g, "<em>");
            html = html.replace(/\[i\]/g, "</em>");
            html = html.replace(/\[B\]/g, "<strong>");
            html = html.replace(/\[b\]/g, "</strong>");
            html = html.replace(/\[P\]/g, "</p><p>");
            html = html.replace(/\[p\]/g, "");
            html = html.replace(/\[BR\]/g, "<br/>");
            html = $filter('symbolFilter')(html);
            return $sce.trustAsHtml(html);
        } else {
            return null;
        }
    };
});

App.filter('infoFilter', function ($sce, $filter) {
    // One <Mod> can hold two <MiscDesc> siblings -- the Glop Grenade is the one
    // row that does -- which SimpleXML turns into an array. Reading only the
    // string shape dropped both sentences and then logged 'debugging!', because
    // a MiscDesc-only mod has no <Key> to fall back on. Returns '' when the mod
    // carries no description at all, which is the signal to read its Key.
    function miscDesc(mod) {
        var out = '', i, l;
        if (typeof mod.MiscDesc == 'string') {
            return "<li>" + mod.MiscDesc + "</li>";
        }
        if (typeof mod.MiscDesc == 'object' && typeof mod.MiscDesc.length == 'number') {
            for (i = 0, l = mod.MiscDesc.length; i < l; i++) {
                out += "<li>" + mod.MiscDesc[i] + "</li>";
            }
        }
        return out;
    }

    // The <li> for a mod that names a <Key>. The count prefix is the book's own
    // "2 Skill (Athletics) Mods".
    //
    // A SkillIsCareer mod is the exception: it carries no Count and grants no
    // rank, it makes the skill a career skill, and it shares its <Key> with the
    // Skill Mod above -- so the flag is the only thing telling the two apart,
    // and it is visible here and nowhere else (descriptorFilter only ever sees
    // the bare key). The "Skill (...) Mod" wording that filter produces is what
    // marks a key as a skill in the first place; if it is ever reworded, this
    // falls through and prints the Skill Mod line rather than breaking.
    function modLine(mod) {
        var text = $filter('modFilter')(mod.Key), count = '';
        if (mod.SkillIsCareer == 'true') {
            return "<li>" + text.replace(/^Skill \((.+)\) Mod$/, '$1 as a career skill') + "</li>";
        }
        if (typeof mod.Count == 'number' && mod.Count != 0) {
            count = mod.Count + ' x ';
        }
        return "<li>" + count + text + "</li>";
    }

    return function (item) {
        var html = '', mods = '', desc;

        if (typeof item.BaseMods == 'object') {
            if (typeof item.BaseMods.Mod == 'object' && item.BaseMods.Mod.length > 0) {
                for (var i = 0, l = item.BaseMods.Mod.length; i < l; i++) {
                    desc = miscDesc(item.BaseMods.Mod[i]);
                    if (desc.length > 0) {
                        mods += desc;
                    } else {
                        if (typeof item.BaseMods.Mod[i].Key == 'string') {
                            mods += modLine(item.BaseMods.Mod[i]);
                        } else {
                            console.log('debugging!');
                        }
                    }
                }
            } else {
                if (typeof item.BaseMods.Mod != 'undefined') {
                    desc = miscDesc(item.BaseMods.Mod);
                    if (desc.length > 0) {
                        mods += desc;
                    } else {
                        if (typeof item.BaseMods.Mod.Key == 'string') {
                            mods += modLine(item.BaseMods.Mod);
                        } else {
                            console.log('debugging!');
                        }
                    }
                }
            }
            if (mods.length > 0) {
                html += "<p><strong>Base Mods:</strong></p><ul>" + mods + "</ul>";
            }
        }
        if (typeof item.AddedMods == 'object') {
            mods = '';
            if (typeof item.AddedMods.Mod == 'object' && item.AddedMods.Mod.length > 0) {
                for (i = 0, l = item.AddedMods.Mod.length; i < l; i++) {
                    desc = miscDesc(item.AddedMods.Mod[i]);
                    if (desc.length > 0) {
                        mods += desc;
                    } else {
                        if (typeof item.AddedMods.Mod[i].Key == 'string') {
                            mods += modLine(item.AddedMods.Mod[i]);
                        } else {
                            console.log('debugging!');
                        }
                    }
                }
            } else {
                if (typeof item.AddedMods.Mod != 'undefined') {
                    desc = miscDesc(item.AddedMods.Mod);
                    if (desc.length > 0) {
                        mods += desc;
                    } else {
                        if (typeof item.AddedMods.Mod.Key == 'string') {
                            mods += modLine(item.AddedMods.Mod);
                        } else {
                            console.log('debugging!');
                        }
                    }
                }
            }
            if (mods.length > 0) {
                html += "<p><strong>Additional Mods:</strong></p><ul>" + mods + "</ul>";
            }
        }
        if (html.length > 0) {
            html = html.replace("[H3]" + item.Name + "[h3]", "");
            html = html.replace("[H4]" + item.Name + "[h4]", "");
            html = html.replace(/\[H3\]/g, "<div><em>");
            html = html.replace(/\[h3\]/g, "</em></div>");
            html = html.replace(/\[H4\]/g, "<div><em>");
            html = html.replace(/\[h4\]/g, "</em></div>");
            html = html.replace(/\[I\]/g, "<em>");
            html = html.replace(/\[i\]/g, "</em>");
            html = html.replace(/\[B\]/g, "<strong>");
            html = html.replace(/\[b\]/g, "</strong>");
            html = html.replace(/\[P\]/g, "</p><p>");
            html = html.replace(/\[p\]/g, "");
            html = html.replace(/\[BR\]/g, "<br/>");
            html = $filter('symbolFilter')(html);
            return $sce.trustAsHtml(html);
        } else {
            return null;
        }
    };
});

App.filter('symbolFilter', function ($sce) {
    return function (text) {
        if (typeof text === 'string') {
            //[ABILITY] or [AB]
            text = text.replace(/\[(ABILITY|AB)\]/g, "<span class='sw-symbol sw-color-ability'>&#100;</span>");
            //[ADVANTAGE] or [AD]
            text = text.replace(/\[(ADVANTAGE|AD)\]/g, "<span class='sw-symbol'>&#97;</span>");
            //[BOOST] or [BO]
            text = text.replace(/\[(BOOST|BO)\]/g, "<span class='sw-symbol sw-color-boost'>&#98;</span>");
            //[CHALLENGE] or [CH]
            text = text.replace(/\[(CHALLENGE|CH)\]/g, "<span class='sw-symbol sw-color-challenge'>&#99;</span>");
            //[DARK] or [DA]
            text = text.replace(/\[(DARK|DA)\]/g, "<span class='sw-symbol'>&#122;</span>");
            //[DESPAIR] or [DE]
            text = text.replace(/\[(DESPAIR|DE)\]/g, "<span class='sw-symbol'>&#121;</span>");
            //[DIFFICULTY] or [DI]
            text = text.replace(/\[(DIFFICULTY|DI)\]/g, "<span class='sw-symbol sw-color-difficulty'>&#100;</span>");
            //[FORCEPOINT] or [FP]
            text = text.replace(/\[(FORCEPOINT|FP)\]/g, "<span class='sw-symbol'>&#70;</span>");
            //[FAILURE] or [FA]
            text = text.replace(/\[(FAILURE|FA)\]/g, "<span class='sw-symbol'>&#102;</span>");
            //[FORCE] or [FO]
            text = text.replace(/\[(FORCE|FO)\]/g, "<span class='sw-symbol'>&#67;</span>");
            //[LIGHT] or [LI]
            text = text.replace(/\[(LIGHT|LI)\]/g, "<span class='sw-symbol'>&#90;</span>");
            //[PROFICIENCY] or [PR]
            text = text.replace(/\[(PROFICIENCY|PR)\]/g, "<span class='sw-symbol sw-color-proficiency'>&#99;</span>");
            //[REMSETBACK] or [RS]
            //text = text.replace(/\[(REMSETBACK|RS)\]/g, "<span class='sw-symbol'></span>");
            //[RESTRICTED] or [RE]
            //text = text.replace(/\[(RESTRICTED|RE)\]/g, "<span class='sw-symbol'></span>");
            //[SETBACK] or [SE]
            text = text.replace(/\[(SETBACK|SE)\]/g, "<span class='sw-symbol'>&#98;</span>");
            //[SUCCESS] or [SU]
            text = text.replace(/\[(SUCCESS|SU)\]/g, "<span class='sw-symbol'>&#115;</span>");
            //[THREAT] or [TH]
            text = text.replace(/\[(THREAT|TH)\]/g, "<span class='sw-symbol'>&#116;</span>");
            //[TRIUMPH] or [TR]
            text = text.replace(/\[(TRIUMPH|TR)\]/g, "<span class='sw-symbol'>&#120;</span>");
            return text;
        } else {
            return '';
        }
    }
});

App.filter('skillFilter', function () {
    return function (text) {
        if (typeof text === 'string') {
            text = text.replace(/RANGLT/g, "Range Light");
            text = text.replace(/RANGHVY/g, "Range Heavy");
            text = text.replace(/GUNN/g, "Gunnery");
            text = text.replace(/MELEE/g, "Melee");
            text = text.replace(/MECH/g, "Mechanics");
            text = text.replace(/BRAWL/g, "Brawl");
            text = text.replace(/LTSABER/g, "Lightsaber");
            return text;
        } else {
            return '';
        }
    }
});

/**
 * The item an attachment's <ItemLimit> names, as a display name. OggDude's
 * export carries the key only -- BLASTLTREP, KIHRAXZLTSTAR -- and the item it
 * points at lives in a JSON file the attachment tabs never load, so the names
 * are listed here rather than looked up at runtime.
 *
 * One text.replace line per key, anchored, the way descriptorFilter and
 * talentFilter are written. A key with no mapping falls through as itself and is
 * reported, so new data shows up in the console instead of reading as gibberish
 * in the Limits column.
 */
App.filter('itemLimitFilter', function () {
    return function (text) {
        if (typeof text === 'string') {
            var initText = text;
            text = text.replace(/^A36PTHFNDR$/g, "A-36 Pathfinder-class Force Recon Vessel");
            text = text.replace(/^AD1SMOD$/g, "AD-1S Modular Multi-Role Starfighter");
            text = text.replace(/^BARCSPEEDER$/g, "BARC Speeder");
            text = text.replace(/^BLASTHVYREP$/g, "Heavy Repeating Blaster");
            text = text.replace(/^BLASTLTREP$/g, "Light Repeating Blaster");
            text = text.replace(/^DARVROLTFR$/g, "Darvro-Class Light Freighter");
            text = text.replace(/^DUSTCRAWLER$/g, "Dustcrawler");
            text = text.replace(/^EODMKII$/g, "EOD-Mk II Armor");
            text = text.replace(/^IONTHRUST$/g, "Ion Thruster Gun");
            text = text.replace(/^KIHRAXZLTSTAR$/g, "Kihraxz Light Starfighter");
            text = text.replace(/^LORONARE9$/g, "Loronar E-9 Explorer-class Long Range Scout");
            text = text.replace(/^MILMODBACK$/g, "Military Modular Backpack Frame");
            text = text.replace(/^MODEL77$/g, "Model 77 Air Rifle");
            text = text.replace(/^MODPACK$/g, "Mk. IV Modular Backpack");
            text = text.replace(/^MODPACK3$/g, "Mk. III Modular Backpack");
            text = text.replace(/^MULTIGOO$/g, "Multi-Goo Gun");
            text = text.replace(/^PODCOCK$/g, "Podracer Cockpit");
            text = text.replace(/^RIVETGUN$/g, "Rivet Gun");
            text = text.replace(/^SHEATHIPEDESPY$/g, "Sheathipede-Class Spy Shuttle");
            text = text.replace(/^SPACESLUG$/g, "Enormous Space Slug");
            text = text.replace(/^STARHAWKSPEED$/g, "Starhawk Speeder Bike");
            text = text.replace(/^TALLANX$/g, "Tallanx-Class Stealth Fighter");
            if (initText == text) {
                console.log('Please add an item limit mapping for: ' + text);
            }
            return text;
        } else {
            return '';
        }
    }
});

App.filter('rangeFilter', function () {
    return function (text) {
        if (typeof text === 'string') {
            text = text.replace(/wrClose/g, "Close");
            text = text.replace(/wrNoRange/g, "No Range");
            text = text.replace(/wrShort/g, "Short");
            text = text.replace(/wrMedium/g, "Medium");
            text = text.replace(/wrLong/g, "Long");
            text = text.replace(/wrExtreme/g, "Extreme");
            text = text.replace(/wrEngaged/g, "Engaged");
            return text;
        } else {
            return '';
        }
    }
});

/**
 * A base or added mod key as display text. The two key lists it chains are tried
 * in turn, and **this is the only place that reports a miss**: a mod key is a
 * descriptor or a talent, never both (the two lists share no key), so whichever
 * one does not hold it would report every key the other resolves. That is what
 * filled the console with lines like "Please add base mod mapping for: Additional
 * Damage Mod" -- already-resolved display text, reported by talentFilter for a
 * key descriptorFilter had just mapped correctly. Neither list has any other
 * caller, so the check belongs here, where the whole chain is known to have
 * failed.
 *
 * A key talentFilter resolves is a talent the item grants, and the books print
 * that as "2 Innate Talent (Brace) Mods" -- so the name is wrapped here rather
 * than in the list, which holds bare talent names and is 474 lines long. All 33
 * talent keys the data actually uses are real rows on the Talents tab, and each
 * equals that talent's own Key. Three talent-*sounding* names -- Demon Mask, Iron
 * Fists, Meditation Focus -- are in descriptorFilter instead and stay unwrapped,
 * correctly: none is a talent, each is an artifact effect named after its own
 * piece of gear.
 *
 * Both lists are anchored /^KEY$/, so returning as soon as one matches is what
 * running both always did -- a display name with spaces in it can never match the
 * other list. symbolFilter is unanchored and still runs on whatever comes out.
 */
App.filter('modFilter', function ($filter) {
    return function (text) {
        if (typeof text === 'string') {
            var mapped = $filter('descriptorFilter')(text);
            if (mapped != text) {
                return $filter('symbolFilter')(mapped);
            }
            mapped = $filter('talentFilter')(text);
            if (mapped != text) {
                return "Innate Talent (" + $filter('symbolFilter')(mapped) + ") Mod";
            }
            mapped = $filter('symbolFilter')(text);
            if (mapped == text) {
                console.log('Please add base mod mapping for: ' + text);
            }
            return mapped;
        } else {
            return '';
        }
    }
});

App.filter('descriptorFilter', function ($filter) {
    return function (text) {
        if (typeof text === 'string') {
            text = text.replace(/^DAMADD$/g, "Additional Damage Mod");
			text = text.replace(/^DAMSUB$/g, "Reduced Damage Mod");
			text = text.replace(/^DAMSET$/g, "Base Damage Mod");
			text = text.replace(/^DAMADDCRYS$/g, "Additional Damage Mod (Crystal)");
			text = text.replace(/^DAMSUBCRYS$/g, "Reduced Damage Mod (Crystal)");
			text = text.replace(/^RESDOSE$/g, "Increase doses by 1 Mod");
			text = text.replace(/^HOLSTER3$/g, "Hoster Weapon up to Encumbrance 3 Mod");
			text = text.replace(/^MOUNT3$/g, "Mount Weapon up to Encumbrance 3 Mod");
			text = text.replace(/^MOUNTRANGED4$/g, "Mount Ranged Weapon up to Encumbrance 4 Mod");
			text = text.replace(/^MOUNTADDL$/g, "Increase Allowable Mounted Weapon Encumbrance by 1 Mod");
			text = text.replace(/^CARRY1$/g, "Carry Items up to Encumbrance 1 Mod");
			text = text.replace(/^CARRY0$/g, "Carry Items of Encumbrance 0 Mod");
			text = text.replace(/^ADVADD$/g, "Add Advantage to Successful Check Mod");
			text = text.replace(/^SUCCADD$/g, "Add Success to Check Mod");
			text = text.replace(/^ADVADDCOM$/g, "Add Advantage to Combat Check Mod");
			text = text.replace(/^THRADD$/g, "Add Threat to Check Mod");
			text = text.replace(/^THRCANCEL$/g, "Cancel Threat from Check Mod");
			text = text.replace(/^UPGRADEDIFF$/g, "Upgrade Difficulty of Check Mod");
			text = text.replace(/^ADVADDINIT$/g, "Add Advantage to Initiative Check Mod");
			text = text.replace(/^HPADD$/g, "Add Hard Points Mod");
			text = text.replace(/^HPADD2$/g, "Add 2 Hard Points to Vehicle Mod");
			text = text.replace(/^HPSUB$/g, "Remove Hard Points from Item Mod");
			text = text.replace(/^CRITSET$/g, "Base Critical Rating Mod");
			text = text.replace(/^STRAINADD$/g, "Additional Strain Mod");
			text = text.replace(/^RANGEADD$/g, "Additional Range Mod");
			text = text.replace(/^RANGESUB$/g, "Reduced Range Mod");
			text = text.replace(/^ENCTOTSUB$/g, "Decreases Total Encumbrance Mod");
			text = text.replace(/^ENCSUB$/g, "Decreases Encumbrance Mod");
			text = text.replace(/^ENCSUB2$/g, "Decreases Encumbrance by 2 Mod");
			text = text.replace(/^ENCADD$/g, "Increases Encumbrance Mod");
			text = text.replace(/^ENCTADD$/g, "Increases Encumbrance Threshold Mod");
			text = text.replace(/^ENCTBRADD$/g, "Increases Brawn for Determining Encumbrance Threshold Mod");
			text = text.replace(/^ENCTADD3$/g, "Increases Encumbrance Threshold by 3 Mod");
			text = text.replace(/^ENCTSUB$/g, "Decreases Encumbrance Threshold Mod");
			text = text.replace(/^CRITSUB$/g, "Decrease Critical Mod");
			text = text.replace(/^SOAKADD$/g, "Increase Soak Mod");
			text = text.replace(/^SOAKSET$/g, "Base Soak Mod");
			text = text.replace(/^MELEEDEFADD$/g, "Increase Melee Defense Mod");
			text = text.replace(/^RANGEDEFADD$/g, "Increase Ranged Defense Mod");
			text = text.replace(/^DEFADD$/g, "Increase Defense Mod");
			text = text.replace(/^DEFSET$/g, "Base Defense Mod");
			text = text.replace(/^DEFADDFORCE$/g, "Increase Defense per Force Rating Mod");
			text = text.replace(/^SETBACKADD$/g, "Add Setback Mod");
			text = text.replace(/^SETBACKSUB$/g, "Remove Setback Mod");
			text = text.replace(/^BOOSTADD$/g, "Add Boost Mod");
			text = text.replace(/^DIFFSUBLONG$/g, "Decrease Long Range Difficulty Mod");
			text = text.replace(/^DIFFSUBLONGEXT$/g, "Decrease Long and Extreme Range Difficulty Mod");
			text = text.replace(/^NOSTUN$/g, "Cannot deal strain damage");
			text = text.replace(/^HEALPLUSONE$/g, "Successful Medicine checks heal +1 wound Mod");
			text = text.replace(/^USERANGLT$/g, "Weapon's skill changes to Ranged-Light Mod");
			text = text.replace(/^USERANGHVY$/g, "Weapon's skill changes to Ranged-Heavy Mod");
			text = text.replace(/^ADDCRYSTNC$/g, "Add Additional Crystal with no HP Cost Mod");
			text = text.replace(/^PRICEHALF$/g, "Item is Half Price Mod");
			text = text.replace(/^PRICE20000$/g, "Add 20,000 Credits to Price Mod");
			text = text.replace(/^SEAL$/g, "Sealable Mod");
			text = text.replace(/^SEALED$/g, "Sealed Mod");
			text = text.replace(/^RANGEREDMED$/g, "Reduce Range to Medium Mod");
			text = text.replace(/^DEMONMASK$/g, "Demon Mask");
			text = text.replace(/^MEDFOCUS$/g, "Meditation Focus");
			text = text.replace(/^IRONFIST$/g, "Iron Fists");
			text = text.replace(/^FORCEADD$/g, "Add Force Rating Mod");
			text = text.replace(/^FORCESUB$/g, "Subtract from Force Rating Mod");
			text = text.replace(/^CYBERADD$/g, "Add to Cybernetics Cap Mod");
			text = text.replace(/^CYBERSUB$/g, "Subtract from Cybernetics Cap Mod");
			text = text.replace(/^CYBERNONE$/g, "Does not count toward Cybernetics Cap Mod");
			text = text.replace(/^JURYADD$/g, "May Select Additional Jury Rigged Option Mod");
			text = text.replace(/^SILHADD$/g, "Increase Silhouette Mod");
			text = text.replace(/^ARMORADD$/g, "Increase Armor Mod");
			text = text.replace(/^HANDLINGSUB$/g, "Decreases Handling Mod");
			text = text.replace(/^HANDLINGADD$/g, "Increases Handling Mod");
			text = text.replace(/^SSTRAINSUB$/g, "Decreases System Strain Mod");
			text = text.replace(/^SSTRAINSUB2$/g, "Decreases System Strain by 2 Mod");
			text = text.replace(/^SSTRAINADD$/g, "Increases System Strain Mod");
			text = text.replace(/^SSTRAINADDSIL$/g, "Increases System Strain by Silhouette Mod");
			text = text.replace(/^DEFZONEADD$/g, "Increase Defense Zone Mod");
			text = text.replace(/^SMUGENC$/g, "Convert 25 encumbrance capacity to smuggling compartment Mod");
			text = text.replace(/^HANGER$/g, "Retrofits Hangar Bay Mod");
			text = text.replace(/^HANGERSIZE$/g, "Increase Silhouette Capacity of Hangar Bay by 1 Mod");
			text = text.replace(/^HYPERDRIVESUB$/g, "Decreases Hyperdrive Class by 1, to a minimum of 1 Mod");
			text = text.replace(/^HYPERDRIVESUB5$/g, "Decreases Hyperdrive Class by 1, to a minimum of .5 Mod");
			text = text.replace(/^HYPERDRIVEBACKSUB5$/g, "Decreases Backup Hyperdrive Class by 1, to a minimum of .5 Mod");
			text = text.replace(/^HYPERDRIVEBACKSUB$/g, "Decreases Backup Hyperdrive Class by 1, to a minimum of 1 Mod");
			text = text.replace(/^HYPERDRIVEADD8$/g, "Add Class 8 Hyperdrive Mod");
			text = text.replace(/^HYPERDRIVEADD4$/g, "Add Class 4 Hyperdrive Mod");
			text = text.replace(/^HYPERDRIVEADDBACK14$/g, "Add Class 14 Backup Hyperdrive Mod");
			text = text.replace(/^MASSIVEADD$/g, "Add to Massive Mod");
			text = text.replace(/^MASSIVESET$/g, "Change Massive Mod");
			text = text.replace(/^ADDALT50$/g, "Increase Altitude by 50 Mod");
			text = text.replace(/^SETDEFFORE$/g, "Sets Forward Defense Mod");
			text = text.replace(/^SETDEFAFT$/g, "Sets Aft Defense Mod");
			text = text.replace(/^SETDEFPORT$/g, "Sets Port Defense Mod");
			text = text.replace(/^SETDEFSTAR$/g, "Sets Starboard Defense Mod");
			text = text.replace(/^SETDEFFORECRAFT$/g, "Sets Forward Defense When Crafting Mod");
			text = text.replace(/^SETDEFAFTCRAFT$/g, "Sets Aft Defense When Crafting Mod");
			text = text.replace(/^SETDEFPORTCRAFT$/g, "Sets Port Defense When Crafting Mod");
			text = text.replace(/^SETDEFSTARCRAFT$/g, "Sets Starboard Defense When Crafting Mod");
			text = text.replace(/^SETHAND$/g, "Sets Handling Mod");
			text = text.replace(/^SETHANDCRAFT$/g, "Sets Handling When Crafting Mod");
			text = text.replace(/^SETSSTRAIN$/g, "Sets System Strain Mod");
			text = text.replace(/^SETSSTRAINSIL$/g, "Sets System Strain to Silhouette Mod");
			text = text.replace(/^SETSSTRAINSILCRAFT$/g, "Sets System Strain When Crafting to Silhouette Mod");
			text = text.replace(/^SETSPEED$/g, "Sets Speed Mod");
			text = text.replace(/^SETSPEEDCRAFT$/g, "Sets Speed When Crafting Mod");
			text = text.replace(/^SETARMOR$/g, "Sets Armor Mod");
			text = text.replace(/^SETARMORCRAFT$/g, "Sets Armor Value When Crafting Mod");
			text = text.replace(/^ADDDEFFORE$/g, "Increase Forward Defense Mod");
			text = text.replace(/^ADDDEFPORT$/g, "Increase Port Defense Mod");
			text = text.replace(/^ADDDEFSTAR$/g, "Increase Starboard Defense Mod");
			text = text.replace(/^ADDDEFAFT$/g, "Increase Aft Defense Mod");
			text = text.replace(/^SPEEDSUB$/g, "Decrease Speed Mod");
			text = text.replace(/^SPEEDADD$/g, "Increase Speed Mod");
			text = text.replace(/^SPEEDADD2$/g, "Increases Speed by 2 Mod");
			text = text.replace(/^SRANGEADD$/g, "Additional Sensor Range Mod");
			text = text.replace(/^SRANGESUB$/g, "Reduced Sensor Range Mod");
			text = text.replace(/^CRANGEADD$/g, "Additional Comms Range Mod");
			text = text.replace(/^CRANGESUB$/g, "Reduced Comms Range Mod");
			text = text.replace(/^HULLADDSIL$/g, "Increase Hull Trauma by Silhouette Mod");
			text = text.replace(/^HULLADD$/g, "Increase Hull Trauma Mod");
			text = text.replace(/^HULLADD3$/g, "Increase Hull Trauma by 3 Mod");
			text = text.replace(/^HULLSUB$/g, "Decrease Hull Trauma Mod");
			text = text.replace(/^PASSADD$/g, "Increase Passenger Capacity Mod");
			text = text.replace(/^PASSADDCRAFT$/g, "Increase Passenger Capacity When Crafting Mod");
			text = text.replace(/^PASSADD2$/g, "Increase Passenger Capacity by 2 Mod");
			text = text.replace(/^PASSADD10$/g, "Increase Passenger Capacity by 10 Mod");
			text = text.replace(/^PASSADDSIL$/g, "Increase Passenger Capacity by Silhouette Mod");
			text = text.replace(/^PASSSUB$/g, "Decrease Passenger Capacity Mod");
			text = text.replace(/^ADDSILWEAP$/g, "Vehicle can carry a weapon for craft 1 silhouette larger Mod");
			text = text.replace(/^BOARDTUBETIME$/g, "Decrease time to cut through hull by 1 round Mod");
			text = text.replace(/^DAMWEAPSYSADD$/g, "Increase damage of weapon system by one Mod");
			text = text.replace(/^ENCCADDSIL$/g, "Increases Encumbrance Capacity by Silhouette Mod");
			text = text.replace(/^ENCCADD$/g, "Increases Encumbrance Capacity Mod");
			text = text.replace(/^ENCCADDCRAFT$/g, "Increases Encumbrance Capacity When Crafting Mod");
			text = text.replace(/^ENCCADD100$/g, "Increases Encumbrance Capacity by 100 Mod");
			text = text.replace(/^ENCCSUB$/g, "Decreases Encumbrance Capacity Mod");
			text = text.replace(/^UPGUNN$/g, "Upgrade ability of Gunnery checks Mod");
			text = text.replace(/^VAKSAI$/g, "Replace Light Blaster Cannons with Light Laser Cannons Mod");
			text = text.replace(/^ACCURATE$/g, "Accurate Quality");
			text = text.replace(/^AUTOFIRE$/g, "Auto-Fire Quality");
			text = text.replace(/^BREACH$/g, "Breach Quality");
			text = text.replace(/^BURN$/g, "Burn Quality");
			text = text.replace(/^BLAST$/g, "Blast Quality");
			text = text.replace(/^CONCUSSIVE$/g, "Concussive Quality");
			text = text.replace(/^CORTOSIS$/g, "Cortosis Quality");
			text = text.replace(/^CUMBERSOME$/g, "Cumbersome Quality");
			text = text.replace(/^DEFENSIVE$/g, "Defensive Quality");
			text = text.replace(/^DEFLECTION$/g, "Deflection Quality");
			text = text.replace(/^DISORIENT$/g, "Disorient Quality");
			text = text.replace(/^ENSNARE$/g, "Ensnare Quality");
			text = text.replace(/^GUIDED$/g, "Guided Quality");
			text = text.replace(/^KNOCKDOWN$/g, "Knockdown Quality");
			text = text.replace(/^INACCURATE$/g, "Inaccurate Quality");
			text = text.replace(/^INFERIOR$/g, "Inferior Quality");
			text = text.replace(/^ION$/g, "Ion Quality");
			text = text.replace(/^LIMITEDAMMO$/g, "Limited Ammo Quality");
			text = text.replace(/^LINKED$/g, "Linked Quality");
			text = text.replace(/^PIERCE$/g, "Pierce Quality");
			text = text.replace(/^PREPARE$/g, "Prepare Quality");
			text = text.replace(/^SLOWFIRING$/g, "Slow Firing Quality");
			text = text.replace(/^STAGGER$/g, "Stagger Quality");
			text = text.replace(/^STUN$/g, "Stun Quality");
			text = text.replace(/^STUNDROID$/g, "Stun (Droid Only) Quality");
			text = text.replace(/^STUNSETTING$/g, "Stun Setting Quality");
			text = text.replace(/^STUNDAMAGE$/g, "Stun Damage Quality");
			text = text.replace(/^STUNDAMAGEDROID$/g, "Stun Damage (Droid Only) Quality");
			text = text.replace(/^SUNDER$/g, "Sunder Quality");
			text = text.replace(/^SUPERIOR$/g, "Superior Quality");
			text = text.replace(/^TRACTOR$/g, "Tractor Quality");
			text = text.replace(/^VICIOUS$/g, "Vicious Quality");
			text = text.replace(/^VICIOUSDROID$/g, "Vicious (Droid Only) Quality");
			text = text.replace(/^UNWIELDY$/g, "Unwieldy Quality");
			text = text.replace(/^REMQUALBREACH$/g, "Removes Breach Quality Mod");
			text = text.replace(/^REMQUALION$/g, "Removes Ion Quality Mod");
			text = text.replace(/^REMQUALLIMITEDAMMO$/g, "Removes Limited Ammo Quality Mod");
			text = text.replace(/^REMQUALSTUNSETTING$/g, "Removes Stun Setting Quality Mod");
			text = text.replace(/^REMQUALSUNDER$/g, "Removes Sunder Quality Mod");
			text = text.replace(/^SUBQUALCUMBERSOME$/g, "Reduces Cumbersome Quality Mod");
			text = text.replace(/^SUBQUALINACCURATE$/g, "Reduces Inaccurate Quality Mod");
			text = text.replace(/^SUBQUALUNWIELDY$/g, "Reduces Unwieldy Quality Mod");
			text = text.replace(/^SUBQUALVICIOUS$/g, "Reduces Vicious Quality Mod");
			text = text.replace(/^RETRACTWEAPSYSTEM$/g, "Weapon System Retracts When Not In Use Mod");
			text = text.replace(/^MOVEBASIC$/g, "Move Item as a Maneuver Mod");
			// A skill key is FFG's printed "N Skill (Athletics) Mods" -- confirmed
			// against the Strength Enhancing System, whose Modification Options read
			// exactly that for its {"Key":"ATHL","Count":2}. Names come from
			// oggdudes-data/Skills.xml, the same table the Careers and Species
			// importers resolve against, so one skill reads the same on every tab.
			// A SkillIsCareer mod shares these keys but means something else; see
			// infoFilter, which is the only place the flag is visible.
			// The three characteristics take the "Increase ... Mod" shape of the
			// Soak and Defense lines above, matching the book's "Increases wearer's
			// Brawn by one point".
			text = text.replace(/^ASTRO$/g, "Skill (Astrogation) Mod");
			text = text.replace(/^ATHL$/g, "Skill (Athletics) Mod");
			text = text.replace(/^BRAWL$/g, "Skill (Brawl) Mod");
			text = text.replace(/^CHARM$/g, "Skill (Charm) Mod");
			text = text.replace(/^COERC$/g, "Skill (Coercion) Mod");
			text = text.replace(/^COMP$/g, "Skill (Computers) Mod");
			text = text.replace(/^COOL$/g, "Skill (Cool) Mod");
			text = text.replace(/^COORD$/g, "Skill (Coordination) Mod");
			text = text.replace(/^CORE$/g, "Skill (Core Worlds) Mod");
			text = text.replace(/^DECEP$/g, "Skill (Deception) Mod");
			text = text.replace(/^DISC$/g, "Skill (Discipline) Mod");
			text = text.replace(/^EDU$/g, "Skill (Education) Mod");
			text = text.replace(/^GUNN$/g, "Skill (Gunnery) Mod");
			text = text.replace(/^LEAD$/g, "Skill (Leadership) Mod");
			text = text.replace(/^LORE$/g, "Skill (Lore) Mod");
			text = text.replace(/^LTSABER$/g, "Skill (Lightsaber) Mod");
			text = text.replace(/^MECH$/g, "Skill (Mechanics) Mod");
			text = text.replace(/^MED$/g, "Skill (Medicine) Mod");
			text = text.replace(/^NEG$/g, "Skill (Negotiation) Mod");
			text = text.replace(/^OUT$/g, "Skill (Outer Rim) Mod");
			text = text.replace(/^PERC$/g, "Skill (Perception) Mod");
			text = text.replace(/^PILOTPL$/g, "Skill (Piloting - Planetary) Mod");
			text = text.replace(/^PILOTSP$/g, "Skill (Piloting - Space) Mod");
			text = text.replace(/^RANGLT$/g, "Skill (Ranged - Light) Mod");
			text = text.replace(/^RESIL$/g, "Skill (Resilience) Mod");
			text = text.replace(/^SKUL$/g, "Skill (Skulduggery) Mod");
			text = text.replace(/^STEAL$/g, "Skill (Stealth) Mod");
			text = text.replace(/^SURV$/g, "Skill (Survival) Mod");
			text = text.replace(/^SW$/g, "Skill (Streetwise) Mod");
			text = text.replace(/^UND$/g, "Skill (Underworld) Mod");
			text = text.replace(/^VIGIL$/g, "Skill (Vigilance) Mod");
			text = text.replace(/^WARF$/g, "Skill (Warfare) Mod");
			text = text.replace(/^XEN$/g, "Skill (Xenology) Mod");
			text = text.replace(/^BR$/g, "Increase Brawn Mod");
			text = text.replace(/^AG$/g, "Increase Agility Mod");
			text = text.replace(/^INT$/g, "Increase Intellect Mod");
			text = text.replace(/^QUALADVSUB$/g, "Quality Takes One Less Advantage to Activate Mod");
			text = text.replace(/^AUTOFIREADV$/g, "Autofire Takes One Less Advantage to Activate Mod");
			text = text.replace(/^BURNADV$/g, "Burn Takes One Less Advantage to Activate Mod");
			text = text.replace(/^BLASTADV$/g, "Blast Takes One Less Advantage to Activate Mod");
			text = text.replace(/^CONCUSSIVEADV$/g, "Concussive Takes One Less Advantage to Activate Mod");
			text = text.replace(/^DISORIENTADV$/g, "Disorient Takes One Less Advantage to Activate Mod");
			text = text.replace(/^ENSNAREADV$/g, "Ensnare Takes One Less Advantage to Activate Mod");
			text = text.replace(/^GUIDEDADV$/g, "Guided Takes One Less Advantage to Activate Mod");
			text = text.replace(/^KNOCKDOWNADV$/g, "Knockdown Takes One Less Advantage to Activate Mod");
			text = text.replace(/^LINKEDADV$/g, "Linked Takes One Less Advantage to Activate Mod");
			text = text.replace(/^STUNADV$/g, "Stun Takes One Less Advantage to Activate Mod");
			text = text.replace(/^SUNDERADV$/g, "Sunder Takes One Less Advantage to Activate Mod");
            // No miss reported here: a key this list does not hold may still be a
            // talent, and modFilter is the one that knows the chain failed.
            return text;
        } else {
            return '';
        }
    }
});

App.filter('talentFilter', function ($filter) {
    return function (text) {
        if (typeof text === 'string') {
            text = text.replace(/^ADV$/g, "Adversary");
			text = text.replace(/^ANAT$/g, "Anatomy Lessons");
			text = text.replace(/^ALLTERDRIV$/g, "All-Terrain Driver");
			text = text.replace(/^ARM$/g, "Armor Master");
			text = text.replace(/^ARMIMP$/g, "Armor Master (Improved)");
			text = text.replace(/^BACT$/g, "Bacta Specialist");
			text = text.replace(/^BADM$/g, "Bad Motivator");
			text = text.replace(/^BAL$/g, "Balance");
			text = text.replace(/^BAR$/g, "Barrage");
			text = text.replace(/^BASICTRAIN$/g, "Basic Combat Training");
			text = text.replace(/^BLA$/g, "Black Market Contacts");
			text = text.replace(/^BLO$/g, "Blooded");
			text = text.replace(/^BLOIMP$/g, "Blooded (Improved)");
			text = text.replace(/^BOD$/g, "Body Guard");
			text = text.replace(/^BOUGHT$/g, "Bought Info");
			text = text.replace(/^BRA$/g, "Brace");
			text = text.replace(/^BRI$/g, "Brilliant Evasion");
			text = text.replace(/^BYP$/g, "Bypass Security");
			text = text.replace(/^CAREPLAN$/g, "Careful Planning");
			text = text.replace(/^CLEVERSOLN$/g, "Clever Solution");
			text = text.replace(/^COD$/g, "Codebreaker");
			text = text.replace(/^COM$/g, "Command");
			text = text.replace(/^COMMPRES$/g, "Commanding Presence");
			text = text.replace(/^CONF$/g, "Confidence");
			text = text.replace(/^CONT$/g, "Contraption");
			text = text.replace(/^CONV$/g, "Convincing Demeanor");
			text = text.replace(/^COORDASS$/g, "Coordinated Assault");
			text = text.replace(/^CREATKILL$/g, "Creative Killer");
			text = text.replace(/^CRIPV$/g, "Crippling Blow");
			text = text.replace(/^DEAD$/g, "Dead to Rights");
			text = text.replace(/^DEADIMP$/g, "Dead to Rights (Improved)");
			text = text.replace(/^DEADACC$/g, "Deadly Accuracy");
			text = text.replace(/^DEPSHOT$/g, "Debilitating Shot");
			text = text.replace(/^DEDI$/g, "Dedication");
			text = text.replace(/^DEFDRI$/g, "Defensive Driving");
			text = text.replace(/^DEFSLI$/g, "Defensive Slicing");
			text = text.replace(/^DEFSLIIMP$/g, "Defensive Slicing (Improved)");
			text = text.replace(/^DEFSTA$/g, "Defensive Stance");
			text = text.replace(/^DISOR$/g, "Disorient");
			text = text.replace(/^DODGE$/g, "Dodge");
			text = text.replace(/^DURA$/g, "Durable");
			text = text.replace(/^DYNFIRE$/g, "Dynamic Fire");
			text = text.replace(/^ENDUR$/g, "Enduring");
			text = text.replace(/^EXHPORT$/g, "Exhaust Port");
			text = text.replace(/^EXTRACK$/g, "Expert Tracker");
			text = text.replace(/^FAMSUNS$/g, "Familiar Suns");
			text = text.replace(/^FERSTR$/g, "Feral Strength");
			text = text.replace(/^FLDCOMM$/g, "Field Commander");
			text = text.replace(/^FLDCOMMIMP$/g, "Field Commander (Improved)");
			text = text.replace(/^FINETUN$/g, "Fine Tuning");
			text = text.replace(/^FIRECON$/g, "Fire Control");
			text = text.replace(/^FORAG$/g, "Forager");
			text = text.replace(/^FORCEWILL$/g, "Force of Will");
			text = text.replace(/^FORCERAT$/g, "Force Rating");
			text = text.replace(/^FORMONME$/g, "Form On Me");
			text = text.replace(/^FRENZ$/g, "Frenzied Attack");
			text = text.replace(/^FULLSTOP$/g, "Full Stop");
			text = text.replace(/^FULLTH$/g, "Full Throttle");
			text = text.replace(/^FULLTHIMP$/g, "Full Throttle (Improved)");
			text = text.replace(/^FULLTHSUP$/g, "Full Throttle (Supreme)");
			text = text.replace(/^GALMAP$/g, "Galaxy Mapper");
			text = text.replace(/^GEARHD$/g, "Gearhead");
			text = text.replace(/^GREASE$/g, "Greased Palms");
			text = text.replace(/^GRIT$/g, "Grit");
			text = text.replace(/^HARDHD$/g, "Hard Headed");
			text = text.replace(/^HARDHDIMP$/g, "Hard Headed (Improved)");
			text = text.replace(/^HEIGHT$/g, "Heightened Awareness");
			text = text.replace(/^HERO$/g, "Heroic Fortitude");
			text = text.replace(/^HIDD$/g, "Hidden Storage");
			text = text.replace(/^HOLDTOG$/g, "Hold Together");
			text = text.replace(/^HUNT$/g, "Hunter");
			text = text.replace(/^INCITE$/g, "Incite Rebellion");
			text = text.replace(/^INDIS$/g, "Indistinguishable");
			text = text.replace(/^INSIGHT$/g, "Insight");
			text = text.replace(/^INSPRHET$/g, "Inspiring Rhetoric");
			text = text.replace(/^INSPRHETIMP$/g, "Inspiring Rhetoric (Improved)");
			text = text.replace(/^INSPRHETSUP$/g, "Inspiring Rhetoric (Supreme)");
			text = text.replace(/^INTENSFOC$/g, "Intense Focus");
			text = text.replace(/^INTENSPRE$/g, "Intense Presence");
			text = text.replace(/^INTIM$/g, "Intimidating");
			text = text.replace(/^INVENT$/g, "Inventor");
			text = text.replace(/^INVIG$/g, "Invigorate");
			text = text.replace(/^ITSNOTTHATBAD$/g, "It's Not that Bad");
			text = text.replace(/^JUMP$/g, "Jump Up");
			text = text.replace(/^JURY$/g, "Jury Rigged");
			text = text.replace(/^KILL$/g, "Kill With Kindness");
			text = text.replace(/^KNOCK$/g, "Knockdown");
			text = text.replace(/^KNOWSOM$/g, "Know Somebody");
			text = text.replace(/^KNOWSPEC$/g, "Knowledge Specialization");
			text = text.replace(/^KNOWSCH$/g, "Known Schematic");
			text = text.replace(/^LETSRIDE$/g, "Let's Ride");
			text = text.replace(/^LETHALBL$/g, "Lethal Blows");
			text = text.replace(/^MASDOC$/g, "Master Doctor");
			text = text.replace(/^MASDRIV$/g, "Master Driver");
			text = text.replace(/^MASGREN$/g, "Master Grenadier");
			text = text.replace(/^MASLEAD$/g, "Master Leader");
			text = text.replace(/^MASMERC$/g, "Master Merchant");
			text = text.replace(/^MASSHAD$/g, "Master of Shadows");
			text = text.replace(/^MASPIL$/g, "Master Pilot");
			text = text.replace(/^MASSLIC$/g, "Master Slicer");
			text = text.replace(/^MASSTAR$/g, "Master Starhopper");
			text = text.replace(/^MENTFOR$/g, "Mental Fortress");
			text = text.replace(/^NATBRAW$/g, "Natural Brawler");
			text = text.replace(/^NATCHARM$/g, "Natural Charmer");
			text = text.replace(/^NATDOC$/g, "Natural Doctor");
			text = text.replace(/^NATDRIV$/g, "Natural Driver");
			text = text.replace(/^NATENF$/g, "Natural Enforcer");
			text = text.replace(/^NATHUN$/g, "Natural Hunter");
			text = text.replace(/^NATLEAD$/g, "Natural Leader");
			text = text.replace(/^NATMAR$/g, "Natural Marksman");
			text = text.replace(/^NATNEG$/g, "Natural Negotiator");
			text = text.replace(/^NATOUT$/g, "Natural Outdoorsman");
			text = text.replace(/^NATPIL$/g, "Natural Pilot");
			text = text.replace(/^NATPRO$/g, "Natural Programmer");
			text = text.replace(/^NATROG$/g, "Natural Rogue");
			text = text.replace(/^NATSCH$/g, "Natural Scholar");
			text = text.replace(/^NATTIN$/g, "Natural Tinkerer");
			text = text.replace(/^NOBFOOL$/g, "Nobody's Fool");
			text = text.replace(/^OUTDOOR$/g, "Outdoorsman");
			text = text.replace(/^OVEREM$/g, "Overwhelm Emotions");
			text = text.replace(/^OVERDEF$/g, "Overwhelm Defenses");
			text = text.replace(/^PHYSTRAIN$/g, "Physical Training");
			text = text.replace(/^PLAUSDEN$/g, "Plausible Deniability");
			text = text.replace(/^POINTBL$/g, "Point Blank");
			text = text.replace(/^PWRBLST$/g, "Powerful Blast");
			text = text.replace(/^PRECAIM$/g, "Precise Aim");
			text = text.replace(/^PRESPNT$/g, "Pressure Point");
			text = text.replace(/^QUICKDR$/g, "Quick Draw");
			text = text.replace(/^QUICKFIX$/g, "Quick Fix");
			text = text.replace(/^QUICKST$/g, "Quick Strike");
			text = text.replace(/^RAPREA$/g, "Rapid Reaction");
			text = text.replace(/^RAPREC$/g, "Rapid Recovery");
			text = text.replace(/^REDUNSYS$/g, "Redundant Systems");
			text = text.replace(/^RESEARCH$/g, "Researcher");
			text = text.replace(/^RESOLVE$/g, "Resolve");
			text = text.replace(/^RESPSCHOL$/g, "Respected Scholar");
			text = text.replace(/^SCATH$/g, "Scathing Tirade");
			text = text.replace(/^SCATHIMP$/g, "Scathing Tirade (Improved)");
			text = text.replace(/^SCATHSUP$/g, "Scathing Tirade (Supreme)");
			text = text.replace(/^SECWIND$/g, "Second Wind");
			text = text.replace(/^SELDETON$/g, "Selective Detonation");
			text = text.replace(/^SENSDANG$/g, "Sense Danger");
			text = text.replace(/^SENSDEMO$/g, "Sense Emotions");
			text = text.replace(/^SHORTCUT$/g, "Shortcut");
			text = text.replace(/^SIDESTEP$/g, "Side Step");
			text = text.replace(/^SITAWARE$/g, "Situational Awareness");
			text = text.replace(/^SIXSENSE$/g, "Sixth Sense");
			text = text.replace(/^SKILLJOCK$/g, "Skilled Jockey");
			text = text.replace(/^SKILLSLIC$/g, "Skilled Slicer");
			text = text.replace(/^SLEIGHTMIND$/g, "Sleight of Mind");
			text = text.replace(/^SMOOTHTALK$/g, "Smooth Talker");
			text = text.replace(/^SNIPSHOT$/g, "Sniper Shot");
			text = text.replace(/^SOFTSP$/g, "Soft Spot");
			text = text.replace(/^SOLREP$/g, "Solid Repairs");
			text = text.replace(/^SOUNDINV$/g, "Sound Investments");
			text = text.replace(/^SPARECL$/g, "Spare Clip");
			text = text.replace(/^SPKBIN$/g, "Speaks Binary");
			text = text.replace(/^STALK$/g, "Stalker");
			text = text.replace(/^STNERV$/g, "Steely Nerves");
			text = text.replace(/^STIMAP$/g, "Stim Application");
			text = text.replace(/^STIMAPIMP$/g, "Stim Application (Improved)");
			text = text.replace(/^STIMAPSUP$/g, "Stim Application (Supreme)");
			text = text.replace(/^STIMSPEC$/g, "Stimpack Specialization");
			text = text.replace(/^STRSMART$/g, "Street Smarts");
			text = text.replace(/^STRGEN$/g, "Stroke of Genius");
			text = text.replace(/^STRONG$/g, "Strong Arm");
			text = text.replace(/^STUNBL$/g, "Stunning Blow");
			text = text.replace(/^STUNBLIMP$/g, "Stunning Blow (Improved)");
			text = text.replace(/^SUPREF$/g, "Superior Reflexes");
			text = text.replace(/^SURG$/g, "Surgeon");
			text = text.replace(/^SWIFT$/g, "Swift");
			text = text.replace(/^TACTTRAIN$/g, "Tactical Combat Training");
			text = text.replace(/^TARGBL$/g, "Targeted Blow");
			text = text.replace(/^TECHAPT$/g, "Technical Aptitude");
			text = text.replace(/^TIME2GO$/g, "Time to Go");
			text = text.replace(/^TIME2GOIMP$/g, "Time to Go (Improved)");
			text = text.replace(/^TINK$/g, "Tinkerer");
			text = text.replace(/^TOUCH$/g, "Touch of Fate");
			text = text.replace(/^TOUGH$/g, "Toughened");
			text = text.replace(/^TRICK$/g, "Tricky Target");
			text = text.replace(/^TRUEAIM$/g, "True Aim");
			text = text.replace(/^UNCANREAC$/g, "Uncanny Reactions");
			text = text.replace(/^UNCANSENS$/g, "Uncanny Senses");
			text = text.replace(/^UNSTOP$/g, "Unstoppable");
			text = text.replace(/^UTIL$/g, "Utility Belt");
			text = text.replace(/^UTINNI$/g, "Utinni!");
			text = text.replace(/^VEHTRAIN$/g, "Vehicle Combat Training");
			text = text.replace(/^WELLROUND$/g, "Well Rounded");
			text = text.replace(/^WELLTRAV$/g, "Well Traveled");
			text = text.replace(/^WHEEL$/g, "Wheel and Deal");
			text = text.replace(/^WORKLIKECHARM$/g, "Works Like A Charm");
			text = text.replace(/^PIN$/g, "Pin");
			text = text.replace(/^MUSEUMWORTHY$/g, "Museum Worthy");
			text = text.replace(/^BRNGITDWN$/g, "Bring It Down");
			text = text.replace(/^HUNTERQUARRY$/g, "Hunter's Quarry");
			text = text.replace(/^HUNTQIMP$/g, "Hunter's Quarry (Improved)");
			text = text.replace(/^BURLY$/g, "Burly");
			text = text.replace(/^FEARSOME$/g, "Fearsome");
			text = text.replace(/^HEAVYHITTER$/g, "Heavy Hitter");
			text = text.replace(/^HEROICRES$/g, "Heroic Resilience");
			text = text.replace(/^IMPDET$/g, "Improvised Detonation");
			text = text.replace(/^IMPDETIMP$/g, "Improvised Detonation (Improved)");
			text = text.replace(/^LOOM$/g, "Loom");
			text = text.replace(/^RAINDEATH$/g, "Rain of Death");
			text = text.replace(/^STEADYNERVES$/g, "Steady Nerves");
			text = text.replace(/^TALKTALK$/g, "Talk the Talk");
			text = text.replace(/^WALKWALK$/g, "Walk the Walk");
			text = text.replace(/^IDEALIST$/g, "Idealist");
			text = text.replace(/^AAO$/g, "Against All Odds");
			text = text.replace(/^ANIMALBOND$/g, "Animal Bond");
			text = text.replace(/^ANIMALBONDIMP$/g, "Animal Bond (Improved)");
			text = text.replace(/^ANIMALEMP$/g, "Animal Empathy");
			text = text.replace(/^ATARU$/g, "Ataru Technique");
			text = text.replace(/^BODIMP$/g, "Body Guard (Improved)");
			text = text.replace(/^BODSUP$/g, "Body Guard (Supreme)");
			text = text.replace(/^CALMAURA$/g, "Calming Aura");
			text = text.replace(/^CALMAURAIMP$/g, "Calming Aura (Improved)");
			text = text.replace(/^CENTBEING$/g, "Center of Being");
			text = text.replace(/^CENTBEINGIMP$/g, "Center of Being (Improved)");
			text = text.replace(/^CIRCLESHELTER$/g, "Circle of Shelter");
			text = text.replace(/^COMPTECH$/g, "Comprehend Technology");
			text = text.replace(/^CONDITIONED$/g, "Conditioned");
			text = text.replace(/^CONTPLAN$/g, "Contingency Plan");
			text = text.replace(/^COUNTERST$/g, "Counterstrike");
			text = text.replace(/^DEFCIRCLE$/g, "Defensive Circle");
			text = text.replace(/^DEFTRAIN$/g, "Defensive Training");
			text = text.replace(/^DISRUPSTRIKE$/g, "Disruptive Strike");
			text = text.replace(/^DJEMSODEFL$/g, "Djem So Deflection");
			text = text.replace(/^DRAWCLOSER$/g, "Draw Closer");
			text = text.replace(/^DUELTRAIN$/g, "Duelist's Training");
			text = text.replace(/^ENHLEAD$/g, "Enhanced Leader");
			text = text.replace(/^FALLAVAL$/g, "Falling Avalanche");
			text = text.replace(/^FEINT$/g, "Feint");
			text = text.replace(/^FORCEASSAULT$/g, "Force Assault");
			text = text.replace(/^FORCEPROT$/g, "Force Protection");
			text = text.replace(/^FOREWARN$/g, "Forewarning");
			text = text.replace(/^HAWKSWOOP$/g, "Hawk Bat Swoop");
			text = text.replace(/^HEALTRANCE$/g, "Healing Trance");
			text = text.replace(/^HEALTRANCEIMP$/g, "Healing Trance (Improved)");
			text = text.replace(/^IMBUEITEM$/g, "Imbue Item");
			text = text.replace(/^INTUITEVA$/g, "Intuitive Evasion");
			text = text.replace(/^INTUITIMP$/g, "Intuitive Improvements");
			text = text.replace(/^INTUITSHOT$/g, "Intuitive Shot");
			text = text.replace(/^INTUITSTRIKE$/g, "Intuitive Strike");
			text = text.replace(/^KEENEYED$/g, "Keen Eyed");
			text = text.replace(/^KNOWPOW$/g, "Knowledge is Power");
			text = text.replace(/^KNOWHEAL$/g, "Knowledgeable Healing");
			text = text.replace(/^MAKFIN$/g, "Makashi Finish");
			text = text.replace(/^MAKFLOUR$/g, "Makashi Flourish");
			text = text.replace(/^MAKTECH$/g, "Makashi Technique");
			text = text.replace(/^MASTART$/g, "Master Artisan");
			text = text.replace(/^MENTBOND$/g, "Mental Bond");
			text = text.replace(/^MENTTOOLS$/g, "Mental Tools");
			text = text.replace(/^MULTOPP$/g, "Multiple Opponents");
			text = text.replace(/^NATBLADE$/g, "Natural Blademaster");
			text = text.replace(/^NATMYSTIC$/g, "Natural Mystic");
			text = text.replace(/^NIMTECH$/g, "Niman Technique");
			text = text.replace(/^NOWYOUSEE$/g, "Now You See Me");
			text = text.replace(/^ONEUNI$/g, "One With The Universe");
			text = text.replace(/^PARRY$/g, "Parry");
			text = text.replace(/^PARRYIMP$/g, "Parry (Improved)");
			text = text.replace(/^PARRYSUP$/g, "Parry (Supreme)");
			text = text.replace(/^PHYSICIAN$/g, "Physician");
			text = text.replace(/^PREEMAVOID$/g, "Preemptive Avoidance");
			text = text.replace(/^PREYWEAK$/g, "Prey on the Weak");
			text = text.replace(/^QUICKMOVE$/g, "Quick Movement");
			text = text.replace(/^REFLECT$/g, "Reflect");
			text = text.replace(/^REFLECTIMP$/g, "Reflect (Improved)");
			text = text.replace(/^REFLECTSUP$/g, "Reflect (Supreme)");
			text = text.replace(/^RESDISARM$/g, "Resist Disarm");
			text = text.replace(/^SABERSW$/g, "Saber Swarm");
			text = text.replace(/^SABERTHROW$/g, "Saber Throw");
			text = text.replace(/^SARSWEEP$/g, "Sarlacc Sweep");
			text = text.replace(/^SENSEADV$/g, "Sense Advantage");
			text = text.replace(/^SHAREPAIN$/g, "Share Pain");
			text = text.replace(/^SHIENTECH$/g, "Shien Technique");
			text = text.replace(/^SHROUD$/g, "Shroud");
			text = text.replace(/^SLIPMIND$/g, "Slippery Minded");
			text = text.replace(/^SORESUTECH$/g, "Soresu Technique");
			text = text.replace(/^STRATFORM$/g, "Strategic Form");
			text = text.replace(/^SUMDJEM$/g, "Sum Djem");
			text = text.replace(/^TERRIFY$/g, "Terrify");
			text = text.replace(/^TERRIFYIMP$/g, "Terrify (Improved)");
			text = text.replace(/^FORCEALLY$/g, "The Force Is My Ally");
			text = text.replace(/^UNITYASSAULT$/g, "Unity Assault");
			text = text.replace(/^VALFACT$/g, "Valuable Facts");
			text = text.replace(/^BADCOP$/g, "Bad Cop");
			text = text.replace(/^BIGGESTFAN$/g, "Biggest Fan");
			text = text.replace(/^CONGENIAL$/g, "Congenial");
			text = text.replace(/^COORDODGE$/g, "Coordination Dodge");
			text = text.replace(/^DISBEH$/g, "Distracting Behavior");
			text = text.replace(/^DISBEHIMP$/g, "Distracting Behavior (Improved)");
			text = text.replace(/^DECEPTAUNT$/g, "Deceptive Taunt");
			text = text.replace(/^GOODCOP$/g, "Good Cop");
			text = text.replace(/^NATATHL$/g, "Natural Athlete");
			text = text.replace(/^NATMERCH$/g, "Natural Merchant");
			text = text.replace(/^THROWCRED$/g, "Throwing Credits");
			text = text.replace(/^UNRELSKEP$/g, "Unrelenting Skeptic");
			text = text.replace(/^UNRELSKEPIMP$/g, "Unrelenting Skeptic (Improved)");
			text = text.replace(/^BEASTWRANG$/g, "Beast Wrangler");
			text = text.replace(/^BOLSTARMOR$/g, "Bolstered Armor");
			text = text.replace(/^CORSEND$/g, "Corellian Sendoff");
			text = text.replace(/^CORSENDIMP$/g, "Corellian Sendoff (Improved)");
			text = text.replace(/^CUSTCOOL$/g, "Customized Cooling Unit");
			text = text.replace(/^EXHANDLER$/g, "Expert Handler");
			text = text.replace(/^FANCPAINT$/g, "Fancy Paint Job");
			text = text.replace(/^FORTVAC$/g, "Fortified Vacuum Seal");
			text = text.replace(/^HIGHGTRAIN$/g, "High-G Training");
			text = text.replace(/^KOITURN$/g, "Koiogran Turn");
			text = text.replace(/^LARGEPROJ$/g, "Larger Project");
			text = text.replace(/^NOTTODAY$/g, "Not Today");
			text = text.replace(/^OVERAMMO$/g, "Overstocked Ammo");
			text = text.replace(/^REINFRAME$/g, "Reinforced Frame");
			text = text.replace(/^SHOWBOAT$/g, "Showboat");
			text = text.replace(/^SIGVEH$/g, "Signature Vehicle");
			text = text.replace(/^SOOTHTONE$/g, "Soothing Tone");
			text = text.replace(/^SPUR$/g, "Spur");
			text = text.replace(/^SPURIMP$/g, "Spur (Improved)");
			text = text.replace(/^SPURSUP$/g, "Spur (Supreme)");
			text = text.replace(/^TUNEDTHRUST$/g, "Tuned Maneuvering Thrusters");
			text = text.replace(/^CALLEM$/g, "Call 'Em");
			text = text.replace(/^DISARMSMILE$/g, "Disarming Smile");
			text = text.replace(/^DONTSHOOT$/g, "Don't Shoot!");
			text = text.replace(/^DOUBLEORNOTHING$/g, "Double or Nothing");
			text = text.replace(/^DOUBLEORNOTHINGIMP$/g, "Double or Nothing (Improved)");
			text = text.replace(/^DOUBLEORNOTHINGSUP$/g, "Double or Nothing (Supreme)");
			text = text.replace(/^FORTFAVORBOLD$/g, "Fortune Favors the Bold");
			text = text.replace(/^GUNSBLAZING$/g, "Guns Blazing");
			text = text.replace(/^JUSTKID$/g, "Just Kidding!");
			text = text.replace(/^QUICKDRIMP$/g, "Quick Draw (Improved)");
			text = text.replace(/^SECCHANCE$/g, "Second Chances");
			text = text.replace(/^SORRYMESS$/g, "Sorry About the Mess");
			text = text.replace(/^SPITFIRE$/g, "Spitfire");
			text = text.replace(/^UPANTE$/g, "Up the Ante");
			text = text.replace(/^WORKLIKECHARM$/g, "Works Like a Charm");
			text = text.replace(/^BADPRESS$/g, "Bad Press");
			text = text.replace(/^BLACKMAIL$/g, "Blackmail");
			text = text.replace(/^CUTQUEST$/g, "Cutting Question");
			text = text.replace(/^DISCREDIT$/g, "Discredit");
			text = text.replace(/^ENCCOMM$/g, "Encoded Communique");
			text = text.replace(/^ENCWORD$/g, "Encouraging Words");
			text = text.replace(/^INKNOW$/g, "In The Know");
			text = text.replace(/^INKNOWIMP$/g, "In The Know (Improved)");
			text = text.replace(/^INFORM$/g, "Informant");
			text = text.replace(/^INTERJECT$/g, "Interjection");
			text = text.replace(/^KNOWALL$/g, "Know-It-All");
			text = text.replace(/^PLAUSDENIMP$/g, "Plausible Deniability (Improved)");
			text = text.replace(/^POSSPIN$/g, "Positive Spin");
			text = text.replace(/^POSSPINIMP$/g, "Positive Spin (Improved)");
			text = text.replace(/^RESEARCHIMP$/g, "Researcher (Improved)");
			text = text.replace(/^SUPPEVI$/g, "Supporting Evidence");
			text = text.replace(/^THORASS$/g, "Thorough Assessment");
			text = text.replace(/^TWISTWORD$/g, "Twisted Words");
			text = text.replace(/^DRIVEBACK$/g, "Drive Back");
			text = text.replace(/^ARMSUP$/g, "Armor Master (Supreme)");
			text = text.replace(/^BALEGAZE$/g, "Baleful Gaze");
			text = text.replace(/^BLINDSPOT$/g, "Blind Spot");
			text = text.replace(/^GRAPPLE$/g, "Grapple");
			text = text.replace(/^NOESC$/g, "No Escape");
			text = text.replace(/^OVERBAL$/g, "Overbalance");
			text = text.replace(/^PRECSTR$/g, "Precision Strike");
			text = text.replace(/^PRIMEPOS$/g, "Prime Positions");
			text = text.replace(/^PRESSHOT$/g, "Prescient Shot");
			text = text.replace(/^PROPAIM$/g, "Prophetic Aim");
			text = text.replace(/^REINITEM$/g, "Reinforce Item");
			text = text.replace(/^SUPPRFIRE$/g, "Suppressing Fire");
			text = text.replace(/^CALMCOMM$/g, "Calm Commander");
			text = text.replace(/^CLEVCOMM$/g, "Clever Commander");
			text = text.replace(/^COMMPRESIMP$/g, "Commanding Presence (Improved)");
			text = text.replace(/^CONFIMP$/g, "Confidence (Improved)");
			text = text.replace(/^MASINST$/g, "Master Instructor");
			text = text.replace(/^MASSTRAT$/g, "Master Strategist");
			text = text.replace(/^NATINST$/g, "Natural Instructor");
			text = text.replace(/^READANY$/g, "Ready for Anything");
			text = text.replace(/^READANYIMP$/g, "Ready for Anything (Improved)");
			text = text.replace(/^THATHOWDONE$/g, "That's How It's Done");
			text = text.replace(/^WELLREAD$/g, "Well Read");
			text = text.replace(/^CUSTLOAD$/g, "Custom Loadout");
			text = text.replace(/^CYBERNETICIST$/g, "Cyberneticist");
			text = text.replace(/^DEFTMAKER$/g, "Deft Maker");
			text = text.replace(/^ENGREDUN$/g, "Engineered Redundancies");
			text = text.replace(/^EYEDET$/g, "Eye for Detail");
			text = text.replace(/^ENERGTRANS$/g, "Energy Transfer");
			text = text.replace(/^MACHMEND$/g, "Machine Mender");
			text = text.replace(/^MOREMACH$/g, "More Machine Than Man");
			text = text.replace(/^OVERCHARGE$/g, "Overcharge");
			text = text.replace(/^OVERCHARGEIMP$/g, "Overcharge (Improved)");
			text = text.replace(/^OVERCHARGESUP$/g, "Supreme Overcharge");
			text = text.replace(/^REROUTEPROC$/g, "Reroute Processors");
			text = text.replace(/^RESOURCEREFIT$/g, "Resourceful Refit");
			text = text.replace(/^SPKBINIMP$/g, "Speaks Binary (Improved)");
			text = text.replace(/^SPKBINSUP$/g, "Speaks Binary (Supreme)");
			text = text.replace(/^DEATHBLOW$/g, "Deathblow");
			text = text.replace(/^ESSENKILL$/g, "Essential Kill");
			text = text.replace(/^FORCECONN$/g, "Force Connection");
			text = text.replace(/^HARASS$/g, "Harass");
			text = text.replace(/^HOLNAV$/g, "Holistic Navigation");
			text = text.replace(/^INTUITNAV$/g, "Intuitive Navigation");
			text = text.replace(/^MARKDEATH$/g, "Marked for Death");
			text = text.replace(/^MENACE$/g, "Menace");
			text = text.replace(/^MINDMAT$/g, "Mind Over Matter");
			text = text.replace(/^ONENAT$/g, "One with Nature");
			text = text.replace(/^PLANMAP$/g, "Planet Mapper");
			text = text.replace(/^SHORTCUTIMP$/g, "Shortcut (Improved)");
			text = text.replace(/^STUDPLOT$/g, "Studious Plotting");
			text = text.replace(/^SURVFIT$/g, "Survival of the Fittest");
			text = text.replace(/^TERRKILL$/g, "Terrifying Kill");
			text = text.replace(/^AMBUSH$/g, "Ambush");
			text = text.replace(/^CUNNSNARE$/g, "Cunning Snare");
			text = text.replace(/^MOVTARGET$/g, "Moving Target");
			text = text.replace(/^SEIZEINIT$/g, "Seize the Initiative");
			text = text.replace(/^MOUNTDOMEST$/g, "Domesticable");
			text = text.replace(/^MOUNTTRAINED$/g, "Trained Mount");
			text = text.replace(/^MOUNTBURDEN$/g, "Beast of Burden");
			text = text.replace(/^MOUNTSTUBBORN$/g, "Stubborn");
			text = text.replace(/^MOUNTDOMESTED$/g, "Domesticated");
			text = text.replace(/^MOUNTFLY$/g, "Flyer");
			text = text.replace(/^BETTERLUCK$/g, "Better Luck Next Time");
			text = text.replace(/^CONSTVIGIL$/g, "Constant Vigilance");
			text = text.replace(/^FEARSHAD$/g, "Fear the Shadows");
			text = text.replace(/^FREERUN$/g, "Freerunning");
			text = text.replace(/^FREERUNIMP$/g, "Freerunning (Improved)");
			text = text.replace(/^IMPOSFALL$/g, "Impossible Fall");
			text = text.replace(/^RECSCENE$/g, "Reconstruct the Scene");
			text = text.replace(/^SABERTHROWIMP$/g, "Saber Throw (Improved)");
			text = text.replace(/^SENSESCENE$/g, "Sense the Scene");
			text = text.replace(/^STRSMARTIMP$/g, "Street Smarts (Improved)");
			text = text.replace(/^SUPHUMAN$/g, "Superhuman Reflexes");
			text = text.replace(/^HARDBOILED$/g, "Hard-Boiled");
			text = text.replace(/^HINDERSHOT$/g, "Hindering Shot");
			text = text.replace(/^IRONBODY$/g, "Iron Body");
			text = text.replace(/^MARTIALGRACE$/g, "Martial Grace");
			text = text.replace(/^OFFDRIVE$/g, "Offensive Driving");
			text = text.replace(/^PRECSTRIMP$/g, "Precision Strike (Improved)");
			text = text.replace(/^PRECSTRSUP$/g, "Precision Strike (Supreme)");
			text = text.replace(/^UNARMPARRY$/g, "Unarmed Parry");
			text = text.replace(/^AGGRNEG$/g, "Aggressive Negotiations");
			text = text.replace(/^CRUCPOINT$/g, "Crucial Point");
			text = text.replace(/^EMPTYSOUL$/g, "Empty Soul");
			text = text.replace(/^GOWITHOUT$/g, "Go Without");
			text = text.replace(/^IRONSOUL$/g, "Iron Soul");
			text = text.replace(/^MEDTRANCE$/g, "Meditative Trance");
			text = text.replace(/^MINDBLEED$/g, "Mind Bleed");
			text = text.replace(/^NOWMAST$/g, "Now the Master");
			text = text.replace(/^ONCELEARN$/g, "Once A Learner");
			text = text.replace(/^SAVVYNEG$/g, "Savvy Negotiator");
			text = text.replace(/^SAVVYNEGIMP$/g, "Savvy Negotiator (Improved)");
			text = text.replace(/^SKILLEDTEACH$/g, "Skilled Teacher");
			text = text.replace(/^SUNDERIMP$/g, "Sunder (Improved)");
			text = text.replace(/^WISEWAR$/g, "Wise Warrior");
			text = text.replace(/^WISEWARIMP$/g, "Wise Warrior (Improved)");
			text = text.replace(/^COMBATPROG$/g, "Combat Programming");
			text = text.replace(/^CONSTSPEC$/g, "Construction Specialist");
			text = text.replace(/^CREATDES$/g, "Creative Design");
			text = text.replace(/^DESPREP$/g, "Desperate Repairs");
			text = text.replace(/^DESFLAW$/g, "Design Flaw");
			text = text.replace(/^DOCKEXP$/g, "Dockyard Expertise");
			text = text.replace(/^IMPDEF$/g, "Improvised Defenses");
			text = text.replace(/^IMPPOS$/g, "Improvised Position");
			text = text.replace(/^MASTDEMO$/g, "Master Demolitionist");
			text = text.replace(/^PUSHSPEC$/g, "Push the Specs");
			text = text.replace(/^REPPATCHSPEC$/g, "Repair Patch Specialization");
			text = text.replace(/^SMARTHAND$/g, "Smart Handling");
			text = text.replace(/^WEAKFOUND$/g, "Weak Foundation");
			text = text.replace(/^ALCARTS$/g, "Alchemical Arts");
			text = text.replace(/^CHANAG$/g, "Channel Agony");
			text = text.replace(/^FONTPOW$/g, "Font of Power");
			text = text.replace(/^IDING$/g, "Identify Ingredients");
			text = text.replace(/^IMPCONC$/g, "Improvised Concoction");
			text = text.replace(/^OVERWAURA$/g, "Overwhelming Aura");
			text = text.replace(/^OVERWAURAIMP$/g, "Overwhelming Aura (Improved)");
			text = text.replace(/^POWDARK$/g, "Power of Darkness");
			text = text.replace(/^SECRETLORE$/g, "Secret Lore");
			text = text.replace(/^TRANSMOG$/g, "Transmogrify");

            // No miss reported here either -- see modFilter. This list ran second,
            // so by now `text` is usually a descriptor's display name rather than
            // a key, and reporting it named the wrong thing entirely.
            return text;
        } else {
            return '';
        }
    }
});

App.filter('qualityFilter', function () {
    return function (text) {
        if (typeof text === 'string') {
            text = text.replace(/STUNSETTING/g, "Stun Setting");
            text = text.replace(/LIMITEDAMMO/g, "Limited Ammo");
            text = text.replace(/INFERIOR/g, "Inferior");
            text = text.replace(/INACCURATE/g, "Inaccurate");
            text = text.replace(/DEFLECTION/g, "Deflection"); // not sure
            text = text.replace(/ACCURATE/g, "Accurate");
            text = text.replace(/PIERCE/g, "Pierce");
            text = text.replace(/DISORIENT/g, "Disorient");
            text = text.replace(/SUPERIOR/g, "Superior");
            text = text.replace(/VICIOUSDROID/g, "Vicious Droid"); // not sure
            text = text.replace(/VICIOUS/g, "Vicious");
            text = text.replace(/AUTOFIRE/g, "Auto-Fire");
            text = text.replace(/LINKED/g, "Linked");
            text = text.replace(/CUMBERSOME/g, "Cumbersome");
            text = text.replace(/BLAST/g, "Blast");
            text = text.replace(/CONCUSSIVE/g, "Concussive");
            text = text.replace(/SLOWFIRING/g, "Slow-Firing");
            text = text.replace(/STUNDAMAGEDROID/g, "Stun Damage Droid"); // not sure
            text = text.replace(/STUNDAMAGE/g, "Stun Damage");
            text = text.replace(/PREPARE/g, "Prepare");
            text = text.replace(/UNWIELDY/g, "Unwieldy");
            text = text.replace(/BREACH/g, "Breach");
            text = text.replace(/BURN/g, "Burn");
            text = text.replace(/CORTOSIS/g, "Cortosis");
            text = text.replace(/DEFENSIVE/g, "Defensive");
            text = text.replace(/ENSNARE/g, "Ensnare");
            text = text.replace(/GUIDED/g, "Guided");
            text = text.replace(/ION/g, "Ion");
            text = text.replace(/KNOCKDOWN/g, "Knockdown");
            text = text.replace(/STUN/g, "Stun");
            text = text.replace(/SUNDER/g, "Sunder");
            text = text.replace(/TRACTOR/g, "Tractor");
            return text;
        } else {
            return '';
        }
    }
});

App.filter('tooltipFilter', function ($filter) {
    return function (text) {
        if (typeof text === 'string') {
            text = text.replace(/STUNSETTING/g, "Passive: Can switch weapon to Stun Damage");
            text = text.replace(/LIMITEDAMMO/g, "Passive: May be used to make a number of attacks equal to it's Limited Ammo rating before it must be reloaded.");
            text = text.replace(/INFERIOR/g, "Passive: Generates automatic [THREAT] on all checks.");
            text = text.replace(/INACCURATE/g, "Passive: Add [SETBACK] to the attacker's dice pool equal to their Inaccurate rating.");
            text = text.replace(/DEFLECTION/g, "Passive: Increases the ranged defense against ion attacks equal to its Deflect Ion rating");
            text = text.replace(/ACCURATE/g, "Passive: Add [SETBACK] to the attacker's dice pool equal to their Inaccurate rating.");
            text = text.replace(/PIERCE/g, "Passive: Ignores one point of Soak for each rank of Pierce");
            text = text.replace(/DISORIENT/g, "Active: The target is disoriented for a number of rounds equal to the weapon's Disorient rating.");
            text = text.replace(/SUPERIOR/g, "Passive: Generates automatic [ADVANTAGE] on all checks");
            text = text.replace(/VICIOUSDROID/g, "Passive: Add 10 times the Vicious rating to the critical roll against droids.");
            text = text.replace(/VICIOUS/g, "Passive: Add 10 times the Vicious rating to the critical roll.");
            text = text.replace(/AUTOFIRE/g, "Active: Increase the difficulty of the attack by [DIFFICULTY]. If the attack hits the attacker can trigger Auto-fire. Auto-fire can be triggered multiple times.Each time the attacker triggers Auto-fire it deals an additional hit to the target.");
            text = text.replace(/LINKED/g, "Active: On a successful attack the wielder may activate to gain an additional hit and may do so a number of times equal to the weapon's Linked rating.");
            text = text.replace(/CUMBERSOME/g, "Passive: The character needs a Brawn characteristic equal to or greater than the weapon's Cumbersome rating.");
            text = text.replace(/BLAST/g, "Active: If the attack is successful and Blast activates, each character (friend or foe) Engaged with the original target sufferes wounds equal to the weapon's Blast rating.");
            text = text.replace(/CONCUSSIVE/g, "Active: The target is staggered for a number of rounds equal to the weapon's Concussive rating.");
            text = text.replace(/SLOWFIRING/g, "Passive: Weapon must waith a number of rounds equal to its Slow-Firing rating before firing again.");
            text = text.replace(/STUNDAMAGEDROID/g, "Passive: Weapon deals damage as strain instead of wounds against droids.");
            text = text.replace(/STUNDAMAGE/g, "Passive: Weapon deals damage as strain instead of wounds.");
            text = text.replace(/PREPARE/g, "Passive: The user must perform a number of Prepare maneuvers equal to the weapon's Prepare rating before making attacks.");
            text = text.replace(/UNWIELDY/g, "Passive: To wield correctly, character needs Agility characteristic equal or greater than rating.");
            text = text.replace(/BREACH/g, "Passive: Ignore one point of Armor for every rank of Breach");
            text = text.replace(/BURN/g, "Active: If the attack is successful, the target continues to take the weapon's base damage for a number of rounds equal to the weapon's Burn rating.");
            text = text.replace(/CORTOSIS/g, "Passive: Weapons with the Cortosis quality are immune to the Sunder quality.");
            text = text.replace(/DEFENSIVE/g, "Passive: A character wielding a weapon with the Defensive quality increases his melee defense by the weapons's Defensive rating.");
            text = text.replace(/ENSNARE/g, "Active: The target is immobilized for a number of rounds equal to the weapon's Ensnare rating.");
            text = text.replace(/GUIDED/g, "Active: Weapon can make an attack check at the end of the round, the check's Ability dice are equal to the weapon's Guided rating.");
            text = text.replace(/ION/g, "Passive: Damage is dealt as System Strain (Vehicles) or Strain Threshold (Droids)");
            text = text.replace(/KNOCKDOWN/g, "Active: The target is knocked prone.");
            text = text.replace(/STUN/g, "Passive: Weapon causes Strain to the target");
            text = text.replace(/SUNDER/g, "Active: Damages opposing weapon one step.");
            text = text.replace(/TRACTOR/g, "Passive: Target may not move unless it makes a successful Piloting check with a difficulty based on the tractor beam's rating.");
            return text;
        } else {
            return '';
        }
    }
});

/**
 * An empty box means "no bound"; 0 is a bound like any other. `!search` treated
 * the two the same, so a min or max of 0 silently did nothing -- which matters
 * most for Handling, the one stat that runs negative (-6 to +3), where 0 sits in
 * the middle of the range rather than at the bottom of it. An empty number input
 * gives undefined, a cleared one '', and an unparseable one NaN; all three mean
 * unfiltered.
 */
App.filter('min', function () {
    return function (items, search, attribute) {
        if (search === undefined || search === null || search === '' || isNaN(search)) {
            return items;
        }
        return items.filter(function (item) {
            return parseInt(item[attribute]) >= search;
        });
    };
});

App.filter('max', function () {
    return function (items, search, attribute) {
        if (search === undefined || search === null || search === '' || isNaN(search)) {
            return items;
        }
        return items.filter(function (item) {
            return parseInt(item[attribute]) <= search;
        });
    };
});

/**
 * Keeps the items printed in a line that is switched on. Reads the normalised
 * Sources array, so it belongs after fetchSource() has reshaped the rows.
 *
 * An item is kept when *any* of its books is in a line that is on -- the same
 * rule the Source multi-select uses, so something reprinted in two books stays
 * visible while either line is on. It is also kept when none of its books maps to
 * a line at all: unfiled books, and the 'Missing' placeholder fetchSource() gives
 * the handful of rows with no <Source>, must not make items vanish.
 *
 * Unmapped books are reported once each, in the house style, so new data shows up
 * in the console rather than sitting in the wrong bucket.
 */
App.filter('sourceLineFilter', function (sourceLines) {
    var lineOfBook = {},
        reported = {},
        i, l, i2, l2;
    for (i = 0, l = sourceLines.length; i < l; i++) {
        for (i2 = 0, l2 = sourceLines[i].books.length; i2 < l2; i2++) {
            lineOfBook[sourceLines[i].books[i2]] = sourceLines[i].key;
        }
    }

    function lineOf(book) {
        if (lineOfBook.hasOwnProperty(book)) {
            return lineOfBook[book];
        }
        // fetchSource()'s own placeholder for a row with no <Source> at all. Not a
        // book, so it belongs to no line and is not a missing mapping.
        if (book != 'Missing' && !reported[book]) {
            reported[book] = true;
            console.log('Please add a source line mapping for: ' + book);
        }
        return null;
    }

    return function (items, enabled) {
        if (!enabled) {
            return items;
        }
        return items.filter(function (item) {
            var i3, l3, line, filed = false;
            if (!item.Sources || typeof item.Sources.length != 'number') {
                return true;
            }
            for (i3 = 0, l3 = item.Sources.length; i3 < l3; i3++) {
                line = lineOf(item.Sources[i3].Book);
                if (line === null) {
                    continue;
                }
                filed = true;
                if (enabled[line]) {
                    return true;
                }
            }
            return !filed;
        });
    };
});

/**
 * Keeps the vehicles of one class, so Vehicles.json can feed more than one tab.
 * 'space' is everything that travels between planets, 'land' everything that
 * stays on one -- ground, air and water alike. An empty class keeps every row,
 * which is what the tabs that are not vehicles pass.
 *
 * This runs on the raw rows, before fetchSource() reshapes <Categories> into an
 * array of {Key}, so it reads OggDude's own shape: one <Category> comes through
 * as a string, several as an array.
 *
 * The 16 rows that carry no <Categories> at all are decided by their Type --
 * hyperdrive sleds and docking rings and the one space slug fly, field
 * equipment, walkers and submersibles do not. Anything the two category lists
 * do not cover logs, in the house style, rather than landing in a tab by
 * accident.
 */
App.filter('vehicleClassFilter', function () {
    var spaceCategories = ['Starship', 'Non-Fighter Starship', 'Capital Ship', 'Station'],
        landCategories = ['Land Vehicle', 'Air Vehicle', 'Walker', 'Wheeled Vehicle',
            'Tracked Vehicle', 'Watercraft'],
        spaceTypes = ['Hyperdrive Sled', 'Hyperdrive Docking Ring', 'Space-dwelling Creature'];

    function categoriesOf(item) {
        var category = item.Categories && item.Categories.Category;
        if (typeof category == 'string') {
            return [category];
        }
        if (typeof category == 'object' && typeof category.length == 'number') {
            return category;
        }
        return [];
    }

    function matches(categories, list) {
        var i, l = categories.length;
        for (i = 0; i < l; i++) {
            if (list.indexOf(categories[i]) > -1) {
                return true;
            }
        }
        return false;
    }

    function classOf(item) {
        var categories = categoriesOf(item);
        if (matches(categories, spaceCategories)) {
            return 'space';
        }
        if (matches(categories, landCategories)) {
            return 'land';
        }
        if (spaceTypes.indexOf(item.Type) > -1) {
            return 'space';
        }
        if (categories.length > 0) {
            console.log('Please add a vehicle class mapping for: ' + categories.join(', '));
        }
        return 'land';
    }

    return function (items, vehicleClass) {
        if (!vehicleClass) {
            return items;
        }
        return items.filter(function (item) {
            return classOf(item) == vehicleClass;
        });
    };
});

/**
 * Keeps the attachments of one class, so ItemAttachments.json can feed more than
 * one tab -- the same split the vehicles get, and for the same reason: 125 of the
 * 357 attachments bolt onto a vehicle and share nothing with the 232 that bolt
 * onto a weapon, a suit of armor or a piece of gear. An empty class keeps every
 * row, which is what the tabs that are not attachments pass.
 *
 * The rule is the attachment's own Type, which every row but one carries, and it
 * needs no category lists: 'Vehicle' is a vehicle attachment and everything else
 * is not. The four 'Mount' rows -- saddlebags, riding tack -- stay with the item
 * attachments on purpose, since a riding animal is a creature and no mount
 * appears in Vehicles.json.
 *
 * A Type this does not know lands in the item tab and logs, in the house style,
 * so new data surfaces instead of quietly picking a side. The one row with no
 * Type at all is the Christophsis Crystal, a lightsaber crystal, and it is silent
 * because it is an item attachment by the only field it has -- its Lightsaber
 * category limit.
 *
 * The two halves must stay a partition: item + vehicle == 357 today, with
 * nothing in both and nothing in neither.
 */
App.filter('attachmentClassFilter', function () {
    var itemTypes = ['Weapon', 'Armor', 'Gear', 'Mount'];

    function classOf(item) {
        if (item.Type == 'Vehicle') {
            return 'vehicle';
        }
        if (typeof item.Type == 'string' && itemTypes.indexOf(item.Type) == -1) {
            console.log('Please add an attachment class mapping for: ' + item.Type);
        }
        return 'item';
    }

    return function (items, attachmentClass) {
        if (!attachmentClass) {
            return items;
        }
        return items.filter(function (item) {
            return classOf(item) == attachmentClass;
        });
    };
});

App.directive('errSrc', function () {
    return {
        link: function (scope, element, attrs) {
            element.bind('error', function () {
                if (attrs.src != attrs.errSrc) {
                    attrs.$set('src', attrs.errSrc);
                }
            });
        }
    }
});

App.directive('itemList', function () {
        return {
            templateUrl: 'app/components/items.html',
            scope: {
                sourceUrl: '@',
                isActive: '@',
                name: '@sourceName',
                keyDesc: '@keyDesc',
                vehicleClass: '@',
                attachmentClass: '@',
            },
            link: function (scope, elem, attrs) {
                // Two tabs share the Vehicle type key and two more share
                // ItemAttachments, so the class has to be part of the id --
                // $mdSidenav looks components up by it, and two sideNav-Vehicles
                // would toggle each other's panel.
                scope.sideNavComponentId = 'sideNav-' + scope.name +
                    (scope.vehicleClass ? '-' + scope.vehicleClass : '') +
                    (scope.attachmentClass ? '-' + scope.attachmentClass : '');
            },
            controller: function ($scope, $timeout, $mdSidenav, $http, $filter, $sce, defaultDisabledSources, sourceLineSelection) {
                $scope.items = [];
                $scope.favourites = [];
                $scope.types = [];
                $scope.categories = [];
                $scope.sensorRanges = [];
                $scope.skills = [];
                $scope.grantedSkills = [];
                $scope.treeTalents = [];
                $scope.restrictions = [];
                $scope.sources = [];
                $scope.ranges = [];
                $scope.qualities = [];
                $scope.baseMods = [];
                $scope.addedMods = [];
                $scope.filteredItems = [];
                $scope.outputItems = [];
                $scope.min = {};
                $scope.max = {};
                $scope.filters = {};
                $scope.order = 'Name';
                $scope.filterItems = function () {
                    $scope.promise = $timeout(function () {
                        if (typeof $scope.items != 'undefined') {
                            var filteredItems = $filter('searchFilter')($scope.items, $scope.filters.searchText);
                            filteredItems = $filter('min')(filteredItems, $scope.filters.minDamage, 'Damage');
                            filteredItems = $filter('max')(filteredItems, $scope.filters.maxDamage, 'Damage');
                            filteredItems = $filter('min')(filteredItems, $scope.filters.minSoak, 'Soak');
                            filteredItems = $filter('max')(filteredItems, $scope.filters.maxSoak, 'Soak');
                            filteredItems = $filter('min')(filteredItems, $scope.filters.minDefensive, 'Defensive');
                            filteredItems = $filter('max')(filteredItems, $scope.filters.maxDefensive, 'Defensive');
                            filteredItems = $filter('min')(filteredItems, $scope.filters.minDeflection, 'Deflection');
                            filteredItems = $filter('max')(filteredItems, $scope.filters.maxDeflection, 'Deflection');
                            filteredItems = $filter('min')(filteredItems, $scope.filters.minCrit, 'Crit');
                            filteredItems = $filter('max')(filteredItems, $scope.filters.maxCrit, 'Crit');
                            filteredItems = $filter('min')(filteredItems, $scope.filters.minRarity, 'Rarity');
                            filteredItems = $filter('max')(filteredItems, $scope.filters.maxRarity, 'Rarity');
                            filteredItems = $filter('min')(filteredItems, $scope.filters.minEncumbrance, 'Encumbrance');
                            filteredItems = $filter('max')(filteredItems, $scope.filters.maxEncumbrance, 'Encumbrance');
                            filteredItems = $filter('min')(filteredItems, $scope.filters.minHP, 'HP');
                            filteredItems = $filter('max')(filteredItems, $scope.filters.maxHP, 'HP');
                            filteredItems = $filter('min')(filteredItems, $scope.filters.minPrice, 'Price');
                            filteredItems = $filter('max')(filteredItems, $scope.filters.maxPrice, 'Price');
                            filteredItems = $filter('min')(filteredItems, $scope.filters.minSilhouette, 'Silhouette');
                            filteredItems = $filter('max')(filteredItems, $scope.filters.maxSilhouette, 'Silhouette');
                            filteredItems = $filter('min')(filteredItems, $scope.filters.minSpeed, 'Speed');
                            filteredItems = $filter('max')(filteredItems, $scope.filters.maxSpeed, 'Speed');
                            filteredItems = $filter('min')(filteredItems, $scope.filters.minHandling, 'Handling');
                            filteredItems = $filter('max')(filteredItems, $scope.filters.maxHandling, 'Handling');
                            filteredItems = $filter('min')(filteredItems, $scope.filters.minArmor, 'Armor');
                            filteredItems = $filter('max')(filteredItems, $scope.filters.maxArmor, 'Armor');
                            filteredItems = $filter('min')(filteredItems, $scope.filters.minHullTrauma, 'HullTrauma');
                            filteredItems = $filter('max')(filteredItems, $scope.filters.maxHullTrauma, 'HullTrauma');
                            filteredItems = $filter('min')(filteredItems, $scope.filters.minSystemStrain, 'SystemStrain');
                            filteredItems = $filter('max')(filteredItems, $scope.filters.maxSystemStrain, 'SystemStrain');
                            filteredItems = $filter('min')(filteredItems, $scope.filters.minWoundThreshold, 'WoundThreshold');
                            filteredItems = $filter('max')(filteredItems, $scope.filters.maxWoundThreshold, 'WoundThreshold');
                            filteredItems = $filter('min')(filteredItems, $scope.filters.minStrainThreshold, 'StrainThreshold');
                            filteredItems = $filter('max')(filteredItems, $scope.filters.maxStrainThreshold, 'StrainThreshold');
                            filteredItems = $filter('min')(filteredItems, $scope.filters.minExperience, 'Experience');
                            filteredItems = $filter('max')(filteredItems, $scope.filters.maxExperience, 'Experience');
                            filteredItems = $filter('min')(filteredItems, $scope.filters.minMinForceRating, 'MinForceRating');
                            filteredItems = $filter('max')(filteredItems, $scope.filters.maxMinForceRating, 'MinForceRating');
                            filteredItems = $filter('min')(filteredItems, $scope.filters.minBrawn, 'Brawn');
                            filteredItems = $filter('max')(filteredItems, $scope.filters.maxBrawn, 'Brawn');
                            filteredItems = $filter('min')(filteredItems, $scope.filters.minAgility, 'Agility');
                            filteredItems = $filter('max')(filteredItems, $scope.filters.maxAgility, 'Agility');
                            filteredItems = $filter('min')(filteredItems, $scope.filters.minIntelligence, 'Intelligence');
                            filteredItems = $filter('max')(filteredItems, $scope.filters.maxIntelligence, 'Intelligence');
                            filteredItems = $filter('min')(filteredItems, $scope.filters.minCunning, 'Cunning');
                            filteredItems = $filter('max')(filteredItems, $scope.filters.maxCunning, 'Cunning');
                            filteredItems = $filter('min')(filteredItems, $scope.filters.minWillpower, 'Willpower');
                            filteredItems = $filter('max')(filteredItems, $scope.filters.maxWillpower, 'Willpower');
                            filteredItems = $filter('min')(filteredItems, $scope.filters.minPresence, 'Presence');
                            filteredItems = $filter('max')(filteredItems, $scope.filters.maxPresence, 'Presence');
                            filteredItems = $filter('fulltextFilter')(filteredItems, $scope.filters.type, 'Type');
                            filteredItems = $filter('fulltextFilter')(filteredItems, $scope.filters.skill, 'SkillKey');
                            filteredItems = $filter('fulltextFilter')(filteredItems, $scope.filters.range, 'RangeValue');
                            filteredItems = $filter('fulltextFilter')(filteredItems, $scope.filters.sensorRange, 'SensorRange');
                            filteredItems = $filter('fulltextFilter')(filteredItems, $scope.filters.restriction, 'Restricted');
                            filteredItems = $filter('arrayFulltextFilter')(filteredItems, $scope.filters.category, 'Categories', 'Key');
                            filteredItems = $filter('arrayFulltextFilter')(filteredItems, $scope.filters.grantedSkill, 'Skills', 'Name');
                            filteredItems = $filter('arrayFulltextFilter')(filteredItems, $scope.filters.treeTalent, 'Talents', 'Name');
                            filteredItems = $filter('arrayFulltextFilter')(filteredItems, $scope.filters.baseMod, 'BaseMods', 'Key');
                            filteredItems = $filter('arrayFulltextFilter')(filteredItems, $scope.filters.addedMod, 'AddedMods', 'Key');
                            filteredItems = $filter('arrayFulltextFilter')(filteredItems, $scope.filters.quality, 'Qualities', 'Key');
                            filteredItems = $filter('arrayFulltextFilterOr')(filteredItems, $scope.filters.source, 'Sources', 'Book');
                            // The global line buttons, on top of this tab's own Source
                            // selection: an item has to pass both.
                            filteredItems = $filter('sourceLineFilter')(filteredItems, sourceLineSelection.enabled);
                            if ($scope.order.length > 0) {
                                filteredItems = $filter('orderBy')(filteredItems, $scope.order);
                            }
                            $scope.filteredItems = filteredItems;
                            if (filteredItems.length <= 20) {
                                $scope.outputItems = $scope.filteredItems;
                            } else {
                                $scope.outputItems = $filter('limitTo')($scope.filteredItems, 10);
                            }
                        }
                    });
                };
                $scope.hasFilters = function () {
                    // True when anything is narrowing the list. `source` is skipped:
                    // it always holds the default selection, so counting it would
                    // pin "Clear filters" open permanently.
                    //
                    // Tested per value rather than for truthiness, because a min or
                    // max of 0 is a real bound -- see the min/max filters.
                    var key, value;
                    for (key in $scope.filters) {
                        if (!$scope.filters.hasOwnProperty(key) || key == 'source') {
                            continue;
                        }
                        value = $scope.filters[key];
                        if (value === undefined || value === null || value === '') {
                            continue;
                        }
                        if (typeof value.length == 'number' && value.length == 0) {
                            continue;
                        }
                        return true;
                    }
                    return false;
                };
                $scope.getDefaultSources = function () {
                    var i, l = $scope.sources.length, defaultSources = [];
                    for (i = 0; i < l; i++) {
                        if (defaultDisabledSources.indexOf($scope.sources[i]) === -1) {
                            defaultSources.push($scope.sources[i]);
                        }
                    }
                    return defaultSources;
                };
                $scope.resetFilters = function () {
                    $scope.filters = {
                        source: $scope.getDefaultSources()
                    };
                    $scope.filterItems();
                };
                $scope.increaseLimit = function () {
                    $scope.loading = true;
                    $timeout(function () {
                        var newItems = $filter('limitTo')($scope.filteredItems, 100, $scope.outputItems.length), l, i;
                        l = newItems.length;
                        for (i = 0; i < l; i++) {
                            $scope.outputItems.push(newItems[i]);
                        }
                        $scope.loading = false;
                    });
                };
                $scope.showAll = function () {
                    $scope.loading = true;
                    $timeout(function () {
                        var newItems = $filter('limitTo')($scope.filteredItems, $scope.filteredItems.length, $scope.outputItems.length), l, i;
                        l = newItems.length;
                        for (i = 0; i < l; i++) {
                            $scope.outputItems.push(newItems[i]);
                        }
                        $scope.loading = false;
                    });
                };
                $scope.fetchSource = function () {
                    $scope.loading = true;
                    $http.get($scope.sourceUrl).then(function (res) {
                        var i, l, i2, l2, items, qualities, baseMods, addedMods, talents, skills, abilities, sources, categoryLimits, itemLimits, typeLimits, skillLimits, categories, vehicleWeapons, builtInAttachments, specializations, outputItems = [];
                        items = res.data[$scope.name];
                        // Before anything reads the rows, so the sliders' ranges and
                        // the filter dropdowns describe this tab's half of the file.
                        items = $filter('vehicleClassFilter')(items, $scope.vehicleClass);
                        items = $filter('attachmentClassFilter')(items, $scope.attachmentClass);
                        l = items.length;
                        $scope.min.Damage = $scope.getMinValue(items, 'Damage');
                        $scope.max.Damage = $scope.getMaxValue(items, 'Damage');
                        $scope.min.Soak = $scope.getMinValue(items, 'Soak');
                        $scope.max.Soak = $scope.getMaxValue(items, 'Soak');
                        $scope.min.Crit = $scope.getMinValue(items, 'Crit');
                        $scope.max.Crit = $scope.getMaxValue(items, 'Crit');
                        $scope.min.Rarity = $scope.getMinValue(items, 'Rarity');
                        $scope.max.Rarity = $scope.getMaxValue(items, 'Rarity');
                        $scope.min.Encumbrance = $scope.getMinValue(items, 'Encumbrance');
                        $scope.max.Encumbrance = $scope.getMaxValue(items, 'Encumbrance');
                        $scope.min.HP = $scope.getMinValue(items, 'HP');
                        $scope.max.HP = $scope.getMaxValue(items, 'HP');
                        $scope.min.Price = $scope.getMinValue(items, 'Price');
                        $scope.max.Price = $scope.getMaxValue(items, 'Price');
                        $scope.min.Silhouette = $scope.getMinValue(items, 'Silhouette');
                        $scope.max.Silhouette = $scope.getMaxValue(items, 'Silhouette');
                        $scope.min.Speed = $scope.getMinValue(items, 'Speed');
                        $scope.max.Speed = $scope.getMaxValue(items, 'Speed');
                        $scope.min.Handling = $scope.getMinValue(items, 'Handling');
                        $scope.max.Handling = $scope.getMaxValue(items, 'Handling');
                        $scope.min.Armor = $scope.getMinValue(items, 'Armor');
                        $scope.max.Armor = $scope.getMaxValue(items, 'Armor');
                        $scope.min.HullTrauma = $scope.getMinValue(items, 'HullTrauma');
                        $scope.max.HullTrauma = $scope.getMaxValue(items, 'HullTrauma');
                        $scope.min.SystemStrain = $scope.getMinValue(items, 'SystemStrain');
                        $scope.max.SystemStrain = $scope.getMaxValue(items, 'SystemStrain');
                        for (i = 0; i < l; i++) {
                            //if (items[i].Type == 'Vehicle') {
                            //    continue;
                            //}
                            qualities = [];
                            sources = [];
                            talents = [];
                            skills = [];
                            abilities = [];
                            baseMods = [];
                            addedMods = [];
                            categoryLimits = [];
                            categories = [];
                            vehicleWeapons = [];
                            builtInAttachments = [];
                            specializations = [];
                            itemLimits = [];
                            skillLimits = [];
                            typeLimits = [];
                            items[i].Deflection = 0;

                            items[i].Info = $filter('infoFilter')(items[i]);
                            if (typeof items[i].Defense == 'number') {
                                items[i].Defensive = items[i].Defense;
                            } else {
                                items[i].Defensive = 0;
                            }
                            if (typeof items[i].Thumbnail == 'string') {
                                items[i].imageUrl = $sce.trustAsHtml(items[i].Thumbnail);
                            } else {
                                items[i].imageUrl = $sce.trustAsHtml('data/img/' + $scope.name + items[i].Key + '.png');
                            }
                            if (typeof items[i].Description == 'string') {
                                items[i].Description = $filter('descriptionFilter')(items[i]);
                            }
                            if (typeof items[i].Name == 'string') {
                                items[i].Name = $filter('nameFilter')(items[i]);
                            }
                            if (typeof items[i].Damage == 'undefined') {
                                items[i].Damage = 0;
                            }
                            if (typeof items[i].DamageAdd == 'undefined') {
                                items[i].DamageAdd = 0;
                            }
                            if (typeof items[i].HP == 'undefined') {
                                items[i].HP = 0;
                            }
                            // OggDude writes Restricted as the *string* "true" or
                            // "false", so the value has to be compared -- "false"
                            // is truthy. It is also simply absent on rows nobody
                            // flagged either way (204 weapons, 235 gear), and an
                            // absent flag means the same as an explicit "false":
                            // defaulting them here is what keeps picking
                            // "Unrestricted" from hiding two thirds of the tab.
                            //
                            // Turned into the label the badge and the dropdown
                            // both read, the way SkillKey and RangeValue are
                            // rewritten in place above. Only on the types that
                            // carry the field at all -- species, careers and
                            // talents have no legality to speak of, and would
                            // otherwise get a dropdown with one useless option.
                            if ($scope.name == 'Weapon' || $scope.name == 'Armor' ||
                                $scope.name == 'Gear' || $scope.name == 'Vehicle' ||
                                $scope.name == 'ItemAttachments') {
                                if (items[i].Restricted == 'true') {
                                    items[i].Restricted = 'Restricted';
                                } else {
                                    items[i].Restricted = 'Unrestricted';
                                }
                            }
                            if (typeof items[i].Qualities == 'object') {
                                if (typeof items[i].Qualities.Quality == 'object') {
                                    if (typeof items[i].Qualities.Quality.Key == 'string') {
                                        items[i].Qualities.Quality.Tooltip = $filter('tooltipFilter')(items[i].Qualities.Quality.Key);
                                        items[i].Qualities.Quality.Key = $filter('qualityFilter')(items[i].Qualities.Quality.Key);
                                        if (items[i].Qualities.Quality.Key == 'Defensive') {
                                            items[i].Defensive = items[i].Qualities.Quality.Count;
                                        }
                                        if (items[i].Qualities.Quality.Key == 'Deflection') {
                                            items[i].Deflection = items[i].Qualities.Quality.Count;
                                        }
                                        qualities.push(items[i].Qualities.Quality);
                                    } else {
                                        if (typeof items[i].Qualities.Quality.length == 'number') {
                                            l2 = items[i].Qualities.Quality.length;
                                            for (i2 = 0; i2 < l2; i2++) {
                                                items[i].Qualities.Quality[i2].Tooltip = $filter('tooltipFilter')(items[i].Qualities.Quality[i2].Key);
                                                items[i].Qualities.Quality[i2].Key = $filter('qualityFilter')(items[i].Qualities.Quality[i2].Key);
                                                if (items[i].Qualities.Quality[i2].Key == 'Defensive') {
                                                    items[i].Defensive = items[i].Qualities.Quality[i2].Count;
                                                }
                                                if (items[i].Qualities.Quality[i2].Key == 'Deflection') {
                                                    items[i].Deflection = items[i].Qualities.Quality[i2].Count;
                                                }
                                                qualities.push(items[i].Qualities.Quality[i2]);
                                            }
                                        }
                                    }
                                }
                            }
                            if (typeof items[i].Quality == 'string') {
                                if (typeof items[i].Quality.Key == 'string') {
                                    items[i].Quality.Key = $filter('qualityFilter')(items[i].Quality.Key);
                                    if (items[i].Quality.Key == 'Defensive') {
                                        items[i].Defensive = items[i].Quality.Count;
                                    }
                                    if (items[i].Quality.Key == 'Deflection') {
                                        items[i].Deflection = items[i].Quality.Count;
                                    }
                                    qualities.push(items[i].Quality);
                                }
                            }
                            items[i].Qualities = qualities;
                            if (typeof items[i].Sources != 'undefined' && typeof items[i].Sources.Source != 'undefined') {
                                for (var i4 = 0, l4 = items[i].Sources.Source.length; i4 < l4; i4++) {
                                    if (typeof items[i].Sources.Source[i4].Book == 'string') {
                                        sources.push(items[i].Sources.Source[i4]);
                                    }
                                    if (typeof items[i].Sources.Source == 'object' && typeof items[i].Sources.Source[i4] == 'string') {
                                        sources.push({'Book': items[i].Sources.Source[i4]});
                                    }

                                }
                                if (typeof items[i].Sources.Source == 'string') {
                                    sources.push({'Book': items[i].Sources.Source});
                                }
                                if (typeof items[i].Sources.Source == 'object' && typeof items[i].Sources.Source.Book == 'string') {
                                    if (typeof items[i].Sources.Source.Page == 'number' || typeof items[i].Sources.Source.Page == 'string') {
                                        sources.push({'Book': items[i].Sources.Source.Book, 'Page' : items[i].Sources.Source.Page});
                                    } else {
                                    	sources.push({'Book': items[i].Sources.Source.Book});
                                    }
                                }
                            }
                            if (typeof items[i].Source == 'object' && typeof items[i].Source.Book == 'string') {
                                sources.push(items[i].Source);
                                delete items[i].Source;
                            }
                            if (typeof items[i].Source == 'string') {
                                sources.push({'Book': items[i].Source});
                                delete items[i].Source;
                            }
                            if (sources.length == 0) {
                                sources.push({'Book': 'Missing'});
                            }
                            items[i].Sources = sources;


                            if (typeof items[i].BaseMods == 'object') {
                                if (typeof items[i].BaseMods.Mod == 'object' && items[i].BaseMods.Mod.length > 0) {
                                    for (var i3 = 0, l3 = items[i].BaseMods.Mod.length; i3 < l3; i3++) {
                                        if (typeof items[i].BaseMods.Mod[i3].Key == 'string') {
                                            items[i].BaseMods.Mod[i3].Key = $filter('modFilter')(items[i].BaseMods.Mod[i3].Key);
                                            baseMods.push(items[i].BaseMods.Mod[i3]);
                                        }
                                    }
                                } else {
                                    if (typeof items[i].BaseMods.Mod != 'undefined') {
                                        if (typeof items[i].BaseMods.Mod.Key == 'string') {
                                            items[i].BaseMods.Mod.Key = $filter('modFilter')(items[i].BaseMods.Mod.Key);
                                            baseMods.push(items[i].BaseMods.Mod);
                                        }
                                    }
                                }
                            }
                            items[i].BaseMods = baseMods;
                            if (typeof items[i].AddedMods == 'object') {
                                if (typeof items[i].AddedMods.Mod == 'object' && items[i].AddedMods.Mod.length > 0) {
                                    for (i3 = 0, l3 = items[i].AddedMods.Mod.length; i3 < l3; i3++) {
                                        if (typeof items[i].AddedMods.Mod[i3].Key == 'string') {
                                            items[i].AddedMods.Mod[i3].Key = $filter('modFilter')(items[i].AddedMods.Mod[i3].Key);
                                            addedMods.push(items[i].AddedMods.Mod[i3]);
                                        }
                                    }
                                } else {
                                    if (typeof items[i].AddedMods.Mod != 'undefined') {
                                        if (typeof items[i].AddedMods.Mod.Key == 'string') {
                                            items[i].AddedMods.Mod.Key = $filter('modFilter')(items[i].AddedMods.Mod.Key);
                                            addedMods.push(items[i].AddedMods.Mod);
                                        }
                                    }
                                }
                            }
                            items[i].AddedMods = addedMods;
                            if (typeof items[i].SkillKey == 'string') {
                                items[i].SkillKey = $filter('skillFilter')(items[i].SkillKey);
                                if (items[i].SkillKey == 'Melee' || items[i].SkillKey == 'Lightsaber' || items[i].SkillKey == 'Brawl' || items[i].Type == 'Thrown') {
                                    if (items[i].DamageAdd > 0 && items[i].Damage == 0) {
                                        items[i].Damage = items[i].DamageAdd;
                                    }
                                }
                            }
                            if (typeof items[i].RangeValue == 'string') {
                                items[i].RangeValue = $filter('rangeFilter')(items[i].RangeValue);
                            }
                            if (typeof items[i].Characteristics == 'object') {
                                if (typeof items[i].Characteristics.Characteristic == 'object') {
                                    if (typeof items[i].Characteristics.Characteristic.length == 'number') {
                                        l2 = items[i].Characteristics.Characteristic.length;
                                        for (i2 = 0; i2 < l2; i2++) {
                                            if (items[i].Characteristics.Characteristic[i2].Key == 'BR') {
                                                items[i].Brawn = items[i].Characteristics.Characteristic[i2].Rank;
                                            }
                                            if (items[i].Characteristics.Characteristic[i2].Key == 'AG') {
                                                items[i].Agility = items[i].Characteristics.Characteristic[i2].Rank;
                                            }
                                            if (items[i].Characteristics.Characteristic[i2].Key == 'INT') {
                                                items[i].Intelligence = items[i].Characteristics.Characteristic[i2].Rank;
                                            }
                                            if (items[i].Characteristics.Characteristic[i2].Key == 'CUN') {
                                                items[i].Cunning = items[i].Characteristics.Characteristic[i2].Rank;
                                            }
                                            if (items[i].Characteristics.Characteristic[i2].Key == 'WIL') {
                                                items[i].Willpower = items[i].Characteristics.Characteristic[i2].Rank;
                                            }
                                            if (items[i].Characteristics.Characteristic[i2].Key == 'PR') {
                                                items[i].Presence = items[i].Characteristics.Characteristic[i2].Rank;
                                            }
                                        }
                                    }
                                }
                                if (items[i].Characteristics.Brawn) {
                                    items[i].Brawn = items[i].Characteristics.Brawn;
                                }
                                if (items[i].Characteristics.Agility) {
                                    items[i].Agility = items[i].Characteristics.Agility;
                                }
                                if (items[i].Characteristics.Intellect) {
                                    items[i].Intelligence = items[i].Characteristics.Intellect;
                                }
                                if (items[i].Characteristics.Cunning) {
                                    items[i].Cunning = items[i].Characteristics.Cunning;
                                }
                                if (items[i].Characteristics.Willpower) {
                                    items[i].Willpower = items[i].Characteristics.Willpower;
                                }
                                if (items[i].Characteristics.Presence) {
                                    items[i].Presence = items[i].Characteristics.Presence;
                                }
                            }
                            if (typeof items[i].Talents == 'object') {
                                if (typeof items[i].Talents.Talent == 'object') {
                                    if (typeof items[i].Talents.Talent.Name == 'string') {
                                        if (typeof items[i].Talents.Talent.Rank == 'undefined') {
                                            items[i].Talents.Talent.Rank = 1;
                                        }
                                        talents.push(items[i].Talents.Talent);
                                    } else {
                                        if (typeof items[i].Talents.Talent.length == 'number') {
                                            l2 = items[i].Talents.Talent.length;
                                            for (i2 = 0; i2 < l2; i2++) {
                                                if (typeof items[i].Talents.Talent[i2].Rank == 'undefined') {
                                                    items[i].Talents.Talent[i2].Rank = 1;
                                                }
                                                talents.push(items[i].Talents.Talent[i2]);
                                            }
                                        }
                                    }
                                }
                            }
                            items[i].Talents = talents;
                            if (typeof items[i].Skills == 'object') {
                                if (typeof items[i].Skills.Skill == 'object') {
                                    if (typeof items[i].Skills.Skill.Name == 'string') {
                                        if (typeof items[i].Skills.Skill.Rank == 'undefined') {
                                            items[i].Skills.Skill.Rank = 1;
                                        }
                                        skills.push(items[i].Skills.Skill);
                                    } else {
                                        if (typeof items[i].Skills.Skill.length == 'number') {
                                            l2 = items[i].Skills.Skill.length;
                                            for (i2 = 0; i2 < l2; i2++) {
                                                if (typeof items[i].Skills.Skill[i2].Rank == 'undefined') {
                                                    items[i].Skills.Skill[i2].Rank = 1;
                                                }
                                                skills.push(items[i].Skills.Skill[i2]);
                                            }
                                        }
                                    }
                                }
                            }
                            items[i].Skills = skills;
                            if (typeof items[i].Abilities == 'object') {
                                if (typeof items[i].Abilities.Ability == 'object') {
                                    if (typeof items[i].Abilities.Ability.Name == 'string') {
                                        abilities.push(items[i].Abilities.Ability);
                                    } else {
                                        if (typeof items[i].Abilities.Ability.length == 'number') {
                                            l2 = items[i].Abilities.Ability.length;
                                            for (i2 = 0; i2 < l2; i2++) {
                                                abilities.push(items[i].Abilities.Ability[i2]);
                                            }
                                        }
                                    }
                                }
                            }
                            items[i].Abilities = abilities;
                            if (typeof items[i].SpecialAbilities == 'object') {
                                if (typeof items[i].SpecialAbilities.SpecialAbility == 'object') {
                                    if (typeof items[i].SpecialAbilities.SpecialAbility.Description == 'string') {
                                        items[i].SpecialAbilities.SpecialAbility = [
                                            {
                                                Name: items[i].SpecialAbilities.SpecialAbility.Name,
                                                Description: $sce.trustAsHtml($filter('symbolFilter')(items[i].SpecialAbilities.SpecialAbility.Description))
                                            }
                                        ]
                                    } else {
                                        if (typeof items[i].SpecialAbilities.SpecialAbility.length == 'number') {
                                            l2 = items[i].SpecialAbilities.SpecialAbility.length;
                                            for (i2 = 0; i2 < l2; i2++) {
                                                items[i].SpecialAbilities.SpecialAbility[i2].Description = $sce.trustAsHtml($filter('symbolFilter')(items[i].SpecialAbilities.SpecialAbility[i2].Description));
                                            }
                                        }
                                    }
                                }
                            }
                            if (typeof items[i].Attributes != 'undefined') {
                                if (typeof items[i].Attributes.Soak == 'number') {
                                    items[i].Soak = items[i].Attributes.Soak;
                                }
                                if (typeof items[i].Attributes.WoundThreshold == 'number') {
                                    items[i].WoundThreshold = items[i].Attributes.WoundThreshold;
                                }
                                if (typeof items[i].Attributes.WoundThreshold == 'number') {
                                    items[i].StrainThreshold = items[i].Attributes.StrainThreshold;
                                }
                                if (typeof items[i].Attributes.Experience == 'number') {
                                    items[i].Experience = items[i].Attributes.Experience;
                                }
                                if (typeof items[i].Attributes.ForceRating == 'number') {
                                    items[i].ForceRating = items[i].Attributes.ForceRating;
                                }
                            }
                            if (typeof items[i].CategoryLimit == 'object') {
                                if (typeof items[i].CategoryLimit.Category == 'string') {
                                    categoryLimits.push(items[i].CategoryLimit.Category);
                                }
                                if (typeof items[i].CategoryLimit.Category == 'object') {
                                    if (typeof items[i].CategoryLimit.Category.length == 'number') {
                                        l2 = items[i].CategoryLimit.Category.length;
                                        for (i2 = 0; i2 < l2; i2++) {
                                            categoryLimits.push(items[i].CategoryLimit.Category[i2]);
                                        }
                                    }
                                }
                            }
                            items[i].CategoryLimit = categoryLimits;
                            // <ItemLimit> holds <Key>, not <Item> -- reading the
                            // wrong child left this array empty on all 35 rows
                            // that carry one, which is why no "Item:" line has
                            // ever appeared beside the category and type limits.
                            // The key is an item in another JSON file, so it goes
                            // through the name list rather than to the template.
                            if (typeof items[i].ItemLimit == 'object') {
                                if (typeof items[i].ItemLimit.Key == 'string') {
                                    itemLimits.push($filter('itemLimitFilter')(items[i].ItemLimit.Key));
                                }
                                if (typeof items[i].ItemLimit.Key == 'object') {
                                    if (typeof items[i].ItemLimit.Key.length == 'number') {
                                        l2 = items[i].ItemLimit.Key.length;
                                        for (i2 = 0; i2 < l2; i2++) {
                                            itemLimits.push($filter('itemLimitFilter')(items[i].ItemLimit.Key[i2]));
                                        }
                                    }
                                }
                            }
                            items[i].ItemLimit = itemLimits;
                            if (typeof items[i].TypeLimit == 'object') {
                                if (typeof items[i].TypeLimit.Type == 'string') {
                                    typeLimits.push(items[i].TypeLimit.Type);
                                }
                                if (typeof items[i].TypeLimit.Type == 'object') {
                                    if (typeof items[i].TypeLimit.Type.length == 'number') {
                                        l2 = items[i].TypeLimit.Type.length;
                                        for (i2 = 0; i2 < l2; i2++) {
                                            typeLimits.push(items[i].TypeLimit.Type[i2]);
                                        }
                                    }
                                }
                            }
                            items[i].TypeLimit = typeLimits;
                            // <SkillLimit> holds <Key> too, and the same six skill
                            // codes the Weapons tab already resolves, so it reuses
                            // skillFilter rather than a list of its own.
                            if (typeof items[i].SkillLimit == 'object') {
                                if (typeof items[i].SkillLimit.Key == 'string') {
                                    skillLimits.push($filter('skillFilter')(items[i].SkillLimit.Key));
                                }
                                if (typeof items[i].SkillLimit.Key == 'object') {
                                    if (typeof items[i].SkillLimit.Key.length == 'number') {
                                        l2 = items[i].SkillLimit.Key.length;
                                        for (i2 = 0; i2 < l2; i2++) {
                                            skillLimits.push($filter('skillFilter')(items[i].SkillLimit.Key[i2]));
                                        }
                                    }
                                }
                            }
                            items[i].SkillLimit = skillLimits;
                            // What decides whether a vehicle mod actually fits the
                            // hull: a silhouette range, whether it has to be a
                            // starship, whether the hull needs a hyperdrive, and a
                            // floor on encumbrance capacity. Built here rather than
                            // in the template so the Limits cell stays the flat list
                            // of strings the category and type limits above it are.
                            //
                            // A MinSize, MaxSize or MinEncumCap of 0 is OggDude's
                            // "no bound" and not a limit to print -- two rows pair a
                            // MinSize of 3 or 5 with a MaxSize of 0 -- and the two
                            // flags are the string "true"/"false" the way Restricted
                            // is, so they have to be compared rather than tested.
                            items[i].SilhouetteLimit = $scope.sizeLimit(items[i].MinSize, items[i].MaxSize);
                            items[i].StarshipLimit = items[i].MustBeStarship == 'true';
                            items[i].HyperdriveLimit = items[i].MustHaveHyperdrive == 'true';
                            if (typeof items[i].MinEncumCap == 'number' && items[i].MinEncumCap > 0) {
                                items[i].EncumbranceCapacityLimit = items[i].MinEncumCap;
                            } else {
                                items[i].EncumbranceCapacityLimit = 0;
                            }
                            // Weapons, Armor and Gear carry <Categories> too, but some of
                            // their rows use the whitespace-quirk array shape this block
                            // does not read, which would give those tabs a half-populated
                            // Category filter. Vehicles, talents and careers only, until
                            // that shape is handled -- all three of those files are written
                            // by an importer that emits nothing but plain <Category>
                            // strings. On careers the one value is 'Force'; on
                            // specializations it is the careers that offer the tree,
                            // plus 'Universal' for the eleven any career may take --
                            // which is what makes "the Guardian trees" a filter
                            // rather than a column, the same trick careers play.
                            if ($scope.name == 'Vehicle' || $scope.name == 'Talent' ||
                                $scope.name == 'Career' || $scope.name == 'Specialization') {
                                if (typeof items[i].Categories == 'object') {
                                    if (typeof items[i].Categories.Category == 'string') {
                                        categories.push({'Key': items[i].Categories.Category});
                                    }
                                    if (typeof items[i].Categories.Category == 'object') {
                                        if (typeof items[i].Categories.Category.length == 'number') {
                                            l2 = items[i].Categories.Category.length;
                                            for (i2 = 0; i2 < l2; i2++) {
                                                categories.push({'Key': items[i].Categories.Category[i2]});
                                            }
                                        }
                                    }
                                }
                                // Assigned even when the row carries no <Categories> at
                                // all, so this is an array on every row of the tab the
                                // way Qualities and Sources are: arrayFulltextFilter
                                // reads .length on each one, and picking a category used
                                // to throw on the 16 vehicles -- and would have thrown on
                                // the 323 talents -- that have none.
                                items[i].Categories = categories;
                                $scope.collectValues(items[i].Categories, 'Key', $scope.categories);
                            }
                            // One vehicle weapon comes through as an object, several as an
                            // array -- the same SimpleXML shape the Qualities block above
                            // has to cope with.
                            if (typeof items[i].VehicleWeapons == 'object') {
                                if (typeof items[i].VehicleWeapons.VehicleWeapon == 'object') {
                                    if (typeof items[i].VehicleWeapons.VehicleWeapon.Name == 'string') {
                                        vehicleWeapons.push(items[i].VehicleWeapons.VehicleWeapon);
                                    } else {
                                        if (typeof items[i].VehicleWeapons.VehicleWeapon.length == 'number') {
                                            l2 = items[i].VehicleWeapons.VehicleWeapon.length;
                                            for (i2 = 0; i2 < l2; i2++) {
                                                vehicleWeapons.push(items[i].VehicleWeapons.VehicleWeapon[i2]);
                                            }
                                        }
                                    }
                                }
                                l2 = vehicleWeapons.length;
                                for (i2 = 0; i2 < l2; i2++) {
                                    vehicleWeapons[i2].Qualities = $scope.readQualities(vehicleWeapons[i2], $filter);
                                }
                            }
                            items[i].VehicleWeapons = vehicleWeapons;
                            if (typeof items[i].BuiltInAttachments == 'object') {
                                if (typeof items[i].BuiltInAttachments.Attachment == 'string') {
                                    builtInAttachments.push(items[i].BuiltInAttachments.Attachment);
                                }
                                if (typeof items[i].BuiltInAttachments.Attachment == 'object') {
                                    if (typeof items[i].BuiltInAttachments.Attachment.length == 'number') {
                                        l2 = items[i].BuiltInAttachments.Attachment.length;
                                        for (i2 = 0; i2 < l2; i2++) {
                                            builtInAttachments.push(items[i].BuiltInAttachments.Attachment[i2]);
                                        }
                                    }
                                }
                            }
                            items[i].BuiltInAttachments = builtInAttachments;
                            // A career's specialisations: the names only, since the
                            // specialisation itself is a talent tree this app has no
                            // renderer for. One comes through as a string, several as an
                            // array -- the BuiltInAttachments shape exactly.
                            if (typeof items[i].Specializations == 'object') {
                                if (typeof items[i].Specializations.Specialization == 'string') {
                                    specializations.push(items[i].Specializations.Specialization);
                                }
                                if (typeof items[i].Specializations.Specialization == 'object') {
                                    if (typeof items[i].Specializations.Specialization.length == 'number') {
                                        l2 = items[i].Specializations.Specialization.length;
                                        for (i2 = 0; i2 < l2; i2++) {
                                            specializations.push(items[i].Specializations.Specialization[i2]);
                                        }
                                    }
                                }
                            }
                            items[i].Specializations = specializations;
                            // A career's Skills are the six or eight it makes cheap, a
                            // species' the one or two it starts with a rank in -- the
                            // same shape and the same question ("which of these gives
                            // me Piloting - Space?"), so both tabs collect into the
                            // one dropdown, which is why it is labelled just "Skill".
                            // The other types' Skills array is always empty; the gate
                            // says so rather than relying on it.
                            if ($scope.name == 'Career' || $scope.name == 'Species' ||
                                $scope.name == 'Specialization') {
                                $scope.collectValues(items[i].Skills, 'Name', $scope.grantedSkills);
                            }
                            // The two tree tabs. Both carry <Tree>, and both list
                            // what the tree teaches under <Talents> -- a force
                            // power's entries are its abilities, written in the
                            // species <Talent><Name> shape on purpose, so the
                            // block above has already turned them into an array
                            // and one column, one dropdown and one renderer
                            // serve both tabs.
                            if ($scope.name == 'Specialization' || $scope.name == 'ForcePower') {
                                items[i].Tree = $scope.readTree(items[i]);
                                $scope.collectValues(items[i].Talents, 'Name', $scope.treeTalents);
                            }
                            $scope.collectValues(items[i].Qualities, 'Key', $scope.qualities);
                            $scope.collectValues(items[i].BaseMods, 'Key', $scope.baseMods);
                            $scope.collectValues(items[i].AddedMods, 'Key', $scope.addedMods);
                            $scope.collectValues(items[i].Sources, 'Book', $scope.sources);
                            outputItems.push(items[i]);
                        }
                        $scope.min.Defensive = $scope.getMinValue(items, 'Defensive');
                        $scope.max.Defensive = $scope.getMaxValue(items, 'Defensive');
                        $scope.min.Deflection = $scope.getMinValue(items, 'Deflection');
                        $scope.max.Deflection = $scope.getMaxValue(items, 'Deflection');
                        $scope.collectValues(outputItems, 'SkillKey', $scope.skills);
                        $scope.collectValues(outputItems, 'Type', $scope.types);
                        $scope.collectValues(outputItems, 'Restricted', $scope.restrictions);
                        $scope.collectValues(outputItems, 'RangeValue', $scope.ranges);
                        $scope.collectValues(outputItems, 'SensorRange', $scope.sensorRanges);
                        $scope.min.WoundThreshold = $scope.getMinValue(items, 'WoundThreshold');
                        $scope.max.WoundThreshold = $scope.getMaxValue(items, 'WoundThreshold');
                        $scope.min.StrainThreshold = $scope.getMinValue(items, 'StrainThreshold');
                        $scope.max.StrainThreshold = $scope.getMaxValue(items, 'StrainThreshold');
                        $scope.min.Experience = $scope.getMinValue(items, 'Experience');
                        $scope.max.Experience = $scope.getMaxValue(items, 'Experience');
                        // Only force powers carry one, and only 14 of the 20 state
                        // it -- the six that do not are left out rather than
                        // defaulted to 1, so the slider's floor is a number the
                        // books actually print.
                        $scope.min.MinForceRating = $scope.getMinValue(items, 'MinForceRating');
                        $scope.max.MinForceRating = $scope.getMaxValue(items, 'MinForceRating');
                        $scope.min.Brawn = $scope.getMinValue(items, 'Brawn');
                        $scope.max.Brawn = $scope.getMaxValue(items, 'Brawn');
                        $scope.min.Agility = $scope.getMinValue(items, 'Agility');
                        $scope.max.Agility = $scope.getMaxValue(items, 'Agility');
                        $scope.min.Intelligence = $scope.getMinValue(items, 'Intelligence');
                        $scope.max.Intelligence = $scope.getMaxValue(items, 'Intelligence');
                        $scope.min.Cunning = $scope.getMinValue(items, 'Cunning');
                        $scope.max.Cunning = $scope.getMaxValue(items, 'Cunning');
                        $scope.min.Willpower = $scope.getMinValue(items, 'Willpower');
                        $scope.max.Willpower = $scope.getMaxValue(items, 'Willpower');
                        $scope.min.Presence = $scope.getMinValue(items, 'Presence');
                        $scope.max.Presence = $scope.getMaxValue(items, 'Presence');
                        $scope.items = outputItems;
                        $scope.filters.source = $scope.getDefaultSources();
                        $scope.filterItems();
                        $scope.loading = false;
                    });

                };
                $scope.readQualities = function (owner, $filter) {
                    // A vehicle weapon carries the same <Qualities><Quality> block a
                    // weapon does, so it needs the same unwrapping: one quality is an
                    // object, several are an array, and the key has to be turned into
                    // a display name with a tooltip.
                    var quality, i, l, out = [];
                    if (typeof owner.Qualities != 'object') {
                        return out;
                    }
                    if (typeof owner.Qualities.Quality != 'object') {
                        return out;
                    }
                    if (typeof owner.Qualities.Quality.Key == 'string') {
                        out.push(owner.Qualities.Quality);
                    } else {
                        if (typeof owner.Qualities.Quality.length == 'number') {
                            l = owner.Qualities.Quality.length;
                            for (i = 0; i < l; i++) {
                                out.push(owner.Qualities.Quality[i]);
                            }
                        }
                    }
                    l = out.length;
                    for (i = 0; i < l; i++) {
                        quality = out[i];
                        quality.Tooltip = $filter('tooltipFilter')(quality.Key);
                        quality.Key = $filter('qualityFilter')(quality.Key);
                    }
                    return out;
                };
                $scope.readList = function (holder, child) {
                    // SimpleXML's one-or-many shape, as an array every time:
                    // one <Node> is an object, several are an array, none is a
                    // missing key. The same three cases the Qualities, Sources
                    // and Categories blocks each unwrap inline -- pulled out
                    // here because a tree nests them four deep and doing it
                    // inline would be unreadable.
                    var i, l, out = [];
                    if (typeof holder != 'object' || holder === null) {
                        return out;
                    }
                    if (typeof holder[child] != 'object' || holder[child] === null) {
                        return out;
                    }
                    if (typeof holder[child].length == 'number') {
                        l = holder[child].length;
                        for (i = 0; i < l; i++) {
                            out.push(holder[child][i]);
                        }
                    } else {
                        out.push(holder[child]);
                    }
                    return out;
                };
                $scope.readTree = function (item) {
                    // A specialization's talent tree or a force power's upgrade
                    // tree, flattened into what the renderer walks. The importer
                    // has already done the layout -- see
                    // oggdude_specializations_to_app.py -- so this only turns
                    // SimpleXML's shapes into arrays and gives every row four
                    // column slots to draw into.
                    //
                    // Two things are deliberately not four entries long. A row's
                    // Nodes hold one entry per BOX, and a box may span several
                    // columns, so a force power row can be a single node with a
                    // Span of 4. Its Down list holds only the columns that are
                    // joined to the row below, which is why it is expanded here
                    // into four booleans the template can index by position.
                    var rows, nodes, down, tree = [], i, l, i2, l2, node, bars;
                    rows = $scope.readList(item.Tree, 'Row');
                    l = rows.length;
                    for (i = 0; i < l; i++) {
                        nodes = $scope.readList(rows[i], 'Nodes');
                        nodes = nodes.length ? $scope.readList(nodes[0], 'Node') : [];
                        // Four slots, one per grid column: true where a connector
                        // runs down to the row below. Written once, by the row
                        // above, so the last row's list is simply empty.
                        bars = [false, false, false, false];
                        down = $scope.readList(rows[i], 'Down');
                        l2 = down.length;
                        for (i2 = 0; i2 < l2; i2++) {
                            if (typeof down[i2].Col == 'number' &&
                                down[i2].Col >= 0 && down[i2].Col < bars.length) {
                                bars[down[i2].Col] = true;
                            }
                        }
                        l2 = nodes.length;
                        for (i2 = 0; i2 < l2; i2++) {
                            node = nodes[i2];
                            // "true"/"false" as a string, the way Restricted and
                            // the vehicle flags are, so it has to be compared.
                            node.Linked = node.LinkRight == 'true';
                            // A cell with no talent in it is a hole in the grid
                            // and still has to take up its column, or the row
                            // would come out narrower than the ones around it.
                            node.Empty = typeof node.Name != 'string';
                        }
                        tree.push({Cost: rows[i].Cost, Nodes: nodes, Down: bars});
                    }
                    return tree;
                };
                $scope.sizeLimit = function (min, max) {
                    // The silhouettes a vehicle attachment fits, as one string.
                    // 0 is OggDude's "no bound", so a MinSize of 5 beside a
                    // MaxSize of 0 reads "5+" rather than "5-0"; a row with
                    // neither bound gets '' and prints no line at all.
                    var hasMin = typeof min == 'number' && min > 0,
                        hasMax = typeof max == 'number' && max > 0;
                    if (hasMin && hasMax) {
                        return min + '-' + max;
                    }
                    if (hasMin) {
                        return min + '+';
                    }
                    if (hasMax) {
                        return 'up to ' + max;
                    }
                    return '';
                };
                $scope.collectValues = function (items, attribute, values) {
                    var value, i, l = items.length;
                    for (i = 0; i < l; i++) {
                        if (typeof items[i][attribute] === 'string') {
                            value = items[i][attribute];
                            if (values.indexOf(value, 0) === -1) {
                                values.push(value);
                            }
                        }
                    }
                    values.sort();
                };
                $scope.getMinValue = function (items, attribute) {
                    var value, min, i, l = items.length;
                    for (i = 0; i < l; i++) {
                        if (typeof items[i][attribute] === 'number') {
                            value = items[i][attribute];
                            if (typeof min == 'undefined' || value < min) {
                                min = value;
                            }
                        }
                    }
                    return min;
                };
                $scope.getMaxValue = function (items, attribute) {
                    var value, max, i, l = items.length;
                    for (i = 0; i < l; i++) {
                        if (typeof items[i][attribute] === 'number') {
                            value = items[i][attribute];
                            if (typeof max == 'undefined' || value > max) {
                                max = value;
                            }
                        }
                    }
                    return max;
                };
                $scope.getMinValue = function (items, attribute) {
                    var value, min, i, l = items.length;
                    for (i = 0; i < l; i++) {
                        if (typeof items[i][attribute] === 'number') {
                            value = items[i][attribute];
                            if (typeof min == 'undefined' || value < min) {
                                min = value;
                            }
                        }
                    }
                    return min;
                };
                $scope.toggleSideNav = function () {
                    $mdSidenav($scope.sideNavComponentId).toggle();
                };
                $scope.$watch('isActive', function () {
                    if ($scope.isActive == "true" && $scope.items.length == 0) {
                        $scope.fetchSource();
                    }
                });
                // md-tabs keeps a tab's scope in the tree once it has been opened, so
                // the tabs in the background re-filter too and are right when the user
                // gets back to them. A tab never opened has no scope yet and loads with
                // the current selection anyway.
                $scope.$on('sourceLinesChanged', function () {
                    $scope.filterItems();
                });
            }
        }
    }
);