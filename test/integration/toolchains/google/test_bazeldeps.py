import os
import pathlib
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_bazel():
    # https://github.com/conan-io/conan/issues/10471
    dep = textwrap.dedent("""
        from conan import ConanFile
        class ExampleConanIntegration(ConanFile):
            name = "dep"
            version = "0.1"
            def package_info(self):
                self.cpp_info.includedirs = []
                self.cpp_info.libs = []
        """)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.google import BazelToolchain, BazelDeps

        class ExampleConanIntegration(ConanFile):
            generators = 'BazelDeps', 'BazelToolchain'
            requires = 'dep/0.1',
        """)
    c = TestClient()
    c.save({"dep/conanfile.py": dep,
            "consumer/conanfile.py": conanfile})
    c.run("create dep")
    c.run("install consumer")
    assert "conanfile.py: Generator 'BazelToolchain' calling 'generate()'" in c.out


def test_bazel_relative_paths():
    # https://github.com/conan-io/conan/issues/10476
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.google import BazelToolchain, BazelDeps

        class ExampleConanIntegration(ConanFile):
            generators = 'BazelDeps', 'BazelToolchain'
            requires = 'dep/0.1'

            def layout(self):
                self.folders.generators = "conandeps"
        """)
    c = TestClient()
    c.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
            "consumer/conanfile.py": conanfile})
    c.run("create dep")
    c.run("install consumer")
    assert "conanfile.py: Generator 'BazelToolchain' calling 'generate()'" in c.out
    build_file = c.load("consumer/conandeps/dep/BUILD.bazel")
    expected = textwrap.dedent("""\
    # Components precompiled libs
    # Root package precompiled libs

    # Components libraries declaration
    # Package library declaration
    cc_library(
        name = "dep",
        hdrs = glob([
            "include/**",
        ]),
        includes = [
            "include",
        ],
        visibility = ["//visibility:public"],
    )

    # Filegroup library declaration
    filegroup(
        name = "dep_binaries",
        srcs = glob([
            "bin/**",
        ]),
        visibility = ["//visibility:public"],
    )
    """)
    assert build_file == expected


def test_bazel_exclude_folders():
    # https://github.com/conan-io/conan/issues/11081
    dep = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import save
        class ExampleConanIntegration(ConanFile):
            name = "dep"
            version = "0.1"
            def package(self):
                save(self, os.path.join(self.package_folder, "lib", "mymath", "otherfile.a"), "")
                save(self, os.path.join(self.package_folder, "lib", "libmymath.a"), "")
            def package_info(self):
                self.cpp_info.libs = ["mymath"]
        """)
    c = TestClient()
    c.save({"dep/conanfile.py": dep})
    c.run("create dep")
    c.run("install --requires=dep/0.1 -g BazelDeps")
    build_file = c.load("dep/BUILD.bazel")
    assert 'static_library = "lib/libmymath.a"' in build_file


def test_bazeldeps_and_tool_requires():
    """
    Testing that direct build requires are not included in dependencies BUILD.bazel files

    Issues related:
        * https://github.com/conan-io/conan/issues/12444
        * https://github.com/conan-io/conan/issues/12236
    """
    c = TestClient()
    tool = textwrap.dedent("""
        import os
        from conan import ConanFile

        class ToolConanfile(ConanFile):
            name = "tool"
            version = "0.1"

            def package_info(self):
                self.cpp_info.libs = ["mymath"]
        """)
    c.save({"tool/conanfile.py": tool})
    c.run("create tool")
    dep = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import save
        class ExampleConanIntegration(ConanFile):
            name = "dep"
            version = "0.1"

            def build_requirements(self):
                self.tool_requires("tool/0.1")
            def package(self):
                save(self, os.path.join(self.package_folder, "lib", "mymath", "otherfile.a"), "")
                save(self, os.path.join(self.package_folder, "lib", "libmymath.a"), "")
            def package_info(self):
                self.cpp_info.libs = ["mymath"]
                self.cpp_info.bindirs = ["bin1", "bin2"]
        """)
    c.save({"dep/conanfile.py": dep})
    c.run("export dep")
    c.run("install --requires=dep/0.1 -g BazelDeps --build=missing")
    build_file = c.load("dep/BUILD.bazel")
    expected = textwrap.dedent("""\
    # Components precompiled libs
    # Root package precompiled libs
    cc_import(
        name = "mymath_precompiled",
        static_library = "lib/libmymath.a",
    )

    # Components libraries declaration
    # Package library declaration
    cc_library(
        name = "dep",
        hdrs = glob([
            "include/**",
        ]),
        includes = [
            "include",
        ],
        visibility = ["//visibility:public"],
        deps = [
            ":mymath_precompiled",
        ],
    )

    # Filegroup library declaration
    filegroup(
        name = "dep_binaries",
        srcs = glob([
            "bin1/**",
            "bin2/**",
        ]),
        visibility = ["//visibility:public"],
    )
    """)
    assert expected == build_file


def test_pkg_with_public_deps_and_component_requires():
    """
    Testing a complex structure like:

    * first/0.1
        - Global bazel_target_name == "myfirstlib"
        - Components: "cmp1"
    * other/0.1
    * second/0.1
        - Requires: "first/0.1"
        - Components: "mycomponent", "myfirstcomp"
            + "mycomponent" requires "first::cmp1"
            + "myfirstcomp" requires "mycomponent"
    * third/0.1
        - Requires: "second/0.1", "other/0.1"

    Expected file structure after running BazelDeps as generator:
        - second/BUILD.bazel
        - third/BUILD.bazel
        - other/BUILD.bazel
        - myfirstlib/BUILD.bazel
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import save

        class Recipe(ConanFile):

            def package(self):
                # Saving an empty lib
                dest_lib = os.path.join(self.package_folder, "lib", "libcmp1.a")
                save(self, dest_lib, "")

            def package_info(self):
                self.cpp_info.set_property("bazel_target_name", "myfirstlib")
                self.cpp_info.components["cmp1"].libs = ["libcmp1"]
    """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=first --version=0.1")
    client.save({"conanfile.py": GenConanfile("other", "0.1").with_package_file("file.h", "0.1")})
    client.run("create .")

    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class PkgBazelConan(ConanFile):
            requires = "first/0.1"

            def package_info(self):
                self.cpp_info.components["mycomponent"].requires.append("first::cmp1")
                self.cpp_info.components["myfirstcomp"].requires.append("mycomponent")

        """)
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("create . --name=second --version=0.1")
    client.save({"conanfile.py": GenConanfile("third", "0.1").with_package_file("file.h", "0.1")
                                                             .with_require("second/0.1")
                                                             .with_require("other/0.1")},
                clean_first=True)
    client.run("create .")

    client2 = TestClient(cache_folder=client.cache_folder)
    conanfile = textwrap.dedent("""
        [requires]
        third/0.1

        [generators]
        BazelDeps
        """)
    client2.save({"conanfile.txt": conanfile})
    client2.run("install .")
    content = client2.load("third/BUILD.bazel")
    assert textwrap.dedent("""\
    cc_library(
        name = "third",
        hdrs = glob([
            "include/**",
        ]),
        includes = [
            "include",
        ],
        visibility = ["//visibility:public"],
        deps = [
            "@second//:second",
            "@other//:other",
        ],
    )""") in content
    content = client2.load("second/BUILD.bazel")
    assert textwrap.dedent("""\
    # Components libraries declaration
    cc_library(
        name = "second-mycomponent",
        hdrs = glob([
            "include/**",
        ]),
        includes = [
            "include",
        ],
        visibility = ["//visibility:public"],
        deps = [
            "@first//:myfirstlib-cmp1",
        ],
    )

    cc_library(
        name = "second-myfirstcomp",
        hdrs = glob([
            "include/**",
        ]),
        includes = [
            "include",
        ],
        visibility = ["//visibility:public"],
        deps = [
            ":second-mycomponent",
        ],
    )

    # Package library declaration
    cc_library(
        name = "second",
        hdrs = glob([
            "include/**",
        ]),
        includes = [
            "include",
        ],
        visibility = ["//visibility:public"],
        deps = [
            ":second-mycomponent",
            ":second-myfirstcomp",
            "@first//:myfirstlib",
        ],
    )""") in content
    content = client2.load("first/BUILD.bazel")
    assert textwrap.dedent("""\
    # Components precompiled libs
    cc_import(
        name = "libcmp1_precompiled",
        static_library = "lib/libcmp1.a",
    )

    # Root package precompiled libs

    # Components libraries declaration
    cc_library(
        name = "myfirstlib-cmp1",
        hdrs = glob([
            "include/**",
        ]),
        includes = [
            "include",
        ],
        visibility = ["//visibility:public"],
        deps = [
            ":libcmp1_precompiled",
        ],
    )

    # Package library declaration
    cc_library(
        name = "myfirstlib",
        hdrs = glob([
            "include/**",
        ]),
        includes = [
            "include",
        ],
        visibility = ["//visibility:public"],
        deps = [
            ":myfirstlib-cmp1",
        ],
    )""") in content
    content = client2.load("other/BUILD.bazel")
    assert "deps =" not in content


def test_pkg_with_public_deps_and_component_requires_2():
    """
    Testing another complex structure like:

    * other/0.1
        - Global bazel_target_name == "fancy_name"
        - Components: "cmp1", "cmp2", "cmp3"
            + "cmp1" bazel_target_name == "component1" (it shouldn't be affected by "fancy_name")
            + "cmp3" bazel_target_name == "component3" (it shouldn't be affected by "fancy_name")
            + "cmp3" requires "cmp1"
    * pkg/0.1
        - Requires: "other/0.1" -> "other::cmp1"

    Expected file structure after running BazelDeps as generator:
        - fancy_name/BUILD.bazel (components: "component1", "fancy_name-cmp2", "component3")
        - pkg/BUILD.bazel
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import save

        class Recipe(ConanFile):

            def package(self):
                # Saving an empty lib
                dest_lib = os.path.join(self.package_folder, "lib", "libother_cmp1.a")
                dest_lib2 = os.path.join(self.package_folder, "lib", "libother_cmp2.a")
                save(self, dest_lib, "")
                save(self, dest_lib2, "")

            def package_info(self):
                self.cpp_info.set_property("bazel_target_name", "fancy_name")
                self.cpp_info.components["cmp1"].libs = ["other_cmp1"]
                self.cpp_info.components["cmp1"].set_property("bazel_target_name", "component1")
                self.cpp_info.components["cmp2"].libs = ["other_cmp2"]
                self.cpp_info.components["cmp3"].requires.append("cmp1")
                self.cpp_info.components["cmp3"].set_property("bazel_target_name", "component3")
    """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=other --version=1.0")

    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class PkgBazelConan(ConanFile):
            requires = "other/1.0"

            def package_info(self):
                self.cpp_info.requires = ["other::cmp1"]
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=pkg --version=0.1")

    client2 = TestClient(cache_folder=client.cache_folder)
    conanfile = textwrap.dedent("""
        [requires]
        pkg/0.1

        [generators]
        BazelDeps
        """)
    client2.save({"conanfile.txt": conanfile})
    client2.run("install .")
    content = client2.load("pkg/BUILD.bazel")
    assert textwrap.dedent("""\
    # Package library declaration
    cc_library(
        name = "pkg",
        hdrs = glob([
            "include/**",
        ]),
        includes = [
            "include",
        ],
        visibility = ["//visibility:public"],
        deps = [
            "@other//:component1",
        ],
    )""") in content
    content = client2.load("other/BUILD.bazel")
    assert textwrap.dedent("""\
    # Components precompiled libs
    cc_import(
        name = "other_cmp1_precompiled",
        static_library = "lib/libother_cmp1.a",
    )

    cc_import(
        name = "other_cmp2_precompiled",
        static_library = "lib/libother_cmp2.a",
    )


    # Root package precompiled libs

    # Components libraries declaration
    cc_library(
        name = "component1",
        hdrs = glob([
            "include/**",
        ]),
        includes = [
            "include",
        ],
        visibility = ["//visibility:public"],
        deps = [
            ":other_cmp1_precompiled",
        ],
    )

    cc_library(
        name = "fancy_name-cmp2",
        hdrs = glob([
            "include/**",
        ]),
        includes = [
            "include",
        ],
        visibility = ["//visibility:public"],
        deps = [
            ":other_cmp2_precompiled",
        ],
    )

    cc_library(
        name = "component3",
        hdrs = glob([
            "include/**",
        ]),
        includes = [
            "include",
        ],
        visibility = ["//visibility:public"],
        deps = [
            ":component1",
        ],
    )

    # Package library declaration
    cc_library(
        name = "fancy_name",
        hdrs = glob([
            "include/**",
        ]),
        includes = [
            "include",
        ],
        visibility = ["//visibility:public"],
        deps = [
            ":component1",
            ":fancy_name-cmp2",
            ":component3",
        ],
    )""") in content


def test_pkgconfigdeps_with_test_requires():
    """
    BazelDeps has to create any declared test requirements on the recipe.
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import save

        class Recipe(ConanFile):

            def package(self):
                # Saving an empty lib
                dest_lib = os.path.join(self.package_folder, "lib", "liblib{0}.a")
                save(self, dest_lib, "")

            def package_info(self):
                self.cpp_info.libs = ["lib{0}"]
        """)
    with client.chdir("app"):
        client.save({"conanfile.py": conanfile.format("app")})
        client.run("create . --name=app --version=1.0")
    with client.chdir("test"):
        client.save({"conanfile.py": conanfile.format("test")})
        client.run("create . --name=test --version=1.0")
    # Create library having build and test requires
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class HelloLib(ConanFile):
            def build_requirements(self):
                self.test_requires('app/1.0')
                self.test_requires('test/1.0')
        """)
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("install . -g BazelDeps")
    expected = textwrap.dedent("""\
    # Root package precompiled libs
    cc_import(
        name = "lib{0}_precompiled",
        static_library = "lib/liblib{0}.a",
    )

    # Components libraries declaration
    # Package library declaration
    cc_library(
        name = "{0}",
        hdrs = glob([
            "include/**",
        ]),
        includes = [
            "include",
        ],
        visibility = ["//visibility:public"],
        deps = [
            ":lib{0}_precompiled",
        ],
    )""")
    assert expected.format("test") in client.load("test/BUILD.bazel")
    assert expected.format("app") in client.load("app/BUILD.bazel")


def test_with_editable_layout():
    """
    Testing if editable mode is working for a Bazel project (using BazelDeps and bazel_layout)
    """
    client = TestClient()
    dep = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.google import bazel_layout
        from conan.tools.files import save
        class Dep(ConanFile):
            name = "dep"
            version = "0.1"

            def layout(self):
                bazel_layout(self, target_folder="main")
                self.cpp.source.includedirs = ["include"]

            def package_info(self):
                self.cpp_info.libs = ["mylib"]
        """)
    client.save({"dep/conanfile.py": dep,
                 "dep/include/header.h": "",
                 "dep/bazel-bin/main/libmylib.a": "",
                 "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_requires("dep/0.1")})
    client.run("create dep")
    client.run("editable add dep --name=dep --version=0.1")
    recipes_folder = client.current_folder.replace("\\", "/")
    with client.chdir("pkg"):
        client.run("install . -g BazelDeps")
        # TODO: Remove when dropped Bazel 6.x compatibility
        content = client.load("dependencies.bzl")
        assert textwrap.dedent(f"""\
        def load_conan_dependencies():
            native.new_local_repository(
                name="dep",
                path="{recipes_folder}/dep",
                build_file="{recipes_folder}/pkg/dep/BUILD.bazel",
            )""") in content
        # Bazel 7.x
        content = client.load("conan_deps_module_extension.bzl")
        assert textwrap.dedent(f"""\
        def _load_dependenies_impl(mctx):
            conan_dependency_repo(
                name = "dep",
                package_path = "{recipes_folder}/dep",
                build_file_path = "{recipes_folder}/pkg/dep/BUILD.bazel",
            )""") in content
        content = client.load("dep/BUILD.bazel")
        assert pathlib.Path(client.current_folder, "conan_deps_repo_rules.bzl").exists()
        assert textwrap.dedent("""\
        cc_import(
            name = "mylib_precompiled",
            static_library = "bazel-bin/main/libmylib.a",
        )

        # Components libraries declaration
        # Package library declaration
        cc_library(
            name = "dep",
            hdrs = glob([
                "include/**",
            ]),
            includes = [
                "include",
            ],
            visibility = ["//visibility:public"],
            deps = [
                ":mylib_precompiled",
            ],
        )""") in content


def test_tool_requires():
    """
    Testing if BUILD files are created for tool requires if build_context_activated=True is used.
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class PkgBazelConan(ConanFile):

            def package_info(self):
                self.cpp_info.libs = ["libtool"]
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=tool --version=1.0")

    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class PkgBazelConan(ConanFile):

            def package_info(self):
                self.cpp_info.set_property("bazel_target_name", "libother")
                self.cpp_info.set_property("bazel_repository_name", "other-repo")
                self.cpp_info.components["cmp1"].libs = ["other_cmp1"]
                self.cpp_info.components["cmp1"].set_property("bazel_target_name", "component1")
                self.cpp_info.components["cmp2"].libs = ["other_cmp2"]
                self.cpp_info.components["cmp3"].requires.append("cmp1")
                self.cpp_info.components["cmp3"].set_property("bazel_target_name", "component3")
        """)
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("create . --name=other --version=1.0")

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.google import BazelDeps

        class PkgBazelConan(ConanFile):
            name = "demo"
            version = "1.0"

            def build_requirements(self):
                self.tool_requires("tool/1.0")
                self.tool_requires("other/1.0")

            def generate(self):
                tc = BazelDeps(self)
                tc.build_context_activated = ["other", "tool"]
                tc.generate()
        """)
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("install . -pr:h default -pr:b default")
    assert 'name = "tool"' in client.load("build-tool/BUILD.bazel")
    assert textwrap.dedent("""\
    # Components libraries declaration
    cc_library(
        name = "component1",
        hdrs = glob([
            "include/**",
        ]),
        includes = [
            "include",
        ],
        visibility = ["//visibility:public"],
    )

    cc_library(
        name = "libother-cmp2",
        hdrs = glob([
            "include/**",
        ]),
        includes = [
            "include",
        ],
        visibility = ["//visibility:public"],
    )

    cc_library(
        name = "component3",
        hdrs = glob([
            "include/**",
        ]),
        includes = [
            "include",
        ],
        visibility = ["//visibility:public"],
        deps = [
            ":component1",
        ],
    )

    # Package library declaration
    cc_library(
        name = "libother",
        hdrs = glob([
            "include/**",
        ]),
        includes = [
            "include",
        ],
        visibility = ["//visibility:public"],
        deps = [
            ":component1",
            ":libother-cmp2",
            ":component3",
        ],
    )""") in client.load("build-other-repo/BUILD.bazel")
    # TODO: Remove when dropped Bazel 6.x compatibility
    # Let's check if the names used in the dependencies.bzl are correct
    content = client.load("dependencies.bzl")
    assert 'name="build-other-repo"' in content  # build context + bazel_repository_name prop
    assert 'name="build-tool"' in content  # build context + package reference name
    # Bazel 7.x
    # Let's check if the names used in the conan_deps_repo_rules.bzl are correct
    content = client.load("conan_deps_module_extension.bzl")
    assert 'name = "build-other-repo"' in content  # build context + bazel_repository_name prop
    assert 'name = "build-tool"' in content  # build context + package reference name


def test_tool_requires_not_created_if_no_activated():
    """
    Testing if there are no BUILD files created in no context are activated
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class PkgBazelConan(ConanFile):

            def package_info(self):
                self.cpp_info.libs = ["libtool"]
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=tool --version=1.0")

    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class PkgBazelConan(ConanFile):
            name = "demo"
            version = "1.0"
            generators = "BazelDeps"

            def build_requirements(self):
                self.tool_requires("tool/1.0")

        """)
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("install . -pr:h default -pr:b default")
    assert not os.path.exists(os.path.join(client.current_folder, "tool"))


def test_tool_requires_raise_exception_if_exist_both_require_and_build_one():
    """
    Testing if same dependency exists in both host and build context
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class PkgBazelConan(ConanFile):

            def package_info(self):
                self.cpp_info.libs = ["libtool"]
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . --name=tool --version=1.0")

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.google import BazelDeps

        class PkgBazelConan(ConanFile):
            name = "demo"
            version = "1.0"

            def requirements(self):
                self.requires("tool/1.0")

            def build_requirements(self):
                self.tool_requires("tool/1.0")

            def generate(self):
                tc = BazelDeps(self)
                tc.build_context_activated = ["tool"]
                tc.generate()
        """)
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("install . -pr:h default -pr:b default")
    # Different Bazel repository names, same target names
    assert 'name = "tool"' in client.load("build-tool/BUILD.bazel")
    assert 'name = "tool"' in client.load("tool/BUILD.bazel")


def test_error_missing_bazel_build_files_in_build_context():
    """
    BazelDeps should generate BUILD files in the build context for a
    test_package that both requires(example/1.0) and tool_requires(example/1.0),
    which depends on other requirements
    * Issue related: https://github.com/conan-io/conan/issues/12664
    """
    c = TestClient()
    example = textwrap.dedent("""
        import os
        from conan import ConanFile
        class Example(ConanFile):
            name = "example"
            version = "1.0"
            requires = "game/1.0"
            generators = "BazelDeps"
            settings = "build_type"
            def build(self):
                context = "build-" if self.context == "build" else ""
                assert os.path.exists(os.path.join(f"{context}math", "BUILD.bazel"))
                assert os.path.exists(os.path.join(f"{context}engine", "BUILD.bazel"))
                assert os.path.exists(os.path.join(f"{context}game", "BUILD.bazel"))
            """)
    c.save({"math/conanfile.py": GenConanfile("math", "1.0").with_settings("build_type"),
            "engine/conanfile.py": GenConanfile("engine", "1.0").with_settings("build_type")
                                                                .with_require("math/1.0"),
            "game/conanfile.py": GenConanfile("game", "1.0").with_settings("build_type")
                                                            .with_requires("engine/1.0"),
            "example/conanfile.py": example,
            # With ``with_test()`` it already generates a requires(example/1.0)
            "example/test_package/conanfile.py": GenConanfile().with_build_requires("example/1.0")
                                                               .with_test("pass")})
    c.run("create math")
    c.run("create engine")
    c.run("create game")
    # This used to crash because of the assert inside the build() method
    c.run("create example -pr:b=default -pr:h=default")
    # Now make sure we can actually build with build!=host context
    # The debug binaries are missing, so adding --build=missing
    c.run("create example -pr:b=default -pr:h=default -s:h build_type=Debug --build=missing "
          "--build=example")
    c.assert_listed_require({"example/1.0": "Cache"})
    c.assert_listed_require({"example/1.0": "Cache"}, build=True)


class TestBazelGenerationBuildContext:
    """
    https://github.com/conan-io/conan/issues/15764
    """
    def test_bazel_generate(self):
        c = TestClient()
        tool = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.google import BazelDeps
            class Example(ConanFile):
                name = "tool"
                version = "1.0"
                requires = "wayland/1.0"
                tool_requires = "wayland/1.0"
                def generate(self):
                    tc = BazelDeps(self)
                    tc.build_context_activated = ["wayland", "dep"]
                    tc.generate()
                def build(self):
                    # Build context
                    assert os.path.exists(os.path.join("build-wayland", "BUILD.bazel"))
                    # Revisit this after investigation -> build_req = conanfile.dependencies.direct_build
                    # assert os.path.exists(os.path.join("build-dep", "BUILD.bazel"))
                    # Host context
                    assert os.path.exists(os.path.join("wayland", "BUILD.bazel"))
                    assert os.path.exists(os.path.join("dep", "BUILD.bazel"))
                """)
        c.save({"dep/conanfile.py": GenConanfile("dep", "1.0").with_package_type("shared-library"),
                "wayland/conanfile.py": GenConanfile("wayland", "1.0").with_requires("dep/1.0"),
                "tool/conanfile.py": tool,
                "app/conanfile.py": GenConanfile().with_tool_requires("tool/1.0")})
        c.run("export dep")
        c.run("export wayland")
        c.run("export tool")
        c.run("install app --build=missing")
        assert "Install finished successfully" in c.out  # the asserts in build() didn't fail
        # Now make sure we can actually build with build!=host context
        c.run("install app -s:h build_type=Debug --build=missing")
        assert "Install finished successfully" in c.out  # the asserts in build() didn't fail

    def test_bazel_generate_components(self):
        c = TestClient()
        tool = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.google import BazelDeps
            class Example(ConanFile):
                name = "tool"
                version = "1.0"
                requires = "wayland/1.0"
                tool_requires = "wayland/1.0"
                def generate(self):
                    tc = BazelDeps(self)
                    tc.build_context_activated = ["wayland", "dep"]
                    tc.generate()
                def build(self):
                    # Build context
                    assert os.path.exists(os.path.join("build-wayland", "BUILD.bazel"))
                    # Revisit this after investigation -> build_req = conanfile.dependencies.direct_build
                    # assert os.path.exists(os.path.join("build-dep", "BUILD.bazel"))
                    # Host context
                    assert os.path.exists(os.path.join("wayland", "BUILD.bazel"))
                    assert os.path.exists(os.path.join("dep", "BUILD.bazel"))
                """)
        wayland = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "wayland"
                version = "1.0"
                requires = "dep/1.0"
                def package_info(self):
                    self.cpp_info.components["client"].libs = []
                    self.cpp_info.components["server"].libs = []
            """)
        c.save({"dep/conanfile.py": GenConanfile("dep", "1.0").with_package_type("shared-library"),
                "wayland/conanfile.py": wayland,
                "tool/conanfile.py": tool,
                "app/conanfile.py": GenConanfile().with_tool_requires("tool/1.0")})
        c.run("export dep")
        c.run("export wayland")
        c.run("export tool")
        c.run("install app --build=missing")
        assert "Install finished successfully" in c.out  # the asserts in build() didn't fail
        # Now make sure we can actually build with build!=host context
        c.run("install app -s:h build_type=Debug --build=missing")
        assert "Install finished successfully" in c.out  # the asserts in build() didn't fail
