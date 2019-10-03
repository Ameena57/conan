import unittest
from textwrap import dedent

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, GenConanfile


class FullRevisionModeTest(unittest.TestCase):

    def recipe_revision_mode_test(self):
        liba_ref = ConanFileReference.loads("liba/0.1@user/testing")
        libb_ref = ConanFileReference.loads("libb/0.1@user/testing")

        clienta = TestClient()
        clienta.run("config set general.default_package_id_mode=recipe_revision_mode")
        conanfilea = dedent("""
            from conans import ConanFile
            from conans.tools import save
            import uuid, os
            class Pkg(ConanFile):
                def package(self):
                    save(os.path.join(self.package_folder, "file.txt"),
                         str(uuid.uuid1()))
            """)
        clienta.save({"conanfile.py": conanfilea})
        clienta.run("create . liba/0.1@user/testing")

        clientb = TestClient(cache_folder=clienta.cache_folder)
        clientb.save({"conanfile.py": GenConanfile().with_name("libb").with_version("0.1")
                                                    .with_require(liba_ref)})
        clientb.run("create . user/testing")

        clientc = TestClient(cache_folder=clienta.cache_folder)
        clientc.save({"conanfile.py": GenConanfile().with_name("libc").with_version("0.1")
                                                    .with_require(libb_ref)})
        clientc.run("install . user/testing")

        # Do a minor change to the recipe, it will change the recipe revision
        clienta.save({"conanfile.py": conanfilea + "# comment"})
        clienta.run("create . liba/0.1@user/testing")

        clientc.run("install . user/testing", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'libb/0.1@user/testing'", clientc.out)
        # Building b with the new recipe revision of liba works
        clientc.run("install . user/testing --build=libb")

        # Now change only the package revision of liba
        clienta.run("create . liba/0.1@user/testing")
        clientc.run("install . user/testing")
        clientc.run("config set general.default_package_id_mode=package_revision_mode")
        clientc.run("install . user/testing", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'libb/0.1@user/testing'", clientc.out)
        clientc.run("install . user/testing --build=libb")
        clientc.run("info . --build-order=ALL")

        clienta.run("create . liba/0.1@user/testing")
        clientc.run("install . user/testing", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'libb/0.1@user/testing'", clientc.out)

        clienta.run("create . liba/0.1@user/testing")
        clientc.run("info . --build-order=ALL")

    def binary_id_recomputation_after_build_test(self):
        clienta = TestClient()
        clienta.run("config set general.default_package_id_mode=recipe_revision_mode")
        conanfile = dedent("""
            from conans import ConanFile
            from conans.tools import save
            import uuid, os
            class Pkg(ConanFile):
                %s
                def package(self):
                    save(os.path.join(self.package_folder, "file.txt"),
                         str(uuid.uuid1()))
            """)
        clienta.save({"conanfile.py": conanfile % ""})
        clienta.run("create . liba/0.1@user/testing")

        clientb = TestClient(cache_folder=clienta.cache_folder)
        clientb.save({"conanfile.py": conanfile % "requires = 'liba/0.1@user/testing'"})
        clientb.run("config set general.default_package_id_mode=package_revision_mode")
        clientb.run("create . libb/0.1@user/testing")

        clientc = TestClient(cache_folder=clienta.cache_folder)
        clientc.save({"conanfile.py": conanfile % "requires = 'libb/0.1@user/testing'"})
        clientc.run("config set general.default_package_id_mode=package_revision_mode")
        clientc.run("create . libc/0.1@user/testing")

        clientd = TestClient(cache_folder=clienta.cache_folder)
        clientd.run("config set general.default_package_id_mode=package_revision_mode")
        clientd.save({"conanfile.py": conanfile % "requires = 'libc/0.1@user/testing'"})
        clientd.run("install . libd/0.1@user/testing")

        # Change A PREV
        clienta.run("create . liba/0.1@user/testing")
        clientd.run("install . libd/0.1@user/testing", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'libb/0.1@user/testing'", clientd.out)
        clientd.run("install . libd/0.1@user/testing --build=missing")

        self.assertIn("libc/0.1@user/testing: Unknown binary", clientd.out)
        self.assertIn("libc/0.1@user/testing: Updated ID", clientd.out)
        self.assertIn("libc/0.1@user/testing: Binary for updated ID from: Build", clientd.out)
        self.assertIn("libc/0.1@user/testing: Calling build()", clientd.out)

    def binary_id_recomputation_with_build_requires_test(self):
        clienta = TestClient()
        clienta.save({"conanfile.py": GenConanfile().with_name("Tool").with_version("0.1")
                                                    .with_package_info(cpp_info={"libs":
                                                                                 ["tool.lib"]},
                                                                       env_info={})})
        clienta.run("create . user/testing")
        clienta.run("config set general.default_package_id_mode=recipe_revision_mode")
        conanfile = dedent("""
            from conans import ConanFile
            from conans.tools import save
            import uuid, os
            class Pkg(ConanFile):
                build_requires = "Tool/0.1@user/testing"
                %s
                def build(self):
                    self.output.info("TOOLS LIBS: {}".format(self.deps_cpp_info["Tool"].libs))
                def package(self):
                    save(os.path.join(self.package_folder, "file.txt"),
                         str(uuid.uuid1()))
            """)
        clienta.save({"conanfile.py": conanfile % ""})
        clienta.run("create . liba/0.1@user/testing")

        clientb = TestClient(cache_folder=clienta.cache_folder)
        clientb.save({"conanfile.py": conanfile % "requires = 'liba/0.1@user/testing'"})
        clientb.run("config set general.default_package_id_mode=package_revision_mode")
        clientb.run("create . libb/0.1@user/testing")

        clientc = TestClient(cache_folder=clienta.cache_folder)
        clientc.save({"conanfile.py": conanfile % "requires = 'libb/0.1@user/testing'"})
        clientc.run("config set general.default_package_id_mode=package_revision_mode")
        clientc.run("create . libc/0.1@user/testing")

        clientd = TestClient(cache_folder=clienta.cache_folder)
        clientd.run("config set general.default_package_id_mode=package_revision_mode")
        clientd.save({"conanfile.py": conanfile % "requires = 'libc/0.1@user/testing'"})
        clientd.run("install . libd/0.1@user/testing")

        # Change A PREV
        clienta.run("create . liba/0.1@user/testing")
        clientd.run("install . libd/0.1@user/testing", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'libb/0.1@user/testing'", clientd.out)
        clientd.run("install . libd/0.1@user/testing --build=missing")

        self.assertIn("libc/0.1@user/testing: Unknown binary", clientd.out)
        self.assertIn("libc/0.1@user/testing: Updated ID", clientd.out)
        self.assertIn("libc/0.1@user/testing: Binary for updated ID from: Build", clientd.out)
        self.assertIn("libc/0.1@user/testing: Calling build()", clientd.out)

    def reusing_artifacts_after_build_test(self):
        # An unknown binary that after build results in the exact same PREF with PREV, doesn't
        # fire build of downstream
        client = TestClient()
        client.run("config set general.default_package_id_mode=package_revision_mode")
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . liba/0.1@user/testing")

        client.save({"conanfile.py": GenConanfile().with_require_plain('liba/0.1@user/testing')})
        client.run("create . libb/0.1@user/testing")

        client.save({"conanfile.py": GenConanfile().with_require_plain('libb/0.1@user/testing')})
        client.run("create . libc/0.1@user/testing")

        client.save({"conanfile.py": GenConanfile().with_require_plain('libc/0.1@user/testing')})
        # Telling to build LibA doesn't change the final result of LibA, which has same ID and PREV
        client.run("install . libd/0.1@user/testing --build=liba")
        # So it is not necessary to build the downstream consumers of LibA
        for lib in ("libb", "libc"):
            self.assertIn("%s/0.1@user/testing: Unknown binary" % lib, client.out)
            self.assertIn("%s/0.1@user/testing: Updated ID" % lib, client.out)
            self.assertIn("%s/0.1@user/testing: Binary for updated ID from: Cache" % lib, client.out)
            self.assertIn("%s/0.1@user/testing: Already installed!" % lib, client.out)


class PackageRevisionModeTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()
        self.client.run("config set general.revisions_enabled=1")
        self.client.run("config set general.default_package_id_mode=package_revision_mode")

    def _generate_graph(self, dependencies, names_versions):
        refs = {}
        for name, version in names_versions:
            refs[name] = {"ref": ConanFileReference(name, version, None, None, None),
                          "conanfile": GenConanfile().with_name(name).with_version(version)}

        for name, data in refs.items():
            for dep in dependencies[name]:
                conanfile = refs[name]["conanfile"]
                refs[name]["conanfile"] = conanfile.with_require(refs[dep]["ref"])

        for name, data in refs.items():
            filename = "%s.py" % name
            self.client.save({filename: data["conanfile"]})
            self.client.run("export %s" % filename)
        return refs

    def simple_dependency_graph_test(self):
        dependencies = {
            "Log4Qt": [],
            "MccApi": ["Log4Qt"],
            "Util": ["MccApi"],
            "Invent": ["Util"]
        }
        names_versions = [("Log4Qt", "0.3.0"), ("MccApi", "3.0.9"), ("Util", "0.3.5"),
                          ("Invent", "1.0")]
        self._generate_graph(dependencies, names_versions)

        self.client.run("install Invent.py --build missing")
        self.assertIn("MccApi/3.0.9: Package '484784c96c359def1283e7354eec200f9f9c5cd8' created",
                      self.client.out)
        self.assertIn("Util/0.3.5: Package 'ba438cd9d192b914edb1669b3e0149822290f7d8' created",
                      self.client.out)

    def triangle_dependency_graph_test(self):
        dependencies = {
            "Log4Qt": [],
            "MccApi": ["Log4Qt"],
            "Util": ["MccApi"],
            "GenericSU": ["Log4Qt", "MccApi", "Util"]
                        }
        names_versions = [("Log4Qt", "0.3.0"),
                          ("MccApi", "3.0.9"),
                          ("Util", "0.3.5"),
                          ("GenericSU", "0.3.5")]
        self._generate_graph(dependencies, names_versions)

        self.client.run("install GenericSU.py --build missing")
        self.assertIn("MccApi/3.0.9: Package '484784c96c359def1283e7354eec200f9f9c5cd8' created",
                      self.client.out)
        self.assertIn("Util/0.3.5: Package 'ba438cd9d192b914edb1669b3e0149822290f7d8' created",
                      self.client.out)

    def diamond_dependency_graph_test(self):
        dependencies = {
            "Log4Qt": [],
            "MccApi": ["Log4Qt"],
            "Util": ["Log4Qt"],
            "GenericSU": ["MccApi", "Util"]
                        }
        names_versions = [("Log4Qt", "0.3.0"),
                          ("MccApi", "3.0.9"),
                          ("Util", "0.3.5"),
                          ("GenericSU", "0.3.5")]
        self._generate_graph(dependencies, names_versions)

        self.client.run("install GenericSU.py --build missing")
        self.assertIn("MccApi/3.0.9: Package '484784c96c359def1283e7354eec200f9f9c5cd8' created",
                      self.client.out)
        self.assertIn("Util/0.3.5: Package '484784c96c359def1283e7354eec200f9f9c5cd8' created",
                      self.client.out)

    def full_dependency_graph_test(self):
        dependencies = {
            "Log4Qt": [],
            "MccApi": ["Log4Qt"],
            "Util": ["MccApi"],
            "GenericSU": ["Log4Qt", "MccApi", "Util"],
            "ManagementModule": ["Log4Qt", "MccApi", "Util"],
            "StationInterfaceModule": ["ManagementModule", "GenericSU"],
            "PleniterGenericSuApp": ["ManagementModule", "GenericSU", "Log4Qt", "MccApi", "Util"],
            "StationinterfaceRpm": ["StationInterfaceModule", "PleniterGenericSuApp"]
                        }
        names_versions = [("Log4Qt", "0.3.0"),
                          ("MccApi", "3.0.9"),
                          ("Util", "0.3.5"),
                          ("GenericSU", "0.3.5"),
                          ("ManagementModule", "0.3.5"),
                          ("StationInterfaceModule", "0.13.0"),
                          ("PleniterGenericSuApp", "0.1.8"),
                          ("StationinterfaceRpm", "2.2.0")]
        self._generate_graph(dependencies, names_versions)

        self.client.run("install StationinterfaceRpm.py --build missing")
        self.assertIn("Log4Qt/0.3.0: Package '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9' created",
                      self.client.out)
        self.assertIn("MccApi/3.0.9: Package '484784c96c359def1283e7354eec200f9f9c5cd8' created",
                      self.client.out)
        self.assertIn("Util/0.3.5: Package 'ba438cd9d192b914edb1669b3e0149822290f7d8' created",
                      self.client.out)
        self.assertIn("GenericSU/0.3.5: Package '2d950a3e4c53e41a8a8946cc4d0eb8f5ef13510a' created",
                      self.client.out)
        self.assertIn("ManagementModule/0.3.5: Package '2d950a3e4c53e41a8a8946cc4d0eb8f5ef13510a' "
                      "created", self.client.out)
        self.assertIn("PleniterGenericSuApp/0.1.8: Package "
                      "'69dda8da2b232bcff8af1579b0f37b34ef7b1829' created", self.client.out)
        self.assertIn("StationInterfaceModule/0.13.0: Package "
                      "'69dda8da2b232bcff8af1579b0f37b34ef7b1829' create", self.client.out)