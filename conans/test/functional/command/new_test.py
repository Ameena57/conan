import pytest as pytest

from conans.test.utils.tools import TestClient


@pytest.mark.tool("cmake")
def test_diamonds_cmake_with_new():
    tc = TestClient()
    tc.run("new cmake_lib -d name=math -d version=3.14")
    tc.run("create .")
    tc.run("new cmake_lib -d name=ai -d version=0.1 -d requires=math/3.14 -f")
    tc.run("create .")
    assert "math/3.14: Hello World" in tc.out
    tc.run("new cmake_lib -d name=ui -d version=1.0 -d requires=math/3.14 -f")
    tc.run("create .")
    assert "math/3.14: Hello World" in tc.out
    tc.run("new cmake_exe -d name=game -d version=0.0 -d requires=ai/0.1 -d requires=ui/1.0 -f")
    tc.run("create .")
    assert "math/3.14: Hello World" in tc.out
    assert "ai/0.1: Hello World" in tc.out
    assert "ui/1.0: Hello World" in tc.out


