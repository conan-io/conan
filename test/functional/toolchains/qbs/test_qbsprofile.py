import textwrap
import pytest

from conan.test.utils.tools import TestClient
from conan.test.assets.sources import gen_function_cpp


@pytest.mark.tool("qbs")
def test_qbsprofile():
    client = TestClient()

    conanfile = textwrap.dedent('''
        from conan import ConanFile
        from conan.tools.qbs import Qbs

        class Recipe(ConanFile):
            name = "app"
            version = "1.2"
            exports_sources = "*.cpp", "*.h", "*.qbs"
            settings = "os", "compiler", "build_type", "arch"
            generators = "QbsProfile"

            def layout(self):
                self.folders.generators = "generators"

            def build(self):
                qbs = Qbs(self)
                qbs.resolve()
                qbs.build()

            def package(self):
                qbs = Qbs(self)
                qbs.install()
        ''')

    qbsfile = textwrap.dedent('''
        CppApplication {
            files: ["main.cpp"]
        }
    ''')

    client.save({
        "conanfile.py": conanfile,
        "main.cpp": gen_function_cpp(name="main"),
        "app.qbs": qbsfile,
    }, clean_first=True)
    client.run("create .")

    assert "qbs resolve --settings-dir" in client.out
    assert "qbs build --settings-dir" in client.out
    assert "qbs install --settings-dir" in client.out
