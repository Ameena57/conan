import textwrap

from conans.test.utils.tools import TestClient


class TestValidPackageIdValue:

    def test_valid(self):
        c = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                options = {"shared": [False, True]}
            """)

        c.save({"conanfile.py": conanfile})

        c.run("create . --name=pkg --version=0.1", assert_error=True)
        assert "pkg/0.1: Invalid: 'options.shared' doesn't have a value." in c.out
