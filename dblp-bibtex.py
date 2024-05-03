import argparse
import html
import json
import os
import re
import time
from pathlib import Path

import Levenshtein
import requests
# need to import latexcodec to .decode('latex')
from pybtex.database import BibliographyData
from pybtex.database import parse_string
from pybtex.database.input import bibtex
from tqdm import tqdm
from unidecode import unidecode

parser = argparse.ArgumentParser(
    description='Match the content of a bibtex file with the DBLP database, '
                'updating entries with the found information.')
parser.add_argument('bibfile',
                    help='The path to the bibtex file to parse.')
parser.add_argument('--outputpath', dest='outputpath', default='./',
                    help='Path of the output location for the new bibtex file and json info file.')
parser.add_argument('--outputfile', dest='outputfile', default='new_bibtex',
                    help='Name of the output file.')

args = parser.parse_args()

request_timer_sec = 5

BASE_URL = 'https://dblp.org'
SEARCH_URL = '/search/publ/api'
RECORD_URL = '/rec'

bib_file = bibtex.Parser(encoding='utf-8').parse_file(args.bibfile)

not_found = []
not_matched = []
request_failed = []
found_entries = []
match_reasons = {
    'doi': [],
    'levenshtein': {
        '>=0.98': [],
        'other': []
    }
}

for citation_key, entry in tqdm(bib_file.entries.items(), desc='Matching Entries to DBLP'):
    title = entry.fields['title']
    authors = entry.persons['author']
    doi = entry.fields['doi'].replace('https://doi.org/', '') if 'doi' in entry.fields else None

    time.sleep(request_timer_sec)
    response = requests.get(f'{BASE_URL + SEARCH_URL}?q={title}&format=json')

    if response.ok:
        content = json.loads(response.text)

        hits = content['result']['hits']
        if int(hits['@total']) > 0:
            best_match = hits['hit'][0]
            match_doi = best_match['info']['doi'].replace('https://doi.org/', '') if 'doi' in \
                                                                                     best_match[
                                                                                         'info'] else None

            if doi is not None and match_doi is not None:
                if doi.lower() == match_doi.lower():
                    found_entries.append((citation_key, best_match))
                    match_reasons['doi'].append(citation_key)
                    continue

            levenshtein_ratio_title = Levenshtein.ratio(title.lower(),
                                                        html.unescape(
                                                            best_match['info']['title'].lower()))
            if isinstance(best_match['info']['authors']['author'], dict):
                author_match = best_match['info']['authors']['author']['text']
            elif len(best_match['info']['authors']['author']) > 0:
                author_match = best_match['info']['authors']['author'][0]['text']
            else:
                author_match = ''

            author = (' '.join(authors[0].first_names) + ' ' + ' '.join(
                authors[0].last_names)).strip()
            author_match = re.sub(r'\d', '', author_match).strip()
            author = author.split(' ')[0] + ' ' + author.split(' ')[-1]
            author_match = author_match.split(' ')[0] + ' ' + author_match.split(' ')[-1]

            author = unidecode(unidecode(author
                                         .replace('{', '')
                                         .replace('}', ''))
                               .encode('utf-8').decode('latex'))
            author_match = unidecode(author_match)

            levenshtein_ratio_first_author = Levenshtein.ratio(author.lower(),
                                                               author_match.lower())

            if levenshtein_ratio_title > 0.9 and levenshtein_ratio_first_author > 0.9:
                found_entries.append((citation_key, best_match))
                levenshtein_info = {
                    'title': title,
                    'title_match': best_match['info']['title'],
                    'title_levenshtein': levenshtein_ratio_title,
                    'author': author,
                    'author_match': author_match,
                    'author_levenshtein': levenshtein_ratio_first_author
                }

                if (levenshtein_ratio_title + levenshtein_ratio_first_author) / 2 >= 0.98:
                    match_reasons['levenshtein']['>=0.98'].append(
                        (citation_key, levenshtein_info))
                else:
                    match_reasons['levenshtein']['other'].append(
                        (citation_key, levenshtein_info))

            else:
                not_matched.append((citation_key, title, {
                    'title': title,
                    'title_match': best_match['info']['title'],
                    'title_levenshtein': levenshtein_ratio_title,
                    'author': author,
                    'author_match': author_match,
                    'author_levenshtein': levenshtein_ratio_first_author,
                    'doi': doi,
                    'match_doi': match_doi,
                }))
        else:
            not_found.append((citation_key, title))
    else:
        request_failed.append((citation_key, title, response.status_code))

parsed_entries = []
key_map = {}

bibtex_bibliography = BibliographyData()
bibtex_bibliography_not_matched = BibliographyData()

for entry in tqdm(found_entries, desc='Retrieving matched DBLP Bibtex Files'):
    time.sleep(request_timer_sec)
    r = requests.get(f'{BASE_URL + RECORD_URL}/{entry[1]["info"]["key"]}.bib?param=1')
    if r.ok:
        bibtex_str = r.text.replace('\_', '_')
        bib_object = parse_string(bibtex_str, bib_format='bibtex')
        bib_object.key = entry[0]
        bibtex_bibliography.entries[entry[0]] = list(bib_object.entries.values())[0]
    else:
        request_failed.append((entry[0], entry[1]['info']['text'], r.status_code))

for entry in request_failed + not_found + not_matched:
    key = entry[0]
    original_entry = bib_file.entries[key]
    bibtex_bibliography_not_matched.entries[key] = original_entry

biblio_str = bibtex_bibliography.to_string('bibtex')
biblio_str = biblio_str.replace('\_', '_')
biblio_str = biblio_str.replace('\\_', '_')

biblio_str_not_matched = bibtex_bibliography_not_matched.to_string('bibtex')
biblio_str_not_matched = biblio_str_not_matched.replace('\_', '_')
biblio_str_not_matched = biblio_str_not_matched.replace('\\_', '_')

bib_export_path = os.path.join(Path(args.outputpath), args.outputfile + '.bib')
json_export_path = os.path.join(Path(args.outputpath), args.outputfile + '_info.json')

with open(bib_export_path, 'w', encoding='utf8') as f:
    f.write(biblio_str)

with open(bib_export_path, 'a', encoding='utf8') as f:
    f.write('\n\n@ Following: Old entries that were not updated with DBLP information\n\n')

with open(bib_export_path, 'a', encoding='utf8') as f:
    f.write(biblio_str_not_matched)

parsing_info = {
    'entries_not_found': not_found,
    'entries_not_matched': not_matched,
    'requests_failed': request_failed,
    'parsed_entries': [x[0] for x in found_entries],
    'match_reasons': match_reasons
}

with open(json_export_path, 'w') as f:
    json.dump(parsing_info, f, indent=2)
