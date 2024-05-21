import os
import textwrap

from conan.test.utils.tools import TestClient
from conans.util.files import load


class TestSourceDirty:
    def test_keep_failing_source_folder(self):
        # https://github.com/conan-io/conan/issues/4025
        client = TestClient()
        conanfile = textwrap.dedent("""\
            from conan import ConanFile
            from conan.tools.files import save
            class Pkg(ConanFile):
                def source(self):
                    save(self, "somefile.txt", "hello world!!!")
                    raise Exception("boom")
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg --version=1.0", assert_error=True)
        assert "ERROR: pkg/1.0: Error in source() method, line 6" in client.out
        # Check that we can debug and see the folder
        source_file = os.path.join(client.exported_layout().source(), "somefile.txt")
        assert load(source_file) == "hello world!!!"
        # Without any change, the export will generate same recipe revision, reuse source folder
        client.run("create . --name=pkg --version=1.0", assert_error=True)
        assert "pkg/1.0: Source folder is corrupted, forcing removal" in client.out
        assert "ERROR: pkg/1.0: Error in source() method, line 6" in client.out

        # The install also removes corrupted source folder before proceeding, then call source
        client.run("install --requires=pkg/1.0 --build=missing", assert_error=True)
        assert "pkg/1.0: WARN: Trying to remove corrupted source folder" in client.out
        assert "ERROR: pkg/1.0: Error in source() method, line 6" in client.out

        # This creates a new revision that doesn't need removal, different source folder
        client.save({"conanfile.py": conanfile.replace("source(", "source2(")})
        client.run("create . --name=pkg --version=1.0")
        assert "corrupted, forcing removal" not in client.out
        # Check that it is empty
        assert os.listdir(os.path.join(client.exported_layout().source())) == []
