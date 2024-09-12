import textwrap

from conan.test.utils.tools import TestClient


class TestExportFoldersAvailability:

    def test_export_sources_folder_availability_local_methods(self):
        conanfile = textwrap.dedent('''
        import os
        from conan import ConanFile

        class ConanLib(ConanFile):

            def layout(self):
                self.folders.source = "MY_SOURCE"

            def generate(self):
                assert os.path.exists(self.export_sources_folder)

            def export(self):
                assert self.export_sources_folder is None

            def export_sources(self):
                assert os.path.exists(self.export_sources_folder)

            def source(self):
                assert os.path.exists(self.export_sources_folder)

            def build(self):
                assert os.path.exists(self.export_sources_folder)

            def package(self):
                assert os.path.exists(self.export_sources_folder)

        ''')
        client = TestClient()
        client.save({"conanfile.py": conanfile})

        client.run("export . --name foo --version 1.0")
        client.run("install .")
        client.run("source .")
        client.run("build .")

    def test_export_folder_availability_local_methods(self):
        conanfile = textwrap.dedent('''
        import os
        from conan import ConanFile

        class ConanLib(ConanFile):

            def layout(self):
                self.folders.source = "MY_SOURCE"

            def generate(self):
                assert os.path.exists(self.export_sources_folder)

            def export_sources(self):
                # We need it available for the post_export hook so it is available
                assert os.path.exists(self.export_folder)

            def export(self):
                assert os.path.exists(self.export_folder)

            def source(self):
                assert os.path.exists(self.export_sources_folder)

            def build(self):
                assert os.path.exists(self.export_sources_folder)

            def package(self):
                assert os.path.exists(self.export_sources_folder)

        ''')
        client = TestClient()
        client.save({"conanfile.py": conanfile})

        client.run("export . --name foo --version 1.0")
        client.run("install .")
        client.run("source .")
        client.run("build .")

    def test_export_folder_availability_create(self):
        conanfile = textwrap.dedent('''
        import os
        from conan import ConanFile

        class ConanLib(ConanFile):

            def layout(self):
                self.folders.source = "MY_SOURCE"

            def generate(self):
                assert self.export_folder is None

            def export(self):
                assert os.path.exists(self.export_folder)

            def export_sources(self):
                # We need it available for the post_export hook so it is available
                assert os.path.exists(self.export_folder)

            def source(self):
                assert self.export_folder is None

            def build(self):
                assert self.export_folder is None

            def package(self):
                assert self.export_folder is None

        ''')
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . --name foo --version 1.0")

    def test_export_sources_folder_availability_create(self):
        conanfile = textwrap.dedent('''
        import os
        from conan import ConanFile

        class ConanLib(ConanFile):

            def layout(self):
                self.folders.source = "MY_SOURCE"

            def generate(self):
                assert os.path.exists(self.export_sources_folder)

            def export(self):
                assert self.export_sources_folder is None

            def export_sources(self):
                assert os.path.exists(self.export_sources_folder)

            def source(self):
                assert os.path.exists(self.export_sources_folder)

            def build(self):
                assert os.path.exists(self.export_sources_folder)

            def package(self):
                assert os.path.exists(self.export_sources_folder)

        ''')
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . --name foo --version 1.0")
