import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from contextlib import closing

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import resolve_paper as resolve
import download_pdf as download
import import_to_zotero as native
import summarize_paper as summary

FEED = '''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:x="http://arxiv.org/schemas/atom"><entry>
<id>http://arxiv.org/abs/2602.03070v5</id><title>Power Systems\n Modeling</title>
<published>2026-02-03T00:00:00Z</published><summary>A study.</summary>
<author><name>Jane Doe</name></author><x:doi>10.1234/published</x:doi></entry></feed>'''


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pdf = self.root / '论文.pdf'
        self.pdf.write_bytes(b'%PDF-1.7\nfixture\n%%EOF')
        self.meta = resolve.parse_arxiv_feed(FEED, '2602.03070v5')

    def test_arxiv_forms_and_versions(self):
        for value in ['https://arxiv.org/abs/2602.03070v5', 'https://arxiv.org/pdf/2602.03070v5.pdf', 'arXiv:2602.03070v5', '10.48550/arXiv.2602.03070v5']:
            self.assertEqual(resolve.arxiv_id(value), '2602.03070v5')
        self.assertEqual(resolve.arxiv_id('https://arxiv.org/abs/hep-th/9901001v2'), 'hep-th/9901001v2')
        self.assertIsNone(resolve.arxiv_id('https://example.com/2602.03070'))
        self.assertEqual(self.meta['doi'], '10.48550/arXiv.2602.03070')
        self.assertEqual(self.meta['arxiv_id'], '2602.03070v5')
        with self.assertRaises(ValueError): resolve.parse_arxiv_feed(FEED, '2601.05632')
        with self.assertRaises(ValueError): resolve.parse_arxiv_feed(FEED, '2602.03070v4')

    def test_arxiv_doi_bypasses_crossref(self):
        with patch.object(resolve, 'resolve_by_arxiv', return_value=self.meta) as fetch:
            self.assertEqual(resolve.resolve_by_doi('10.48550/arXiv.2602.03070'), self.meta)
            fetch.assert_called_once()

    def test_nature_slug_and_preprint_versions(self):
        self.assertEqual(download.doi_to_nature_slug('10.1038/s41586-026-10644-y'), 's41586-026-10644-y')
        self.assertEqual(download.candidate_urls('10.48550/arXiv.2602.03070v5', ''), [('arxiv','https://arxiv.org/pdf/2602.03070v5','preprint')])
        fake = MagicMock(returncode=0, stdout=json.dumps({'oa_locations': [
            {'url_for_pdf': 'https://repo/preprint.pdf', 'version': 'submittedVersion'},
            {'url_for_pdf': 'https://publisher/published.pdf', 'version': 'publishedVersion'}]}))
        with patch.object(download.subprocess, 'run', return_value=fake):
            self.assertEqual(download.unpaywall_pdf('10.1/test', 'test@example.org')[1], 'publishedVersion')

    def test_native_preparation_preserves_metadata_and_attachment(self):
        report = native.prepare([{'metadata': self.meta, 'pdf': str(self.pdf)}], self.root/'papers.ris', 'Parent/Child')
        self.assertEqual(report['results'][0]['status'], 'prepared')
        text = (self.root/'papers.ris').read_text(encoding='utf-8')
        self.assertIn('TY  - RPRT', text)
        self.assertIn('AU  - Doe, Jane', text)
        self.assertIn('N1  - arXiv: 2602.03070v5', text)
        self.assertIn('N1  - Published DOI: 10.1234/published', text)
        self.assertIn('L1  - ' + str(self.pdf.resolve()), text)
        self.assertEqual(report['collection'], 'Parent/Child')

    def test_batch_duplicates_and_partial_failure(self):
        good = {'metadata': self.meta, 'pdf': str(self.pdf)}
        other = dict(self.meta, doi='10.48550/arXiv.2601.05632')
        bad = {'metadata': other, 'pdf': str(self.root/'missing.pdf')}
        report = native.prepare([good, good, bad], self.root/'papers.ris', 'Imported')
        self.assertEqual([x['status'] for x in report['results']], ['prepared','skipped','failed'])

    def test_invalid_metadata_isolated_from_valid_records(self):
        result = native.prepare([{'metadata': 'bad', 'pdf': str(self.pdf)}, {'metadata': self.meta, 'pdf': str(self.pdf)}], self.root/'papers.ris', 'Imported')
        self.assertEqual([r['status'] for r in result['results']], ['failed', 'prepared'])

    def test_html_rejected_and_existing_output_preserved(self):
        self.pdf.write_text('<html>paywall</html>')
        out = self.root/'papers.ris'
        out.write_text('previous batch')
        result = native.prepare([{'metadata': self.meta, 'pdf': str(self.pdf)}], out, 'Imported')
        self.assertIsNone(result['ris'])
        self.assertEqual(result['results'][0]['status'], 'failed')
        self.assertEqual(out.read_text(), 'previous batch')

    def test_library_readonly_duplicate_normalization_and_deleted_items(self):
        db = self.root/'zotero.sqlite'
        with closing(sqlite3.connect(db)) as conn:
            conn.executescript('''CREATE TABLE items(itemID INTEGER); CREATE TABLE deletedItems(itemID INTEGER);
                CREATE TABLE fields(fieldID INTEGER, fieldName TEXT);
                CREATE TABLE itemData(itemID INTEGER, fieldID INTEGER, valueID INTEGER);
                CREATE TABLE itemDataValues(valueID INTEGER, value TEXT);
                INSERT INTO items VALUES (1),(2); INSERT INTO deletedItems VALUES(2);
                INSERT INTO fields VALUES(1,'DOI');
                INSERT INTO itemData VALUES(1,1,1),(2,1,2);
                INSERT INTO itemDataValues VALUES(1,'https://doi.org/10.48550/arXiv.2602.03070v1'),(2,'10.1/deleted');''')
            conn.commit()
        before = db.read_bytes()
        ids = native.library_identifiers(db)
        self.assertIn('arxiv:2602.03070', ids)
        self.assertNotIn('10.1/deleted', ids)
        self.assertEqual(before, db.read_bytes())
        result = native.prepare([{'metadata':self.meta,'pdf':str(self.pdf)}],self.root/'papers.ris','Imported', ids)
        self.assertEqual(result['results'][0]['status'], 'skipped')

    def test_orcarouter_request_shape_and_output(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps({'choices':[{'message':{'content':'Summary'}}], 'usage':{'total_tokens':12}}).encode()
        with patch.object(summary, 'urlopen', return_value=response) as network:
            result = summary.request_summary('An abstract.', 'orcarouter/free', 'https://api.orcarouter.ai/v1', 'test-key')
        request = network.call_args.args[0]
        self.assertEqual(request.full_url, 'https://api.orcarouter.ai/v1/chat/completions')
        self.assertEqual(request.get_header('Authorization'), 'Bearer test-key')
        payload = json.loads(request.data)
        self.assertEqual(payload['model'], 'orcarouter/free')
        self.assertEqual(payload['messages'][1]['content'], 'An abstract.')
        self.assertEqual(result['summary'], 'Summary')

    def test_optional_llm_does_not_send_without_flag(self):
        text = self.root/'abstract.txt'
        text.write_text('An abstract.')
        process = subprocess.run([sys.executable, str(Path(summary.__file__)), '--provider','orcarouter','--model','orcarouter/free','--input',str(text),'--output',str(self.root/'summary.md')],capture_output=True,text=True,encoding='utf-8',env={**os.environ,'ORCAROUTER_API_KEY':'','ORCA_KEY':''})
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)['status'], 'preview')
        self.assertFalse((self.root/'summary.md').exists())


if __name__ == '__main__': unittest.main()
