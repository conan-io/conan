import os
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conans.util.files import save


def test_custom_global_generator():
    c = TestClient()
    generator = textwrap.dedent("""
        class MyCustomGenerator:
            def __init__(self, conanfile):
                self._conanfile = conanfile
            def generate(self):
                pkg = self._conanfile.dependencies["pkg"].ref
                self._conanfile.output.info(f"DEP: {pkg}!!")
        """)
    save(os.path.join(c.cache.custom_generators_path, "mygen.py"), generator)
    conanfile = textwrap.dedent("""
        [requires]
        pkg/0.1

        [generators]
        MyCustomGenerator
        """)
    c.save({"pkg/conanfile.py": GenConanfile("pkg", "0.1"),
            "conanfile.txt": conanfile})
    c.run("create pkg")
    c.run("install .")
    assert "conanfile.txt: Generator 'MyCustomGenerator' calling 'generate()'" in c.out
    assert "conanfile.txt: DEP: pkg/0.1!!" in c.out

    # By CLI also works
    conanfile = textwrap.dedent("""
        [requires]
        pkg/0.1
        """)
    c.save({"conanfile.txt": conanfile})
    c.run("install . -g MyCustomGenerator")
    assert "conanfile.txt: Generator 'MyCustomGenerator' calling 'generate()'" in c.out
    assert "conanfile.txt: DEP: pkg/0.1!!" in c.out

    # In conanfile.py also works
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class MyPkg(ConanFile):
            requires = "pkg/0.1"
            generators = "MyCustomGenerator"
            """)
    c.save({"conanfile.py": conanfile}, clean_first=True)
    c.run("install . ")
    assert "conanfile.py: Generator 'MyCustomGenerator' calling 'generate()'" in c.out
    assert "conanfile.py: DEP: pkg/0.1!!" in c.out


def test_custom_global_generator_imports():
    """
    our custom generator can use python imports
    """
    c = TestClient()
    generator = textwrap.dedent("""
        from _myfunc import mygenerate

        class MyCustomGenerator:
            def __init__(self, conanfile):
                self._conanfile = conanfile
            def generate(self):
                mygenerate(self._conanfile)
        """)
    myaux = textwrap.dedent("""
        def mygenerate(conanfile):
            conanfile.output.info("MYGENERATE WORKS!!")
        """)
    save(os.path.join(c.cache.custom_generators_path, "mygen.py"), generator)
    save(os.path.join(c.cache.custom_generators_path, "_myfunc.py"), myaux)

    c.save({"conanfile.txt": ""})
    c.run("install . -g MyCustomGenerator")
    assert "conanfile.txt: Generator 'MyCustomGenerator' calling 'generate()'" in c.out
    assert "conanfile.txt: MYGENERATE WORKS!!" in c.out


def test_custom_global_generator_multiple():
    """
    multiple custom generators with different names load correctly
    """
    c = TestClient()
    for num in range(3):
        generator = textwrap.dedent(f"""
            class MyGenerator{num}:
                def __init__(self, conanfile):
                    self._conanfile = conanfile
                def generate(self):
                    self._conanfile.output.info(f"MyGenerator{num}!!")
            """)
        save(os.path.join(c.cache.custom_generators_path, f"mygen{num}.py"), generator)
    conanfile = textwrap.dedent("""
        [requires]
        pkg/0.1

        [generators]
        MyGenerator0
        MyGenerator1
        MyGenerator2
        """)
    c.save({"pkg/conanfile.py": GenConanfile("pkg", "0.1"),
            "conanfile.txt": conanfile})
    c.run("create pkg")
    c.run("install .")
    assert "conanfile.txt: Generator 'MyGenerator0' calling 'generate()'" in c.out
    assert "conanfile.txt: Generator 'MyGenerator1' calling 'generate()'" in c.out
    assert "conanfile.txt: Generator 'MyGenerator2' calling 'generate()'" in c.out
    assert "conanfile.txt: MyGenerator0!!" in c.out
    assert "conanfile.txt: MyGenerator1!!" in c.out
    assert "conanfile.txt: MyGenerator2!!" in c.out
