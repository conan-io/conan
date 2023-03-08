import os
import re
import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_editable_python_requires():
    c = TestClient()
    dep = textwrap.dedent("""
        from conan import ConanFile

        number = 42

        class Dep(ConanFile):
            name = "dep"
            version = "1.0"
        """)
    pkg = textwrap.dedent("""
        from conan import ConanFile

        number = 42

        class Dep(ConanFile):
            name = "pkg"
            version = "1.0"
            python_requires = "dep/1.0"

            def generate(self):
                self.output.info(f"NUMBER GEN: {self.python_requires['dep'].module.number}")
            def build(self):
                self.output.info(f"NUMBER BUILD: {self.python_requires['dep'].module.number}")
        """)

    c.save({"dep/conanfile.py": dep,
            "pkg/conanfile.py": pkg})
    c.run("editable add dep")
    c.run("build pkg")
    assert "conanfile.py (pkg/1.0): NUMBER GEN: 42" in c.out
    assert "conanfile.py (pkg/1.0): NUMBER BUILD: 42" in c.out
