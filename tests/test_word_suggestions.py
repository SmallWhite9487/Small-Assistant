import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modules.ai_service import AIService
from modules.storage import VocabularyStore
from services import WordService


class WordSuggestionsTests(unittest.TestCase):
    def test_completion_checks_and_normalizes_vocabulary_for_both_providers(self):
        words = [
            {"id": "verb", "word": "食べました", "reading": "", "meaning": "", "part_of_speech": ""},
            {"id": "adjective", "word": "高かった", "reading": "たかかった", "meaning": "was expensive", "part_of_speech": "adj"},
            {"id": "na", "word": "静かな", "reading": "しずかな", "meaning": "quiet", "part_of_speech": "adj"},
            {"id": "name", "word": "山田", "reading": "やまだ", "meaning": "Yamada", "part_of_speech": "n"},
            {"id": "attributive", "word": "大きな", "reading": "おおきな", "meaning": "big", "part_of_speech": "adj-pre"},
        ]
        expected = [
            {"id": "verb", "word": "食べる", "reading": "たべる", "meaning": "to eat", "part_of_speech": "v", "reason": "Restored dictionary form and completed fields."},
            {"id": "adjective", "word": "高い", "reading": "たかい", "meaning": "expensive", "part_of_speech": "adj", "reason": "Restored dictionary form."},
            {"id": "na", "word": "静か", "reading": "しずか", "meaning": "quiet", "part_of_speech": "adj", "reason": "Removed attributive na."},
            {**words[3], "reason": "Looks correct."},
            {**words[4], "reason": "Independent attributive; unchanged."},
        ]
        for provider in ("local", "online"):
            with self.subTest(provider=provider), patch.object(
                AIService, "generate_response", return_value=json.dumps(expected[::-1])
            ) as generate:
                result = AIService.word_suggestions(words, provider, "Traditional Chinese")
            self.assertEqual(result, expected)
            prompt, instruction, selected_provider = generate.call_args.args
            self.assertEqual(json.loads(prompt), words)
            self.assertEqual(selected_provider, provider)
            for requirement in (
                "Correct identifiable spelling errors",
                "Fill missing reading",
                "Normalize conjugated verbs",
                "i-adjectives",
                "na-adjectives",
                "Update reading, meaning, and part_of_speech",
                "大きな",
                "小さな",
                "ambiguous",
                "Traditional Chinese",
            ):
                self.assertIn(requirement, instruction)
            self.assertTrue(generate.call_args.kwargs["json_mode"])

    def test_applying_dictionary_entry_preserves_record_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "words.csv"
            original = {
                "id": "verb", "word": "食べました", "reading": "たべました",
                "meaning": "ate", "part_of_speech": "v", "notes": "keep notes",
                "check_ai": "False", "added_on": "2026-11-12",
            }
            VocabularyStore(path).save([original])
            service = WordService(path)
            change = {
                "id": "verb", "word": "食べる", "reading": "たべる",
                "meaning": "to eat", "part_of_speech": "v",
            }
            applied = service.apply_corrections([change])
            stored = VocabularyStore(path).load()
            self.assertEqual(applied, stored)
            self.assertEqual(stored, [{**original, **change}])


if __name__ == "__main__":
    unittest.main()
