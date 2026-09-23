import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "src" / "claude_reference_trace.py"
sys.path.insert(0, str(PROJECT_ROOT / "src"))
SPEC = importlib.util.spec_from_file_location("claude_reference_trace", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ClaudeReferenceTraceTest(unittest.TestCase):
    def test_stream_records_ordered_tool_path_and_final_reference(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            subject = root / "subject"
            source = subject / "src"
            source.mkdir(parents=True)
            (source / "client.py").write_text("def connect():\n    pass\n")

            raw = root / "raw.jsonl"
            events = [
                {
                    "type": "assistant",
                    "message": {
                        "content": [{
                            "type": "tool_use",
                            "id": "tool-1",
                            "name": "Glob",
                            "input": {"pattern": "**/*.py", "path": "."},
                        }]
                    },
                },
                {
                    "type": "user",
                    "message": {
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": "tool-1",
                            "content": "src/client.py",
                        }]
                    },
                },
                {
                    "type": "assistant",
                    "message": {
                        "content": [{
                            "type": "tool_use",
                            "id": "tool-2",
                            "name": "Read",
                            "input": {
                                "file_path": str(source / "client.py"),
                                "offset": 1,
                                "limit": 20,
                            },
                        }]
                    },
                },
                {
                    "type": "user",
                    "message": {
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": "tool-2",
                            "content": "1: def connect():\n2:     pass",
                        }]
                    },
                },
                {
                    "type": "result",
                    "result": json.dumps({
                        "schema_version": 1,
                        "kind": "code-localization-draft",
                        "task": "locate connection",
                        "producer": {
                            "system": "claude_code",
                            "model": "test-model",
                        },
                        "summary": "connection implementation",
                        "files": [{
                            "path": "src/client.py",
                            "role": "primary",
                            "reason": "connect implementation",
                            "evidence": [{
                                "start_line": 1,
                                "end_line": 2,
                                "reason": "connect function",
                            }],
                        }],
                    }),
                    "duration_ms": 1234,
                    "num_turns": 2,
                    "usage": {"input_tokens": 10, "output_tokens": 20},
                },
            ]
            raw.write_text(
                "\n".join(json.dumps(event) for event in events) + "\n",
                encoding="utf-8",
            )

            steps, terminal, final_text = MODULE.parse_stream(raw, subject)
            raw_result = json.loads(MODULE.strip_json_fence(final_text))
            localization = MODULE.normalize_claude_draft(
                raw_result,
                subject,
                "test-model",
            )

            self.assertEqual(["Glob", "Read"], [step["tool"] for step in steps])
            self.assertEqual(
                "src/client.py",
                steps[1]["input"]["file_path"],
            )
            self.assertEqual(1234, terminal["duration_ms"])
            self.assertEqual(
                "1: def connect():\n2:     pass",
                localization["files"][0]["evidence"][0]["content"],
            )
            self.assertEqual(
                "src/client.py",
                localization["files"][0]["path"],
            )


if __name__ == "__main__":
    unittest.main()
