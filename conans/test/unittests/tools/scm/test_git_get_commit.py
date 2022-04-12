import os

from conan.tools.scm import Git
from conans.test.utils.mocks import MockConanfile
from conans.test.utils.tools import TestClient


def test_change_branch_in_root_commit():
    """
    https://github.com/conan-io/conan/issues/10971#issuecomment-1089316912
    """
    c = TestClient()
    conanfile = MockConanfile({})
    c.save({"root.txt": "", "subfolder/subfolder.txt": ""})
    c.run_command("git init .")
    c.run_command('git config user.name myname')
    c.run_command('git config user.email myname@mycompany.com')
    c.run_command("git add .")
    c.run_command('git commit -m "initial commit"')
    c.run_command("git checkout -b change_branch")
    c.save({"subfolder/subfolder.txt": "CHANGED"})
    c.run_command("git add .")
    c.run_command('git commit -m "second commit"')
    c.run_command("git checkout master")
    c.run_command("git merge --no-ff change_branch -m 'Merge branch'")

    git = Git(conanfile, folder=c.current_folder)
    commit_conan = git.get_commit()

    c.run_command("git rev-parse HEAD")
    commit_real = str(c.out).splitlines()[0]
    assert commit_conan == commit_real


def test_multi_folder_repo():
    c = TestClient()
    conanfile = MockConanfile({})
    c.save({"lib_a/conanfile.py": ""})
    c.run_command("git init .")
    c.run_command('git config user.name myname')
    c.run_command('git config user.email myname@mycompany.com')
    c.run_command("git add .")
    c.run_command('git commit -m "lib_a commit"')
    c.save({"lib_b/conanfile.py": ""})
    c.run_command("git add .")
    c.run_command('git commit -m "lib_b commit"')
    c.save({"lib_c/conanfile.py": ""})
    c.run_command("git add .")
    c.run_command('git commit -m "lib_c commit"')
    c.save({"root_change": ""})
    c.run_command("git add .")
    c.run_command('git commit -m "root change"')

    # Git object for lib_a
    git = Git(conanfile, folder=os.path.join(c.current_folder, "lib_a"))
    commit_libA = git.get_commit()

    git = Git(conanfile, folder=os.path.join(c.current_folder, "lib_b"))
    commit_libB = git.get_commit()

    git = Git(conanfile, folder=os.path.join(c.current_folder, "lib_c"))
    commit_libC = git.get_commit()

    git = Git(conanfile, folder=c.current_folder)
    commit_root = git.get_commit()

    # All different
    assert len({commit_libA, commit_libB, commit_libC, commit_root}) == 4

    c.run_command("git rev-parse HEAD")
    commit_real = str(c.out).splitlines()[0]
    assert commit_root == commit_real

    # New commit in A
    c.save({"lib_a/conanfile.py": "CHANGED"})
    c.run_command("git add .")
    c.run_command('git commit -m "lib_a commit2"')

    # Git object for lib_a
    git = Git(conanfile, folder=os.path.join(c.current_folder, "lib_a"))
    new_commit_libA = git.get_commit()

    git = Git(conanfile, folder=os.path.join(c.current_folder, "lib_b"))
    new_commit_libB = git.get_commit()

    git = Git(conanfile, folder=os.path.join(c.current_folder, "lib_c"))
    new_commit_libC = git.get_commit()

    git = Git(conanfile, folder=c.current_folder)
    new_commit_root = git.get_commit()

    assert new_commit_libA != commit_libA
    assert new_commit_libB == commit_libB
    assert new_commit_libC == commit_libC
    assert new_commit_root != commit_root

    c.run_command("git rev-parse HEAD")
    commit_real = str(c.out).splitlines()[0]
    assert new_commit_root == commit_real
