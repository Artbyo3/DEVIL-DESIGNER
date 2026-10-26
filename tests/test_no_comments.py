import unittest
from pathlib import Path
from tools.check_comments import check_repository, check_source


class NoCommentsTests(unittest.TestCase):
    def test_repository_has_no_comments_or_docstrings(self):
        self.assertGreater(check_repository(Path(__file__).resolve().parents[1]), 0)

    def test_comments_are_rejected(self):
        for source in ('# note\n', 'value = 1 # note\n'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                check_source(source)

    def test_docstrings_and_standalone_strings_are_rejected(self):
        for source in (
            '\"\"\"module note\"\"\"\n',
            "'''module note'''\n",
            'class Example:\n    "class note"\n    pass\n',
            'def example():\n    "function note"\n    return 1\n',
            'value = 1\n"standalone note"\n',
            'f"standalone {1}"\n',
        ):
            with self.subTest(source=source), self.assertRaises(ValueError):
                check_source(source)

    def test_functional_strings_are_preserved(self):
        check_source('label = "# visible label"\nscript = """print(1)"""\ndef label_text():\n    return "label"\nprint(label)\n')

    def test_invalid_source_is_rejected(self):
        with self.assertRaises(SyntaxError):
            check_source('def broken(:\n')
