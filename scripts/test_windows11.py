"""Windows 11 image factory failure gates; no cluster access."""
import importlib.util
import json
import os
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

with patch.dict(os.environ, {'NAMESPACE':'image-factory','BUILD_ID':'win11-test','IMAGE_NAME':'win11-test-v1-0-0','IMAGE_VERSION':'v1.0.0','MODE':'developer'}):
    spec=importlib.util.spec_from_file_location('win11',Path(__file__).resolve().parents[1]/'pipelines/windows11/image-controller.py')
    win11=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(win11)


class Windows11Tests(unittest.TestCase):
    def test_license_gate_precedes_mutations(self):
        with patch.dict(os.environ,{'ACCEPT_EULA':'false'}),patch.object(win11,'create') as create:
            with self.assertRaises(ValueError):win11.prepare()
            create.assert_not_called()

    def test_existing_output_is_not_replaced(self):
        with patch.dict(os.environ,{'ACCEPT_EULA':'true'}),patch.object(win11,'get',return_value={'metadata':{}}),patch.object(win11,'create') as create:
            with self.assertRaises(ValueError):win11.prepare()
            create.assert_not_called()

    def test_ready_non_windows11_source_is_rejected(self):
        source={'metadata':{'labels':{}},'status':{'conditions':[{'type':'Ready','status':'True'}]}}
        with patch.dict(os.environ,{'ACCEPT_EULA':'true','SOURCE_IMAGE':'server-image'}),patch.object(win11,'get',side_effect=[None,None,None,source]),patch.object(win11,'create') as create:
            with self.assertRaises(ValueError):win11.prepare()
            create.assert_not_called()

    def test_missing_evidence_prevents_publication(self):
        with patch.object(win11,'get',return_value=None),patch.object(win11,'create') as create:
            with self.assertRaises(RuntimeError):win11.publish()
            create.assert_not_called()

    def test_wrong_mode_evidence_prevents_publication(self):
        evidence={'data':{'validation.json':json.dumps({'passed':True,'version':'v1.0.0','mode':'base'})}}
        with patch.object(win11,'get',return_value=evidence),patch.object(win11,'create') as create:
            with self.assertRaises(RuntimeError):win11.publish()
            create.assert_not_called()

    def test_running_builder_cannot_be_published(self):
        evidence={'data':{'validation.json':json.dumps({'passed':True,'version':'v1.0.0','mode':'developer'})}}
        with patch.object(win11,'get',side_effect=[evidence,{'status':{'phase':'Running'}}]),patch.object(win11,'create') as create:
            with self.assertRaises(RuntimeError):win11.publish()
            create.assert_not_called()


class Windows11AnswerTests(unittest.TestCase):
    def test_base_license_defaults_false_and_windows11_drivers(self):
        source=Path(__file__).resolve().parents[1]/'pipelines/windows11/base-autounattend.xml'
        root=ET.parse(source).getroot()
        ns={'u':'urn:schemas-microsoft-com:unattend'}
        self.assertEqual(root.find('.//u:AcceptEula',ns).text,'false')
        self.assertTrue(all('w11' in x.text for x in root.findall('.//u:DriverPaths//u:Path',ns)))
        self.assertLessEqual(len(root.find('.//u:RunSynchronousCommand/u:Path',ns).text),259)

    def test_runtime_password_xml_escaping_and_local_account(self):
        spec=importlib.util.spec_from_file_location('win11login',Path(__file__).with_name('create-windows11-login.py'))
        login=importlib.util.module_from_spec(spec);spec.loader.exec_module(login)
        password='Demo<&>ExamplePassword1!'
        root=ET.fromstring(login.answer('WIN11-DEV-01','demo',password))
        ns={'u':'urn:schemas-microsoft-com:unattend'}
        self.assertEqual(root.find('.//u:LocalAccount/u:Password/u:Value',ns).text,password)
        self.assertIsNone(root.find('.//u:AutoLogon',ns))


if __name__=='__main__':unittest.main()
