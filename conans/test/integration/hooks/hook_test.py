import os
import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import save


complete_hook = """
import os

def pre_export(conanfile):
    conanfile.output.info("Hello")

def post_export(conanfile):
    conanfile.output.info("Hello")

def pre_source(conanfile):
    conanfile.output.info("Hello")

def post_source(conanfile):
    conanfile.output.info("Hello")

def pre_build(conanfile):
    conanfile.output.info("Hello")

def post_build(conanfile):
    conanfile.output.info("Hello")

def pre_package(conanfile):
    conanfile.output.info("Hello")

def post_package(conanfile):
    conanfile.output.info("Hello")

def pre_package_info(conanfile):
    conanfile.output.info("Hello")

def post_package_info(conanfile):
    conanfile.output.info("Hello")
"""


class TestHooks:

    def test_complete_hook(self):
        c = TestClient()
        hook_path = os.path.join(c.cache.hooks_path, "complete_hook", "hook_complete.py")
        save(hook_path, complete_hook)
        c.save({"conanfile.py": GenConanfile("pkg", "0.1")})

        c.run("source .")
        hook_msg = "[HOOK - complete_hook/hook_complete.py]"
        assert f"conanfile.py (pkg/0.1): {hook_msg} pre_source(): Hello" in c.out
        assert f"conanfile.py (pkg/0.1): {hook_msg} post_source(): Hello" in c.out

        c.run("install .")
        assert "HOOK" not in c.out
        c.run("build .")
        assert f"conanfile.py (pkg/0.1): {hook_msg} pre_build(): Hello" in c.out
        assert f"conanfile.py (pkg/0.1): {hook_msg} post_build(): Hello" in c.out

        c.run("export . ")
        assert f"pkg/0.1: {hook_msg} pre_export(): Hello" in c.out
        assert f"pkg/0.1: {hook_msg} post_export(): Hello" in c.out

        c.run("export-pkg . ")
        assert f"pkg/0.1: {hook_msg} pre_export(): Hello" in c.out
        assert f"pkg/0.1: {hook_msg} post_export(): Hello" in c.out
        assert f"pkg/0.1: {hook_msg} pre_package(): Hello" in c.out
        assert f"pkg/0.1: {hook_msg} post_package(): Hello" in c.out

        c.run("create . ")
        assert f"pkg/0.1: {hook_msg} pre_export(): Hello" in c.out
        assert f"pkg/0.1: {hook_msg} post_export(): Hello" in c.out
        assert f"pkg/0.1: {hook_msg} pre_source(): Hello" in c.out
        assert f"pkg/0.1: {hook_msg} post_source(): Hello" in c.out
        assert f"pkg/0.1: {hook_msg} pre_build(): Hello" in c.out
        assert f"pkg/0.1: {hook_msg} post_build(): Hello" in c.out
        assert f"pkg/0.1: {hook_msg} pre_package(): Hello" in c.out
        assert f"pkg/0.1: {hook_msg} post_package(): Hello" in c.out
        assert f"pkg/0.1: {hook_msg} pre_package_info(): Hello" in c.out
        assert f"pkg/0.1: {hook_msg} post_package_info(): Hello" in c.out

    def test_import_hook(self):
        """ Test that a hook can import another random python file
        """
        custom_module = textwrap.dedent("""
            def my_printer(output):
                output.info("my_printer(): CUSTOM MODULE")
            """)

        my_hook = textwrap.dedent("""
            from custom_module.custom import my_printer

            def pre_export(conanfile):
                my_printer(conanfile.output)
            """)
        c = TestClient()
        hook_path = os.path.join(c.cache.hooks_path, "my_hook", "hook_my_hook.py")
        init_path = os.path.join(c.cache.hooks_path, "my_hook", "custom_module", "__init__.py")
        custom_path = os.path.join(c.cache.hooks_path, "my_hook", "custom_module", "custom.py")
        c.save({init_path: "",
                custom_path: custom_module,
                hook_path: my_hook,
                "conanfile.py": GenConanfile("pkg", "1.0")})

        c.run("export . ")
        assert "[HOOK - my_hook/hook_my_hook.py] pre_export(): my_printer(): CUSTOM MODULE" \
               in c.out

    def test_hook_raising(self):
        """ Test output when a hook raises
        """
        c = TestClient()
        my_hook = textwrap.dedent("""
            def pre_export(conanfile):
                raise Exception("Boom")
            """)
        hook_path = os.path.join(c.cache.hooks_path, "my_hook", "hook_my_hook.py")
        c.save({hook_path: my_hook,
                "conanfile.py": GenConanfile("pkg", "1.0")})

        c.run("export . ", assert_error=True)
        assert "ERROR: [HOOK - my_hook/hook_my_hook.py] pre_export(): Boom" in c.out
