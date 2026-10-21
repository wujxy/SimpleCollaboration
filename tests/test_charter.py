from pathlib import Path
import tempfile
import unittest

from simplecollab.charter import build_charter, member_names
from simplecollab.runtime import RunConfig, build_specs


class CharterTests(unittest.TestCase):
    def test_charter_names_every_peer_without_roles(self):
        names = member_names("abcd1234", 3)
        text = build_charter(names)

        self.assertEqual(
            names,
            (
                "sc-abcd1234-member-1",
                "sc-abcd1234-member-2",
                "sc-abcd1234-member-3",
            ),
        )
        self.assertTrue(all(name in text for name in names))
        self.assertIn("SendMessage", text)
        self.assertIn("ListAgents", text)
        self.assertNotIn("reviewer", text.lower())
        self.assertNotIn("executor", text.lower())

    def test_names_reject_fewer_than_two_members(self):
        with self.assertRaisesRegex(ValueError, "at least two"):
            member_names("abcd1234", 1)

    def test_specs_use_streaming_input_and_one_shared_cwd(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = root / "state"
            state.mkdir()
            (state / "charter.md").write_text("charter", encoding="utf-8")
            (state / "settings.json").write_text("{}", encoding="utf-8")
            config = RunConfig(cwd=root, state_dir=state, claude="claude", members=2)

            specs = build_specs(config, member_names("abcd1234", 2))

        self.assertEqual(len(specs), 2)
        self.assertEqual({spec.cwd for spec in specs}, {root})
        for spec in specs:
            self.assertIn("--input-format", spec.argv)
            self.assertIn("stream-json", spec.argv)
            self.assertIn("--output-format", spec.argv)
            self.assertIn("--name", spec.argv)
            self.assertIn("--append-system-prompt-file", spec.argv)


if __name__ == "__main__":
    unittest.main()
