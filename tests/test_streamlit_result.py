"""Source rendering without a Streamlit server or network services."""
import importlib.util
from pathlib import Path
from types import ModuleType
import unittest
from unittest.mock import MagicMock, patch

from rag_assistant import api


class StreamlitResultTests(unittest.TestCase):
    def test_abstention_renders_separate_sources_with_evidence_limitation(self):
        streamlit = MagicMock()
        errors = ModuleType("streamlit.errors")
        errors.StreamlitSecretNotFoundError = type("StreamlitSecretNotFoundError", (Exception,), {})
        spec = importlib.util.spec_from_file_location(
            "result_ui", Path(__file__).resolve().parents[1] / "streamlit_app.py"
        )
        module = importlib.util.module_from_spec(spec)
        with patch.dict("sys.modules", {"streamlit": streamlit, "streamlit.errors": errors}):
            spec.loader.exec_module(module)
        source_url = "https://github.com/encode/starlette/issues/12"
        for category in (None, "bug"):
            with self.subTest(category=category):
                streamlit.reset_mock()
                citation = {"repository": "encode/starlette", "issue_number": 12,
                            "source_url": source_url, "chunk_type": "comment"}
                if category:
                    citation.update(predicted_category=category, classification_confidence="high")
                payload = {"answer": api.MODEL_ABSTENTION_ANSWER, "citations": [citation]}
                module._show_result(payload)
                self.assertEqual(streamlit.markdown.call_args_list[0].args, (api.MODEL_ABSTENTION_ANSWER,))
                self.assertIn(source_url, streamlit.markdown.call_args_list[1].args[0])
                streamlit.subheader.assert_called_with("Retrieved GitHub sources")
                self.assertIn("does not establish an answer", streamlit.caption.call_args.args[0])
                streamlit.metric.assert_not_called()
                streamlit.info.assert_not_called()
                displayed = streamlit.json.call_args.args[0]["citations"][0]
                self.assertNotIn("predicted_category", displayed)
                self.assertNotIn("classification_confidence", displayed)
                if category:
                    self.assertEqual(payload["citations"][0]["predicted_category"], category)
                    self.assertEqual(payload["citations"][0]["classification_confidence"], "high")
