import os
import shutil
import textwrap

from conan.test.utils.tools import TestClient


class TestEditableImport:

    def test_copy_from_dep_in_generate(self):
        """ as we are removing the imports explicit functionality, test if the editable
        can still work for the "imports" case. It seem possible if:

        - "dep" package, both in cache and editable mode, defines correctly its layout
        - Tricky: "dep" package musth use self.source_folder+res instead of layout to package()
        - IMPORTANT: Consumers should use dep.cpp_info.resdirs[0], not dep.package_folder
        """
        t = TestClient()
        dep = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.files import copy
            class Pkg(ConanFile):
                exports_sources = "*"
                def layout(self):
                    self.folders.source = "src"
                    self.cpp.source.resdirs = ["res"]
                def package(self):
                    resdir = os.path.join(self.source_folder, "res")
                    copy(self, "*", resdir, os.path.join(self.package_folder, "data"))
                def package_info(self):
                    self.cpp_info.resdirs = ["data"]
            """)
        consumer = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.files import copy
            class Pkg(ConanFile):
                requires = "dep/0.1"

                def generate(self):
                    dep = self.dependencies["dep"]
                    resdir = dep.cpp_info.resdirs[0]
                    copy(self, "*", resdir, os.path.join(self.build_folder, "imports"))
            """)
        t.save({'dep/conanfile.py': dep,
                'dep/src/res/myfile.txt': "mydata",
                "consumer/conanfile.py": consumer})

        t.run("create dep --name=dep --version=0.1")
        t.run("install consumer")
        assert t.load("consumer/imports/myfile.txt") == "mydata"

        t.run("remove * -c")
        t.run('editable add dep --name=dep --version=0.1')
        shutil.rmtree(os.path.join(t.current_folder, "consumer", "imports"))
        t.run("install consumer")
        assert t.load("consumer/imports/myfile.txt") == "mydata"
