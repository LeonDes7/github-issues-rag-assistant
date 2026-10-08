import unittest
from rag_assistant import api
from rag_assistant.redaction import redact_sensitive_text, safe_excerpt, safe_display_payload, UNSAFE_SETTINGS_ANSWER


class RedactionTests(unittest.TestCase):
    def test_literals_are_redacted_without_modifying_reference(self):
        text = 'JWT_SECRET = "synthetic-test-secret"\n{"password": "synthetic-password"}\nBearer synthetic-token\n[1]'
        safe = redact_sensitive_text(text)
        for literal in ("synthetic-test-secret", "synthetic-password", "synthetic-token"):
            self.assertNotIn(literal, safe)
        self.assertIn("[1]", safe)

    def test_setting_names_and_masked_examples_are_not_credentials(self):
        text = 'JWT_SECRET = config("JWT_SECRET", cast=Secret)\nSecret(\'**********\')'
        self.assertEqual(redact_sensitive_text(text), text)

    def test_tokens_keys_and_database_url_passwords_are_redacted(self):
        text = 'sk-' + 'x' * 24 + ' AKIA' + 'X' * 16 + ' postgresql://user:synthetic-password@host/db'
        safe = redact_sensitive_text(text)
        self.assertNotIn('synthetic-password', safe)
        self.assertNotIn('AKIA', safe)
        self.assertNotIn('sk-', safe)

    def test_unsafe_settings_dump_is_withheld_even_with_warning(self):
        answer = 'Use:\n```python\ndctconfig = dict(settings.config)\nreturn dctconfig\n```\nHowever this shows secrets [1].'
        self.assertEqual(api.finalize_generated_answer(answer, [answer]), UNSAFE_SETTINGS_ANSWER)
        self.assertNotIn('dict(settings.config)', safe_excerpt(answer))

    def test_displayed_excerpts_preserve_links_and_metadata(self):
        payload = {'citations': [{'source_url': 'https://github.com/encode/starlette/issues/408',
                    'issue_number': 408, 'similarity_score': .75,
                    'excerpt': 'API_KEY = "synthetic-example-key"'}]}
        safe = safe_display_payload(payload)
        for key in ('source_url', 'issue_number', 'similarity_score'):
            self.assertEqual(safe['citations'][0][key], payload['citations'][0][key])
        self.assertNotIn('synthetic-example-key', safe['citations'][0]['excerpt'])
        self.assertIn('synthetic-example-key', payload['citations'][0]['excerpt'])

    def test_model_facing_excerpts_redact_before_budgeting_and_keep_source(self):
        source = {'repository': 'encode/starlette', 'issue_number': 408,
                  'issue_url': 'https://github.com/encode/starlette/issues/408',
                  'source_url': 'https://github.com/encode/starlette/issues/408',
                  'chunk_type': 'comment', 'similarity_score': .75,
                  'chunk_text': 'JWT_SECRET = "synthetic-secret-for-test"'}
        messages, sent = api.prepare_generation_messages('gpt-4o-mini', 'question', [source], 12000)
        self.assertNotIn('synthetic-secret-for-test', messages[0]['content'])
        self.assertIn(source['source_url'], messages[0]['content'])
        self.assertNotIn('synthetic-secret-for-test', sent[0])
        self.assertIn('synthetic-secret-for-test', source['chunk_text'])

    def test_redaction_preserves_secret_constructor_and_handles_yaml(self):
        text = 'JWT_SECRET = Secret("synthetic-value")\nPASSWORD: synthetic-password'
        safe = redact_sensitive_text(text)
        self.assertIn('Secret("[REDACTED]")', safe)
        self.assertNotIn('synthetic-value', safe)
        self.assertNotIn('synthetic-password', safe)

    def test_ui_withholds_unsafe_answer_from_older_api(self):
        payload = {'answer': 'Use dict(settings.config) to expose settings [1].',
                   'citations': [{'issue_number': 408}]}
        self.assertEqual(safe_display_payload(payload)['answer'], UNSAFE_SETTINGS_ANSWER)
        self.assertEqual(safe_display_payload(payload)['citations'], payload['citations'])
