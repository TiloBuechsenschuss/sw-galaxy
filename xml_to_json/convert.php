<?php
/**
 * Execute this script only from the shell
 */
$validFileNames = array(
    'Armor' => 'Armor.xml',
    'Weapon' => 'Weapons.xml',
    'ItemAttachments' => 'ItemAttachments.xml',
    'Gear' => 'Gear.xml',
    'Species' => 'Species.xml'
);

/**
 * Fan-made books. An entry sourced only from these always loses to an entry
 * with an official book, whatever order the source folders are read in.
 */
$deprioritisedBooks = array('Unofficial Species Menagerie');


/**
 * OggDude stores the page as an attribute: <Source Page="44">Forged in Battle</Source>.
 * simplexml_load_string() throws attributes away, so those 1783 page numbers never
 * reached the JSON and the item cards rendered a book with no page. Rewrite them
 * into the <Book>/<Page> child shape before converting -- the shape Species already
 * use and items.html already renders. xml_to_json/convert.py does the same in
 * expand_source_pages().
 *
 * @param string $xml
 * @return string
 */
function expandSourcePages($xml)
{
    $doc = new DOMDocument();
    if (!@$doc->loadXML($xml)) {
        return $xml;
    }
    $xpath = new DOMXPath($doc);
    /** @var DOMElement $source */
    foreach ($xpath->query('//Source[@Page]') as $source) {
        // Species already carry <Book>/<Page> children; leave those alone.
        if ($source->getElementsByTagName('*')->length > 0) {
            continue;
        }
        $book = $source->textContent;
        $page = $source->getAttribute('Page');
        $source->removeAttribute('Page');
        while ($source->firstChild !== null) {
            $source->removeChild($source->firstChild);
        }
        $bookNode = $doc->createElement('Book');
        $bookNode->appendChild($doc->createTextNode($book));
        $source->appendChild($bookNode);
        $pageNode = $doc->createElement('Page');
        $pageNode->appendChild($doc->createTextNode($page));
        $source->appendChild($pageNode);
    }
    return $doc->saveXML();
}

/**
 * Every book name attached to a row, across both shapes the data uses:
 * <Sources><Source>..</Sources> and a single <Source>.
 *
 * @param stdClass $row
 * @return string[]
 */
function sourceBooks($row)
{
    $books = array();
    if (isset($row->Sources) && isset($row->Sources->Source)) {
        $src = $row->Sources->Source;
        if (is_array($src)) {
            foreach ($src as $one) {
                if (is_object($one) && isset($one->Book) && is_string($one->Book)) {
                    $books[] = $one->Book;
                } elseif (is_string($one)) {
                    $books[] = $one;
                }
            }
        } elseif (is_object($src) && isset($src->Book) && is_string($src->Book)) {
            $books[] = $src->Book;
        } elseif (is_string($src)) {
            $books[] = $src;
        }
    }
    if (isset($row->Source)) {
        if (is_object($row->Source) && isset($row->Source->Book) && is_string($row->Source->Book)) {
            $books[] = $row->Source->Book;
        } elseif (is_string($row->Source)) {
            $books[] = $row->Source;
        }
    }
    return $books;
}

/**
 * True when every source for this row is fan-made.
 *
 * @param stdClass $row
 * @param string[] $deprioritisedBooks
 * @return bool
 */
function isDeprioritised($row, $deprioritisedBooks)
{
    $books = sourceBooks($row);
    if (count($books) === 0) {
        return false;
    }
    foreach ($books as $book) {
        if (!in_array($book, $deprioritisedBooks, true)) {
            return false;
        }
    }
    return true;
}

/**
 * The book a row sorts under: the first of its source books, or '' when it
 * carries none.
 *
 * @param stdClass $row
 * @return string
 */
function sortBook($row)
{
    $books = sourceBooks($row);
    return count($books) > 0 ? $books[0] : '';
}

/**
 * Rows are written ordered by their first Source book, then by Name, with Key
 * as the tie-breaker so the committed JSON diffs cleanly. xml_to_json/convert.py
 * sorts the same way.
 *
 * @param stdClass $a
 * @param stdClass $b
 * @return int
 */
function compareRows($a, $b)
{
    $cmp = strcmp(strtolower(trim(sortBook($a))), strtolower(trim(sortBook($b))));
    if ($cmp !== 0) {
        return $cmp;
    }
    $aName = strtolower(trim(isset($a->Name) ? $a->Name : ''));
    $bName = strtolower(trim(isset($b->Name) ? $b->Name : ''));
    $cmp = strcmp($aName, $bName);
    if ($cmp !== 0) {
        return $cmp;
    }
    return strcmp(isset($a->Key) ? $a->Key : '', isset($b->Key) ? $b->Key : '');
}
if (function_exists('apache_request_headers')) {
    print "<pre>";
}
foreach ($validFileNames as $typeKey => $fileName) {
    $xmlFilePattern = dirname(__FILE__) . '/xml_sources/*/' . $fileName;
    $xmlFiles = glob($xmlFilePattern, GLOB_BRACE);
    $jsonFile = dirname(__FILE__) . '/../data/json/' . preg_replace("/^(.*)\.xml$/", "$1.json", $fileName);
    $fileData = array($typeKey => array());
    /** @var string $xmlFile */
    foreach ($xmlFiles as $xmlFile) {
        /** @var SimpleXMLElement $data */
        $data = simplexml_load_string(expandSourcePages(file_get_contents($xmlFile)));
        // remove comment nodes
        unset($data->comment);
        $data = json_decode(json_encode($data, JSON_NUMERIC_CHECK));
        $values = reset($data);
        foreach ($values as &$row) {
            if (isset($row->Key) && isset($row->Name) && strlen(trim($row->Name)) > 0) {
                if (empty($row->Key) || is_numeric($row->Key)) {
                    $row->Key = 'MISSING_KEY_' . strtoupper(preg_replace("/(\"|\'| |-)/", '_', $row->Name));
                }
                if (isset($fileData[$typeKey][$row->Key])) {
                    // First one wins, unless the entry already held is fan-made
                    // only and this one carries an official book.
                    $incumbentIsFanMade = isDeprioritised($fileData[$typeKey][$row->Key], $deprioritisedBooks);
                    if (!$incumbentIsFanMade || isDeprioritised($row, $deprioritisedBooks)) {
                        continue;
                    }
                }
                if (!isset($row->Description) || !is_string($row->Description)) {
                    $row->Description = "";
                }
                if (!isset($row->Descriptors) || !is_string($row->Descriptors)) {
                    unset($row->Descriptors);
                }
                if ($typeKey == 'Species' && isset($row->Source) && isset($row->Source->Page) && !is_numeric($row->Source->Page)) {
                    unset($row->Source->Page);
                }
//                if (isset($row->Sources) || empty($row->Sources)) {
//                    unset($row->Sources);
//                }
                $thumbnail = 'data/img/' . $typeKey . $row->Key . '.png';
                if (file_exists(dirname(__FILE__) . '/../' . $thumbnail)) {
                    $row->Thumbnail = $thumbnail;
                } else {
                    $row->Thumbnail = 'img/no_image.png';
                }
                $fileData[$typeKey][$row->Key] = $row;
                // print "$typeKey: ".$typeKey;
                // print "$row->Key: ".$row->Key;
                // print "$row: ". $row;
            }
        }
        print "Read {$xmlFile}\n";
    }
    foreach ($fileData as $dataKey => $rows) {
        $rows = array_values($rows);
        usort($rows, 'compareRows');
        $fileData[$dataKey] = $rows;
    }
    // The committed JSON is pretty-printed with CRLF line endings; keep it that
    // way so regenerating does not rewrite every line. xml_to_json/convert.py
    // must produce byte-identical output -- see xml_to_json/README.md.
    $json = json_encode($fileData, JSON_PRETTY_PRINT);
    $json = str_replace("\r\n", "\n", $json);
    $json = str_replace("\n", "\r\n", $json);
    file_put_contents($jsonFile, $json);
    print "=> Wrote {$jsonFile}\n";
}
if (function_exists('apache_request_headers')) {
    print "</pre>";
}
print "XML to JSON File conversion finished!\n";