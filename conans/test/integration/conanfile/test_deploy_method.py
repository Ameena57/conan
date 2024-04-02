import textwrap

from conans.test.utils.tools import TestClient


def test_deploy_method():
    c = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import copy, save
        class Pkg(ConanFile):
            name = "{name}"
            version = "0.1"
            {requires}
            def package(self):
                save(self, os.path.join(self.package_folder, f"my{name}file.txt"), "HELLO!!!!")
            def deploy(self):
                copy(self, "*", src=self.package_folder, dst=self.deploy_folder)
            """)
    c.save({"dep/conanfile.py": conanfile.format(name="dep", requires=""),
            "pkg/conanfile.py": conanfile.format(name="pkg", requires="requires='dep/0.1'")})
    c.run("create dep")
    assert "Executing deploy()" not in c.out
    c.run("create pkg")
    assert "Executing deploy()" not in c.out

    # Doesn't install by default
    c.run("install --requires=pkg/0.1")
    assert "Executing deploy()" not in c.out

    # Doesn't install with other patterns
    c.run("install --requires=pkg/0.1 --deployer-package=other")
    assert "Executing deploy()" not in c.out

    # install can deploy all
    c.run("install --requires=pkg/0.1 --deployer-package=* --deployer-folder=mydeploy")
    assert "dep/0.1: Executing deploy()" in c.out
    assert "pkg/0.1: Executing deploy()" in c.out
    assert c.load("mydeploy/mydepfile.txt") == "HELLO!!!!"
    assert c.load("mydeploy/mypkgfile.txt") == "HELLO!!!!"

    # install can deploy only "pkg"
    c.run("install --requires=pkg/0.1 --deployer-package=pkg/* --deployer-folder=mydeploy")
    assert "dep/0.1: Executing deploy()" not in c.out
    assert "pkg/0.1: Executing deploy()" in c.out


def test_deploy_local():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import copy
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            def deploy(self):
                copy(self, "*", src=self.package_folder, dst=self.deploy_folder)
        """)
    c.save({"conanfile.py": conanfile})
    c.run("install . --deployer-package=*", assert_error=True)
    assert "ERROR: conanfile.py (pkg/0.1): Error in deploy() method, line 8" in c.out
    assert "copy() received 'src=None' argument" in c.out

    # Without name/version same error
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            def deploy(self):
                assert self.package_folder  # will fail if None
        """)
    c.save({"conanfile.py": conanfile})
    c.run("install . --deployer-package=*", assert_error=True)
    assert "ERROR: conanfile.py: Error in deploy() method, line 5" in c.out

    # I can exclude the current consumer, it won't fail
    c.run("install . --deployer-package=!& --deployer-package=*")
    assert "Install finished successfully" in c.out
