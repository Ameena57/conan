# coding=utf-8
import sys
import unittest
from types import MethodType
from unittest import mock

from parameterized import parameterized

from conans.cli.output import ConanOutput
from conans.client.userio import init_colorama


class ConanOutputTest(unittest.TestCase):

    @parameterized.expand([(False, {}),
                           (True, {"CLICOLOR": "0"}),
                           (False, {"CLICOLOR": "1"}),
                           (False, {"CLICOLOR_FORCE": "0"})])
    def test_output_no_color(self, isatty, env):
        with mock.patch("colorama.init") as init:
            with mock.patch("sys.stderr.isatty", return_value=isatty), \
                 mock.patch.dict("os.environ", env, clear=True):
                init_colorama(sys.stderr)
                out = ConanOutput()
                assert out.color is False
                init.assert_called()

    @parameterized.expand([(True, {}),
                           (False, {"CLICOLOR_FORCE": "1"}),
                           (True, {"CLICOLOR": "1"})])
    def test_output_color(self, isatty, env):
        with mock.patch("colorama.init") as init:
            with mock.patch("sys.stderr.isatty", return_value=isatty), \
                 mock.patch.dict("os.environ", env, clear=True):
                init_colorama(sys.stderr)
                out = ConanOutput()
                assert out.color is True
                init.assert_called()

    @parameterized.expand([(True, {"NO_COLOR": "1"}),
                           (True, {"NO_COLOR": "1", "CLICOLOR_FORCE": "1"}),
                           (True, {"NO_COLOR": "1", "CLICOLOR_FORCE": "1", "CLICOLOR": "1"}),
                           (False, {"NO_COLOR": "1", "CLICOLOR_FORCE": "1", "CLICOLOR": "1"})])
    def test_output_color_prevent_strip(self, isatty, env):
        with mock.patch("colorama.init") as init:
            with mock.patch("sys.stderr.isatty", return_value=isatty), \
                 mock.patch.dict("os.environ", env, clear=True):
                init_colorama(sys.stderr)
                out = ConanOutput()
                assert out.color is False
                init.assert_not_called()
