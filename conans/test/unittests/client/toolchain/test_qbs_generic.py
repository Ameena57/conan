import unittest
import textwrap
import conans.client.toolchain.qbs.generic as qbs

from conans.client import tools
from conans.test.utils.mocks import MockConanfile, MockSettings


class RunnerMock(object):
    class Expectation(object):
        def __init__(self, return_ok=True, output=None):
            self.return_ok = return_ok
            self.output = output

    def __init__(self, expectations=[Expectation()]):
        self.command_called = []
        self.expectations = expectations

    def __call__(self, command, output, win_bash=False, subsystem=None):
        self.command_called.append(command)
        self.win_bash = win_bash
        self.subsystem = subsystem
        if not self.expectations:
            return 1
        expectation = self.expectations.pop(0)
        if expectation.output and output and hasattr(output, "write"):
            output.write(expectation.output)
        return 0 if expectation.return_ok else 1


class MockConanfileWithFolders(MockConanfile):
    build_folder = "just/some/foobar/path"

    def run(self, *args, **kwargs):
        if self.runner:
            if "output" not in kwargs:
                kwargs["output"] = None
            self.runner(*args, **kwargs)


class QbsGenericTest(unittest.TestCase):
    def test_split_env_var_into_list(self):
        list = ['-p1', '-p2', '-p3_with_value=13',
                '-p_with_space1="hello world"',
                '"-p_with_space2=Hello World"']
        expected_list = ['-p1', '-p2', '-p3_with_value=13',
                         '-p_with_space1=hello world',
                         '-p_with_space2=Hello World']
        env_var = " ".join(list)
        self.assertEqual(qbs._env_var_to_list(env_var), expected_list)

    def test_compiler_not_in_settings(self):
        conanfile = MockConanfile(MockSettings({}))
        with self.assertRaises(qbs.QbsException):
            qbs._check_for_compiler(conanfile)

    def test_compiler_in_settings_not_supported(self):
        conanfile = MockConanfile(
            MockSettings({"compiler": "not realy a compiler name"}))
        with self.assertRaises(qbs.QbsException):
            qbs._check_for_compiler(conanfile)

    def test_valid_compiler(self):
        supported_compilers = ["Visual Studio", "gcc", "clang"]
        for compiler in supported_compilers:
            conanfile = MockConanfile(MockSettings({"compiler": compiler}))
            qbs._check_for_compiler(conanfile)

    @staticmethod
    def _settings_to_test_against():
        return [
            {"os": "Windows", "compiler": "gcc", "qbs_compiler": "mingw"},
            {"os": "Windows", "compiler": "clang",
             "qbs_compiler": "clang-cl"},
            {"os": "Windows", "compiler": "Visual Studio",
             "qbs_compiler": "cl"},
            {"os": "Windows", "compiler": "Visual Studio",
             "compiler.toolset": "ClangCl", "qbs_compiler": "clang-cl"},
            {"os": "Linux", "compiler": "gcc", "qbs_compiler": "gcc"},
            {"os": "Linux", "compiler": "clang", "qbs_compiler": "clang"}
        ]

    def test_convert_compiler_name_to_qbs_compiler_name(self):
        for settings in self._settings_to_test_against():
            def expected():
                return settings["qbs_compiler"]
            conanfile = MockConanfile(MockSettings(settings))
            self.assertEqual(qbs._compiler_name(conanfile), expected())

    def test_settings_dir_location(self):
        conanfile = MockConanfileWithFolders(MockSettings({}))
        self.assertEqual(qbs._settings_dir(conanfile), conanfile.build_folder)

    def test_setup_toolchain_without_any_env_values(self):
        for settings in self._settings_to_test_against():
            conanfile = MockConanfileWithFolders(MockSettings(settings),
                                                 runner=RunnerMock())
            qbs._setup_toolchains(conanfile)
            self.assertEqual(len(conanfile.runner.command_called), 1)
            self.assertEqual(
                conanfile.runner.command_called[0],
                "qbs-setup-toolchains --settings-dir %s %s %s" % (
                    conanfile.build_folder, settings["qbs_compiler"],
                    qbs._profile_name))

    def test_setup_toolchain_with_compiler_from_env(self):
        compiler = "compiler_from_env"
        for settings in self._settings_to_test_against():
            conanfile = MockConanfileWithFolders(MockSettings(settings),
                                                 runner=RunnerMock())
            with tools.environment_append({"CC": compiler}):
                qbs._setup_toolchains(conanfile)
            self.assertEqual(len(conanfile.runner.command_called), 1)
            self.assertEqual(
                conanfile.runner.command_called[0],
                "qbs-setup-toolchains --settings-dir %s %s %s" % (
                    conanfile.build_folder, compiler,
                    qbs._profile_name))

    @staticmethod
    def _generate_flags(flag, qbs_key):
        return {"env": ('-{0}1 -{0}2 -{0}3_with_value=13 '
                        '-{0}_with_space="hello world"').format(flag),
                "qbs_value": ("['-{0}1', '-{0}2', '-{0}3_with_value=13', "
                              "'-{0}_with_space=hello world']").format(flag),
                "qbs_key": qbs_key}

    def test_flags_from_env(self):
        asm = self._generate_flags("asm", "assemblerFlags")
        c = self._generate_flags("c", "cFlags")
        cpp = self._generate_flags("cpp", "cppFlags")
        cxx = self._generate_flags("cxx", "cxxFlags")
        wl = self._generate_flags("Wl,", "linkerFlags")
        ld = self._generate_flags("ld", "linkerFlags")
        env = {
            "ASFLAGS": asm["env"],
            "CFLAGS": c["env"],
            "CPPFLAGS": cpp["env"],
            "CXXFLAGS": cxx["env"],
            "LDFLAGS": "%s -Wl,%s" % (wl["env"], ld["env"].replace(" -", ",-"))
        }
        with tools.environment_append(env):
            flags_from_env = qbs._flags_from_env()

        expected_flags = {
            'cpp.'+asm["qbs_key"]: asm["qbs_value"],
            'cpp.'+c["qbs_key"]: c["qbs_value"],
            'cpp.'+cpp["qbs_key"]: cpp["qbs_value"],
            'cpp.'+cxx["qbs_key"]: cxx["qbs_value"],
            'cpp.'+wl["qbs_key"]: ("%s%s" % (wl["qbs_value"],
                                             ld["qbs_value"])).replace(
                                                "][", ", ", 1).replace(
                                                "-Wl,", ""),
        }
        self.assertEqual(flags_from_env, expected_flags)

    @staticmethod
    def _generate_qbs_config_output():
        return textwrap.dedent('''\
            profiles.conan.cpp.cCompilerName: "gcc"
            profiles.conan.cpp.compilerName: "g++"
            profiles.conan.cpp.cxxCompilerName: "g++"
            profiles.conan.cpp.driverFlags: \
            ["-march=armv7e-m", "-mtune=cortex-m4", "--specs=nosys.specs"]
            profiles.conan.cpp.platformCommonCompilerFlags: undefined
            profiles.conan.cpp.platformLinkerFlags: undefined
            profiles.conan.cpp.toolchainInstallPath: "/usr/bin"
            profiles.conan.cpp.toolchainPrefix: "arm-none-eabi-"
            profiles.conan.qbs.targetPlatform: ""
            profiles.conan.qbs.someBoolProp: "true"
            profiles.conan.qbs.someIntProp: "13"
            profiles.conan.qbs.toolchain: ["gcc"]
            ''')

    def test_read_qbs_toolchain_from_qbs_config_output(self):
        expected_config = {
            'cpp.cCompilerName': '"gcc"',
            'cpp.compilerName': '"g++"',
            'cpp.cxxCompilerName': '"g++"',
            'cpp.driverFlags': '["-march=armv7e-m", "-mtune=cortex-m4", "--specs=nosys.specs"]',
            'cpp.platformCommonCompilerFlags': 'undefined',
            'cpp.platformLinkerFlags': 'undefined',
            'cpp.toolchainInstallPath': '"/usr/bin"',
            'cpp.toolchainPrefix': '"arm-none-eabi-"',
            'qbs.targetPlatform': '""',
            'qbs.someBoolProp': 'true',
            'qbs.someIntProp': '13',
            'qbs.toolchain': '["gcc"]'
        }

        conanfile = MockConanfileWithFolders(
            MockSettings({}), runner=RunnerMock(
                expectations=[RunnerMock.Expectation(
                    output=self._generate_qbs_config_output())]))
        config = qbs._read_qbs_toolchain_from_config(conanfile)
        self.assertEqual(len(conanfile.runner.command_called), 1)
        self.assertEqual(conanfile.runner.command_called[0],
                         "qbs-config --settings-dir %s --list" % (
                            conanfile.build_folder))
        self.assertEqual(config, expected_config)

    def test_toolchain_content(self):
        expected_content = textwrap.dedent('''\
            import qbs

            Project {
                Profile {
                    name: "conan_toolchain_profile"
                    cpp.cCompilerName: "gcc"
                    cpp.compilerName: "g++"
                    cpp.cxxCompilerName: "g++"
                    cpp.driverFlags: ["-march=armv7e-m", "-mtune=cortex-m4", "--specs=nosys.specs"]
                    cpp.platformCommonCompilerFlags: undefined
                    cpp.platformLinkerFlags: undefined
                    cpp.toolchainInstallPath: "/usr/bin"
                    cpp.toolchainPrefix: "arm-none-eabi-"
                    qbs.targetPlatform: ""
                    qbs.someBoolProp: true
                    qbs.someIntProp: 13
                    qbs.toolchain: ["gcc"]
                }
            }''')

        conanfile = MockConanfileWithFolders(
            MockSettings({"compiler": "gcc", "os": "Linux"}),
            runner=RunnerMock(
                expectations=[
                    RunnerMock.Expectation(),
                    RunnerMock.Expectation(
                        output=self._generate_qbs_config_output()),
                ]))

        qbs_toolchain = qbs.QbsGenericToolchain(conanfile)

        self.assertEqual(qbs_toolchain.content, expected_content)
