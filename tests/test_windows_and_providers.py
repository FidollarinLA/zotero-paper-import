import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import doctor
import download_pdf as download
import import_to_zotero as native
import install_skill
import providers
import summarize_paper as summary


class WindowsAndProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / '研究 papers'
        self.root.mkdir()
        self.pdf = self.root / '论文 #1.pdf'
        self.pdf.write_bytes(b'%PDF-1.7\nfixture\n%%EOF')
        self.meta = {'doi': '10.1234/test', 'title': '研究论文',
                     'authors': [{'family': '张', 'given': '明'}]}

    def run_cli(self, script, *args, cwd=None):
        return subprocess.run([sys.executable, str(ROOT / 'scripts' / script), *map(str, args)],
                              cwd=cwd, capture_output=True, text=True, encoding='utf-8',
                              env={**os.environ, 'ORCAROUTER_API_KEY': '', 'ORCA_KEY': '',
                                   'PYTHONIOENCODING': 'ascii'})

    def test_windows_bom_manifest_relative_paths_and_unicode_output(self):
        manifest = self.root / 'batch.json'
        manifest.write_text(json.dumps([{'metadata': self.meta, 'pdf': self.pdf.name}],
                                       ensure_ascii=False), encoding='utf-8-sig')
        output, receipt = self.root / 'output' / 'papers.ris', self.root / 'receipt.json'
        process = self.run_cli('import_to_zotero.py', '--manifest', manifest, '--output', output,
                               '--receipt', receipt, '--zotero-db', self.root / 'absent.sqlite',
                               '--collection', '研究/待读', cwd=self.temp.name)
        self.assertEqual(process.returncode, 0, process.stderr)
        data = json.loads(process.stdout)
        self.assertEqual(data['results'][0]['pdf'], str(self.pdf.resolve()))
        self.assertEqual(data['results'][0]['title'], '研究论文')
        self.assertEqual(data['collection'], '研究/待读')
        self.assertFalse(data['library_checked'])
        self.assertEqual(json.loads(receipt.read_text(encoding='utf-8')), data)
        self.assertIn('AU  - 张, 明', output.read_text(encoding='utf-8'))

    def test_readonly_database_handle_is_closed_even_on_query_failure(self):
        db = self.root / 'empty.sqlite'
        conn = sqlite3.connect(db)
        conn.close()
        with self.assertRaises(sqlite3.Error):
            native.library_identifiers(db)
        # Windows rejects the rename when an SQLite handle has leaked.
        db.rename(self.root / 'moved.sqlite')

    def test_malformed_identifiers_and_authors_do_not_abort_batch(self):
        entries = [
            {'metadata': dict(self.meta, doi=123), 'pdf': str(self.pdf)},
            {'metadata': dict(self.meta, doi='10.1234/bad', authors=['invalid']), 'pdf': str(self.pdf)},
            {'metadata': self.meta, 'pdf': str(self.pdf)},
        ]
        result = native.prepare(entries, self.root / 'papers.ris', 'Imported')
        self.assertEqual([row['status'] for row in result['results']], ['failed', 'failed', 'prepared'])

    def test_failed_transfer_does_not_replace_existing_pdf(self):
        output = self.root / 'saved.pdf'
        output.write_bytes(b'%PDF-1.7\noriginal')
        def failed_download(url, target):
            target.write_bytes(b'%PDF-1.7\ntruncated')
            return 0
        with patch.object(sys, 'argv', ['download_pdf.py', '--doi', '10.1234/test', '--output', str(output)]), \
                patch.object(download, 'candidate_urls', return_value=[('test', 'https://example.org/paper.pdf', 'publishedVersion')]), \
                patch.object(download, 'curl_download', side_effect=failed_download), \
                patch('sys.stderr', new_callable=io.StringIO), self.assertRaises(SystemExit):
            download.main()
        self.assertEqual(output.read_bytes(), b'%PDF-1.7\noriginal')
        self.assertEqual(list(self.root.glob('*.tmp')), [])

    def test_successful_download_replaces_output_on_windows(self):
        output = self.root / 'saved.pdf'
        def good_download(url, target):
            target.write_bytes(b'%PDF-1.7\ncomplete\n%%EOF')
            return 200
        with patch.object(sys, 'argv', ['download_pdf.py', '--doi', '10.1234/test', '--output', str(output)]), \
                patch.object(download, 'candidate_urls', return_value=[('test', 'https://example.org/paper.pdf', 'publishedVersion')]), \
                patch.object(download, 'curl_download', side_effect=good_download), \
                patch('sys.stdout', new_callable=io.StringIO) as stdout:
            download.main()
        self.assertEqual(json.loads(stdout.getvalue())['status'], 'ok')
        self.assertTrue(output.is_file())
        self.assertEqual(list(self.root.glob('*.tmp')), [])

    def test_orca_key_alias_and_conflict(self):
        with patch.dict(os.environ, {'ORCAROUTER_API_KEY': '', 'ORCA_KEY': 'test-alias'}):
            self.assertEqual(providers.provider_key('orcarouter'), 'test-alias')
        with patch.dict(os.environ, {'ORCAROUTER_API_KEY': 'one', 'ORCA_KEY': 'two'}):
            with self.assertRaises(ValueError):
                providers.provider_key('orcarouter')

    def test_default_orcarouter_model_and_bom_text_preview(self):
        text = self.root / '摘要.txt'
        text.write_text('研究摘要。', encoding='utf-8-sig')
        result = self.run_cli('summarize_paper.py', '--provider', 'orcarouter', '--input', text,
                              '--output', self.root / 'summary.md')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data['model'], 'orcarouter/auto')
        self.assertEqual(data['input_characters'], len('研究摘要。'))
        self.assertFalse((self.root / 'summary.md').exists())

    def test_send_uses_alias_and_preserves_unicode_summary(self):
        text, out = self.root / '摘要.txt', self.root / 'summary.md'
        text.write_text('研究摘要。', encoding='utf-8-sig')
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps({'choices': [{'message': {'content': '方法和局限。'}}]}).encode()
        with patch.object(sys, 'argv', ['summarize_paper.py', '--provider', 'orcarouter', '--input', str(text), '--output', str(out), '--send']), \
                patch.dict(os.environ, {'ORCAROUTER_API_KEY': '', 'ORCA_KEY': 'test-alias'}), \
                patch.object(summary, 'urlopen', return_value=response) as network, \
                patch('sys.stdout', new_callable=io.StringIO):
            summary.main()
        request = network.call_args.args[0]
        self.assertEqual(request.get_header('Authorization'), 'Bearer test-alias')
        self.assertEqual(request.full_url, providers.PROVIDER_CONFIG['orcarouter']['base_url'] + '/chat/completions')
        self.assertEqual(json.loads(request.data)['messages'][1]['content'], '研究摘要。')
        self.assertIn('方法和局限。', out.read_text(encoding='utf-8'))

    def test_installer_supports_zip_package_and_preserves_local_config(self):
        destination = Path(self.temp.name) / '安装目录' / 'zotero-paper-import'
        report = install_skill.install(ROOT, destination)
        self.assertEqual(report['status'], 'installed')
        self.assertTrue((destination / 'integrations' / 'providers.json').is_file())
        text = self.root / 'abstract.txt'
        text.write_text('Abstract.', encoding='utf-8')
        process = subprocess.run([sys.executable, str(destination / 'scripts' / 'summarize_paper.py'),
                                  '--provider', 'orcarouter', '--input', str(text), '--output', str(self.root / 'summary.md')],
                                 capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(process.returncode, 0, process.stderr)
        config = destination / 'config.md'
        config.write_text('My local settings', encoding='utf-8')
        with self.assertRaises(ValueError):
            install_skill.install(ROOT, destination)
        install_skill.install(ROOT, destination, update=True)
        self.assertEqual(config.read_text(encoding='utf-8'), 'My local settings')

    def test_installer_rejects_unrelated_or_nested_destinations(self):
        with self.assertRaises(ValueError):
            install_skill.install(ROOT, ROOT / 'nested')
        destination = Path(self.temp.name) / 'unrelated'
        destination.mkdir()
        (destination / 'data.txt').write_text('Keep me', encoding='utf-8')
        with self.assertRaises(ValueError):
            install_skill.install(ROOT, destination, update=True)
        self.assertEqual((destination / 'data.txt').read_text(encoding='utf-8'), 'Keep me')

    def test_doctor_keeps_keys_out_of_output_and_requests_no_inference(self):
        with patch.dict(os.environ, {'ORCAROUTER_API_KEY': 'private-test-value', 'ORCA_KEY': ''}), \
                patch.object(doctor, 'urlopen') as network:
            data = doctor.check_environment(self.root / 'absent.sqlite')
        network.assert_not_called()
        self.assertTrue(data['orcarouter']['api_key_configured'])
        self.assertNotIn('private-test-value', json.dumps(data))

    def test_catalog_access_is_not_reported_as_billing_or_attribution(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{"data": [{"id": "example/model"}]}'
        with patch.object(doctor, 'urlopen', return_value=response) as network:
            result = doctor.check_catalog('test-key', 'https://api.orcarouter.ai/v1')
        self.assertEqual(network.call_args.args[0].full_url, 'https://api.orcarouter.ai/v1/models')
        self.assertEqual(result['model_count'], 1)
        self.assertFalse(result['inference_tested'])
        self.assertFalse(result['attribution_tested'])

    def test_doctor_does_not_report_unreadable_library_as_ready(self):
        db = self.root / 'invalid.sqlite'
        db.write_bytes(b'not an SQLite database')
        with patch.object(doctor.shutil, 'which', return_value='curl'), \
                patch.dict(os.environ, {'ORCAROUTER_API_KEY': '', 'ORCA_KEY': ''}):
            result = doctor.check_environment(db)
        self.assertEqual(result['status'], 'library_unreadable')
        self.assertFalse(result['library_checked'])

    def test_inference_check_uses_fixed_public_text_and_bounded_output(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{"model":"test/model","choices":[{"message":{"content":"ORCA_OK"}}],"usage":{"total_tokens":12}}'
        with patch.object(doctor, 'urlopen', return_value=response) as network:
            result = doctor.check_inference('private-test-value', 'https://api.orcarouter.ai/v1', 'test/model')
        request = network.call_args.args[0]
        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(request.full_url, 'https://api.orcarouter.ai/v1/chat/completions')
        payload = json.loads(request.data)
        self.assertEqual(payload['max_tokens'], 64)
        self.assertEqual(payload['messages'][0]['content'], 'Connectivity test. Reply with the single word ORCA_OK.')
        self.assertTrue(result['inference_tested'])
        self.assertTrue(result['expected_reply'])
        self.assertFalse(result['billing_tested'])
        self.assertFalse(result['attribution_tested'])
        self.assertNotIn('private-test-value', json.dumps(result))

    def test_catalog_flag_never_triggers_inference(self):
        with patch.object(sys, 'argv', ['doctor.py', '--check-provider', '--zotero-db', str(self.root / 'absent.sqlite')]), \
                patch.dict(os.environ, {'ORCAROUTER_API_KEY': '', 'ORCA_KEY': 'test-key'}), \
                patch.object(doctor.shutil, 'which', return_value='curl'), \
                patch.object(doctor, 'check_catalog', return_value={'live_access': 'catalog_accessible'}) as catalog, \
                patch.object(doctor, 'check_inference') as inference, \
                patch('sys.stdout', new_callable=io.StringIO):
            doctor.main()
        catalog.assert_called_once()
        inference.assert_not_called()

    def test_empty_inference_response_is_not_success(self):
        for data in ({'choices': []}, {'choices': [{'message': {'content': ''}}]}):
            response = MagicMock()
            response.__enter__.return_value = response
            response.read.return_value = json.dumps(data).encode()
            with patch.object(doctor, 'urlopen', return_value=response), self.assertRaises(ValueError):
                doctor.check_inference('test-key', 'https://api.orcarouter.ai/v1', 'test/model')


if __name__ == '__main__':
    unittest.main()
