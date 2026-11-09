import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from devil_designer import localization
from devil_designer.localization import catalog, locale_files, translate

LOCALES = Path(__file__).resolve().parents[1] / 'devil_designer' / 'locales'


class LocalizationTests(unittest.TestCase):
    def test_japanese_and_spanish_translate_and_fall_back_per_string(self):
        self.assertEqual(translate('Simulate', 'ja_JP'), 'シミュレート')
        self.assertEqual(translate('Simulate', 'es'), 'Simular')
        self.assertEqual(translate('A label nobody translated', 'ja_JP'), 'A label nobody translated')

    def test_english_and_missing_languages_fall_back_to_english(self):
        self.assertEqual(translate('Simulate', 'en_US'), 'Simulate')
        self.assertEqual(translate('Simulate', 'xx_YY'), 'Simulate')
        self.assertEqual(locale_files('en_GB'), ())
        self.assertEqual(locale_files('pt_BR'), ('pt_BR', 'pt'))

    def test_new_language_file_needs_no_code_change(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, 'zz.json').write_text(json.dumps({'Simulate': 'Zimulate'}), encoding='utf-8')
            with patch.object(localization, 'LOCALE_FOLDER', Path(folder)):
                catalog.cache_clear()
                try:
                    self.assertEqual(translate('Simulate', 'zz'), 'Zimulate')
                    self.assertEqual(translate('Sew', 'zz'), 'Sew')
                finally:
                    catalog.cache_clear()

    def test_shipped_language_files_are_valid_and_complete_strings(self):
        for path in LOCALES.glob('*.json'):
            with self.subTest(language=path.stem):
                data = json.loads(path.read_text(encoding='utf-8'))
                self.assertTrue(data)
                self.assertTrue(all(isinstance(key, str) and isinstance(value, str) and value.strip() for key, value in data.items()))


if __name__ == '__main__':
    unittest.main()
