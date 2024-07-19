import json
import textwrap

from conan.test.utils.tools import TestClient


def test_print_in_conanfile():
    """
    Tests that prints in conanfiles will not ruin json stdout outputs
    """
    c = TestClient(light=True)
    other = textwrap.dedent("""
        def myprint(text):
            print(text)
        """)
    conanfile = textwrap.dedent("""
        import other
        from conan import ConanFile

        class MyTest(ConanFile):
            name = "pkg"
            version = "0.1"

            def generate(self):
                print("Hello world!!")
                other.myprint("Bye world!!")
        """)
    c.save({"other.py": other,
            "conanfile.py": conanfile})
    c.run("install . --format=json")
    assert "Hello world!!" in c.stderr
    assert "Bye world!!" in c.stderr
    info = json.loads(c.stdout)
    # the json is correctly loaded
    assert "graph" in info
