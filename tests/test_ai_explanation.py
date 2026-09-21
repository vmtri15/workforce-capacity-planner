import json
import os
import unittest
from unittest.mock import patch

from scripts.serve_dashboard import build_explanation_prompt, request_ai_explanation


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps({
            'model': 'test-model',
            'output': [{'content': [{'type': 'output_text', 'text': 'Grounded explanation.'}]}],
        }).encode()


class AiExplanationTest(unittest.TestCase):
    def test_prompt_preserves_evidence_boundaries(self):
        prompt = build_explanation_prompt({
            'audience': 'executive',
            'decision': {'answer': 'Residual modeled risk remains.'},
        })
        self.assertIn('Use only the supplied facts', prompt)
        self.assertIn('Do not invent savings', prompt)
        self.assertIn('Residual modeled risk remains', prompt)

    def test_invalid_audience_is_rejected(self):
        with self.assertRaises(ValueError):
            build_explanation_prompt({'audience': 'investor', 'decision': {}})

    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key', 'OPENAI_MODEL': 'test-model'})
    @patch('scripts.serve_dashboard.urllib.request.urlopen', return_value=FakeResponse())
    def test_response_text_is_extracted(self, mocked_urlopen):
        result = request_ai_explanation({'audience': 'operations manager', 'decision': {}})
        self.assertEqual(result['explanation'], 'Grounded explanation.')
        request = mocked_urlopen.call_args.args[0]
        self.assertNotIn(b'test-key', request.data)
        self.assertEqual(request.get_header('Authorization'), 'Bearer test-key')


if __name__ == '__main__':
    unittest.main()
