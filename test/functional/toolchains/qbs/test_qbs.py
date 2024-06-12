import os
import pytest
import textwrap

from conan.internal.api.new.cmake_lib import source_cpp, source_h
from conan.internal.api.new.qbs_lib import qbs_lib_file
from conan.test.utils.tools import TestClient
from jinja2 import Template


def gen_file(template, **context):
    t = Template(template)
    return t.render(**context)


@pytest.mark.parametrize('shared', [
    ('False'),
    ('True'),
])
@pytest.mark.tool("qbs")
def test_api_qbs_create_lib(shared):
    client = TestClient()
    client.run("new qbs_lib -d name=hello -d version=1.0")
    client.run("create . -o:h &:shared={shared}".format(shared=shared))
    assert "compiling hello.cpp" in client.out


@pytest.mark.tool("qbs")
def test_qbs_all_products():
    client = TestClient()

    context = {
        "name": "hello",
        "version": "2.0",
        "package_name": "hello"
    }

    conanfile = textwrap.dedent('''
    import os

    from conan import ConanFile
    from conan.tools.qbs import Qbs

    class Recipe(ConanFile):
        name = "hello"
        version = "1.0"

        exports_sources = "*.cpp", "*.h", "*.qbs"
        settings = "os", "compiler", "arch", "build_type"

        def build(self):
            qbs = Qbs(self)
            qbs.resolve()
            qbs.build_all()
        ''')

    client.save({
        "conanfile.py": conanfile,
        "hello.cpp": gen_file(source_cpp, **context),
        "hello.h": gen_file(source_h, **context),
        "hello.qbs": gen_file(qbs_lib_file, **context),
    }, clean_first=True)

    client.run("create .")
    assert "--all-products" in client.out


@pytest.mark.tool("qbs")
def test_qbs_specific_products():
    client = TestClient()

    context = {
        "name": "hello",
        "version": "2.0",
        "package_name": "hello"
    }

    conanfile = textwrap.dedent('''
    import os

    from conan import ConanFile
    from conan.tools.qbs import Qbs

    class Recipe(ConanFile):
        name = "hello"
        version = "1.0"

        exports_sources = "*.cpp", "*.h", "*.qbs"
        settings = "os", "compiler", "arch", "build_type"

        def build(self):
            qbs = Qbs(self)
            qbs.resolve()
            qbs.build(products=["hello", "hello"])
        ''')

    client.save({
        "conanfile.py": conanfile,
        "hello.cpp": gen_file(source_cpp, **context),
        "hello.h": gen_file(source_h, **context),
        "hello.qbs": gen_file(qbs_lib_file, **context),
    }, clean_first=True)

    client.run("create .")
    assert "--products hello,hello" in client.out


@pytest.mark.tool("qbs")
def test_qbs_multiple_configurations():
    client = TestClient()

    context = {
        "name": "hello",
        "version": "2.0",
        "package_name": "hello"
    }

    conanfile = textwrap.dedent('''
    import os

    from conan import ConanFile
    from conan.tools.qbs import Qbs

    class Recipe(ConanFile):
        name = "hello"
        version = "1.0"

        exports_sources = "*.cpp", "*.h", "*.qbs"
        settings = "os", "compiler", "arch"

        def build(self):
            qbs = Qbs(self)
            qbs.add_configuration("release", {"qbs.debugInformation": False})
            qbs.add_configuration("debug", {"qbs.debugInformation": True})
            qbs.resolve()
            qbs.build()
        ''')

    client.save({
        "conanfile.py": conanfile,
        "hello.cpp": gen_file(source_cpp, **context),
        "hello.h": gen_file(source_h, **context),
        "hello.qbs": gen_file(qbs_lib_file, **context),
    }, clean_first=True)

    client.run("create .")
    build_folder = client.created_layout().build()
    assert os.path.exists(os.path.join(build_folder, "release"))
    assert os.path.exists(os.path.join(build_folder, "debug"))
