import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.fixture()
def client():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.microsoft import MSBuild

        class Pkg(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            def build(self):
                ms = MSBuild(self)
                self.output.info(ms.command("Project.sln"))
        """)
    client.save({"conanfile.py": conanfile})
    yield client


def test_msbuild_no_config(client):
    profile = textwrap.dedent("""\
        [settings]
        os=Windows
        arch=x86_64
        compiler=Visual Studio
        compiler.version=15
        compiler.runtime=MD
        build_type=Release
        """)
    client.save({"myprofile": profile})
    client.run("create . pkg/0.1@ -pr=myprofile")
    assert "verbosity" not in client.out


def test_msbuild_config(client):
    profile = textwrap.dedent("""\
        [settings]
        os=Windows
        arch=x86_64
        compiler=Visual Studio
        compiler.version=15
        compiler.runtime=MD
        build_type=Release
        [conf]
        tools.microsoft.MSBuild:verbosity=Minimal
        """)
    client.save({"myprofile": profile})
    client.run("create . pkg/0.1@ -pr=myprofile")
    assert "/verbosity:Minimal" in client.out


def test_msbuild_config_error(client):
    profile = textwrap.dedent("""\
        [settings]
        os=Windows
        arch=x86_64
        compiler=Visual Studio
        compiler.version=15
        compiler.runtime=MD
        build_type=Release
        [conf]
        tools.microsoft.MSBuild:verbosity=non-existing
        """)
    client.save({"myprofile": profile})
    client.run("create . pkg/0.1@ -pr=myprofile", assert_error=True)
    assert "Uknown MSBuild verbosity: non-existing" in client.out
