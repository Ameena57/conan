import os
import platform

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.integration.toolchains.apple.test_xcodetoolchain import _get_filename
from conans.test.utils.tools import TestClient

_expected_dep_xconfig = [
    "HEADER_SEARCH_PATHS = $(inherited) $(HEADER_SEARCH_PATHS_{name}_{name})",
    "GCC_PREPROCESSOR_DEFINITIONS = $(inherited) $(GCC_PREPROCESSOR_DEFINITIONS_{name}_{name})",
    "OTHER_CFLAGS = $(inherited) $(OTHER_CFLAGS_{name}_{name})",
    "OTHER_CPLUSPLUSFLAGS = $(inherited) $(OTHER_CPLUSPLUSFLAGS_{name}_{name})",
    "FRAMEWORK_SEARCH_PATHS = $(inherited) $(FRAMEWORK_SEARCH_PATHS_{name}_{name})",
    "LIBRARY_SEARCH_PATHS = $(inherited) $(LIBRARY_SEARCH_PATHS_{name}_{name})",
    "OTHER_LDFLAGS = $(inherited) $(OTHER_LDFLAGS_{name}_{name})",
]

_expected_vars_xconfig = [
    "CONAN_{name}_{name}_BINARY_DIRECTORIES[config={configuration}][arch={architecture}][sdk={sdk}{sdk_version}] =",
    "CONAN_{name}_{name}_C_COMPILER_FLAGS[config={configuration}][arch={architecture}][sdk={sdk}{sdk_version}] =",
    "CONAN_{name}_{name}_CXX_COMPILER_FLAGS[config={configuration}][arch={architecture}][sdk={sdk}{sdk_version}] =",
    "CONAN_{name}_{name}_LINKER_FLAGS[config={configuration}][arch={architecture}][sdk={sdk}{sdk_version}] =",
    "CONAN_{name}_{name}_PREPROCESSOR_DEFINITIONS[config={configuration}][arch={architecture}][sdk={sdk}{sdk_version}] =",
    "CONAN_{name}_{name}_INCLUDE_DIRECTORIES[config={configuration}][arch={architecture}][sdk={sdk}{sdk_version}] =",
    "CONAN_{name}_{name}_RESOURCE_DIRECTORIES[config={configuration}][arch={architecture}][sdk={sdk}{sdk_version}] =",
    "CONAN_{name}_{name}_LIBRARY_DIRECTORIES[config={configuration}][arch={architecture}][sdk={sdk}{sdk_version}] =",
    "CONAN_{name}_{name}_LIBRARIES[config={configuration}][arch={architecture}][sdk={sdk}{sdk_version}] = -l{name}",
    "CONAN_{name}_{name}_SYSTEM_LIBS[config={configuration}][arch={architecture}][sdk={sdk}{sdk_version}] =",
    "CONAN_{name}_{name}_FRAMEWORKS_DIRECTORIES[config={configuration}][arch={architecture}][sdk={sdk}{sdk_version}] =",
    "CONAN_{name}_{name}_FRAMEWORKS[config={configuration}][arch={architecture}][sdk={sdk}{sdk_version}] = -framework framework_{name}"
]

_expected_conf_xconfig = [
    "#include \"{vars_name}\"",
    "HEADER_SEARCH_PATHS_{name}_{name} = $(CONAN_{name}_{name}_INCLUDE_DIRECTORIES",
    "GCC_PREPROCESSOR_DEFINITIONS_{name}_{name} = $(CONAN_{name}_{name}_PREPROCESSOR_DEFINITIONS",
    "OTHER_CFLAGS_{name}_{name} = $(CONAN_{name}_{name}_C_COMPILER_FLAGS",
    "OTHER_CPLUSPLUSFLAGS_{name}_{name} = $(CONAN_{name}_{name}_CXX_COMPILER_FLAGS",
    "FRAMEWORK_SEARCH_PATHS_{name}_{name} = $(CONAN_{name}_{name}_FRAMEWORKS_DIRECTORIES",
    "LIBRARY_SEARCH_PATHS_{name}_{name} = $(CONAN_{name}_{name}_LIBRARY_DIRECTORIES",
    "OTHER_LDFLAGS_{name}_{name} = $(CONAN_{name}_{name}_LINKER_FLAGS) $(CONAN_{name}_{name}_LIBRARIES) $(CONAN_{name}_{name}_SYSTEM_LIBS) $(CONAN_{name}_{name}_FRAMEWORKS"
]


def expected_files(current_folder, configuration, architecture, sdk_version):
    files = []
    name = _get_filename(configuration, architecture, sdk_version)
    deps = ["hello", "goodbye"]
    files.extend(
        [os.path.join(current_folder, "build", "generators", "conan_{dep}_{dep}{name}.xcconfig".format(dep=dep, name=name)) for dep in deps])
    files.extend(
        [os.path.join(current_folder,  "build", "generators", "conan_{dep}_{dep}_vars{name}.xcconfig".format(dep=dep, name=name)) for dep in deps])
    files.append(os.path.join(current_folder, "build", "generators", "conandeps.xcconfig"))
    return files


def check_contents(client, deps, configuration, architecture, sdk_version):
    for dep_name in deps:
        dep_xconfig = client.load(os.path.join("build", "generators",
                                               "conan_{dep}_{dep}.xcconfig".format(dep=dep_name)))
        conf_name = "conan_{}_{}{}.xcconfig".format(dep_name, dep_name,
                                                 _get_filename(configuration, architecture, sdk_version))

        assert '#include "{}"'.format(conf_name) in dep_xconfig
        for var in _expected_dep_xconfig:
            line = var.format(name=dep_name)
            assert line in dep_xconfig

        vars_name = "conan_{}_{}_vars{}.xcconfig".format(dep_name, dep_name,
                                                      _get_filename(configuration, architecture, sdk_version))
        conan_vars = client.load(os.path.join("build", "generators", vars_name))
        for var in _expected_vars_xconfig:
            line = var.format(name=dep_name, configuration=configuration, architecture=architecture,
                              sdk="macosx", sdk_version=sdk_version)
            assert line in conan_vars

        conan_conf = client.load(os.path.join("build", "generators", conf_name))
        for var in _expected_conf_xconfig:
            assert var.format(vars_name=vars_name, name=dep_name) in conan_conf


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
def test_generator_files():
    client = TestClient()
    client.save({"hello.py": GenConanfile().with_settings("os", "arch", "compiler", "build_type")
                                           .with_package_info(cpp_info={"libs": ["hello"],
                                                                        "frameworks": ['framework_hello']},
                                                              env_info={})})
    client.run("export hello.py --name=hello --version=0.1")
    client.save({"goodbye.py": GenConanfile().with_settings("os", "arch", "compiler", "build_type")
                                             .with_package_info(cpp_info={"libs": ["goodbye"],
                                                                          "frameworks": ['framework_goodbye']},
                                                                env_info={})})
    client.run("export goodbye.py --name=goodbye --version=0.1")
    client.save({"conanfile.txt": "[requires]\nhello/0.1\ngoodbye/0.1\n"}, clean_first=True)

    for build_type in ["Release", "Debug"]:

        client.run("install . -g XcodeDeps -s build_type={} -s arch=x86_64 -s os.sdk_version=12.1 --build missing".format(build_type))

        for config_file in expected_files(client.current_folder, build_type, "x86_64", "12.1"):
            assert os.path.isfile(config_file)

        conandeps = client.load(os.path.join("build", "generators", "conandeps.xcconfig"))
        assert '#include "conan_hello.xcconfig"' in conandeps
        assert '#include "conan_goodbye.xcconfig"' in conandeps

        conan_config = client.load(os.path.join("build", "generators", "conan_config.xcconfig"))
        assert '#include "conandeps.xcconfig"' in conan_config

        check_contents(client, ["hello", "goodbye"], build_type, "x86_64", "12.1")
