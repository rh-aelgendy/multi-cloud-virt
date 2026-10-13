"""Offline checks for failure boundaries and generated Windows answer files."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


factory = load('factory', ROOT / 'pipelines/factory.py')
runtime = load('runtime', ROOT / 'scripts/create-runtime-secret.py')


class FactoryTests(unittest.TestCase):
    def setUp(self):
        factory.build_id = 'team-x-win-v100-build1'
        factory.version = 'v1.0.0'

    def test_license_gate_precedes_any_cluster_mutation(self):
        with patch.dict(os.environ, {'ACCEPT_EULA': 'false'}), patch.object(factory, 'create') as create:
            with self.assertRaises(ValueError):
                factory.prepare()
            create.assert_not_called()

    def test_attached_disk_cannot_be_published(self):
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, 'validation.json').write_text(json.dumps({'passed': True, 'version': 'v1.0.0'}))
            with patch.dict(os.environ, {'WORKSPACE': temp}), patch.object(factory, 'get', return_value={'status': {'phase': 'Running'}}), patch.object(factory, 'create') as create:
                with self.assertRaises(RuntimeError):
                    factory.publish()
                create.assert_not_called()

    def test_wrong_version_cannot_be_published(self):
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, 'validation.json').write_text(json.dumps({'passed': True, 'version': 'v9.9.9'}))
            with patch.dict(os.environ, {'WORKSPACE': temp}), patch.object(factory, 'create') as create:
                with self.assertRaises(RuntimeError):
                    factory.publish()
                create.assert_not_called()

    def test_missing_evidence_prevents_publication(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'WORKSPACE': temp}), patch.object(factory, 'create') as create:
            with self.assertRaises(FileNotFoundError):
                factory.publish()
            create.assert_not_called()

    def test_builder_must_be_halted_before_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, 'validation.json').write_text(json.dumps({'passed': True, 'version': 'v1.0.0'}))
            with patch.dict(os.environ, {'WORKSPACE': temp}), patch.object(factory, 'get', side_effect=[None, {'spec': {'runStrategy': 'Always'}}]), patch.object(factory, 'create') as create:
                with self.assertRaises(RuntimeError):
                    factory.publish()
                create.assert_not_called()

    def test_dr_transfer_requires_a_published_source(self):
        with patch.object(factory, 'get', return_value=None), patch.object(factory, 'create') as create:
            with self.assertRaises(RuntimeError):
                factory.stage_dr()
            create.assert_not_called()

    def test_aro_builder_has_explicit_virt_placement(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'WORKSPACE': temp, 'VIRTIO_IMAGE': 'example.invalid/virtio@sha256:123'}), patch.object(factory, 'create') as create, patch.object(factory, 'wait_for', side_effect=[{'passed': True}, True]), patch.object(factory, 'oc'), patch('builtins.print'):
            factory.install()
            vm = create.call_args_list[0].args[0]
            self.assertEqual(vm['spec']['template']['spec']['nodeSelector'], {'workload': 'virt'})

    def test_xml_password_is_escaped_and_no_autologon(self):
        password = 'Example<&>Password123!'
        xml = runtime.answer('TEAMX-AZ-01', 'azure', password, 'v1.0.0')
        root = ET.fromstring(xml)
        ns = {'u': 'urn:schemas-microsoft-com:unattend'}
        self.assertEqual(root.find('.//u:AdministratorPassword/u:Value', ns).text, password)
        self.assertIsNone(root.find('.//u:AutoLogon', ns))
        self.assertLessEqual(len(root.find('.//u:RunSynchronousCommand/u:Path', ns).text), 259)
        self.assertEqual(root.find('.//u:UILanguage', ns).text, 'en-US')
        self.assertEqual(root.find('.//u:HideLocalAccountScreen', ns).text, 'true')
        self.assertEqual(root.find('.//u:ComputerName', ns).text, 'TEAMX-AZ-01')

    def test_acm_feedback_uses_controller_field_names(self):
        item = {'status': {'resourceStatus': {'manifests': [{'statusFeedback': {'values': [
            {'name': 'phase', 'fieldValue': {'type': 'String', 'string': 'Succeeded'}}]}}]}}}
        self.assertEqual(factory.feedback_phase(item), 'Succeeded')
        self.assertIsNone(factory.feedback_phase({}))

    def test_install_answer_defaults_to_license_not_accepted(self):
        root = ET.parse(ROOT / 'windows/autounattend.xml').getroot()
        ns = {'u': 'urn:schemas-microsoft-com:unattend'}
        self.assertEqual(root.find('.//u:AcceptEula', ns).text, 'false')


if __name__ == '__main__':
    unittest.main()
