from conans import __version__
from conans.test.utils.tools import TestClient


class TestHelp:

    def test_version(self):
        c = TestClient()
        c.run("--version")
        assert "Conan version %s" % __version__ in c.out

    def test_unknown_command(self):
        c = TestClient()
        c.run("some_unknown_command123", assert_error=True)
        assert "'some_unknown_command123' is not a Conan command" in c.out

    def test_similar(self):
        c = TestClient()
        c.run("instal", assert_error=True)
        assert "The most similar command is" in c.out
        assert "install" in c.out

    def test_help(self):
        c = TestClient()
        c.run("-h")
        assert "Creator commands" in c.out
        assert "Consumer commands" in c.out

    def test_help_command(self):
        c = TestClient()
        c.run("new -h")
        assert "Create a new example recipe" in c.out

    def test_help_subcommand(self):
        c = TestClient()
        c.run("cache -h")
        # When listing subcommands, but line truncated
        assert "Performs file operations in the local cache (of recipes and packages)" in c.out
        c.run("cache path -h")
        assert "Shows the path in the Conan cache af a given reference" in c.out
