from conan.tools.env.environment import environment_wrap_command
from conans.test.assets.pkg_cmake import pkg_cmake, pkg_cmake_app, pkg_cmake_test
from conans.test.utils.mocks import ConanFileMock
from conans.test.utils.tools import TestClient


def test_shared_cmake_toolchain():
    client = TestClient(default_server_user=True)

    client.save(pkg_cmake("hello", "0.1"))
    client.run("create . -o hello:shared=True")
    client.save(pkg_cmake("chat", "0.1", requires=["hello/0.1"]), clean_first=True)
    client.run("create . -o chat:shared=True -o hello:shared=True")
    client.save(pkg_cmake_app("app", "0.1", requires=["chat/0.1"]), clean_first=True)
    client.run("create . -o chat:shared=True -o hello:shared=True")
    client.run("upload * --all -c -r default")
    client.run("remove * -f")

    client = TestClient(servers=client.servers)
    client.run("install --reference=app/0.1@ -o chat:shared=True -o hello:shared=True -g VirtualRunEnv")
    # This only finds "app" executable because the "app/0.1" is declaring package_type="application"
    # otherwise, run=None and nothing can tell us if the conanrunenv should have the PATH.
    command = environment_wrap_command("conanrun", "app", cwd=client.current_folder)

    client.run_command(command)
    assert "main: Release!" in client.out
    assert "chat: Release!" in client.out
    assert "hello: Release!" in client.out


def test_shared_cmake_toolchain_test_package():
    client = TestClient()
    files = pkg_cmake("hello", "0.1")
    files.update(pkg_cmake_test("hello"))
    client.save(files)
    client.run("create . -o hello:shared=True")
    assert "hello: Release!" in client.out
