import os
import platform
import subprocess
import unittest

from conans import load
from conans.test.utils.tools import TestClient


class VirtualBuildEnvTest(unittest.TestCase):

    def environment_deactivate_test(self):

        def env_output_to_dict(env_output):
            env = {}
            for line in env_output.splitlines():
                tmp = line.decode().split("=")
                env[tmp[0]] = tmp[1].replace("\\", "/")
            return env

        conanfile = """
from conans import ConanFile

class TestConan(ConanFile):
    name = "test"
    version = "1.0"
    settings = "os", "compiler", "arch", "build_type"
    generators = "virtualbuildenv"
"""
        in_windows = platform.system() == "Windows"
        client = TestClient(path_with_spaces=False)
        client.save({"conanfile.py": conanfile})
        client.run("install .")
        env_cmd = "set" if in_windows else "env"
        extension = "bat" if in_windows else "sh"
        prefix = "" if in_windows else "source"
        output = subprocess.check_output(env_cmd, shell=True)
        normal_environment = env_output_to_dict(output)
        client.run("install .")
        activate_build_file = os.path.join(client.current_folder, "activate_build.%s" % extension)
        deactivate_build_file = os.path.join(client.current_folder,
                                             "deactivate_build.%s" % extension)
        self.assertTrue(os.path.exists(activate_build_file))
        self.assertTrue(os.path.exists(deactivate_build_file))
        if in_windows:
            activate_build_content = load(activate_build_file)
            deactivate_build_content = load(deactivate_build_file)
            self.assertEqual(len(activate_build_content.splitlines()),
                             len(deactivate_build_content.splitlines()))
        output = subprocess.check_output("%s %s && %s" % (prefix, activate_build_file, env_cmd),
                                         shell=True)
        activate_environment = env_output_to_dict(output)
        self.assertNotEqual(normal_environment, activate_environment)
        output = subprocess.check_output("%s %s && %s" % (prefix, deactivate_build_file, env_cmd),
                                         shell=True)
        deactivate_environment = env_output_to_dict(output)
        self.assertEqual(normal_environment, deactivate_environment)
