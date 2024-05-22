import os
import textwrap

import patch_ng
import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.file_server import TestFileServer
from conan.test.utils.tools import TestClient
from conans.util.files import save


class MockPatchset:
    apply_args = None

    def apply(self, strip=0, root=None, fuzz=False):
        self.apply_args = (root, strip, fuzz)
        return True


@pytest.fixture
def mock_patch_ng(monkeypatch):
    mock = MockPatchset()

    def mock_fromstring(string):
        mock.string = string
        return mock

    monkeypatch.setattr(patch_ng, "fromfile", lambda _: mock)
    monkeypatch.setattr(patch_ng, "fromstring", mock_fromstring)
    return mock


class TestConanToolFiles:

    def test_imports(self):
        conanfile = GenConanfile().with_import("from conan.tools.files import load, save, "
                                               "mkdir, download, get, ftp_download")
        client = TestClient(light=True)
        client.save({"conanfile.py": conanfile})
        client.run("install .")

    def test_load_save_mkdir(self):
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import load, save, mkdir

            class Pkg(ConanFile):
                name = "mypkg"
                version = "1.0"
                def source(self):
                    mkdir(self, "myfolder")
                    save(self, "./myfolder/myfile", "some_content")
                    assert load(self, "./myfolder/myfile") == "some_content"
            """)
        client = TestClient(light=True)
        client.save({"conanfile.py": conanfile})
        client.run("source .")

    def test_download(self):
        client = TestClient(light=True)
        file_server = TestFileServer()
        client.servers["file_server"] = file_server
        save(os.path.join(file_server.store, "myfile.txt"), "some content")

        profile = textwrap.dedent("""\
            [conf]
            tools.files.download:retry=1
            tools.files.download:retry_wait=0
            """)

        conanfile = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.files import download

            class Pkg(ConanFile):
                name = "mypkg"
                version = "1.0"
                def source(self):
                    download(self, "{}/myfile.txt", "myfile.txt")
                    assert os.path.exists("myfile.txt")
            """.format(file_server.fake_url))

        client.save({"conanfile.py": conanfile})
        client.save({"profile": profile})
        client.run("create . -pr=profile")

    def test_download_export_sources(self):
        client = TestClient(light=True)
        file_server = TestFileServer()
        client.servers["file_server"] = file_server
        save(os.path.join(file_server.store, "myfile.txt"), "some content")
        save(os.path.join(file_server.store, "myfile2.txt"), "some content")

        conanfile = textwrap.dedent(f"""
            import os
            from conan import ConanFile
            from conan.tools.files import download

            class Pkg(ConanFile):
                name = "mypkg"
                version = "1.0"
                def export(self):
                    download(self, "{file_server.fake_url}/myfile.txt", "myfile.txt")
                    assert os.path.exists("myfile.txt")
                def export_sources(self):
                    download(self, "{file_server.fake_url}/myfile2.txt", "myfile2.txt")
                    assert os.path.exists("myfile2.txt")
            """)

        client.save({"conanfile.py": conanfile})
        client.run("create .")


def test_patch(mock_patch_ng):
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import patch

        class Pkg(ConanFile):
            name = "mypkg"
            version = "1.0"

            def build(self):
                patch(self, patch_file='path/to/patch-file', patch_type='security')
        """)

    client = TestClient(light=True)
    client.save({"conanfile.py": conanfile})
    client.run('create .')

    # Note: This cannot exist anymore, because the path is moved when prev is computed
    # assert os.path.exists(mock_patch_ng.apply_args[0])
    assert mock_patch_ng.apply_args[1:] == (0, False)
    assert 'mypkg/1.0: Apply patch (security)' in str(client.out)


@pytest.mark.parametrize("no_copy_source", [False, True])
def test_patch_real(no_copy_source):
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import patch, save, load

        class Pkg(ConanFile):
            name = "mypkg"
            version = "1.0"
            exports_sources = "*"
            no_copy_source = %s

            def layout(self):
                self.folders.source = "src"
                self.folders.build = "build"

            def source(self):
                save(self, "myfile.h", "//dummy contents")
                patch(self, patch_file="patches/mypatch_h", patch_type="security")
                self.output.info("SOURCE: {}".format(load(self, "myfile.h")))

            def build(self):
                save(self, "myfile.cpp", "//dummy contents")
                if self.no_copy_source:
                    patch_file = os.path.join(self.source_folder, "../patches/mypatch_cpp")
                else:
                    patch_file = "patches/mypatch_cpp"
                patch(self, patch_file=patch_file, patch_type="security",
                      base_path=self.build_folder)
                self.output.info("BUILD: {}".format(load(self, "myfile.cpp")))
        """ % no_copy_source)

    client = TestClient(light=True)
    patch_contents = textwrap.dedent("""\
        --- myfile.{ext}
        +++ myfile.{ext}
        @@ -1 +1 @@
        -//dummy contents
        +//smart contents
        """)
    client.save({"conanfile.py": conanfile,
                 "patches/mypatch_h": patch_contents.format(ext="h"),
                 "patches/mypatch_cpp": patch_contents.format(ext="cpp")})
    client.run('create .')
    assert "mypkg/1.0: Apply patch (security)" in client.out
    assert "mypkg/1.0: SOURCE: //smart contents" in client.out
    assert "mypkg/1.0: BUILD: //smart contents" in client.out

    # Test local source too
    client.run("install .")
    client.run("source .")
    assert "conanfile.py (mypkg/1.0): Apply patch (security)" in client.out
    assert "conanfile.py (mypkg/1.0): SOURCE: //smart contents" in client.out
    client.run("build .")
    assert "conanfile.py (mypkg/1.0): Apply patch (security)" in client.out
    assert "conanfile.py (mypkg/1.0): BUILD: //smart contents" in client.out


def test_apply_conandata_patches(mock_patch_ng):
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import apply_conandata_patches

        class Pkg(ConanFile):
            name = "mypkg"
            version = "1.11.0"

            def layout(self):
                self.folders.source = "source_subfolder"

            def build(self):
                apply_conandata_patches(self)
        """)
    conandata_yml = textwrap.dedent("""
        patches:
          "1.11.0":
            - patch_file: "patches/0001-buildflatbuffers-cmake.patch"
            - patch_file: "patches/0002-implicit-copy-constructor.patch"
              patch_type: backport
              patch_source: https://github.com/google/flatbuffers/pull/5650
              patch_description: Needed to build with modern clang compilers.
          "1.12.0":
            - patch_file: "patches/0001-buildflatbuffers-cmake.patch"
    """)

    client = TestClient(light=True)
    client.save({'conanfile.py': conanfile,
                 'conandata.yml': conandata_yml})
    client.run('create .')

    assert mock_patch_ng.apply_args[0].endswith('source_subfolder')
    assert mock_patch_ng.apply_args[1:] == (0, False)

    assert 'mypkg/1.11.0: Apply patch (backport): Needed to build with modern' \
           ' clang compilers.' in str(client.out)

    # Test local methods
    client.run("install .")
    client.run("build .")

    assert 'conanfile.py (mypkg/1.11.0): Apply patch (backport): Needed to build with modern' \
           ' clang compilers.' in str(client.out)


def test_apply_conandata_patches_relative_base_path(mock_patch_ng):
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import apply_conandata_patches

        class Pkg(ConanFile):
            name = "mypkg"
            version = "1.11.0"

            def layout(self):
                self.folders.source = "source_subfolder"

            def build(self):
                apply_conandata_patches(self)
        """)
    conandata_yml = textwrap.dedent("""
        patches:
          "1.11.0":
            - patch_file: "patches/0001-buildflatbuffers-cmake.patch"
              base_path: "relative_dir"
    """)

    client = TestClient(light=True)
    client.save({'conanfile.py': conanfile,
                 'conandata.yml': conandata_yml})
    client.run('create .')

    assert mock_patch_ng.apply_args[0].endswith(os.path.join('source_subfolder', "relative_dir"))
    assert mock_patch_ng.apply_args[1:] == (0, False)


def test_no_patch_file_entry():
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import apply_conandata_patches

        class Pkg(ConanFile):
            name = "mypkg"
            version = "1.11.0"

            def layout(self):
                self.folders.source = "source_subfolder"

            def build(self):
                apply_conandata_patches(self)
        """)
    conandata_yml = textwrap.dedent("""
        patches:
          "1.11.0":
            - wrong_entry: "patches/0001-buildflatbuffers-cmake.patch"
          "1.12.0":
            - patch_file: "patches/0001-buildflatbuffers-cmake.patch"
    """)

    client = TestClient(light=True)
    client.save({'conanfile.py': conanfile,
                 'conandata.yml': conandata_yml})
    client.run('create .', assert_error=True)

    assert "The 'conandata.yml' file needs a 'patch_file' or 'patch_string' entry for every patch" \
           " to be applied" in str(client.out)


def test_patch_string_entry(mock_patch_ng):
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import apply_conandata_patches

        class Pkg(ConanFile):
            name = "mypkg"
            version = "1.11.0"

            def build(self):
                apply_conandata_patches(self)
        """)
    conandata_yml = textwrap.dedent("""
        patches:
          "1.11.0":
            - patch_string: mock patch data
              patch_type: string
    """)

    client = TestClient(light=True)
    client.save({'conanfile.py': conanfile,
                 'conandata.yml': conandata_yml})
    client.run('create .')

    # Note: This cannot exist anymore, because the path is moved when prev is computed
    # assert os.path.exists(mock_patch_ng.apply_args[0])
    assert mock_patch_ng.apply_args[1:] == (0, False)
    assert 'mock patch data' == mock_patch_ng.string.decode('utf-8')
    assert 'mypkg/1.11.0: Apply patch (string)' in str(client.out)


def test_relate_base_path_all_versions(mock_patch_ng):
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import apply_conandata_patches

        class Pkg(ConanFile):
            name = "mypkg"
            version = "1.0"

            def layout(self):
                self.folders.source = "source_subfolder"

            def build(self):
                apply_conandata_patches(self)
        """)
    conandata_yml = textwrap.dedent("""
        patches:
          - patch_file: "patches/0001-buildflatbuffers-cmake.patch"
            base_path: "relative_dir"
    """)

    client = TestClient(light=True)
    client.save({'conanfile.py': conanfile,
                 'conandata.yml': conandata_yml})
    client.run('create .')

    assert mock_patch_ng.apply_args[0].endswith(os.path.join('source_subfolder', "relative_dir"))
    assert mock_patch_ng.apply_args[1:] == (0, False)


def test_export_conandata_patches(mock_patch_ng):
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import export_conandata_patches, load

        class Pkg(ConanFile):
            name = "mypkg"
            version = "1.0"

            def layout(self):
                self.folders.source = "source_subfolder"

            def export_sources(self):
                export_conandata_patches(self)

            def source(self):
                self.output.info(load(self, os.path.join(self.export_sources_folder,
                                                         "patches/mypatch.patch")))
        """)
    conandata_yml = textwrap.dedent("""
        patches:
          - patch_file: "patches/mypatch.patch"
    """)

    client = TestClient(light=True)
    client.save({"conanfile.py": conanfile})
    client.run("create .", assert_error=True)
    assert "conandata.yml not defined" in client.out
    # Empty conandata
    client.save({"conandata.yml": ""})
    client.run("create .", assert_error=True)
    assert "export_conandata_patches(): No patches defined in conandata" in client.out
    assert "ERROR: mypkg/1.0: Error in source() method" in client.out
    # wrong patches
    client.save({"conandata.yml": "patches: 123"})
    client.run("create .", assert_error=True)
    assert "conandata.yml 'patches' should be a list or a dict"  in client.out

    # No patch found
    client.save({"conandata.yml": conandata_yml})
    client.run("create .", assert_error=True)
    assert "No such file or directory" in client.out

    client.save({"patches/mypatch.patch": "mypatch!!!"})
    client.run("create .")
    assert "mypkg/1.0: mypatch!!!" in client.out

    conandata_yml = textwrap.dedent("""
        patches:
            "1.0":
                - patch_file: "patches/mypatch.patch"
    """)
    client.save({"conandata.yml": conandata_yml})
    client.run("create .")
    assert "mypkg/1.0: mypatch!!!" in client.out


def test_export_conandata_patches_no_patches():
    # Patch exists but has no contents, this used to hard crash
    client = TestClient(light=True)
    conandata_yml = textwrap.dedent("""
            patches:
                "1.0":
                    # - patch_file: "patches/mypatch.patch"
        """)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import export_conandata_patches, apply_conandata_patches
        class Pkg(ConanFile):
            name = "mypkg"
            version = "1.0"

            def export_sources(self):
                export_conandata_patches(self)

            def build(self):
                apply_conandata_patches(self)
    """)
    client.save({"conandata.yml": conandata_yml, "conanfile.py": conanfile})
    client.run("create .")
    assert "No patches defined for version 1.0 in conandata.yml" in client.out
