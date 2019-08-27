# coding=utf-8

import textwrap

from conans.client.graph.graph import CONTEXT_HOST, CONTEXT_BUILD
from conans.model.profile import Profile
from conans.model.ref import ConanFileReference
from conans.test.functional.cross_building.graph.protoc_basic_test import ClassicProtocExampleBase
from conans.util.files import save


class ProtocWithGTestExample(ClassicProtocExampleBase):
    """ Built on top of the ClassicProtocExample, in this use case we are adding a testing library
        to the project: we add gtest as a build_require and also the protoc executable, BUT
        both of them should be compiled for the host platform, we are running tests in the host!
    """

    gtest = textwrap.dedent("""
        from conans import ConanFile

        class GTest(ConanFile):
            name = "gtest"
            version = "testing"

            settings = "os"  # , "arch", "compiler", "build_type"

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
    """)

    application = textwrap.dedent("""
        from conans import ConanFile

        class Protoc(ConanFile):
            name = "application"
            version = "testing"

            settings = "os"
            
            def requirements(self):
                self.requires("protobuf/testing@user/channel")

            def build_requirements(self):
                self.build_requires("protoc/testing@user/channel", force_host_context=False)
                # Make it explicit that these should be for host_machine
                self.build_requires("protoc/testing@user/channel", force_host_context=True)
                self.build_requires("gtest/testing@user/channel", force_host_context=True)

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
    """)

    gtest_ref = ConanFileReference.loads("gtest/testing@user/channel")
    application_ref = ConanFileReference.loads("application/testing@user/channel")

    def setUp(self):
        super(ProtocWithGTestExample, self).setUp()
        self._cache_recipe(self.gtest_ref, self.protobuf)
        self._cache_recipe(self.application_ref, self.application)

        save(self.cache.settings_path, self.settings_yml)

    def test_not_crossbuilding(self):
        """ Build_requires uses 'force_host_context=False', but no profile for build_machine """
        profile_host = Profile()
        profile_host.settings["os"] = "Host"
        profile_host.process_settings(self.cache)

        try:
            deps_graph = self._build_graph(profile_host=profile_host, profile_build=None)
        except Exception as e:
            self.fail("ERROR! Although the recipe specifies 'force_host_context=False', as we"
                      " are not providing a profile for the build_machine, the context will be"
                      " host for this build_require.\n Exception has been: {}".format(e))
        else:
            # Check packages (all are HOST packages)
            application = deps_graph.root.dependencies[0].dst
            self.assertEqual(len(application.dependencies), 3)
            self.assertEqual(application.conanfile.name, "application")
            self.assertEqual(application.context, CONTEXT_HOST)
            self.assertEqual(application.conanfile.settings.os, profile_host.settings['os'])

            protobuf_host = application.dependencies[0].dst
            self.assertEqual(protobuf_host.conanfile.name, "protobuf")
            self.assertEqual(protobuf_host.context, CONTEXT_HOST)
            self.assertEqual(protobuf_host.conanfile.settings.os, profile_host.settings['os'])

            protoc_host = application.dependencies[1].dst
            self.assertEqual(protoc_host.conanfile.name, "protoc")
            self.assertEqual(protoc_host.context, CONTEXT_HOST)
            self.assertEqual(protoc_host.conanfile.settings.os, profile_host.settings['os'])

            protoc_protobuf_host = protoc_host.dependencies[0].dst
            self.assertEqual(protoc_protobuf_host, protobuf_host)

            gtest_host = application.dependencies[2].dst
            self.assertEqual(gtest_host.conanfile.name, "gtest")
            self.assertEqual(gtest_host.context, CONTEXT_HOST)
            self.assertEqual(gtest_host.conanfile.settings.os, profile_host.settings['os'])

    def test_crossbuilding(self):
        profile_host = Profile()
        profile_host.settings["os"] = "Host"
        profile_host.process_settings(self.cache)

        profile_build = Profile()
        profile_build.settings["os"] = "Build"
        profile_build.process_settings(self.cache)

        deps_graph = self._build_graph(profile_host=profile_host, profile_build=profile_build)

        # Check HOST packages
        application = deps_graph.root.dependencies[0].dst
        self.assertEqual(len(application.dependencies), 4)
        self.assertEqual(application.conanfile.name, "application")
        self.assertEqual(application.context, CONTEXT_HOST)
        self.assertEqual(application.conanfile.settings.os, profile_host.settings['os'])

        protobuf_host = application.dependencies[0].dst
        self.assertEqual(protobuf_host.conanfile.name, "protobuf")
        self.assertEqual(protobuf_host.context, CONTEXT_HOST)
        self.assertEqual(protobuf_host.conanfile.settings.os, profile_host.settings['os'])

        protoc_host = application.dependencies[2].dst
        self.assertEqual(protoc_host.conanfile.name, "protoc")
        self.assertEqual(protoc_host.context, CONTEXT_HOST)
        self.assertEqual(protoc_host.conanfile.settings.os, profile_host.settings['os'])

        protoc_protobuf_host = protoc_host.dependencies[0].dst
        self.assertEqual(protoc_protobuf_host, protobuf_host)

        gtest_host = application.dependencies[3].dst
        self.assertEqual(gtest_host.conanfile.name, "gtest")
        self.assertEqual(gtest_host.context, CONTEXT_HOST)
        self.assertEqual(gtest_host.conanfile.settings.os, profile_host.settings['os'])

        # Check BUILD packages (default behavior changes if we use profile_build)
        protoc_build = application.dependencies[1].dst
        self.assertEqual(protoc_build.conanfile.name, "protoc")
        self.assertEqual(protoc_build.context, CONTEXT_BUILD)
        self.assertEqual(str(protoc_build.conanfile.settings.os), profile_build.settings['os'])

        protobuf_build = protoc_build.dependencies[0].dst
        self.assertEqual(protobuf_build.conanfile.name, "protobuf")
        self.assertEqual(protoc_build.context, CONTEXT_BUILD)
        self.assertEqual(str(protobuf_build.conanfile.settings.os), profile_build.settings['os'])

