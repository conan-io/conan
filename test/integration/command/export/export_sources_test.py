import os
import textwrap

from conan.api.model import RecipeReference
from conan.internal.util.files import gather_files
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_exports():
    """ Check that exported files go to the right folder
    """
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class HelloConan(ConanFile):
            name = "hello"
            version = "0.1"
            exports = "*.h"
        """)
    c = TestClient(light=True)
    c.save({"conanfile.py": conanfile,
            "hello.h": "hello",
            "data.txt": "data"})
    c.run("create .")
    ref = RecipeReference.loads("hello/0.1")
    ref_layout = c.get_latest_ref_layout(ref)

    def assert_files(folder, files):
        assert sorted(os.listdir(folder)) == sorted(files)

    assert_files(ref_layout.source(), [])
    assert_files(ref_layout.export(), ['conanfile.py', 'conanmanifest.txt', 'hello.h'])
    assert_files(ref_layout.export_sources(), [])


def test_exports_sources():
    """ Check that exported-sources files go to the right folder AND to the source folder
        """
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class HelloConan(ConanFile):
            name = "hello"
            version = "0.1"
            exports_sources = "*.h"
        """)
    c = TestClient(light=True)
    c.save({"conanfile.py": conanfile,
            "hello.h": "hello",
            "data.txt": "data"})
    c.run("create .")
    ref = RecipeReference.loads("hello/0.1")
    ref_layout = c.get_latest_ref_layout(ref)

    def assert_files(folder, files):
        assert sorted(os.listdir(folder)) == sorted(files)

    assert_files(ref_layout.source(), ['hello.h'])
    assert_files(ref_layout.export(), ['conanfile.py', 'conanmanifest.txt', ])
    assert_files(ref_layout.export_sources(), ['hello.h'])


def test_exports_sources_multiple_patterns():
    """ Several exports_sources patterns export the union of what they match, minus the excludes
    """
    c = TestClient(light=True)
    c.save({"conanfile.py": GenConanfile("hello", "0.1")
                            .with_exports_sources("*.h", "src/*.cpp", "docs/*.md",
                                                  "!docs/private.md"),
            "hello.h": "", "other.h": "",
            "src/lib.cpp": "", "src/util.cpp": "",
            "docs/readme.md": "", "docs/private.md": "",
            "unmatched.txt": ""})
    c.run("export .")

    ref_layout = c.get_latest_ref_layout(RecipeReference.loads("hello/0.1"))
    exported, _ = gather_files(ref_layout.export_sources())
    assert sorted(exported) == ["docs/readme.md", "hello.h", "other.h",
                                "src/lib.cpp", "src/util.cpp"]


def test_exports_multiple_patterns():
    """ Same for the ``exports`` attribute: union of all the patterns, minus the excludes
    """
    c = TestClient(light=True)
    c.save({"conanfile.py": GenConanfile("hello", "0.1")
                            .with_exports("*.h", "src/*.cpp", "docs/*.md", "!docs/private.md"),
            "hello.h": "", "other.h": "",
            "src/lib.cpp": "", "src/util.cpp": "",
            "docs/readme.md": "", "docs/private.md": "",
            "unmatched.txt": ""})
    c.run("export .")

    ref_layout = c.get_latest_ref_layout(RecipeReference.loads("hello/0.1"))
    exported, _ = gather_files(ref_layout.export())
    assert sorted(exported) == ["conanfile.py", "conanmanifest.txt", "docs/readme.md",
                                "hello.h", "other.h", "src/lib.cpp", "src/util.cpp"]


def test_export_walks_recipe_folder_once_per_exports_attribute():
    """ All the patterns of one attribute are passed to a single copy() call, so the recipe
    folder is walked once for exports_sources and once for exports, not once per pattern.
    copy() traces one "copy(pattern=...)" line per call, visible with -vv (debug)
    """
    c = TestClient(light=True)
    c.save({"conanfile.py": GenConanfile("hello", "0.1")
                            .with_exports_sources("*.h", "src/*.cpp")
                            .with_exports("*.txt", "docs/*.md"),
            "hello.h": "", "src/lib.cpp": "",
            "notes.txt": "", "docs/readme.md": ""})
    c.run("export . -vv")

    walks = [line for line in c.out.splitlines() if "copy(pattern=" in line]
    trace = "\n".join(walks)
    assert len(walks) == 2, f"Expected 1 walk for exports_sources + 1 for exports, got:\n{trace}"
    # and each pair of patterns travelled together, in the very same copy() call
    assert any("*.h" in w and "src/*.cpp" in w for w in walks), trace
    assert any("*.txt" in w and "docs/*.md" in w for w in walks), trace


def test_test_package_copied():
    """The exclusion of the test_package folder have been removed so now we test that indeed is
    exported"""

    client = TestClient(light=True)
    conanfile = GenConanfile().with_exports("*").with_exports_sources("*")
    client.save({"conanfile.py": conanfile,
                 "test_package/foo.txt": "bar"})
    client.run("export . --name foo --version 1.0")
    assert "Copied 2 '.txt' file" in client.out


def test_source_changes_generate_new_revisions():
    tc = TestClient(light=True)
    tc.save({"conanfile.py": GenConanfile("lib", "1.0").with_exports_sources("file.h"),
             "file.h": "Hello World!"})

    tc.run("export .")
    exported_rev = tc.exported_recipe_revision()

    tc.save({"file.h": "Bye World!"})
    tc.run("export .")
    exported_rev_new = tc.exported_recipe_revision()

    assert exported_rev != exported_rev_new
