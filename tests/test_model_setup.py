"""Setup decisions are independent of defaults and of the parent's model."""
import json
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest

from test_package import config, ROOT, CONFIG_SCRIPT


class ModelSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.user = self.write('user.json', {})
        self.pi_user = self.write('pi-user.json', {})
        self.pi_project = self.write('pi-project.json', {})

    def write(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value))
        return path

    def status(self, adapter='herdr', overrides=None):
        value, sources = config.load_config(self.root, self.user, overrides)
        return config.setup_status(value, sources, adapter=adapter, project=self.root,
                                   pi_user_settings=self.pi_user,
                                   pi_project_settings=self.pi_project)

    def pi_roles(self):
        return {'subagents': {'agentOverrides': {
            f'hybrid-conductor.{r}': {'model': f'provider/{r}'}
            for r in config.DELEGATED_ROLES}}}

    def test_recommendations_do_not_complete_setup(self):
        status = self.status()
        self.assertTrue(status['required'])
        self.assertEqual(status['missing_roles'], list(config.DELEGATED_ROLES))
        self.assertEqual(status['recommendations']['worker']['model'], 'gpt-6-luna')

    def test_existing_complete_herdr_configuration_migrates(self):
        self.write('user.json', {'roles': {r: {'model': f'custom-{r}'}
                                         for r in config.DELEGATED_ROLES}})
        self.assertFalse(self.status()['required'])

    def test_explicit_selection_equal_to_default_is_still_selection(self):
        self.write('user.json', {'roles': config.read_object(config.DEFAULTS)['roles']})
        self.assertFalse(self.status()['required'])

    def test_partial_settings_require_all_role_setup(self):
        self.write('user.json', {'roles': {'worker': {'model': 'chosen'}}})
        self.assertNotIn('worker', self.status()['missing_roles'])
        self.assertEqual(len(self.status()['missing_roles']), 4)

    def test_herdr_layers_and_run_override(self):
        self.write('user.json', {'roles': {r: {'model': r} for r in config.DELEGATED_ROLES}})
        self.write('.hybrid-conductor.json', {'roles': {'worker': {'model': 'project'}}})
        run = self.write('run.json', {'roles': {'worker': {'model': 'run'}}})
        self.assertEqual(self.status(overrides=[run])['explicit_roles']['worker']['model'], 'run')

    def test_pi_ignores_herdr_models_global_defaults_and_unqualified_names(self):
        self.write('user.json', {'roles': config.read_object(config.DEFAULTS)['roles']})
        self.write('pi-user.json', {'subagents': {'defaultModel': 'expensive-parent',
                                               'agentOverrides': {'worker': {'model': 'wrong-name'}}}})
        self.assertEqual(len(self.status('pi')['missing_roles']), 5)

    def test_pi_full_setup_and_optional_thinking(self):
        self.write('pi-user.json', self.pi_roles())
        status = self.status('pi')
        self.assertFalse(status['required'])
        self.assertNotIn('thinking', status['explicit_roles']['worker'])

    def test_pi_thinking_false_is_native_opt_out(self):
        roles = self.pi_roles()
        roles['subagents']['agentOverrides']['hybrid-conductor.worker']['thinking'] = False
        self.write('pi-user.json', roles)
        self.assertFalse(self.status('pi')['required'])
        self.assertIs(self.status('pi')['explicit_roles']['worker']['thinking'], False)

    def test_pi_project_precedence_preserves_user_fields(self):
        roles = self.pi_roles()
        roles['subagents']['agentOverrides']['hybrid-conductor.worker']['thinking'] = 'max'
        self.write('pi-user.json', roles)
        self.write('pi-project.json', {'subagents': {'agentOverrides': {
            'hybrid-conductor.worker': {'model': 'other/worker'}}}})
        status = self.status('pi')
        self.assertEqual(status['explicit_roles']['worker'], {'model': 'other/worker', 'thinking': 'max'})

    def test_pi_disabled_role_is_not_ready(self):
        roles = self.pi_roles()
        roles['subagents']['agentOverrides']['hybrid-conductor.worker']['disabled'] = True
        self.write('pi-user.json', roles)
        self.assertEqual(self.status('pi')['disabled_roles'], ['worker'])
        self.assertTrue(self.status('pi')['required'])

    def test_pi_invalid_fields_and_lower_layer_not_hidden(self):
        for value in (None, {'model': ''}, {'model': 'inherit'}, {'thinking': []}, {'thinking': 'bad'}):
            with self.subTest(value=value):
                self.write('pi-user.json', {'subagents': {'agentOverrides': {
                    'hybrid-conductor.worker': value}}})
                self.write('pi-project.json', self.pi_roles())
                with self.assertRaises(config.ConfigError):
                    self.status('pi')

    def test_pi_settings_bad_shapes(self):
        for value in ({'subagents': []}, {'subagents': {'agentOverrides': []}}):
            self.write('pi-user.json', value)
            with self.assertRaises(config.ConfigError):
                self.status('pi')

    def test_native_pi_settings_preserved_read_only(self):
        roles = self.pi_roles()
        roles['theme'] = 'custom'
        roles['subagents']['unrelatedOption'] = 'keep'
        path = self.write('pi-user.json', roles)
        before = path.read_bytes()
        self.status('pi')
        self.assertEqual(path.read_bytes(), before)

    def test_cli_setup_status_and_adapter_selection(self):
        command = [sys.executable, str(CONFIG_SCRIPT), '--project', str(self.root),
                   '--user-config', str(self.user), '--adapter', 'pi', '--check-setup',
                   '--pi-user-settings', str(self.pi_user),
                   '--pi-project-settings', str(self.pi_project)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(json.loads(result.stdout)['setup']['adapter'], 'pi')
        self.write('pi-user.json', self.pi_roles())
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.pi_user.unlink()
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)

    def test_pi_package_exposes_only_native_skills(self):
        manifest = json.loads((ROOT / 'package.json').read_text())
        self.assertEqual(manifest['pi']['skills'], ['./skills/conduct', './skills/pi-adapter'])
        self.assertEqual(manifest['pi']['subagents']['agents'], ['./agents/pi'])
        for role in config.DELEGATED_ROLES:
            agent = (ROOT / 'agents/pi' / f'{role}.md').read_text()
            self.assertIn(f'name: {role}\n', agent)
            self.assertIn('package: hybrid-conductor\n', agent)
            self.assertIn('defaultContext: fresh\n', agent)
            self.assertIn('inheritProjectContext: true\n', agent)
            self.assertIn('inheritGlobalContext: false\n', agent)
            self.assertIn('inheritSkills: false\n', agent)
            self.assertIn('extensions:\n', agent)
            self.assertNotIn('\nmodel:', agent)
            self.assertNotIn('\nmemory:', agent)
        reviewer = (ROOT / 'agents/pi/reviewer.md').read_text()
        self.assertIn('tools: read, grep, find, ls\n', reviewer)


if __name__ == '__main__':
    unittest.main()
