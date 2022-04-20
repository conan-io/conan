import textwrap

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient


class TestExportFoldersAvailability:

    def test_export_sources_folder_availability_local_methods(self):
        conanfile = textwrap.dedent('''
        from conan import ConanFile

        class ConanLib(ConanFile):

            def layout(self):
                self.folders.source = "MY_SOURCE"

            def generate(self):
                self.output.info("Running generate, value {}!".format(self.export_sources_folder))

            def export(self):
                self.output.info("Running export, value {}!".format(self.export_sources_folder))

            def export_sources(self):
                self.output.info("Running export_sources, value {}!".format(self.export_sources_folder))

            def source(self):
                self.output.info("Running source, value {}!".format(self.export_sources_folder))

            def build(self):
                self.output.info("Running build, value {}!".format(self.export_sources_folder))

            def package(self):
                self.output.info("Running package, value {}!".format(self.export_sources_folder))

        ''')
        client = TestClient()
        client.save({"conanfile.py": conanfile})

        client.run("export . foo/1.0@")
        cache_exports_sources = client.cache.package_layout(ConanFileReference.loads("foo/1.0")).export_sources()
        assert "Running export, value None!" in client.out
        assert "Running export_sources, value {}!".format(cache_exports_sources) in client.out

        client.run("install .")
        # This might be a bit unexpected but self.source_folder is also defined in generate()
        # so it looks consistent with having declared the export_sources_folder
        assert "Running generate, value {}!".format(client.current_folder) in client.out

        client.run("source .")
        assert "Running source, value {}!".format(client.current_folder) in client.out

        client.run("build .")
        assert "Running build, value {}!".format(client.current_folder) in client.out

    def test_export_folder_availability_local_methods(self):
        conanfile = textwrap.dedent('''
        from conan import ConanFile

        class ConanLib(ConanFile):

            def layout(self):
                self.folders.source = "MY_SOURCE"

            def generate(self):
                self.output.info("Running generate, value {}!".format(self.export_folder))

            def export(self):
                self.output.info("Running export, value {}!".format(self.export_folder))

            def export_sources(self):
                self.output.info("Running export_sources, value {}!".format(self.export_folder))

            def source(self):
                self.output.info("Running source, value {}!".format(self.export_folder))

            def build(self):
                self.output.info("Running build, value {}!".format(self.export_folder))

            def package(self):
                self.output.info("Running package, value {}!".format(self.export_folder))

        ''')
        client = TestClient()
        client.save({"conanfile.py": conanfile})

        client.run("export . foo/1.0@")
        cache_exports = client.cache.package_layout(ConanFileReference.loads("foo/1.0")).export()
        assert "Running export_sources, value None!" in client.out
        assert "Running export, value {}!".format(cache_exports) in client.out

        client.run("install .")
        assert "Running generate, value None!" in client.out

        client.run("source .")
        assert "Running source, value None!" in client.out

        client.run("build .")
        assert "Running build, value None!" in client.out

    def test_export_folder_availability_create(self):
        conanfile = textwrap.dedent('''
        from conan import ConanFile

        class ConanLib(ConanFile):

            def layout(self):
                self.folders.source = "MY_SOURCE"

            def generate(self):
                self.output.info("Running generate, value {}!".format(self.export_folder))

            def export(self):
                self.output.info("Running export, value {}!".format(self.export_folder))

            def export_sources(self):
                self.output.info("Running export_sources, value {}!".format(self.export_folder))

            def source(self):
                self.output.info("Running source, value {}!".format(self.export_folder))

            def build(self):
                self.output.info("Running build, value {}!".format(self.export_folder))

            def package(self):
                self.output.info("Running package, value {}!".format(self.export_folder))

        ''')
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        cache_exports = client.cache.package_layout(ConanFileReference.loads("foo/1.0")).export()
        client.run("create . foo/1.0@")
        assert "Running export_sources, value None!" in client.out
        assert "Running export, value {}!".format(cache_exports) in client.out
        assert "Running generate, value None!" in client.out
        assert "Running source, value None!" in client.out
        assert "Running build, value None!" in client.out

    def test_export_sources_folder_availability_create(self):
        conanfile = textwrap.dedent('''
        from conan import ConanFile

        class ConanLib(ConanFile):

            def layout(self):
                self.folders.source = "MY_SOURCE"

            def generate(self):
                self.output.info("Running generate, value {}!".format(self.export_sources_folder))

            def export(self):
                self.output.info("Running export, value {}!".format(self.export_sources_folder))

            def export_sources(self):
                self.output.info("Running export_sources, value {}!".format(self.export_sources_folder))

            def source(self):
                self.output.info("Running source, value {}!".format(self.export_sources_folder))

            def build(self):
                self.output.info("Running build, value {}!".format(self.export_sources_folder))

            def package(self):
                self.output.info("Running package, value {}!".format(self.export_sources_folder))

        ''')
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        cache_exports = client.cache.package_layout(ConanFileReference.loads("foo/1.0")).export_sources()
        client.run("create . foo/1.0@")
        assert "Running export, value None!" in client.out
        assert "Running export_sources, value {}!".format(cache_exports) in client.out
        cache_base_source = client.cache.package_layout(ConanFileReference.loads("foo/1.0")).source()
        assert "Running generate, value {}!".format(cache_base_source) in client.out
        assert "Running source, value {}!".format(cache_base_source) in client.out
        assert "Running build, value {}!".format(cache_base_source) in client.out
