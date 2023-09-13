import os
import re

from conans.util.files import load
from conans.test.utils.tools import TestClient, GenConanfile


def test_version_range():
    tc = TestClient()

    with tc.chdir("utils"):
        tc.run("new cmake_lib -d name=utils -d version=0.1.0")
        tc.run("create .")

    with tc.chdir("liba"):
        tc.run("new cmake_lib -d name=liba -d version=0.1.0 -d requires=utils/[>=0.1.0]")
        tc.run("create .")

    with tc.chdir("libc"):
        tc.run("new cmake_lib -d name=libc -d version=0.1.0 -d requires=liba/[>=0.1.0] -d requires=utils/[>=0.1.0]")
        new_conanfile = re.sub("self.requires",
                               "self.test_requires",
                               load(os.path.join(tc.current_folder, "conanfile.py")))
        new_conanfile = re.sub("def requirements", "def build_requirements", new_conanfile)
        tc.save({"conanfile.py": new_conanfile})

        # As per the report, this should fail when compiling libc.cpp, but it doesnt, it can find utils.h
        tc.run("create . -tf=")


def test_tool_requires_conflict():
    tc = TestClient()
    tc.save({"gcc/conanfile.py": GenConanfile("gcc"),
             "tool_a/conanfile.py": GenConanfile("tool_a", "1.0").with_tool_requires("gcc/1.0"),
             "tool_b/conanfile.py": GenConanfile()})

