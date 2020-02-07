import unittest
from conans.client.tools import environment_append
from conans.test.utils.tools import TestClient

from conans.util.conan_v2_mode import CONAN_V2_MODE_ENVVAR


class ConanV2ModeTestCase(unittest.TestCase):

    @staticmethod
    def get_client(*args, **kwargs):
        # TODO: Initialize with the default behavior for Conan v2
        return TestClient(*args, **kwargs)

    def run(self, *args, **kwargs):
        with environment_append({CONAN_V2_MODE_ENVVAR: "1"}):
            super(ConanV2ModeTestCase, self).run(*args, **kwargs)
