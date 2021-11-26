import os

from conans import ConanFile
from conans.cli.api.subapi import api_method
from conans.cli.common import get_lockfile
from conans.cli.conan_app import ConanApp
from conans.cli.output import ConanOutput
from conans.client.conan_api import _make_abs_path
from conans.client.generators import write_generators
from conans.client.graph.build_mode import BuildMode
from conans.client.graph.graph import RECIPE_VIRTUAL
from conans.client.graph.printer import print_graph
from conans.client.importer import run_imports, run_deploy
from conans.client.installer import BinaryInstaller, call_system_requirements
from conans.errors import ConanException
from conans.model.recipe_ref import RecipeReference


class InstallAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def install_binaries(self, deps_graph, build_modes=None, remote=None, update=False):
        """ Install binaries for dependency graph
        @param deps_graph: Dependency graph to intall packages for
        @param build_modes:
        @param remote:
        @param update:
        """
        app = ConanApp(self.conan_api.cache_folder)
        remote = [remote] if remote is not None else None
        app.load_remotes(remote, update=update)
        installer = BinaryInstaller(app)
        # TODO: Extract this from the GraphManager, reuse same object, check args earlier
        build_modes = BuildMode(build_modes)
        installer.install(deps_graph, build_modes)

    # TODO: Look for a better name
    @staticmethod
    def install_consumer(deps_graph, install_folder, base_folder, conanfile_folder,
                         generators=None, reference=None, no_imports=False, create_reference=None,
                         test=None):
        root_node = deps_graph.root
        conanfile = root_node.conanfile

        if hasattr(conanfile, "layout") and not test:
            conanfile.folders.set_base_install(conanfile_folder)
            conanfile.folders.set_base_imports(conanfile_folder)
            conanfile.folders.set_base_generators(conanfile_folder)
        else:
            conanfile.folders.set_base_install(install_folder)
            conanfile.folders.set_base_imports(install_folder)
            conanfile.folders.set_base_generators(base_folder)

        if install_folder:
            # Write generators
            tmp = list(conanfile.generators)  # Add the command line specified generators
            generators = set(generators) if generators else set()
            tmp.extend([g for g in generators if g not in tmp])
            conanfile.generators = tmp
            write_generators(conanfile)

            if not no_imports:
                run_imports(conanfile)
            if type(conanfile).system_requirements != ConanFile.system_requirements:
                call_system_requirements(conanfile)

            if not create_reference and reference:
                # The conanfile loaded is a virtual one. The one w deploy is the first level one
                neighbours = deps_graph.root.neighbors()
                deploy_conanfile = neighbours[0].conanfile
                if hasattr(deploy_conanfile, "deploy") and callable(deploy_conanfile.deploy):
                    run_deploy(deploy_conanfile, install_folder)

        return deps_graph
