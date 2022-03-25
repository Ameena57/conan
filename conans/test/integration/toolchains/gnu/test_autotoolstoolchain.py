import os
import platform
import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import load


def test_extra_flags_via_conf():
    os_ = platform.system()
    os_ = "Macos" if os_ == "Darwin" else os_

    profile = textwrap.dedent("""
        [settings]
        os=%s
        compiler=gcc
        compiler.version=6
        compiler.libcxx=libstdc++11
        arch=armv8
        build_type=Release

        [conf]
        tools.build:cxxflags=["--flag1", "--flag2"]
        tools.build:cflags+=["--flag3", "--flag4"]
        tools.build:ldflags+=["--flag5", "--flag6"]
        tools.build:cppflags+=["DEF1", "DEF2"]
        """ % os_)
    client = TestClient()
    conanfile = GenConanfile().with_settings("os", "arch", "compiler", "build_type")\
        .with_generator("AutotoolsToolchain")
    client.save({"conanfile.py": conanfile,
                "profile": profile})
    client.run("install . --profile:build=profile --profile:host=profile")
    toolchain = client.load("conanautotoolstoolchain{}".format('.bat' if os_ == "Windows" else '.sh'))
    if os_ == "Windows":
        assert 'set "CPPFLAGS=%CPPFLAGS% -DNDEBUG -DDEF1 -DDEF2"' in toolchain
        assert 'set "CXXFLAGS=%CXXFLAGS% -O3 -s --flag1 --flag2"' in toolchain
        assert 'set "CFLAGS=%CFLAGS% -O3 -s --flag3 --flag4"' in toolchain
        assert 'set "LDFLAGS=%LDFLAGS% --flag5 --flag6"' in toolchain
    else:
        assert 'export CPPFLAGS="$CPPFLAGS -DNDEBUG -DDEF1 -DDEF2"' in toolchain
        assert 'export CXXFLAGS="$CXXFLAGS -O3 -s --flag1 --flag2"' in toolchain
        assert 'export CFLAGS="$CFLAGS -O3 -s --flag3 --flag4"' in toolchain
        assert 'export LDFLAGS="$LDFLAGS --flag5 --flag6"' in toolchain


def test_autotools_custom_environment():
    client = TestClient()
    conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.gnu import AutotoolsToolchain

            class Conan(ConanFile):
                settings = "os"
                def generate(self):
                    at = AutotoolsToolchain(self)
                    env = at.environment()
                    env.define("FOO", "BAR")
                    at.generate(env)
            """)

    client.save({"conanfile.py": conanfile})
    client.run("install . -s:b os=Linux -s:h os=Linux")
    content = load(os.path.join(client.current_folder,  "conanautotoolstoolchain.sh"))
    assert 'export FOO="BAR"' in content
