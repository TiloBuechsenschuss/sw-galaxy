## STAR WARS GALAXY

# [CLICK HERE TO USE THE WEB APP](https://tilobuechsenschuss.github.io/sw-galaxy/)

This tool was made to support Star Wars FFG role players to find  weapons, armors and gear fast and easy.
This web application offers a lot of possibilities to search and filter the items.

This website is optimized for mobile devices. This enables the players to search for their preferred items
from their smartphones even when they are currently in a pen and paper session.

### Run the project locally

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
npx http-server -p 8000

# PHP
php -S localhost:8000
```

Then open <http://localhost:8000> in your browser. An internet connection is required on
first load, because AngularJS itself and the Material Icons font are pulled from a CDN.

Any other web server works just as well — just point its document root at this folder.

### Convert the XML data from OggDude Character Generator to JSON files for the STAR WARS GALAXY web application.

Just move following files from the `SWEotECharGen` folder into the folder `xml_to_json/xml_sources/oggdude` and execute
the php script `xml_to_json/convert.php` from a unix like shell like this: `php xml_to_json/convert.php`.

```
Data/Armor.xml
Data/Gear.xml
Data/ItemAttachments.xml
Data/Weapons.xml
```

If you are running a web server like apache or nginx, you can run the `convert.php` script with a http request too.

No PHP? There is a Python port that produces the same output:

```
python xml_to_json/convert.py            # convert everything
python xml_to_json/convert.py --check    # show what would change, write nothing
python xml_to_json/verify_convert.py     # check nothing regressed
```

### Use multiple data sources

Multiple data sets can be merged too. Just create a new folder in `xml_to_json/xml_sources`. The name of the new folder is up to yours.
Then copy your custom XML files in. Currently following file names are supported: `Armor.xml`, `Gear.xml`, `ItemAttachments.xml`, `Weapons.xml`, `Species.xml`.
Then run the `convert.php` like described above.

Folders are read in alphabetical order and the first entry for a given `Key` wins, so an
earlier-sorting folder takes priority. The exception is fan-made data: an entry sourced
only from the *Unofficial Species Menagerie* always loses to one from an official book.

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
