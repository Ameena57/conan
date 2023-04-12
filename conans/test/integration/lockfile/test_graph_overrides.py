import json

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


@pytest.mark.parametrize("override, force", [(True, False), (False, True)])
def test_overrides_half_diamond(override, force):
    r"""
    pkgc -----> pkgb/0.1 --> pkga/0.1
       \--(override/force)-->pkga/0.2
    """
    c = TestClient()
    c.save({"pkga/conanfile.py": GenConanfile("pkga"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("pkga/0.1"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "0.1").with_requirement("pkgb/0.1")
                                                            .with_requirement("pkga/0.2",
                                                                              override=override,
                                                                              force=force)
            })
    c.run("create pkga --version=0.1")
    c.run("create pkga --version=0.2")
    c.run("create pkgb")
    c.run("lock create pkgc")
    lock = json.loads(c.load("pkgc/conan.lock"))
    requires = "\n".join(lock["requires"])
    assert "pkga/0.2" in requires
    assert "pkga/0.1" not in requires
    c.run("graph info pkgc --lockfile=pkgc/conan.lock --format=json")
    assert "pkga/0.2" in c.stdout
    assert "pkga/0.1" not in c.stdout
    # apply the lockfile to pkgb, should it lock to pkga/0.2
    c.run("graph info pkgb --lockfile=pkgc/conan.lock --format=json")
    assert "pkga/0.2" in c.stdout
    assert "pkga/0.1" not in c.stdout


@pytest.mark.parametrize("override, force", [(True, False), (False, True)])
def test_overrides_half_diamond_ranges(override, force):
    r"""
       pkgc -----> pkgb/0.1 --> pkga/[>0.1 <0.2]
          \--(override/force)-->pkga/0.2
    """
    c = TestClient()
    c.save({"pkga/conanfile.py": GenConanfile("pkga"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("pkga/[>=0.1 <0.2]"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "0.1").with_requirement("pkgb/0.1")
                                                            .with_requirement("pkga/0.2",
                                                                              override=override,
                                                                              force=force)
            })
    c.run("create pkga --version=0.1")
    c.run("create pkga --version=0.2")
    c.run("create pkgb")
    assert "pkga/0.2" not in c.out
    assert "pkga/0.1" in c.out
    c.run("lock create pkgc")
    lock = c.load("pkgc/conan.lock")
    assert "pkga/0.2" in lock
    assert "pkga/0.1" not in lock
    c.run("graph info pkgc --lockfile=pkgc/conan.lock")
    assert "pkga/0.2" in c.out
    assert "pkga/0.1" not in c.out


@pytest.mark.parametrize("override, force", [(True, False), (False, True)])
def test_overrides_half_diamond_ranges_inverted(override, force):
    r""" the override is defining the lower bound of the range

       pkgc -----> pkgb/0.1 --> pkga/[>=0.1]
          \--(override/force)-->pkga/0.1
    """
    c = TestClient()
    c.save({"pkga/conanfile.py": GenConanfile("pkga"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("pkga/[>=0.1]"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "0.1").with_requirement("pkgb/0.1")
                                                            .with_requirement("pkga/0.1",
                                                                              override=override,
                                                                              force=force)
            })
    c.run("create pkga --version=0.1")
    c.run("create pkga --version=0.2")
    c.run("create pkgb")
    assert "pkga/0.2" in c.out
    assert "pkga/0.1" not in c.out
    c.run("lock create pkgc")
    lock = c.load("pkgc/conan.lock")
    assert "pkga/0.1" in lock
    assert "pkga/0.2" not in lock
    c.run("graph info pkgc --lockfile=pkgc/conan.lock")
    assert "pkga/0.1" in c.out
    assert "pkga/0.2" not in c.out


@pytest.mark.parametrize("override, force", [(True, False), (False, True)])
def test_overrides_diamond(override, force):
    r"""
    pkgd -----> pkgb/0.1 --> pkga/0.1
       \------> pkgc/0.1 --> pkga/0.2
       \--(override/force)-->pkga/0.3
    """
    c = TestClient()
    c.save({"pkga/conanfile.py": GenConanfile("pkga"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("pkga/0.1"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "0.1").with_requires("pkga/0.2"),
            "pkgd/conanfile.py": GenConanfile("pkgd", "0.1").with_requirement("pkgb/0.1")
                                                            .with_requirement("pkgc/0.1")
                                                            .with_requirement("pkga/0.3",
                                                                              override=override,
                                                                              force=force)
            })
    c.run("create pkga --version=0.1")
    c.run("create pkga --version=0.2")
    c.run("create pkga --version=0.3")
    c.run("create pkgb")
    c.run("create pkgc")
    c.run("lock create pkgd")
    lock = json.loads(c.load("pkgd/conan.lock"))
    requires = "\n".join(lock["requires"])
    assert "pkga/0.3" in requires
    assert "pkga/0.2" not in requires
    assert "pkga/0.1" not in requires
    c.run("graph info pkgd --lockfile=pkgd/conan.lock --format=json")
    assert "pkga/0.3" in c.stdout
    assert "pkga/0.2" not in c.stdout
    assert "pkga/0.1" not in c.stdout
    # apply the lockfile to pkgb, should it lock to pkga/0.3
    c.run("graph info pkgb --lockfile=pkgd/conan.lock --format=json")
    assert "pkga/0.3" in c.stdout
    assert "pkga/0.2" not in c.stdout
    assert "pkga/0.1" not in c.stdout


@pytest.mark.parametrize("override, force", [(True, False), (False, True)])
def test_overrides_diamond_ranges(override, force):
    r"""
    pkgd -----> pkgb/0.1 --> pkga/[>=0.1 <0.2]
       \------> pkgc/0.1 --> pkga/[>=0.2 <0.3]
       \--(override/force)-->pkga/0.3
    """
    c = TestClient()
    c.save({"pkga/conanfile.py": GenConanfile("pkga"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("pkga/[>=0.1 <0.2]"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "0.1").with_requires("pkga/[>=0.2 <0.3]"),
            "pkgd/conanfile.py": GenConanfile("pkgd", "0.1").with_requirement("pkgb/0.1")
                                                            .with_requirement("pkgc/0.1")
                                                            .with_requirement("pkga/0.3",
                                                                              override=override,
                                                                              force=force)
            })
    c.run("create pkga --version=0.1")
    c.run("create pkga --version=0.2")
    c.run("create pkga --version=0.3")
    c.run("create pkgb")
    c.run("create pkgc")
    c.run("lock create pkgd")
    lock = json.loads(c.load("pkgd/conan.lock"))
    requires = "\n".join(lock["requires"])
    assert "pkga/0.3" in requires
    assert "pkga/0.2" not in requires
    assert "pkga/0.1" not in requires
    c.run("graph info pkgd --lockfile=pkgd/conan.lock --format=json")
    assert "pkga/0.3" in c.stdout
    assert "pkga/0.2" not in c.stdout
    assert "pkga/0.1" not in c.stdout
    # apply the lockfile to pkgb, should it lock to pkga/0.3
    c.run("graph info pkgb --lockfile=pkgd/conan.lock --format=json")
    assert "pkga/0.3" in c.stdout
    assert "pkga/0.2" not in c.stdout
    assert "pkga/0.1" not in c.stdout


@pytest.mark.parametrize("override1, force1", [(True, False), (False, True)])
@pytest.mark.parametrize("override2, force2", [(True, False), (False, True)])
def test_overrides_multiple(override1, force1, override2, force2):
    r"""
    pkgd/0.1 -> pkgc/0.1 -> pkgb/0.1 -> pkga/0.1
      \           \--override---------> pkga/0.2
       \---override-------------------> pkga/0.3
    """
    c = TestClient()
    c.save({"pkga/conanfile.py": GenConanfile("pkga"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("pkga/0.1"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "0.1").with_requirement("pkgb/0.1")
                                                            .with_requirement("pkga/0.2",
                                                                              override=override1,
                                                                              force=force1),
            "pkgd/conanfile.py": GenConanfile("pkgd", "0.1").with_requirement("pkgc/0.1")
                                                            .with_requirement("pkga/0.3",
                                                                              override=override2,
                                                                              force=force2)
            })
    c.run("create pkga --version=0.1")
    c.run("create pkga --version=0.2")
    c.run("create pkga --version=0.3")
    c.run("create pkgb")
    c.run("create pkgc --build=missing")
    c.run("lock create pkgd")
    lock = json.loads(c.load("pkgd/conan.lock"))
    requires = "\n".join(lock["requires"])
    assert "pkga/0.3" in requires
    assert "pkga/0.2" not in requires
    assert "pkga/0.1" not in requires
    c.run("graph info pkgd --lockfile=pkgd/conan.lock")
    assert "pkga/0.3" in c.out
    assert "pkga/0.2#" not in c.out
    assert "pkga/0.1#" not in c.out  # appears in override information


def test_graph_different_overrides():
    r"""
    pkga -> toola/0.1 -> toolb/0.1 -> toolc/0.1
                \------override-----> toolc/0.2
    pkgb -> toola/0.2 -> toolb/0.2 -> toolc/0.1
                \------override-----> toolc/0.3
    pkgc -> toola/0.3 -> toolb/0.3 -> toolc/0.1
    """
    c = TestClient()
    c.save({"toolc/conanfile.py": GenConanfile("toolc"),
            "toolb/conanfile.py": GenConanfile("toolb").with_requires("toolc/0.1"),
            "toola/conanfile.py": GenConanfile("toola", "0.1").with_requirement("toolb/0.1")
                                                              .with_requirement("toolc/0.2",
                                                                                override=True),
            "toola2/conanfile.py": GenConanfile("toola", "0.2").with_requirement("toolb/0.2")
                                                               .with_requirement("toolc/0.3",
                                                                                 override=True),
            "toola3/conanfile.py": GenConanfile("toola", "0.3").with_requirement("toolb/0.3"),
            "pkga/conanfile.py": GenConanfile("pkga", "0.1").with_tool_requires("toola/0.1"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("pkga/0.1")
                                                            .with_tool_requires("toola/0.2"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "0.1").with_requires("pkgb/0.1")
                                                            .with_tool_requires("toola/0.3"),
            })
    c.run("create toolc --version=0.1")
    c.run("create toolc --version=0.2")
    c.run("create toolc --version=0.3")

    c.run("create toolb --version=0.1")
    c.run("create toolb --version=0.2")
    c.run("create toolb --version=0.3")

    c.run("create toola --build=missing")
    c.run("create toola2 --build=missing")
    c.run("create toola3 --build=missing")

    c.run("create pkga")
    c.run("create pkgb")
    c.run("lock create pkgc")
    print(c.load("pkgc/conan.lock"))
    lock = json.loads(c.load("pkgc/conan.lock"))
    requires = "\n".join(lock["build_requires"])
    assert "toolc/0.3" in requires
    assert "toolc/0.2" in requires
    assert "toolc/0.1" in requires

    c.run("graph info toolb --build-require --version=0.1 --lockfile=pkgc/conan.lock --format=json")
    # defaults to the non overriden
    c.assert_listed_require({"toolc/0.1": "Cache"}, build=True)
    # TODO: Solve it with build-order or manual overrides for the other packages


def test_graph_same_base_overrides():
    r"""
    pkga -> toola/0.1 -> toolb/0.1 -> toolc/0.1
                \------override-----> toolc/0.2
    pkgb -> toola/0.2 -> toolb/0.1 -> toolc/0.1
                \------override-----> toolc/0.3
    pkgc -> toola/0.3 -> toolb/0.1 -> toolc/0.1
    """
    c = TestClient()
    c.save({"toolc/conanfile.py": GenConanfile("toolc"),
            "toolb/conanfile.py": GenConanfile("toolb").with_requires("toolc/0.1"),
            "toola/conanfile.py": GenConanfile("toola", "0.1").with_requirement("toolb/0.1")
                                                              .with_requirement("toolc/0.2",
                                                                                override=True),
            "toola2/conanfile.py": GenConanfile("toola", "0.2").with_requirement("toolb/0.1")
                                                               .with_requirement("toolc/0.3",
                                                                                 override=True),
            "toola3/conanfile.py": GenConanfile("toola", "0.3").with_requirement("toolb/0.1"),
            "pkga/conanfile.py": GenConanfile("pkga", "0.1").with_tool_requires("toola/0.1"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("pkga/0.1")
                                                            .with_tool_requires("toola/0.2"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "0.1").with_requires("pkgb/0.1")
                                                            .with_tool_requires("toola/0.3"),
            })
    c.run("create toolc --version=0.1")
    c.run("create toolc --version=0.2")
    c.run("create toolc --version=0.3")

    c.run("create toolb --version=0.1")

    c.run("create toola --build=missing")
    c.run("create toola2 --build=missing")
    c.run("create toola3 --build=missing")

    c.run("create pkga")
    c.run("create pkgb")
    c.run("lock create pkgc")
    lock = json.loads(c.load("pkgc/conan.lock"))
    print(c.load("pkgc/conan.lock"))
    requires = "\n".join(lock["build_requires"])
    assert "toolc/0.3" in requires
    assert "toolc/0.2" in requires
    assert "toolc/0.1" in requires

    c.run("graph info pkgc --filter=requires")
    print(c.out)
    c.run("graph build-order pkgc --lockfile=pkgc/conan.lock --format=json --build=*")
    print(c.stdout)


@pytest.mark.parametrize("override, force", [(True, False), (False, True)])
def test_introduced_conflict(override, force):
    r"""
    Using --lockfile-partial we can evaluate and introduce a new conflict
    pkgd -----> pkgb/[*] --> pkga/[>=0.1 <0.2]
    """
    c = TestClient()
    c.save({"pkga/conanfile.py": GenConanfile("pkga"),
            "pkgb/conanfile.py": GenConanfile("pkgb").with_requires("pkga/[>=0.1 <0.2]"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "0.1").with_requires("pkga/[>=0.2 <0.3]"),
            "pkgd/conanfile.py": GenConanfile("pkgd", "0.1").with_requirement("pkgb/[*]")
            })
    c.run("create pkga --version=0.1")
    c.run("create pkga --version=0.2")
    c.run("create pkga --version=0.3")
    c.run("create pkgb --version=0.1")
    c.run("create pkgc")
    c.run("lock create pkgd")
    lock = json.loads(c.load("pkgd/conan.lock"))
    requires = "\n".join(lock["requires"])
    assert "pkga/0.1" in requires
    assert "pkga/0.2" not in requires
    assert "pkga/0.3" not in requires
    # This will not be used thanks to the lockfile
    c.run("create pkgb --version=0.2")
    c.save({"pkgd/conanfile.py": GenConanfile("pkgd", "0.1").with_requirement("pkgb/0.1")
                                                            .with_requirement("pkgc/0.1")
            })

    c.run("graph info pkgd --lockfile=pkgd/conan.lock --lockfile-partial", assert_error=True)
    assert "Version conflict: pkgc/0.1->pkga/[>=0.2 <0.3], pkgd/0.1->pkga/0.1" in c.out
    c.save({"pkgd/conanfile.py": GenConanfile("pkgd", "0.1").with_requirement("pkgb/0.1")
                                                            .with_requirement("pkgc/0.1")
                                                            .with_requirement("pkga/0.3",
                                                                              override=override,
                                                                              force=force)
            })
    c.run("graph info pkgd --lockfile=pkgd/conan.lock --lockfile-partial --lockfile-out=pkgd/conan2.lock")
    assert "pkgb/0.2" not in c.out
    assert "pkgb/0.1" in c.out
    lock = json.loads(c.load("pkgd/conan2.lock"))
    print(c.load("pkgd/conan2.lock"))
    requires = "\n".join(lock["requires"])
