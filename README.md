# DBLP Bibtex Lookup

## Description

Matches the content of a bibtex file against the DBLP-Database and updates the entries if there
exists a match within the database, generating a new bibtex file.
If there is no matching entry found, the old entry is transferred without modification.
The new file keeps the identical keys for the individual bibtex entries.

## Usage

Run `python dblp-bibtex.py ./my_bibtex_file.bib` to parse the content of the
file `my_bibtex_file.bib`.
Due to the request limit of the DBLP API, each entry will take roughly 5 seconds to avoid timeouts.

## Required Positional Arguments

| parameter | description                           |
|-----------|---------------------------------------|
| bibfile   | The path to the bibtex file to parse. |

## Optional Parameters

| parameter    | description                                                             |
|--------------|-------------------------------------------------------------------------|
| --outputpath | Path of the output location for the new bibtex file and json info file. |
| --outputfile | Name of the output file.                                                |

## License
MIT
