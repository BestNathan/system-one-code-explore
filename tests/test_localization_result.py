import importlib.util
import pathlib
import sys
import tempfile
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "src" / "localization_result.py"
sys.path.insert(0, str(PROJECT_ROOT / "src"))
SPEC = importlib.util.spec_from_file_location("localization_result", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class LocalizationResultTest(unittest.TestCase):
    def test_system_one_result_groups_evidence_and_cost(self):
        engine = {
            "query": "find websocket",
            "model": "jev-latest",
            "reader_states": [{
                "files": [{
                    "path": "src/client.py",
                    "phase1_score": 0.88,
                    "last_activation_score": 0.72,
                    "activation_count": 2,
                    "read_count": 2,
                    "stop_reason": "model_stop",
                }],
            }],
            "snippets": [
                {
                    "path": "src/client.py",
                    "start_line": 1,
                    "end_line": 20,
                    "score": 0.91,
                    "action_probability": 0.84,
                    "content": "1: def connect():",
                },
                {
                    "path": "src/client.py",
                    "start_line": 21,
                    "end_line": 40,
                    "score": 0.76,
                    "action_probability": 0.80,
                    "content": "21: def reconnect():",
                },
            ],
            "metrics": {
                "elapsed_ms": 1234,
                "model_calls": 7,
                "input_tokens": 1000,
                "output_tokens": 200,
                "reads_executed": 2,
                "reader_scheduler_rounds": 3,
            },
        }

        result = MODULE.build_system_one_result(engine)

        self.assertEqual("code-localization-result", result["kind"])
        self.assertEqual("system_one", result["producer"]["system"])
        self.assertEqual(1, len(result["files"]))
        self.assertEqual(
            0.91,
            result["files"][0]["confidence"]["score"],
        )
        self.assertEqual(2, len(result["files"][0]["evidence"]))
        self.assertEqual(
            "noul_relevance",
            result["files"][0]["evidence"][0]["confidence"]["type"],
        )
        self.assertEqual(1234, result["cost"]["elapsed_ms"])
        self.assertEqual(7, result["cost"]["model_calls"])
        self.assertEqual(1000, result["cost"]["tokens"]["input"])
        self.assertEqual(
            2,
            result["cost"]["stages"][0]["operations"]["reads_executed"],
        )

    def test_range_runtime_builds_canonical_result_with_subject(self):
        engine = {
            "query": "find websocket",
            "model": "jev-latest",
            "subject": {
                "repository": "BestNathan/nession",
                "revision": "abc123",
            },
            "result_files": [{
                "path": "src/ws.py",
                "score": 0.87,
                "phase1_score": 0.91,
                "termination": "model_stop",
                "read_count": 3,
                "coverage": [[1, 140], [701, 840]],
                "evidence": [{
                    "start_line": 701,
                    "end_line": 840,
                    "score": 0.87,
                    "content": "701: websocket",
                    "navigation": "jump",
                    "selected_action_score": 0.74,
                }],
            }],
            "metrics": {
                "elapsed_ms": 900,
                "model_calls": 5,
                "input_tokens": 500,
                "output_tokens": 50,
                "reads_executed": 3,
                "file_runtimes": 1,
            },
        }

        result = MODULE.build_system_one_range_result(engine)

        self.assertEqual(
            {
                "repository": "BestNathan/nession",
                "revision": "abc123",
            },
            result["subject"],
        )
        self.assertEqual(
            "independent_file_range_runtime",
            result["producer"]["algorithm"],
        )
        self.assertEqual("src/ws.py", result["files"][0]["path"])
        self.assertEqual(
            "model_stop",
            result["files"][0]["provenance"]["termination"],
        )
        self.assertEqual(
            0.87,
            result["files"][0]["evidence"][0]["confidence"]["score"],
        )

    def test_claude_localization_draft_has_no_confidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            src = root / "src"
            src.mkdir()
            (src / "client.py").write_text(
                "line1\nline2\nline3\n",
                encoding="utf-8",
            )
            raw = {
                "schema_version": 1,
                "kind": "code-localization-draft",
                "task": "find client",
                "producer": {
                    "system": "claude_code",
                    "model": "ds",
                },
                "summary": "client implementation",
                "files": [{
                    "path": "src/client.py",
                    "role": "primary",
                    "reason": "main implementation",
                    "evidence": [{
                        "start_line": 2,
                        "end_line": 3,
                        "reason": "relevant logic",
                    }],
                }],
            }

            draft = MODULE.normalize_claude_draft(raw, root, "ds")

            self.assertNotIn("confidence", draft)
            self.assertNotIn("confidence", draft["files"][0])
            self.assertNotIn(
                "confidence",
                draft["files"][0]["evidence"][0],
            )
            self.assertEqual(
                "2: line2\n3: line3",
                draft["files"][0]["evidence"][0]["content"],
            )

    def test_claude_draft_rejects_confidence_from_localization_session(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            src = root / "src"
            src.mkdir()
            (src / "client.py").write_text("line1\n", encoding="utf-8")
            raw = {
                "schema_version": 1,
                "kind": "code-localization-draft",
                "task": "find client",
                "confidence": 0.9,
                "producer": {"system": "claude_code"},
                "summary": "",
                "files": [],
            }

            with self.assertRaises(ValueError):
                MODULE.normalize_claude_draft(raw, root, "ds")

    def test_fresh_confidence_session_cannot_change_localization(self):
        draft = {
            "schema_version": 1,
            "kind": "code-localization-draft",
            "task": "find client",
            "producer": {
                "system": "claude_code",
                "model": "ds",
            },
            "summary": "client implementation",
            "files": [{
                "path": "src/client.py",
                "role": "primary",
                "reason": "main implementation",
                "evidence": [{
                    "id": "src/client.py#evidence-1",
                    "start_line": 2,
                    "end_line": 3,
                    "reason": "relevant logic",
                    "content": "2: line2\n3: line3",
                }],
            }],
        }
        assessment = {
            "schema_version": 1,
            "kind": "code-localization-confidence-assessment",
            "task": "find client",
            "overall": {
                "score": 0.91,
                "reason": "strong grounded evidence",
            },
            "files": [{
                "path": "src/client.py",
                "score": 0.88,
                "reason": "direct implementation",
                "evidence": [{
                    "start_line": 2,
                    "end_line": 3,
                    "score": 0.81,
                    "reason": "directly supports the task",
                }],
            }],
        }
        localization_stage = {
            "name": "localization",
            "elapsed_ms": 1000,
            "api_elapsed_ms": 900,
            "model_calls": None,
            "turns": 10,
            "tool_calls": 6,
            "tokens": {
                "input": 100,
                "output": 20,
                "cache_read_input": 500,
                "cache_creation_input": 0,
                "thinking": 0,
            },
            "provider_cost_usd": 0.4,
        }
        confidence_stage = {
            "name": "confidence_assessment",
            "elapsed_ms": 200,
            "api_elapsed_ms": 180,
            "model_calls": None,
            "turns": 1,
            "tool_calls": 0,
            "tokens": {
                "input": 50,
                "output": 10,
                "cache_read_input": 0,
                "cache_creation_input": 0,
                "thinking": 0,
            },
            "provider_cost_usd": 0.1,
        }

        result = MODULE.build_claude_result(
            draft,
            assessment,
            "ds",
            localization_stage,
            confidence_stage,
        )

        self.assertEqual(
            "src/client.py",
            result["files"][0]["path"],
        )
        self.assertEqual(
            (2, 3),
            (
                result["files"][0]["evidence"][0]["start_line"],
                result["files"][0]["evidence"][0]["end_line"],
            ),
        )
        self.assertEqual(
            0.88,
            result["files"][0]["confidence"]["score"],
        )
        self.assertEqual(1200, result["cost"]["elapsed_ms"])
        self.assertEqual(150, result["cost"]["tokens"]["input"])
        self.assertEqual(0.5, result["cost"]["provider_cost_usd"])
        self.assertEqual(2, len(result["cost"]["stages"]))

        changed = {
            **assessment,
            "files": [{
                **assessment["files"][0],
                "path": "src/other.py",
            }],
        }
        with self.assertRaises(ValueError):
            MODULE.build_claude_result(
                draft,
                changed,
                "ds",
                localization_stage,
                confidence_stage,
            )


if __name__ == "__main__":
    unittest.main()
