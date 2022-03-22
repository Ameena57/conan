import platform
import textwrap
import time
import unittest

import pytest

from conans.test.utils.tools import TestClient, GenConanfile
from conans.util.files import save


class CompatibleIDsTest(unittest.TestCase):

    def test_compatible_setting(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                settings = "os", "compiler"
                def compatibility(self):
                    if self.settings.compiler == "gcc" and self.settings.compiler.version == "4.9":
                        return [{"settings": [("compiler.version", v)]}
                                for v in ("4.8", "4.7", "4.6")]

                def package_info(self):
                    self.output.info("PackageInfo!: Gcc version: %s!"
                                     % self.settings.compiler.version)
            """)
        profile = textwrap.dedent("""
            [settings]
            os = Linux
            compiler=gcc
            compiler.version=4.9
            compiler.libcxx=libstdc++
            """)
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})
        # Create package with gcc 4.8
        client.run("create . --name=pkg --version=0.1 --user=user --channel=stable -pr=myprofile -s compiler.version=4.8")
        package_id = client.created_package_id("pkg/0.1@user/stable")

        # package can be used with a profile gcc 4.9 falling back to 4.8 binary
        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile")
        self.assertIn("pkg/0.1@user/stable: PackageInfo!: Gcc version: 4.8!", client.out)
        client.assert_listed_binary({"pkg/0.1@user/stable": (package_id, "Cache")})
        self.assertIn("pkg/0.1@user/stable: Already installed!", client.out)

    def test_compatible_setting_no_binary(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
           from conan import ConanFile

           class Pkg(ConanFile):
               settings = "os", "compiler"
               def compatibility(self):
                    if self.settings.compiler == "gcc" and self.settings.compiler.version == "4.9":
                        return [{"settings": [("compiler.version", v)]}
                                for v in ("4.8", "4.7", "4.6")]
               def package_info(self):
                   self.output.info("PackageInfo!: Gcc version: %s!"
                                    % self.settings.compiler.version)
           """)
        profile = textwrap.dedent("""
           [settings]
           os = Linux
           compiler=gcc
           compiler.version=4.9
           compiler.libcxx=libstdc++
           """)
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})
        # Create package with gcc 4.8
        client.run("export . --name=pkg --version=0.1 --user=user --channel=stable")
        self.assertIn("pkg/0.1@user/stable: Exported revision: d165eb4bcdd1c894a97d2a212956f5fe",
                      client.out)

        # package can be used with a profile gcc 4.9 falling back to 4.8 binary
        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1@user/stable")})
        # No fallback
        client.run("install . -pr=myprofile --build=missing")
        self.assertIn("pkg/0.1@user/stable: PackageInfo!: Gcc version: 4.9!", client.out)
        client.assert_listed_binary({"pkg/0.1@user/stable":
                                     ("c6715d73365c2dd62f68836b2dee8359a312ff12", "Build")})

    def test_compatible_setting_no_user_channel(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                settings = "os", "compiler"
                def compatibility(self):
                    if self.settings.compiler == "gcc" and self.settings.compiler.version == "4.9":
                        return [{"settings": [("compiler.version", v)]}
                                for v in ("4.8", "4.7", "4.6")]
            """)
        profile = textwrap.dedent("""
            [settings]
            os = Linux
            compiler=gcc
            compiler.version=4.9
            compiler.libcxx=libstdc++
            """)
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})

        # No user/channel
        client.run("create . --name=pkg --version=0.1 -pr=myprofile -s compiler.version=4.8")
        package_id = client.created_package_id("pkg/0.1")

        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1")})
        client.run("install . -pr=myprofile")
        client.assert_listed_binary({"pkg/0.1": (package_id, "Cache")})
        self.assertIn("pkg/0.1: Already installed!", client.out)

    def test_compatible_option(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                options = {"optimized": [1, 2, 3]}
                default_options = {"optimized": 1}

                def compatibility(self):
                    return [{"options": [("optimized", v)]}
                            for v in range(int(self.options.optimized), 0, -1)]

                def package_info(self):
                    self.output.info("PackageInfo!: Option optimized %s!"
                                     % self.options.optimized)
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=stable")
        package_id = client.created_package_id("pkg/0.1@user/stable")
        self.assertIn(f"pkg/0.1@user/stable: Package '{package_id}' created", client.out)

        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1@user/stable")})
        client.run("install . -o pkg/*:optimized=2")
        # Information messages
        missing_id = "508da41e46d27c4c4996d7b31df7942c7bba1e27"
        self.assertIn("pkg/0.1@user/stable: PackageInfo!: Option optimized 1!", client.out)
        self.assertIn("pkg/0.1@user/stable: Compatible package ID "
                      f"{missing_id} equal to the default package ID",
                      client.out)
        self.assertIn("pkg/0.1@user/stable: Main binary package "
                      f"'{missing_id}' missing. Using compatible package"
                      f" '{package_id}'", client.out)
        # checking the resulting dependencies
        client.assert_listed_binary({"pkg/0.1@user/stable": (package_id, "Cache")})
        self.assertIn("pkg/0.1@user/stable: Already installed!", client.out)
        client.run("install . -o pkg/*:optimized=3")
        client.assert_listed_binary({"pkg/0.1@user/stable": (package_id, "Cache")})
        self.assertIn("pkg/0.1@user/stable: Already installed!", client.out)

    def test_package_id_consumers(self):
        # If we fallback to a different binary upstream and we are using a "package_revision_mode"
        # the current package should have a different binary package ID too.
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                settings = "os", "compiler"
                def compatibility(self):
                    return [{"settings": [("compiler.version", "4.8")]}]
                def package_info(self):
                    self.output.info("PackageInfo!: Gcc version: %s!"
                                     % self.settings.compiler.version)
            """)
        profile = textwrap.dedent("""
            [settings]
            os = Linux
            compiler=gcc
            compiler.version=4.9
            compiler.libcxx=libstdc++
            """)
        save(client.cache.new_config_path,
             "core.package_id:default_unknown_mode=recipe_revision_mode")
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})
        # Create package with gcc 4.8
        client.run("create . --name=pkg --version=0.1 --user=user --channel=stable "
                   "-pr=myprofile -s compiler.version=4.8")
        package_id = client.created_package_id("pkg/0.1@user/stable")
        self.assertIn(f"pkg/0.1@user/stable: Package '{package_id}'"
                      " created", client.out)

        # package can be used with a profile gcc 4.9 falling back to 4.8 binary
        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1@user/stable")})
        client.run("create . --name=consumer --version=0.1 --user=user --channel=stable -pr=myprofile")
        self.assertIn("pkg/0.1@user/stable: PackageInfo!: Gcc version: 4.8!", client.out)
        client.assert_listed_binary({"pkg/0.1@user/stable": (package_id, "Cache")})
        self.assertIn("pkg/0.1@user/stable: Already installed!", client.out)
        consumer_id = "b1e86fb9bafd7388fdafb0882a6ea0a1e366e59f"
        client.assert_listed_binary({"consumer/0.1@user/stable": (consumer_id, "Build")})
        self.assertIn(f"consumer/0.1@user/stable: Package '{consumer_id}' created", client.out)

        # Create package with gcc 4.9
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=stable -pr=myprofile")
        self.assertIn("pkg/0.1@user/stable: Package 'c6715d73365c2dd62f68836b2dee8359a312ff12'"
                      " created", client.out)

        # Consume it
        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1@user/stable")})
        client.run("create . --name=consumer --version=0.1 --user=user --channel=stable -pr=myprofile")
        self.assertIn("pkg/0.1@user/stable: PackageInfo!: Gcc version: 4.9!", client.out)
        client.assert_listed_binary({"pkg/0.1@user/stable":
                                         ("c6715d73365c2dd62f68836b2dee8359a312ff12", "Cache")})
        self.assertIn("pkg/0.1@user/stable: Already installed!", client.out)
        consumer_id = "3d3958b1d42fd882cbcf0f702aab5c5d0b2a8333"
        client.assert_listed_binary({"consumer/0.1@user/stable": (consumer_id, "Build")})
        self.assertIn(f"consumer/0.1@user/stable: Package '{consumer_id}' created", client.out)

    def test_build_missing(self):
        # https://github.com/conan-io/conan/issues/6133
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Conan(ConanFile):
                settings = "os"

                def compatibility(self):
                    if self.settings.os == "Windows":
                        return [{"settings": [("os", "Linux")]}]
                """)

        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing -s os=Linux")
        package_id = client.created_package_id("pkg/0.1@user/testing")
        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1@user/testing")})
        client.run("install . -s os=Windows --build=missing")
        client.assert_listed_binary({"pkg/0.1@user/testing": (package_id, "Cache")})
        self.assertIn("pkg/0.1@user/testing: Already installed!", client.out)

    def test_compatible_package_python_requires(self):
        # https://github.com/conan-io/conan/issues/6609
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . --name=tool --version=0.1")
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Conan(ConanFile):
                settings = "os"
                python_requires = "tool/0.1"

                def compatibility(self):
                    if self.settings.os == "Windows":
                        return [{"settings": [("os", "Linux")]}]
                """)

        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing -s os=Linux")
        package_id = client.created_package_id("pkg/0.1@user/testing")
        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1@user/testing")})
        client.run("install . -s os=Windows")
        client.assert_listed_binary({"pkg/0.1@user/testing": (package_id, "Cache")})
        self.assertIn("pkg/0.1@user/testing: Already installed!", client.out)

    @pytest.mark.xfail(reason="lockfiles have been deactivated at the moment")
    def test_compatible_lockfile(self):
        # https://github.com/conan-io/conan/issues/9002
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                settings = "os"
                def compatibility(self):
                    if self.settings.os == "Windows":
                        return [{"settings": [("os", "Linux")]}]
                def package_info(self):
                    self.output.info("PackageInfo!: OS: %s!" % self.settings.os)
            """)

        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=stable -s os=Linux")
        self.assertIn("pkg/0.1@user/stable: PackageInfo!: OS: Linux!", client.out)
        self.assertIn("pkg/0.1@user/stable: Package 'cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31'"
                      " created", client.out)

        client.save({"conanfile.py": GenConanfile().with_require("pkg/0.1@user/stable")})
        client.run("lock create conanfile.py -s os=Windows --lockfile-out=deps.lock")
        client.run("install conanfile.py --lockfile=deps.lock")
        self.assertIn("pkg/0.1@user/stable: PackageInfo!: OS: Linux!", client.out)
        self.assertIn("pkg/0.1@user/stable:cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31", client.out)
        self.assertIn("pkg/0.1@user/stable: Already installed!", client.out)

    def test_compatible_diamond(self):
        # https://github.com/conan-io/conan/issues/9880
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                {}
                settings = "build_type"
                def compatibility(self):
                    if self.settings.build_type == "Debug":
                       return [{{"settings": [("build_type", "Release")]}}]
                """)

        private = """def requirements(self):
        self.requires("pkga/0.1", visible=False)
        """
        client.save({"pkga/conanfile.py": conanfile.format(""),
                     "pkgb/conanfile.py": conanfile.format(private),
                     "pkgc/conanfile.py": conanfile.format('requires = "pkga/0.1"'),
                     "pkgd/conanfile.py": conanfile.format('requires = "pkgb/0.1", "pkgc/0.1"')
                     })
        client.run("create pkga --name=pkga --version=0.1 -s build_type=Release")
        client.run("create pkgb --name=pkgb --version=0.1 -s build_type=Release")
        client.run("create pkgc --name=pkgc --version=0.1 -s build_type=Release")

        client.run("install pkgd -s build_type=Debug")
        assert "pkga/0.1: Main binary package '040ce2bd0189e377b2d15eb7246a4274d1c63317' missing" \
               in client.out
        client.assert_listed_binary({"pkga/0.1":
                                         ("e53d55fd33066c49eb97a4ede6cb50cd8036fe8b", "Cache")})


@pytest.mark.xfail(reason="The conf core.package_id:msvc_visual_incompatible is not passed yet")
def test_msvc_visual_incompatible():
    conanfile = GenConanfile().with_settings("os", "compiler", "build_type", "arch")
    client = TestClient()
    profile = textwrap.dedent("""
        [settings]
        os=Windows
        compiler=msvc
        compiler.version=191
        compiler.runtime=dynamic
        compiler.cppstd=14
        build_type=Release
        arch=x86_64
        """)
    client.save({"conanfile.py": conanfile,
                 "profile": profile})
    client.run('create . --name=pkg --version=0.1 -s os=Windows -s compiler="Visual Studio" -s compiler.version=15 '
               '-s compiler.runtime=MD -s build_type=Release -s arch=x86_64')
    client.run("install --requires=pkg/0.1@ -pr=profile")
    assert "Using compatible package" in client.out
    new_config = "core.package_id:msvc_visual_incompatible=1"
    save(client.cache.new_config_path, new_config)
    client.run("install --requires=pkg/0.1@ -pr=profile", assert_error=True)
    assert "ERROR: Missing prebuilt package for 'pkg/0.1'" in client.out


@pytest.mark.skipif(platform.system() != "Darwin", reason="requires OSX")
def test_apple_clang_compatible():
    """
    From apple-clang version 13 we detect apple-clang version as 13 and we make
    this compiler version compatible with 13.0
    """
    conanfile = GenConanfile().with_settings("os", "compiler", "build_type", "arch")
    client = TestClient()
    profile = textwrap.dedent("""
        [settings]
        os=Macos
        arch=x86_64
        compiler=apple-clang
        compiler.version=13
        compiler.libcxx=libc++
        build_type=Release
        """)
    client.save({"conanfile.py": conanfile,
                 "profile": profile})
    client.run('create . --name=pkg --version=0.1 -s os=Macos -s compiler="apple-clang" -s compiler.version=13.0 '
               '-s build_type=Release -s arch=x86_64')
    client.run("install --requires=pkg/0.1@ -pr=profile")
    assert "Using compatible package" in client.out
