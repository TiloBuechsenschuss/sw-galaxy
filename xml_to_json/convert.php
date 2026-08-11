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
 * Books that are not imported at all. A row whose every source is one of these
 * is skipped, so neither the row nor the book name reaches the JSON.
 */
$excludedBooks = array('Unofficial Species Menagerie');


/**
 * OggDude's export sometimes writes the same field twice on one row: THONTIIN,
 * ZOPHIS and PROTTORPHVY each carry <Type> twice, DATABRBO carries <Restricted>
 * twice. simplexml_load_string() turns repeated siblings into an array, so the
 * field reached the JSON as ["Weapon","Weapon"] and items.html rendered the
 * array instead of the value. Drop the later copies, keeping the first.
 *
 * Deliberately narrow, so nothing legitimately repeated is collapsed:
 *
 *  - only childless elements are considered -- <Mod>, <Skill>, <Option> and the
 *    like have children and are left alone, as are whole duplicated rows, which
 *    the first-Key-wins merge already handles;
 *  - tag, attributes and text must all match, so the two <Source Page="42"> /
 *    <Source Page="46"> entries CONCMISSILEMK10 has for Dangerous Covenants are
 *    kept -- same book, two pages, and both belong in the JSON;
 *  - whitespace-only and empty elements are skipped, so quirk 2 still holds and
 *    <ItemLimit /> style placeholders survive untouched.
 *
 * Runs before expandSourcePages(), so an exactly duplicated <Source> would be
 * caught here too. xml_to_json/convert.py does the same in
 * drop_duplicate_siblings().
 *
 * @param string $xml
 * @return string
 */
function dropDuplicateSiblings($xml)
{
    $doc = new DOMDocument();
    if (!@$doc->loadXML($xml)) {
        return $xml;
    }
    $xpath = new DOMXPath($doc);
    $duplicates = array();
    /** @var DOMElement $parent */
    foreach ($xpath->query('//*') as $parent) {
        $seen = array();
        /** @var DOMNode $child */
        foreach ($parent->childNodes as $child) {
            if ($child->nodeType != XML_ELEMENT_NODE) {
                continue;
            }
            if ($child->getElementsByTagName('*')->length > 0) {
                continue;
            }
            $text = trim($child->textContent);
            if ($text === '') {
                continue;
            }
            $attributes = array();
            foreach ($child->attributes as $attribute) {
                $attributes[] = $attribute->name . '=' . $attribute->value;
            }
            sort($attributes);
            $signature = $child->nodeName . "\0" . implode("\0", $attributes) . "\0" . $text;
            if (isset($seen[$signature])) {
                // Collected first: removing while iterating a live DOMNodeList
                // skips the following sibling.
                $duplicates[] = $child;
                $keyNodes = $parent->getElementsByTagName('Key');
                $rowKey = $keyNodes->length > 0 ? $keyNodes->item(0)->textContent : $parent->nodeName;
                print "  ~ {$rowKey}: dropped duplicate <{$child->nodeName}>{$text}</{$child->nodeName}>\n";
            } else {
                $seen[$signature] = true;
            }
        }
    }
    /** @var DOMElement $duplicate */
    foreach ($duplicates as $duplicate) {
        $duplicate->parentNode->removeChild($duplicate);
    }
    return $doc->saveXML();
}

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
 * True when the row has sources and every one of them is an excluded book, so
 * the row can be dropped. A row with no source at all is kept -- seven generic
 * Gear entries have none, and they are legitimate.
 *
 * @param stdClass $row
 * @param string[] $excludedBooks
 * @return bool
 */
function isExcluded($row, $excludedBooks)
{
    $books = sourceBooks($row);
    if (count($books) === 0) {
        return false;
    }
    foreach ($books as $book) {
        if (!in_array($book, $excludedBooks, true)) {
            return false;
        }
    }
    return true;
}

/**
 * True when the row mixes an excluded book with a book that is kept. No row in
 * the current data does, so such a row is reported rather than handled: keeping
 * it would leak the excluded book name into the app's Source filter, dropping it
 * would lose official content. Decide deliberately if this ever fires.
 *
 * @param stdClass $row
 * @param string[] $excludedBooks
 * @return bool
 */
function mixesExcludedBook($row, $excludedBooks)
{
    $books = sourceBooks($row);
    $excluded = 0;
    foreach ($books as $book) {
        if (in_array($book, $excludedBooks, true)) {
            $excluded++;
        }
    }
    return $excluded > 0 && $excluded < count($books);
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
        $data = simplexml_load_string(expandSourcePages(dropDuplicateSiblings(file_get_contents($xmlFile))));
        // remove comment nodes
        unset($data->comment);
        $data = json_decode(json_encode($data, JSON_NUMERIC_CHECK));
        $values = reset($data);
        $excludedRows = 0;
        foreach ($values as &$row) {
            if (isset($row->Key) && isset($row->Name) && strlen(trim($row->Name)) > 0) {
                if (empty($row->Key) || is_numeric($row->Key)) {
                    $row->Key = 'MISSING_KEY_' . strtoupper(preg_replace("/(\"|\'| |-)/", '_', $row->Name));
                }
                // Excluded before de-duplication, so an excluded row never takes
                // a Key that a kept row would otherwise have claimed.
                if (isExcluded($row, $excludedBooks)) {
                    $excludedRows++;
                    continue;
                }
                if (mixesExcludedBook($row, $excludedBooks)) {
                    print "  ! {$row->Key} mixes an excluded book with a kept one -- see mixesExcludedBook()\n";
                }
                if (isset($fileData[$typeKey][$row->Key])) {
                    // First one wins.
                    continue;
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
        print "Read {$xmlFile}" . ($excludedRows > 0 ? " ({$excludedRows} excluded)" : "") . "\n";
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