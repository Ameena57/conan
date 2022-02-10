import os
import textwrap

import pytest

from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.genconanfile import GenConanfile
from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TestClient
from conans.util.files import save


@pytest.mark.tool("cmake")
def test_install_deploy():
    c = TestClient()
    c.run("new cmake_lib -d name=hello -d version=0.1")
    c.run("create .")
    cmake = gen_cmakelists(appname="my_app", appsources=["main.cpp"], find_package=["hello"])
    deploy = textwrap.dedent("""
        import os, shutil

        # USE **KWARGS to be robust against changes
        def deploy(graph, output_folder, **kwargs):
            for r, d in graph.root.conanfile.dependencies.items():
                new_folder = os.path.join(output_folder, d.ref.name)
                shutil.copytree(d.package_folder, new_folder)
                d.set_deploy_folder(new_folder)
        """)
    c.save({"conanfile.txt": "[requires]\nhello/0.1",
            "deploy.py": deploy,
            "CMakeLists.txt": cmake,
            "main.cpp": gen_function_cpp(name="main", includes=["hello"], calls=["hello"])},
           clean_first=True)
    c.run("install . --deploy=deploy.py -of=mydeploy -g CMakeToolchain -g CMakeDeps")
    c.run("remove * -f")  # Make sure the cache is clean, no deps there
    cwd = c.current_folder.replace("\\", "/")
    deps = c.load("mydeploy/hello-release-x86_64-data.cmake")
    assert f'set(hello_PACKAGE_FOLDER_RELEASE "{cwd}/mydeploy/hello")' in deps
    assert 'set(hello_INCLUDE_DIRS_RELEASE "${hello_PACKAGE_FOLDER_RELEASE}/include")' in deps
    assert 'set(hello_LIB_DIRS_RELEASE "${hello_PACKAGE_FOLDER_RELEASE}/lib")' in deps

    # I can totally build without errors with deployed
    c.run_command("cmake . -DCMAKE_TOOLCHAIN_FILE=mydeploy/conan_toolchain.cmake")
    c.run_command("cmake --build . --config Release")


def test_multi_deploy():
    """ check that we can add more than 1 deployer in the command line, both in local folders
    and in cache.
    Also testing that using .py extension or not, is the same
    Also, the local folder have precedence over the cache extensions
    """
    c = TestClient()
    deploy1 = textwrap.dedent("""
        def deploy(graph, output_folder):
            graph.root.conanfile.output.info("deploy1!!")
        """)
    deploy2 = textwrap.dedent("""
        def deploy(graph, output_folder):
            graph.root.conanfile.output.info("sub/deploy2!!")
        """)
    deploy_cache = textwrap.dedent("""
        def deploy(graph, output_folder):
            graph.root.conanfile.output.info("deploy cache!!")
        """)
    save(os.path.join(c.cache_folder, "extensions", "deploy", "deploy_cache.py"), deploy_cache)
    # This should never be called in this test, always the local is found first
    save(os.path.join(c.cache_folder, "extensions", "deploy", "mydeploy.py"), "CRASH!!!!")
    c.save({"conanfile.txt": "",
            "mydeploy.py": deploy1,
            "sub/mydeploy2.py": deploy2})

    c.run("install . --deploy=mydeploy --deploy=sub/mydeploy2 --deploy=deploy_cache")
    assert "conanfile.txt: deploy1!!" in c.out
    assert "conanfile.txt: sub/deploy2!!" in c.out
    assert "conanfile.txt: deploy cache!!" in c.out

    # Now with .py extension
    c.run("install . --deploy=mydeploy.py --deploy=sub/mydeploy2.py --deploy=deploy_cache.py")
    assert "conanfile.txt: deploy1!!" in c.out
    assert "conanfile.txt: sub/deploy2!!" in c.out
    assert "conanfile.txt: deploy cache!!" in c.out


def test_builtin_deploy():
    """ check the built-in full_deploy
    """
    c = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import save
        class Pkg(ConanFile):
            settings = "arch", "build_type"
            def package(self):
                content = f"{self.settings.build_type}-{self.settings.arch}"
                save(self, os.path.join(self.package_folder, "include/hello.h"), content)
            """)
    c.save({"conanfile.py": conanfile})
    c.run("create . --name=dep --version=0.1")
    c.run("create . --name=dep --version=0.1 -s build_type=Debug -s arch=x86")
    c.save({"conanfile.txt": "[requires]\ndep/0.1"}, clean_first=True)
    c.run("install . --deploy=full_deploy -of=output -g CMakeDeps")
    assert "Conan built-in full deployer" in c.out
    c.run("install . --deploy=full_deploy -of=output -g CMakeDeps "
          "-s build_type=Debug -s arch=x86")
    release = c.load("output/host/dep/0.1/Release/x86_64/include/hello.h")
    assert "Release-x86_64" in release
    debug = c.load("output/host/dep/0.1/Debug/x86/include/hello.h")
    assert "Debug-x86" in debug
    cmake_release = c.load("output/dep-release-x86_64-data.cmake")
    assert 'set(dep_INCLUDE_DIRS_RELEASE "${dep_PACKAGE_FOLDER_RELEASE}/include")' in cmake_release
    assert "output/host/dep/0.1/Release/x86_64" in cmake_release
    cmake_debug = c.load("output/dep-debug-x86-data.cmake")
    assert 'set(dep_INCLUDE_DIRS_DEBUG "${dep_PACKAGE_FOLDER_DEBUG}/include")' in cmake_debug
    assert "output/host/dep/0.1/Debug/x86" in cmake_debug


def test_deploy_reference():
    """ check that we can also deploy a reference
    """
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "1.0").with_package_file("include/hi.h", "hi")})
    c.run("create .")

    c.run("install  --reference=pkg/1.0 --deploy=full_deploy --output-folder=output")
    # NOTE: Full deployer always use build_type/arch, even if None/None in the path, same structure
    header = c.load("output/host/pkg/1.0/None/None/include/hi.h")
    assert "hi" in header

    # Testing that we can deploy to the current folder too
    c.save({}, clean_first=True)
    c.run("install  --reference=pkg/1.0 --deploy=full_deploy")
    # NOTE: Full deployer always use build_type/arch, even if None/None in the path, same structure
    header = c.load("host/pkg/1.0/None/None/include/hi.h")
    assert "hi" in header


def test_deploy_overwrite():
    """ calling several times the install --deploy doesn't crash if files already exist
    """
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "1.0").with_package_file("include/hi.h", "hi")})
    c.run("create .")

    c.run("install  --reference=pkg/1.0 --deploy=full_deploy --output-folder=output")
    header = c.load("output/host/pkg/1.0/None/None/include/hi.h")
    assert "hi" in header

    # modify the package
    c.save({"conanfile.py": GenConanfile("pkg", "1.0").with_package_file("include/hi.h", "bye")})
    c.run("create .")
    c.run("install  --reference=pkg/1.0 --deploy=full_deploy --output-folder=output")
    header = c.load("output/host/pkg/1.0/None/None/include/hi.h")
    assert "bye" in header
