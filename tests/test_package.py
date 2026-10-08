from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CONFIG_SCRIPT = ROOT / "skills/conduct/scripts/config.py"
BOOTSTRAP = ROOT / "skills/herdr-adapter/scripts/bootstrap.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


config = load_module("hc_config", CONFIG_SCRIPT)
installer = load_module("hc_install", ROOT / "scripts/install_codex.py")
bootstrap = load_module("hc_bootstrap", BOOTSTRAP)


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hc-config-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.user = self.write("user.json", {})
        self.base = config.read_object(config.DEFAULTS)

    def write(self, name, obj):
        path = self.root / name
        path.write_text(json.dumps(obj), encoding="utf-8")
        return path

    def test_defaults(self):
        value, sources = config.load_config(self.root, self.user)
        self.assertEqual(value["roles"]["worker"]["model"], "gpt-6-luna")
        self.assertEqual(value["roles"]["researcher"]["effort"], "max")
        self.assertEqual(value["roles"]["main"]["model"], "inherit")
        self.assertEqual(len(sources), 2)
        self.assertNotIn("review", value)

    def test_precedence_and_partial_merge(self):
        self.write("user.json", {"roles": {"worker": {"model": "user-model"}}})
        self.write(".hybrid-conductor.json", {"roles": {"worker": {"model": "project-model"}}})
        first = self.write("first.json", {"roles": {"worker": {"model": "first-model"}}})
        last = self.write("last.json", {"roles": {"worker": {"model": "run-model"}}})
        value, sources = config.load_config(self.root, self.user, [first, last])
        self.assertEqual(value["roles"]["worker"]["model"], "run-model")
        self.assertEqual(value["roles"]["worker"]["effort"], "max")
        self.assertEqual(len(sources), 5)

    def test_optional_files_can_be_absent(self):
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.root / "xdg")}):
            value, sources = config.load_config(self.root)
        self.assertEqual(value, self.base)
        self.assertEqual(len(sources), 1)

    def test_explicit_missing_file_is_error(self):
        with self.assertRaises(config.ConfigError):
            config.load_config(self.root, self.root / "missing.json")
        with self.assertRaises(config.ConfigError):
            config.load_config(self.root, self.user, [self.root / "missing.json"])

    def test_missing_project_is_error(self):
        with self.assertRaises(config.ConfigError):
            config.load_config(self.root / "missing", self.user)

    def test_arbitrary_model_and_cross_cli_override(self):
        value = config.deep_merge(self.base, {"roles": {
            "planner": {"agent": "claude", "model": "provider/custom-model@v2", "effort": "max"}
        }})
        config.validate(value)
        self.assertEqual(value["roles"]["planner"]["model"], "provider/custom-model@v2")

    def test_merge_does_not_mutate_inputs(self):
        override = {"roles": {"worker": {"effort": "high"}}}
        result = config.deep_merge(self.base, override)
        result["roles"]["worker"]["model"] = "another"
        self.assertEqual(self.base["roles"]["worker"]["effort"], "max")
        self.assertNotIn("model", override["roles"]["worker"])

    def test_invalid_configuration(self):
        patches = [
            {"review": {"max_rounds": 2}},
            {"roles": {"resercher": {}}},
            {"roles": {"worker": {"model": "inherit"}}},
            {"roles": {"worker": {"model": " "}}},
            {"roles": {"worker": {"model": "some\nmodel"}}},
            {"roles": {"worker": {"effort": "supermax"}}},
            {"roles": {"worker": {"agent": "unknown-cli"}}},
            {"roles": {"worker": None}},
            {"parallelism": {"workers": True}},
            {"parallelism": {"researchers": 0}},
            {"execution": {"allow_worktrees": "yes"}},
            {"execution": {"adapter": "unsupported"}},
            {"schema_version": True},
            {"schema_version": 2},
        ]
        for patch in patches:
            with self.subTest(patch=patch), self.assertRaises(config.ConfigError):
                config.validate(config.deep_merge(self.base, patch))

    def test_invalid_lower_layer_is_not_hidden(self):
        self.write("user.json", {"roles": {"worker": {"effort": "bad"}}})
        override = self.write("good.json", {"roles": {"worker": {"effort": "max"}}})
        with self.assertRaises(config.ConfigError):
            config.load_config(self.root, self.user, [override])

    def test_json_rejects_bad_shape_duplicates_and_constants(self):
        for text in ('[]', '{', '{"roles": {}, "roles": {}}', '{"workers": NaN}'):
            self.user.write_text(text, encoding="utf-8")
            with self.subTest(text=text), self.assertRaises(config.ConfigError):
                config.read_object(self.user)

    def test_broken_optional_symlink_is_error(self):
        (self.root / ".hybrid-conductor.json").symlink_to(self.root / "absent")
        with self.assertRaises(config.ConfigError):
            config.load_config(self.root, self.user)

    def test_relative_xdg_rejected(self):
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": "relative"}):
            with self.assertRaises(config.ConfigError):
                config.user_config_default()

    def test_cli_only_resolves_and_does_not_execute_values(self):
        sentinel = self.root / "must-not-exist"
        value = f"$(touch {sentinel})"
        override = self.write("run.json", {"roles": {"worker": {"model": value}}})
        result = subprocess.run([
            sys.executable, str(CONFIG_SCRIPT), "--project", str(self.root),
            "--user-config", str(self.user), "--overrides", str(override)
        ], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["config"]["roles"]["worker"]["model"], value)
        self.assertFalse(sentinel.exists())

    def test_examples_validate(self):
        for path in (ROOT / "examples").glob("*.json"):
            with self.subTest(path=path):
                config.validate(config.deep_merge(self.base, config.read_object(path)))

    @unittest.skipUnless(shutil.which("git"), "Git unavailable")
    def test_project_root_discovery(self):
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True,
                       capture_output=True, timeout=10)
        nested = self.root / "nested"
        nested.mkdir()
        self.assertEqual(config.discover_project(nested), self.root)

    def test_non_git_root_discovery(self):
        with mock.patch.object(config.subprocess, "run", side_effect=FileNotFoundError):
            self.assertEqual(config.discover_project(self.root), self.root)


class BootstrapTests(unittest.TestCase):
    """All herdr interaction here uses a clearly isolated fake executable, not a live session."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hc-FAKE-herdr-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.calls = self.root / "calls.jsonl"
        executable = self.root / "herdr"
        executable.write_text(f"#!{sys.executable}\n" + '''
import json, os, sys, time
from pathlib import Path
with Path(os.environ["HC_FAKE_CALLS"]).open("a") as out:
    out.write(json.dumps(sys.argv[1:]) + "\\n")
if sys.argv[1:] != ["--skill"]:
    sys.exit(91)
mode = os.environ.get("HC_FAKE_MODE", "ok")
if mode == "fail":
    print("FAKE --skill failure", file=sys.stderr)
    sys.exit(9)
if mode == "empty":
    sys.exit(0)
if mode == "timeout":
    time.sleep(2)
if mode == "invalid":
    sys.stdout.buffer.write(b"\\xff")
    sys.exit(0)
print("# FAKE TEST GUIDE\\nThis is a fixture, not herdr documentation.")
''', encoding="utf-8")
        executable.chmod(0o755)
        self.env = dict(os.environ)
        self.env.pop("HERDR_ENV", None)
        self.env.update(PATH=str(self.root), HC_FAKE_CALLS=str(self.calls))

    def run_bootstrap(self, mode="ok", inside=False, extra=()):
        env = dict(self.env, HC_FAKE_MODE=mode)
        if inside:
            env["HERDR_ENV"] = "1"  # Test fixture only, never a real session.
        result = subprocess.run([sys.executable, str(BOOTSTRAP), *extra],
                                env=env, capture_output=True, text=True, timeout=8)
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []
        self.assertTrue(all(call == ["--skill"] for call in calls), calls)
        return result, calls

    def test_missing_cli(self):
        self.env["PATH"] = str(self.root / "no-bin")
        result, calls = self.run_bootstrap()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(calls, [])

    def test_outside_context_gets_guide_but_cannot_continue(self):
        result, calls = self.run_bootstrap()
        self.assertEqual(result.returncode, 5)
        self.assertIn("FAKE TEST GUIDE", result.stdout)
        self.assertEqual(calls, [["--skill"]])

    def test_inside_fixture_gets_guide_once(self):
        result, calls = self.run_bootstrap(inside=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("sha256=", result.stderr)
        self.assertIn("NOT been tested", result.stderr)
        self.assertEqual(calls, [["--skill"]])

    def test_skill_failure_does_not_fallback(self):
        result, calls = self.run_bootstrap(mode="fail", inside=True)
        self.assertEqual(result.returncode, 3)
        self.assertEqual(calls, [["--skill"]])

    def test_empty_guide_rejected(self):
        result, _ = self.run_bootstrap(mode="empty", inside=True)
        self.assertEqual(result.returncode, 4)

    def test_non_utf8_guide_rejected(self):
        result, _ = self.run_bootstrap(mode="invalid", inside=True)
        self.assertEqual(result.returncode, 4)

    def test_guide_print_timeout_is_not_a_session_operation(self):
        # Deterministic timeout simulation: process startup scheduling must not make this flaky.
        with mock.patch.object(bootstrap.shutil, "which", return_value="/fake/herdr"), \
             mock.patch.object(bootstrap.subprocess, "run", side_effect=
                               subprocess.TimeoutExpired(["/fake/herdr", "--skill"], 30)) as run, \
             mock.patch.object(bootstrap.sys, "stderr", io.StringIO()):
            self.assertEqual(bootstrap.main([]), 3)
        run.assert_called_once_with(["/fake/herdr", "--skill"], capture_output=True,
                                    timeout=30, check=False)

    def test_invalid_timeout_rejected_without_executing(self):
        for value in ("0", "-1", "nan", "inf"):
            with self.subTest(value=value):
                result, calls = self.run_bootstrap(extra=("--timeout", value))
                self.assertEqual(result.returncode, 2)
                self.assertEqual(calls, [])


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hc-install-test-")
        self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name) / "skills"

    def test_install_and_idempotence(self):
        paths = installer.install(self.target)
        self.assertEqual(len(paths), 2)
        for path in paths:
            self.assertTrue(path.is_symlink())
            self.assertTrue((path / "SKILL.md").is_file())
        self.assertEqual(installer.install(self.target), [])

    def test_existing_directory_never_overwritten(self):
        occupied = self.target / "herdr-adapter"
        occupied.mkdir(parents=True)
        (occupied / "keep.txt").write_text("keep")
        with self.assertRaises(ValueError):
            installer.install(self.target)
        self.assertFalse((self.target / "conduct").exists())
        self.assertEqual((occupied / "keep.txt").read_text(), "keep")

    def test_broken_symlink_never_overwritten(self):
        self.target.mkdir()
        occupied = self.target / "conduct"
        occupied.symlink_to(self.target / "missing")
        with self.assertRaises(ValueError):
            installer.install(self.target)
        self.assertTrue(occupied.is_symlink())

    def test_partial_failure_rolls_back_new_links(self):
        original = Path.symlink_to
        def fail_second(path, target, target_is_directory=False):
            if path.name == "herdr-adapter":
                raise OSError("simulated symlink failure")
            return original(path, target, target_is_directory=target_is_directory)
        with mock.patch.object(Path, "symlink_to", autospec=True, side_effect=fail_second):
            with self.assertRaises(OSError):
                installer.install(self.target)
        self.assertFalse((self.target / "conduct").is_symlink())


class PackageTests(unittest.TestCase):
    def test_manifest_structure(self):
        manifest = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
        self.assertEqual(manifest["name"], "hybrid-conductor")
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
        self.assertFalse((ROOT / "hooks").exists())
        self.assertFalse((ROOT / ".mcp.json").exists())

    def test_two_skill_frontmatters(self):
        paths = sorted((ROOT / "skills").glob("*/SKILL.md"))
        self.assertEqual(len(paths), 3)
        for path in paths:
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"))
            frontmatter = text.split("---", 2)[1]
            self.assertRegex(frontmatter, rf"(?m)^name: {re.escape(path.parent.name)}$")
            self.assertRegex(frontmatter, r'(?m)^description: ".+"$')
            self.assertLess(len(text.splitlines()), 100)

    def test_relative_markdown_links(self):
        for path in ROOT.rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            for link in re.findall(r"\]\(([^)]+)\)", text):
                if "://" in link or link.startswith("#"):
                    continue
                local = link.split("#", 1)[0]
                with self.subTest(path=path, link=link):
                    self.assertTrue((path.parent / local).exists(), f"Broken local link: {path}: {link}")

    def test_core_policies_are_present(self):
        review = (ROOT / "skills/conduct/references/review.md").read_text()
        self.assertIn("レビュー・修正の回数上限はない", review)
        self.assertIn("未解決の指摘・前回からの差分・修正の影響範囲", review)
        self.assertIn("workerの自己申告だけでは", review)
        self.assertIn("新たに分かった実害は追加できる", review)
        adapter = (ROOT / "skills/herdr-adapter/SKILL.md").read_text()
        self.assertIn("herdr --skill", adapter)
        self.assertIn("値を自分で設定して条件を偽装しない", adapter)
        self.assertIn("(references/launch.md)", adapter)

    def test_launch_policies_are_present(self):
        launch = (ROOT / "skills/herdr-adapter/references/launch.md").read_text()
        self.assertIn("導入版の `herdr --skill` とhelpが常に優先", launch)
        self.assertIn("shellのプロンプトを待つ", launch)
        self.assertIn("paneとagentに同じ役割名を付ける", launch)
        self.assertIn("自分が作っていないpaneのラベルは変更しない", launch)
        self.assertIn("default_permissions=\":workspace-write\"", launch)
        self.assertIn("mainのpaneを左40%に残し、右60%を子agentの領域にする", launch)
        self.assertIn("mainのpaneは再び分割しない", launch)
        self.assertRegex(launch, r"planner / researcher / reviewer \| `<project>/\.hybrid-conductor/runs/")
        self.assertIn("報告の受け渡し", launch)
        self.assertIn("runs/<run-id>/agents/<agent名>", launch)
        workflow = (ROOT / "skills/conduct/references/workflow.md").read_text()
        self.assertIn("子の返却を既定で報告ファイルにする", workflow)
        self.assertIn("報告ファイルは上書きしない", workflow)
        self.assertIn("mainは全文を書き写さず", workflow)
        self.assertIn("`.hybrid-conductor/` を含めない", workflow)
        self.assertIn("報告ファイルで受け取る", (ROOT / "skills/herdr-adapter/SKILL.md").read_text())
        self.assertIn("勝手に選ばずユーザーに確認する", launch)


if __name__ == "__main__":
    unittest.main()
