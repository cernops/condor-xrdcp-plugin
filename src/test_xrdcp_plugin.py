from unittest import TestCase
try:
    # python 3.4+ should use builtin unittest.mock not mock pkg
    from unittest.mock import patch
except ImportError:
    from mock import patch
from io import StringIO
from src.xrdcp_plugin import parse_args
from src.xrdcp_plugin import print_capabilities
from src.xrdcp_plugin import get_error_dict
from src.xrdcp_plugin import XRDCPPlugin
import sys


class Test(TestCase):
    def test_parse_args(self):
        outfile_val = "hello.txt"
        infile_val = "path/to/file.txt"
        test_args = ['test', '-infile', infile_val, '-outfile', outfile_val]
        with patch.object(sys, 'argv', test_args):
            args = parse_args()
            self.assertFalse(args['upload'], args)
            self.assertEqual(args['infile'], infile_val, "-infile value doesn't match")
            self.assertEqual(args['outfile'], outfile_val, "-outfile value doesn't match")

    def test_bad_args(self):
        patch("sys.argv", ['-infile', "hello.txt"])
        with patch('sys.stdout', new=StringIO()) as fakeOutput:
            with self.assertRaises(SystemExit) as cm:
                with patch.object(sys, 'argv', ['test', '-infile', "hello.txt"]):
                    parse_args()
                    self.assertEqual(cm.exception.code, -1)
                    output = fakeOutput.getvalue().split("\n")
                    self.assertRegex(output[0], "^Usage:")
        with patch('sys.stdout', new=StringIO()) as fakeOutput:
            with self.assertRaises(SystemExit) as dm:
                with patch.object(sys, 'argv', ['test', '-outfile', 'foo/bar']):
                    parse_args()
                    self.assertEqual(dm.exception.code, -1)
                    output = fakeOutput.getvalue().split("\n")
                    self.assertRegex(output[0], "^Usage")

    def test_print_capabilities(self):
        with patch('sys.stdout', new=StringIO()) as fakeOutput:
            print_capabilities()
            output = fakeOutput.getvalue().split("\n")
            self.assertEqual(output[1], 'SupportedMethods = "root"')

    def test_args_classad(self):
        with patch('sys.stdout', new=StringIO()) as fakeOutput:
            with self.assertRaises(SystemExit) as cm:
                with patch.object(sys, 'argv', ['test', '-classad']):
                    parse_args()
                    self.assertEqual(cm.exception.code, 0)
            output = fakeOutput.getvalue().split("\n")
            self.assertEqual(output[1], 'SupportedMethods = "root"')

    def test_error_dict(self):
        e = "test_error"
        url = "xrdcp:///foo"
        error_dict = get_error_dict(e, url)
        self.assertEqual(error_dict['TransferUrl'], url)
        self.assertEqual(error_dict['TransferError'], f"str: {e}")

    def test_too_long_error(self):
        e = "f"*4000
        url = "xrdcp:///foo"
        error_dict = get_error_dict(e, url)
        self.assertTrue(len(error_dict['TransferError']) < 1500)

    def test_parse_root_uri(self):
        xrdcp = XRDCPPlugin()
        baduri = 'root://eos/user/b/bejones'
        gooduri = 'root://eosuser.cern.ch//eos/user/b/bejones'
        with self.assertRaises(ValueError):
            xrdcp.parse_url(baduri)
        (server, path) = xrdcp.parse_url(gooduri)
        self.assertEqual(server, "root://eosuser.cern.ch")
        self.assertEqual(path, "/eos/user/b/bejones")