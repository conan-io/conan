import os
import textwrap

from jinja2 import Template

from conans.client.cache.remote_registry import Remotes
from conans.client.graph.build_mode import BuildMode
from conans.client.installer import BinaryInstaller
from conans.client.recorder.action_recorder import ActionRecorder
from conans.model.graph_info import GraphInfo
from conans.model.options import OptionsValues
from conans.model.ref import ConanFileReference
from conans.test.integration.graph.core.graph_manager_base import GraphManagerTest
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


class CrossBuildingBaseTestCase(GraphManagerTest):
    """ Provides reusable bits for other TestCases """

    cmake = textwrap.dedent("""
        from conans import ConanFile

        class BuildRequiresLibrary(ConanFile):
            name = "cmake"
            version = "testing"

            settings = "os"

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))

            def package_info(self):
                cmake_str = "cmake-host" if self.settings.os == "Host" else "cmake-build"

                self.cpp_info.includedirs = [cmake_str, ]
                self.cpp_info.libdirs = [cmake_str, ]
                self.cpp_info.bindirs = [cmake_str, ]

                self.env_info.PATH.append(cmake_str)
                self.env_info.OTHERVAR = cmake_str
    """)

    gtest_tpl = Template(textwrap.dedent("""
        from conans import ConanFile

        class BuildRequires(ConanFile):
            name = "gtest"
            version = "testing"

            settings = "os"

            {% if build_requires %}
            def build_requirements(self):
            {%- for it, force_host in build_requires %}
                self.build_requires("{{ it }}"{% if force_host %}, force_host_context=True{% endif %})
            {%- endfor %}
            {%- endif %}

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))

            def package_info(self):
                gtest_str = "gtest-host" if self.settings.os == "Host" else "gtest-build"

                self.cpp_info.includedirs = [gtest_str, ]
                self.cpp_info.libdirs = [gtest_str, ]
                self.cpp_info.bindirs = [gtest_str, ]

                self.env_info.PATH.append(gtest_str)
                self.env_info.OTHERVAR = gtest_str
    """))

    protobuf_tpl = Template(textwrap.dedent("""
        from conans import ConanFile

        class Protobuf(ConanFile):
            name = "protobuf"
            version = "testing"

            settings = "os"

            {% if build_requires %}
            def build_requirements(self):
            {%- for it, force_host in build_requires %}
                self.build_requires("{{ it }}"{% if force_host %}, force_host_context=True{% endif %})
            {%- endfor %}
            {%- endif %}

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))

            def package_info(self):
                protobuf_str = "protobuf-host" if self.settings.os == "Host" else "protobuf-build"

                self.cpp_info.includedirs = [protobuf_str, ]
                self.cpp_info.libdirs = [protobuf_str, ]
                self.cpp_info.bindirs = [protobuf_str, ]

                self.env_info.PATH.append(protobuf_str)
                self.env_info.OTHERVAR = protobuf_str
    """))

    protoc_tpl = Template(textwrap.dedent("""
        from conans import ConanFile

        class Protoc(ConanFile):
            name = "protoc"
            version = "testing"

            settings = "os"
            requires = "protobuf/testing@user/channel"

            {% if build_requires %}
            def build_requirements(self):
            {%- for it, force_host in build_requires %}
                self.build_requires("{{ it }}"{% if force_host %}, force_host_context=True{% endif %})
            {%- endfor %}
            {%- endif %}

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))

            def package_info(self):
                protoc_str = "protoc-host" if self.settings.os == "Host" else "protoc-build"

                self.cpp_info.includedirs = [protoc_str, ]
                self.cpp_info.libdirs = [protoc_str, ]
                self.cpp_info.bindirs = [protoc_str, ]

                self.env_info.PATH.append(protoc_str)
                self.env_info.OTHERVAR = protoc_str
    """))

    library_tpl = Template(textwrap.dedent("""
        from conans import ConanFile

        class {{name}}(ConanFile):
            settings = "os"

            {% if requires %}
            def requirements(self):
            {%- for it in requires %}
                self.requires("{{ it }}")
            {%- endfor %}
            {%- endif %}

            {% if build_requires %}
            def build_requirements(self):
            {%- for it, force_host in build_requires %}
                self.build_requires("{{ it }}"{% if force_host %}, force_host_context=True{% endif %})
            {%- endfor %}
            {%- endif %}

            def package_info(self):
                lib_str = "{{name}}-host" if self.settings.os == "Host" else "{{name}}-build"
                lib_str += "-" + self.version
                self.cpp_info.libs = [lib_str, ]
                self.cpp_info.includedirs = [lib_str, ]
                self.cpp_info.libdirs = [lib_str, ]
                self.cpp_info.bindirs = [lib_str, ]

                self.env_info.PATH.append(lib_str)
                self.env_info.OTHERVAR = lib_str
        """))

    gtest = gtest_tpl.render()
    protobuf = protobuf_tpl.render()
    protoc = protoc_tpl.render()

    settings_yml = textwrap.dedent("""
        os:
            Host:
            Build:
    """)

    protobuf_ref = ConanFileReference.loads("protobuf/testing@user/channel")
    protoc_ref = ConanFileReference.loads("protoc/testing@user/channel")
    app_ref = ConanFileReference.loads("app/testing@user/channel")
    cmake_ref = ConanFileReference.loads("cmake/testing@user/channel")
    gtest_ref = ConanFileReference.loads("gtest/testing@user/channel")

    def setUp(self):
        super(CrossBuildingBaseTestCase, self).setUp()
        save(self.cache.settings_path, self.settings_yml)

    def _build_graph(self, profile_host, profile_build, install=False):
        path = temp_folder()
        path = os.path.join(path, "conanfile.txt")
        save(path, textwrap.dedent("""
            [requires]
            app/testing@user/channel
        """))

        ref = ConanFileReference(None, None, None, None, validate=False)
        options = OptionsValues()
        graph_info = GraphInfo(profile_host=profile_host, profile_build=profile_build,
                               options=options, root_ref=ref)
        recorder = ActionRecorder()
        app = self._get_app()
        deps_graph = app.graph_manager.load_graph(path, create_reference=None, graph_info=graph_info,
                                                  build_mode=[], check_updates=False, update=False,
                                                  remotes=Remotes(), recorder=recorder)

        if install:
            build_mode = []  # Means build all
            binary_installer = BinaryInstaller(app, recorder)
            build_mode = BuildMode(build_mode, app.out)
            binary_installer.install(deps_graph, None, build_mode, update=False,
                                     profile_host=profile_host, profile_build=profile_build,
                                     graph_lock=None,
                                     keep_build=False)
        return deps_graph
