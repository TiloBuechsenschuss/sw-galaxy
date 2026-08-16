## STAR WARS GALAXY

# [CLICK HERE TO USE THE WEB APP](https://tilobuechsenschuss.github.io/sw-galaxy/)

This tool was made to support Star Wars FFG role players to find  weapons, armors and gear fast and easy.
This web application offers a lot of possibilities to search and filter the items.

This website is optimized for mobile devices. This enables the players to search for their preferred items
from their smartphones even when they are currently in a pen and paper session.

The filter button at the right of the tab bar switches whole game lines — *Edge of the Empire*,
*Age of Rebellion*, *Force and Destiny* and *Extended Material* — on and off. It applies to every
tab at once, so a group playing only one line can hide the rest, and the browser remembers the
choice for a month. The button turns red while anything is switched off.

### Run the project locally

> **These commands are for you, the person reading this — not for an AI coding agent.**
> Starting a server and checking the page in a browser is the repository owner's job.
> Agents should verify their work with scripts and the pipeline checks instead; see
> *Verifying changes* in [AGENTS.md](AGENTS.md).

STAR WARS GALAXY is a static AngularJS app. There is no build step and no dependencies to
install — everything needed is already in this repository. You only need to serve the
project folder over HTTP.

Opening `index.html` directly from the file system (`file://...`) does **not** work: the app
loads its data with AJAX requests, and browsers block those on the `file://` protocol.

Pick whichever of these you already have installed and run it from the project root:

```
# Python 3
python -m http.server 8000

# Node.js
npx http-server -p 8000 -c-1
```

Then open <http://localhost:8000> in your browser. An internet connection is required on
first load, because AngularJS itself and the Material Icons font are pulled from a CDN.

Any other web server works just as well — just point its document root at this folder.

#### None of these reload by themselves

They are plain static file servers with no file watcher. After editing a file, or after
regenerating `data/json/*.json`, **refresh the browser yourself**. A data change always
needs a full page reload: each tab fetches its JSON once, when the tab is created.

The `-c-1` above matters. Without it `http-server` sends `Cache-Control: max-age=3600`, so
the browser may keep using a cached copy of a JSON file for an hour and a plain refresh will
not show regenerated data. `python -m http.server` sends no such header and revalidates on
every request, so it needs no extra flag.

If you want the browser to reload on its own, use a dev server that watches the folder:

```
npx live-server --port=8000
```

It reloads the page whenever any file changes — including a regenerated `data/json/*.json` —
and hot-swaps CSS without a reload. It works by injecting a small live-reload script into the
HTML it serves, so use it for development only; it is not a deployment target.

### Convert the XML data from OggDude Character Generator to JSON files for the STAR WARS GALAXY web application.

Just move following files from the `SWEotECharGen` folder into the folder `xml_to_json/xml_sources/oggdude`:

```
Data/Armor.xml
Data/Gear.xml
Data/ItemAttachments.xml
Data/Weapons.xml
```

Then run the converter. Python 3 is all it needs — no packages to install:

```
python xml_to_json/convert.py            # convert everything
python xml_to_json/convert.py --check    # show what would change, write nothing
python xml_to_json/verify_convert.py     # check nothing regressed
```

### Use multiple data sources

Multiple data sets can be merged too. Just create a new folder in `xml_to_json/xml_sources`. The name of the new folder is up to yours.
Then copy your custom XML files in. Currently following file names are supported: `Armor.xml`, `Gear.xml`, `ItemAttachments.xml`, `Weapons.xml`, `Species.xml`.
Then run `convert.py` like described above.

Folders are read in alphabetical order and the first entry for a given `Key` wins, so an
earlier-sorting folder takes priority.

Some books can be left out of the import entirely: any entry whose sources are all listed in
`EXCLUDED_BOOKS` (`convert.py`) is skipped, so it shows up neither in the data nor in the
app's Source filter. Add a book name there to drop it.

Species XML from OggDude uses a different schema than this app reads, so it has to be
translated first with `python xml_to_json/oggdude_species_to_app.py`.
See [`xml_to_json/README.md`](xml_to_json/README.md) for the full details.

### Please feel free to contribute!

Please feel free to add your improvements to this projects.
Even small changes like additional images for items are welcome.
To do so, fork this project and send us an merge request.

If you have ideas for new features or found an bug, please create an issue to let us know.

### Oh, Thanks!

Thanks to the original team: Dutzen, MarceloAlves and applification. You can find their original work at https://github.com/applifaction/sw-galaxy

Thank you OggDude for creating and offering your data and awesome [OggDude Character Generator](https://www.legendsofthegalaxy.com/Oggdude/) to us!
