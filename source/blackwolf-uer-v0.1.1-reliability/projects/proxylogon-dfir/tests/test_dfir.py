import unittest
from dfir import detect_iis

class DfirTests(unittest.TestCase):
    def test_exchange_resource(self):
        self.assertIn('x_beresource', detect_iis('GET /ecp/test X-BEResource=Admin@server'))
    def test_webshell_path(self):
        self.assertIn('possible_webshell_path', detect_iis('GET /aspnet_client/system_web/shell.aspx'))
    def test_benign(self):
        self.assertEqual([], detect_iis('GET /owa/healthcheck.htm 200'))
