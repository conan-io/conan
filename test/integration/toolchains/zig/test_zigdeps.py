import re

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def _targets_section(content):
    """ Only the conan_targets map. Executables live in a separate conan_exes map, so
    'is this name absent' assertions must not accidentally match there (or vice versa) """
    return content.split("pub const conan_targets")[1]


def _exes_section(content):
    return content.split("pub const conan_exes")[1].split("pub const conan_targets")[0]


def _target_block(content, target_name):
    """ Extract a single target's own ``Target{ ... }`` body, so assertions can check that
    data isn't leaking between targets (matching on a bare "pkg::name" substring is not
    enough, since that name can also appear inside another target's "requires" list) """
    match = re.search(re.escape(f'.{{ "{target_name}", Target{{') + r"(.*?)\n    } },",
                      content, re.DOTALL)
    assert match, f'target "{target_name}" not found in:\n{content}'
    return match.group(1)


def test_zigdeps_simple_package():
    """ A package without components generates a single "pkg::pkg" target, no redundant
    interface indirection """
    client = TestClient()
    client.save({
        "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_package_info(cpp_info={
            "libs": ["mylib"],
            "location": '"/fake/pkg/lib/libmylib.a"',
            "type": '"static-library"',
            "defines": ["FOO=1", "BAR"],
            "system_libs": ["pthread"],
        }),
        "conanfile.py": GenConanfile("app", "1.0").with_require("pkg/1.0"),
    })
    client.run("create pkg")
    client.run("install . -g ZigDeps")
    content = client.load("conan_zig_deps/conan_deps.zig")

    assert content.count('.{ "pkg::pkg"') == 1
    assert '.kind = .static' in content
    assert '.lib = "/fake/pkg/lib/libmylib.a"' in content
    assert '.name = "FOO", .value = "1"' in content
    assert '.name = "BAR", .value = "1"' in content
    assert '"pthread"' in content

    setup = client.load("conan_zig_deps/conan_setup.zig")
    # The public API operates on a *std.Build.Module: in Zig 0.16 every call used here
    # exists only on Module, not on Step.Compile, and a Module is not necessarily an
    # artifact's root module
    assert "pub fn linkDependency(module: *Module" in setup
    assert "pub fn linkDependencies(module: *Module" in setup
    for call in ("addSystemIncludePath", "addObjectFile", "linkSystemLibrary",
                "linkFramework", "addCMacro", "addFrameworkPath"):
        assert f"module.{call}(" in setup
    # Dependency headers are -isystem, so their warnings aren't the consumer's problem
    assert "module.addIncludePath(" not in setup
    # Conan already resolved what to link; don't let pkg-config override it
    assert ".use_pkg_config = .no" in setup
    # Runtime discovery is deliberately Conan's job (conanrun), not the generator's
    assert "addRPath" not in setup
    assert "addInstallFileWithDir" not in setup


def test_zigdeps_components_own_data_not_merged():
    """ Each component is its own target, carrying only its own includedirs/libs - not merged
    with sibling components - and internal component requires resolve to "pkg::comp" """
    client = TestClient()
    client.save({
        "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_package_info(cpp_info={
            "components": {
                "comp1": {
                    "libs": ["comp1lib"],
                    "location": '"/fake/pkg/lib/libcomp1lib.a"',
                    "type": '"static-library"',
                    "includedirs": ["include/comp1"],
                    "requires": ["comp2"],
                },
                "comp2": {
                    "libs": ["comp2lib"],
                    "location": '"/fake/pkg/lib/libcomp2lib.a"',
                    "type": '"static-library"',
                    "includedirs": ["include/comp2"],
                },
            }
        }),
        "conanfile.py": GenConanfile("app", "1.0").with_require("pkg/1.0"),
    })
    client.run("create pkg")
    client.run("install . -g ZigDeps")
    content = client.load("conan_zig_deps/conan_deps.zig")

    # comp1's own includedirs must not leak comp2's, and vice versa
    comp1_block = _target_block(content, "pkg::comp1")
    assert "include/comp1" in comp1_block
    assert "include/comp2" not in comp1_block
    comp2_block = _target_block(content, "pkg::comp2")
    assert "include/comp2" in comp2_block
    assert "include/comp1" not in comp2_block
    assert '"pkg::comp2"' in comp1_block  # internal requires resolved

    # Synthetic root target requires every real lib-producing component
    root_block = _target_block(content, "pkg::pkg")
    assert '"pkg::comp1"' in root_block
    assert '"pkg::comp2"' in root_block
    assert ".kind = .interface" in root_block


def test_zigdeps_cross_package_component_requires():
    """ A component's cross-package require resolves to "otherpkg::othercomp" when that
    component exists, or falls back to "otherpkg::otherpkg" when it doesn't """
    client = TestClient()
    client.save({
        "dep/conanfile.py": GenConanfile("dep", "1.0").with_package_info(cpp_info={
            "components": {
                "thecomp": {"libs": ["thelib"], "location": '"/fake/dep/lib/libthelib.a"',
                           "type": '"static-library"'},
            }
        }),
        "other/conanfile.py": GenConanfile("other", "1.0").with_package_info(
            cpp_info={"libs": ["otherlib"], "location": '"/fake/other/lib/libotherlib.a"',
                     "type": '"static-library"'}),
        "pkg/conanfile.py": GenConanfile("pkg", "1.0")
            .with_require("dep/1.0")
            .with_require("other/1.0")
            .with_package_info(cpp_info={
                "components": {
                    "comp1": {
                        "libs": ["comp1lib"],
                        "location": '"/fake/pkg/lib/libcomp1lib.a"',
                        "type": '"static-library"',
                        "requires": ["dep::thecomp", "other::other"],
                    },
                }
            }),
        "conanfile.py": GenConanfile("app", "1.0").with_require("pkg/1.0"),
    })
    client.run("create dep")
    client.run("create other")
    client.run("create pkg")
    client.run("install . -g ZigDeps")
    content = client.load("conan_zig_deps/conan_deps.zig")

    comp1_block = _target_block(content, "pkg::comp1")
    assert '"dep::thecomp"' in comp1_block  # real component in "dep"
    assert '"other::other"' in comp1_block  # "other" has no components -> falls back to root


def test_zigdeps_transitive_chain():
    """ Plain (non-component) packages: liba -> libb -> libc, resolved through
    get_transitive_requires (the same helper CMakeConfigDeps uses) """
    client = TestClient()
    client.save({
        "libc/conanfile.py": GenConanfile("libc", "1.0").with_package_info(
            cpp_info={"libs": ["c"], "location": '"/fake/c/libc.a"', "type": '"static-library"'}),
        "libb/conanfile.py": GenConanfile("libb", "1.0").with_require("libc/1.0").with_package_info(
            cpp_info={"libs": ["b"], "location": '"/fake/b/libb.a"', "type": '"static-library"'}),
        "liba/conanfile.py": GenConanfile("liba", "1.0").with_require("libb/1.0").with_package_info(
            cpp_info={"libs": ["a"], "location": '"/fake/a/liba.a"', "type": '"static-library"'}),
        "conanfile.py": GenConanfile("app", "1.0").with_require("liba/1.0"),
    })
    client.run("create libc")
    client.run("create libb")
    client.run("create liba")
    client.run("install . -g ZigDeps")
    content = client.load("conan_zig_deps/conan_deps.zig")

    direct_targets_block = content.split("direct_targets")[1].split("conan_targets")[0]
    assert '"liba::liba"' in direct_targets_block
    assert "libb::libb" not in direct_targets_block  # only direct deps, transitive linking
                                                     # is left to the "requires" recursion

    liba_block = _target_block(content, "liba::liba")
    assert '"libb::libb"' in liba_block
    libb_block = _target_block(content, "libb::libb")
    assert '"libc::libc"' in libb_block


def test_zigdeps_windows_shared_links_import_lib():
    """ A Windows shared lib links against the import lib (.lib), not the runtime .dll.
    Nothing is emitted to make the .dll findable at run time - that is left to Conan's
    conanrun environment, so the .dll path must not appear anywhere """
    client = TestClient()
    client.save({
        "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_package_info(cpp_info={
            "libs": ["mylib"],
            "location": '"C:/pkg/bin/mylib.dll"',
            "link_location": '"C:/pkg/lib/mylib.lib"',
            "type": '"shared-library"',
        }),
        "conanfile.py": GenConanfile("app", "1.0").with_require("pkg/1.0"),
    })
    client.run("create pkg")
    client.run("install . -g ZigDeps")
    content = client.load("conan_zig_deps/conan_deps.zig")

    assert ".kind = .shared" in content
    assert '.lib = "C:/pkg/lib/mylib.lib"' in content
    assert "mylib.dll" not in content


def test_zigdeps_unix_shared_links_library_no_rpath():
    """ A Unix shared lib is linked directly, and deliberately gets no rpath - making it
    loadable at run time is Conan's job via conanrun, not the generator's """
    client = TestClient()
    client.save({
        "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_package_info(cpp_info={
            "libs": ["mylib"],
            "location": '"/fake/pkg/lib/libmylib.so"',
            "type": '"shared-library"',
        }),
        "conanfile.py": GenConanfile("app", "1.0").with_require("pkg/1.0"),
    })
    client.run("create pkg")
    client.run("install . -g ZigDeps")
    content = client.load("conan_zig_deps/conan_deps.zig")

    assert ".kind = .shared" in content
    assert '.lib = "/fake/pkg/lib/libmylib.so"' in content
    assert "rpath" not in content


def test_zigdeps_header_only_no_lib_entry():
    """ A header-only package/component contributes includedirs/defines but no ``lib`` entry,
    and doesn't get skipped just because it has no library file """
    client = TestClient()
    client.save({
        "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_package_info(
            cpp_info={"defines": ["HEADER_ONLY"]}),
        "conanfile.py": GenConanfile("app", "1.0").with_require("pkg/1.0"),
    })
    client.run("create pkg")
    client.run("install . -g ZigDeps")
    content = client.load("conan_zig_deps/conan_deps.zig")

    assert '.{ "pkg::pkg"' in content
    assert ".kind = .interface" in content
    assert ".lib = null" in content
    assert '.name = "HEADER_ONLY", .value = "1"' in content


def test_zigdeps_header_only_components_get_root_target():
    """ Regression test: a components-based package where NO component produces a lib (all
    header-only) must still get a "pkg::pkg" root target, aggregating every contributing
    component - otherwise it's silently missing from linkDependencies()'s direct_targets,
    even though it's a real direct dependency """
    client = TestClient()
    client.save({
        "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_package_info(cpp_info={
            "components": {
                "comp1": {"includedirs": ["include/comp1"], "defines": ["FOO"]},
                "comp2": {"includedirs": ["include/comp2"]},
            }
        }),
        "conanfile.py": GenConanfile("app", "1.0").with_require("pkg/1.0"),
    })
    client.run("create pkg")
    client.run("install . -g ZigDeps")
    content = client.load("conan_zig_deps/conan_deps.zig")

    assert '.{ "pkg::pkg"' in content
    direct_targets_block = content.split("direct_targets")[1].split("conan_targets")[0]
    assert '"pkg::pkg"' in direct_targets_block
    root_block = _target_block(content, "pkg::pkg")
    assert '"pkg::comp1"' in root_block
    assert '"pkg::comp2"' in root_block


def test_zigdeps_dangling_component_reference_pruned():
    """ Regression test: a "requires" pointing at an exe-only component (which never becomes
    a target, since there's nothing to link) must be pruned rather than left dangling - the
    same applies to the analogous package-level (non-component) case """
    client = TestClient()
    client.save({
        "dep/conanfile.py": GenConanfile("dep", "1.0").with_package_info(cpp_info={
            "components": {
                "lib": {"libs": ["lib"], "location": '"/fake/dep/lib/liblib.a"',
                       "type": '"static-library"'},
                "tool": {"exe": '"mytool"', "location": '"/fake/dep/bin/mytool"'},
            }
        }),
        "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_require("dep/1.0").with_package_info(
            cpp_info={"requires": ["dep::tool", "dep::lib"]}),
        "conanfile.py": GenConanfile("app", "1.0").with_require("pkg/1.0"),
    })
    client.run("create dep")
    client.run("create pkg")
    client.run("install . -g ZigDeps")
    content = client.load("conan_zig_deps/conan_deps.zig")

    assert "dep::tool" not in _targets_section(content)  # nothing to link for an exe
    assert '"dep::tool"' in _exes_section(content)  # but its path is still exposed
    pkg_block = _target_block(content, "pkg::pkg")
    assert '"dep::lib"' in pkg_block
    dep_block = _target_block(content, "dep::dep")
    assert '"dep::lib"' in dep_block  # the auto-created root also excludes the exe component


def test_zigdeps_versioned_shared_lib_links_link_location():
    """ A Unix shared lib with a distinct link_location (the common libfoo.so.1.2.3 +
    unversioned libfoo.so link-name pattern) links the unversioned name, since that is what
    link_location is for - the versioned runtime file is not referenced """
    client = TestClient()
    client.save({
        "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_package_info(cpp_info={
            "libs": ["mylib"],
            "location": '"/fake/pkg/lib/libmylib.so.1.2.3"',
            "link_location": '"/fake/pkg/lib/libmylib.so"',
            "type": '"shared-library"',
        }),
        "conanfile.py": GenConanfile("app", "1.0").with_require("pkg/1.0"),
    })
    client.run("create pkg")
    client.run("install . -g ZigDeps")
    content = client.load("conan_zig_deps/conan_deps.zig")

    assert '.lib = "/fake/pkg/lib/libmylib.so"' in content
    assert "libmylib.so.1.2.3" not in content


def test_zigdeps_control_characters_escaped():
    """ Regression test: a raw control character (not just backslash/quote) reaching
    _zigstr must be escaped, or it produces a Zig string literal that fails to compile """
    client = TestClient()
    client.save({
        # A real newline, not the two characters backslash-n: GenConanfile reprs this into
        # the generated recipe, which parses it back to an actual control character
        "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_package_info(
            cpp_info={"defines": ["WEIRD=a\nb"]}),
        "conanfile.py": GenConanfile("app", "1.0").with_require("pkg/1.0"),
    })
    client.run("create pkg")
    client.run("install . -g ZigDeps")
    content = client.load("conan_zig_deps/conan_deps.zig")

    # Escaped into a valid Zig literal, rather than breaking the line in two
    assert '.value = "a\\nb"' in content
    assert '.value = "a' + chr(10) not in content


def test_zigdeps_linkdependency_cycle_guard_present():
    """ The generated setup must guard linkDependency's recursion against a "requires" cycle
    (cpp_info component requires are free-form strings Conan doesn't validate for cycles,
    unlike the package graph) - see the functional cyclic-requires test for an end-to-end
    proof this doesn't crash a real `zig build` """
    client = TestClient()
    client.save({"conanfile.py": GenConanfile("app", "1.0")})
    client.run("install . -g ZigDeps")
    setup = client.load("conan_zig_deps/conan_setup.zig")

    assert "std.StringHashMap" in setup
    assert "visited.contains" in setup


def test_zigdeps_default_components():
    """ When cpp_info.default_components is set, the root target requires exactly those
    components - not every lib-producing one """
    client = TestClient()
    client.save({
        "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_package_info(cpp_info={
            "default_components": ["comp1"],
            "components": {
                "comp1": {"libs": ["comp1lib"], "location": '"/fake/pkg/lib/libcomp1lib.a"',
                         "type": '"static-library"'},
                "comp2": {"libs": ["comp2lib"], "location": '"/fake/pkg/lib/libcomp2lib.a"',
                         "type": '"static-library"'},
            }
        }),
        "conanfile.py": GenConanfile("app", "1.0").with_require("pkg/1.0"),
    })
    client.run("create pkg")
    client.run("install . -g ZigDeps")
    content = client.load("conan_zig_deps/conan_deps.zig")

    root_block = _target_block(content, "pkg::pkg")
    assert '"pkg::comp1"' in root_block
    assert '"pkg::comp2"' not in root_block


def test_zigdeps_app_dependency_excluded_from_requires():
    """ A dependency whose cpp_info marks it as an executable (.exe set, regardless of the
    recipe's own package_type) never becomes a target, so the implicit "link all direct
    deps" fallback _requires uses for a plain package with no explicit .requires must not
    leave a dangling reference to it - it doesn't make sense to link an executable """
    client = TestClient()
    client.save({
        "tool/conanfile.py": GenConanfile("tool", "1.0").with_package_info(
            cpp_info={"exe": '"mytool"', "location": '"/fake/tool/bin/mytool"'}),
        "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_require("tool/1.0").with_package_info(
            cpp_info={"libs": ["pkg"], "location": '"/fake/pkg/lib/libpkg.a"',
                     "type": '"static-library"'}),
        "conanfile.py": GenConanfile("app", "1.0").with_require("pkg/1.0"),
    })
    client.run("create tool")
    client.run("create pkg")
    client.run("install . -g ZigDeps")
    content = client.load("conan_zig_deps/conan_deps.zig")

    assert "tool::tool" not in _targets_section(content)
    pkg_block = _target_block(content, "pkg::pkg")
    assert "tool" not in pkg_block


def test_zigdeps_exe_component_produces_no_target():
    """ A component with .exe set is entirely omitted from conan_deps.zig - there is nothing
    to link for an executable """
    client = TestClient()
    client.save({
        "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_package_info(cpp_info={
            "components": {
                "lib": {"libs": ["lib"], "location": '"/fake/pkg/lib/liblib.a"',
                       "type": '"static-library"'},
                "tool": {"exe": '"mytool"', "location": '"/fake/pkg/bin/mytool"'},
            }
        }),
        "conanfile.py": GenConanfile("app", "1.0").with_require("pkg/1.0"),
    })
    client.run("create pkg")
    client.run("install . -g ZigDeps")
    content = client.load("conan_zig_deps/conan_deps.zig")

    assert '.{ "pkg::lib"' in content
    assert "pkg::tool" not in _targets_section(content)
    assert '"pkg::tool"' in _exes_section(content)  # exposed as an executable path instead


def test_zigdeps_frameworks():
    """ Apple frameworks are collected and rendered for linkFramework() to consume """
    client = TestClient()
    client.save({
        "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_package_info(
            cpp_info={"frameworks": ["CoreFoundation", "Security"]}),
        "conanfile.py": GenConanfile("app", "1.0").with_require("pkg/1.0"),
    })
    client.run("create pkg")
    client.run("install . -g ZigDeps")
    content = client.load("conan_zig_deps/conan_deps.zig")

    pkg_block = _target_block(content, "pkg::pkg")
    assert '"CoreFoundation"' in pkg_block
    assert '"Security"' in pkg_block

    setup = client.load("conan_zig_deps/conan_setup.zig")
    assert "module.linkFramework(framework, .{})" in setup


def test_zigdeps_explicit_root_requires_on_plain_package():
    """ A non-components package that sets cpp_info.requires explicitly (rather than relying
    on the implicit "link all direct deps" fallback) resolves through the same
    parsed_requires() path a components-based package uses, not the transitive_reqs fallback """
    client = TestClient()
    client.save({
        "dep/conanfile.py": GenConanfile("dep", "1.0").with_package_info(cpp_info={
            "components": {
                "used": {"libs": ["used"], "location": '"/fake/dep/lib/libused.a"',
                         "type": '"static-library"'},
                "unused": {"libs": ["unused"], "location": '"/fake/dep/lib/libunused.a"',
                          "type": '"static-library"'},
            }
        }),
        "pkg/conanfile.py": GenConanfile("pkg", "1.0")
            .with_require("dep/1.0")
            .with_package_info(cpp_info={
                "libs": ["pkg"], "location": '"/fake/pkg/lib/libpkg.a"',
                "type": '"static-library"',
                "requires": ["dep::used"],  # only "used", not the whole "dep::dep" root
            }),
        "conanfile.py": GenConanfile("app", "1.0").with_require("pkg/1.0"),
    })
    client.run("create dep")
    client.run("create pkg")
    client.run("install . -g ZigDeps")
    content = client.load("conan_zig_deps/conan_deps.zig")

    pkg_block = _target_block(content, "pkg::pkg")
    assert '"dep::used"' in pkg_block
    assert '"dep::dep"' not in pkg_block
    assert '"dep::unused"' not in pkg_block


def test_zigdeps_experimental_warning():
    """ Like every other recently added generator, ZigDeps announces that it is experimental """
    client = TestClient()
    client.save({"conanfile.py": GenConanfile("app", "1.0")})
    client.run("install . -g ZigDeps")
    assert "ZigDeps is experimental" in client.out


def test_zigdeps_cpp_dependency_links_cpp_runtime():
    """ A C++ dependency must ask for the C++ runtime, or the consumer fails to link with
    undefined std:: symbols. A dependency declaring itself C must not. """
    client = TestClient()
    client.save({
        "cpppkg/conanfile.py": GenConanfile("cpppkg", "1.0")
            .with_class_attribute('languages = "C++"')
            .with_package_info(cpp_info={"libs": ["cpppkg"],
                                         "location": '"/fake/cpppkg/lib/libcpppkg.a"',
                                         "type": '"static-library"'}),
        "cpkg/conanfile.py": GenConanfile("cpkg", "1.0")
            .with_class_attribute('languages = "C"')
            .with_package_info(
            cpp_info={"libs": ["cpkg"], "location": '"/fake/cpkg/lib/libcpkg.a"',
                     "type": '"static-library"'}),
        "conanfile.py": GenConanfile("app", "1.0").with_require("cpppkg/1.0")
            .with_require("cpkg/1.0"),
    })
    client.run("create cpppkg")
    client.run("create cpkg")
    client.run("install . -g ZigDeps")
    content = client.load("conan_zig_deps/conan_deps.zig")

    assert ".link_cpp = true" in _target_block(content, "cpppkg::cpppkg")
    assert ".link_cpp = false" in _target_block(content, "cpkg::cpkg")


def test_zigdeps_requirement_traits_headers_and_libs():
    """ headers=False must keep the dependency's include dirs and defines out of the
    consumer, and libs=False must keep its library from being linked """
    client = TestClient()
    client.save({
        "dep/conanfile.py": GenConanfile("dep", "1.0").with_package_info(cpp_info={
            "libs": ["dep"], "location": '"/fake/dep/lib/libdep.a"',
            "type": '"static-library"', "defines": ["DEP_DEFINE"],
        }),
        "conanfile.py": GenConanfile("app", "1.0").with_requirement(
            "dep/1.0", headers=False, libs=False),
    })
    client.run("create dep")
    client.run("install . -g ZigDeps")
    block = _target_block(client.load("conan_zig_deps/conan_deps.zig"), "dep::dep")

    assert "DEP_DEFINE" not in block             # headers=False -> no defines
    assert ".include_paths = &.{  }," in block   # headers=False -> no include dirs
    assert ".lib = null" in block                # libs=False -> nothing to link


def test_zigdeps_test_requires_are_generated():
    """ test_requires must produce targets - a test build needs them just like host ones """
    client = TestClient()
    client.save({
        "gtest/conanfile.py": GenConanfile("gtest", "1.0").with_package_info(
            cpp_info={"libs": ["gtest"], "location": '"/fake/gtest/lib/libgtest.a"',
                     "type": '"static-library"'}),
        "conanfile.py": GenConanfile("app", "1.0").with_test_requires("gtest/1.0"),
    })
    client.run("create gtest")
    client.run("install . -g ZigDeps")
    content = client.load("conan_zig_deps/conan_deps.zig")

    assert '.{ "gtest::gtest"' in _targets_section(content)


def test_zigdeps_tool_requires_exposed_as_executables():
    """ A tool_require has nothing to link, but its executable path is what a build.zig
    actually wants - exposed through the separate conan_exes map """
    client = TestClient()
    client.save({
        "gen/conanfile.py": GenConanfile("gen", "1.0").with_package_type("application")
            .with_package_info(cpp_info={"exe": '"mygen"',
                                         "location": '"/fake/gen/bin/mygen"'}),
        "conanfile.py": GenConanfile("app", "1.0").with_tool_requires("gen/1.0"),
    })
    client.run("create gen")
    client.run("install . -g ZigDeps")
    content = client.load("conan_zig_deps/conan_deps.zig")

    assert '.{ "gen::gen", "/fake/gen/bin/mygen" }' in _exes_section(content)
    assert "gen::gen" not in _targets_section(content)

    setup = client.load("conan_zig_deps/conan_setup.zig")
    assert "pub fn exePath(" in setup


def test_zigdeps_unappliable_flags_are_exposed_and_warned():
    """ Zig has no way to push a dependency's compiler flags onto sources the consumer owns,
    so they must be surfaced as data and warned about rather than silently dropped """
    client = TestClient()
    client.save({
        "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_package_info(cpp_info={
            "libs": ["pkg"], "location": '"/fake/pkg/lib/libpkg.a"',
            "type": '"static-library"',
            "cflags": ["-pthread"], "cxxflags": ["-fno-rtti"], "exelinkflags": ["-Wl,-z,now"],
        }),
        "conanfile.py": GenConanfile("app", "1.0").with_require("pkg/1.0"),
    })
    client.run("create pkg")
    client.run("install . -g ZigDeps")
    content = client.load("conan_zig_deps/conan_deps.zig")

    assert '"-pthread"' in content
    assert '"-fno-rtti"' in content
    assert '"-Wl,-z,now"' in content
    assert "cannot apply" in client.out or "pass explicitly" in client.out


def test_zigdeps_frameworks_and_package_framework():
    """ frameworkdirs must be emitted as search paths, and a package-shipped .framework
    bundle linked by name with its parent directory as the search path """
    client = TestClient()
    client.save({
        # frameworkdirs is rebased onto the package folder when relative, and a
        # leading-slash path is not absolute on Windows (ntpath.isabs), so an absolute-
        # looking POSIX path would come out drive-prefixed there. Relative, like the
        # includedirs above, behaves the same everywhere.
        "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_package_info(cpp_info={
            "frameworks": ["CoreFoundation"],
            "frameworkdirs": ["myframeworks"],
        }),
        "fw/conanfile.py": GenConanfile("fw", "1.0").with_package_info(cpp_info={
            "package_framework": '"/fake/fw/lib/MyFramework.framework"',
            "type": '"shared-library"',
        }),
        "conanfile.py": GenConanfile("app", "1.0").with_require("pkg/1.0")
            .with_require("fw/1.0"),
    })
    client.run("create pkg")
    client.run("create fw")
    client.run("install . -g ZigDeps")
    content = client.load("conan_zig_deps/conan_deps.zig")

    pkg_block = _target_block(content, "pkg::pkg")
    assert '"CoreFoundation"' in pkg_block
    assert "myframeworks" in pkg_block

    fw_block = _target_block(content, "fw::fw")
    assert '"MyFramework"' in fw_block          # linked by name, .framework stripped
    assert '"/fake/fw/lib"' in fw_block         # parent dir as search path


def test_zigdeps_duplicate_defines_preserved():
    """ Duplicate define names are legal and must not silently collapse to the last one """
    client = TestClient()
    client.save({
        "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_package_info(
            cpp_info={"defines": ["DUP=1", "DUP=2", "OTHER"]}),
        "conanfile.py": GenConanfile("app", "1.0").with_require("pkg/1.0"),
    })
    client.run("create pkg")
    client.run("install . -g ZigDeps")
    block = _target_block(client.load("conan_zig_deps/conan_deps.zig"), "pkg::pkg")

    assert '.name = "DUP", .value = "1"' in block
    assert '.name = "DUP", .value = "2"' in block


def test_zigdeps_invalid_component_require_raises():
    """ A cpp_info.requires naming a component that does not exist is a recipe bug, and must
    be reported rather than silently remapped onto the package root """
    client = TestClient()
    client.save({
        "dep/conanfile.py": GenConanfile("dep", "1.0").with_package_info(cpp_info={
            "components": {"real": {"libs": ["real"],
                                    "location": '"/fake/dep/lib/libreal.a"',
                                    "type": '"static-library"'}}}),
        "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_require("dep/1.0")
            .with_package_info(cpp_info={"requires": ["dep::nonexistent"]}),
        "conanfile.py": GenConanfile("app", "1.0").with_require("pkg/1.0"),
    })
    client.run("create dep")
    client.run("create pkg")
    client.run("install . -g ZigDeps", assert_error=True)
    assert "component 'nonexistent' was not found in 'dep'" in client.out


def test_zigdeps_default_components_skipping_missing():
    """ default_components naming a component that was skipped (exe-only) must not leave a
    dangling reference behind """
    client = TestClient()
    client.save({
        "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_package_info(cpp_info={
            "default_components": ["lib", "tool"],
            "components": {
                "lib": {"libs": ["lib"], "location": '"/fake/pkg/lib/liblib.a"',
                       "type": '"static-library"'},
                "tool": {"exe": '"mytool"', "location": '"/fake/pkg/bin/mytool"'},
            }}),
        "conanfile.py": GenConanfile("app", "1.0").with_require("pkg/1.0"),
    })
    client.run("create pkg")
    client.run("install . -g ZigDeps")
    root_block = _target_block(client.load("conan_zig_deps/conan_deps.zig"), "pkg::pkg")

    assert '"pkg::lib"' in root_block
    assert "pkg::tool" not in root_block  # skipped, so not referenced


def test_zigdeps_libc_always_requested():
    """ Every Conan C/C++ package is built against libc, and Zig does not infer that from an
    object file - without it a dependency's own headers fail on things like malloc """
    client = TestClient()
    client.save({
        "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_package_info(
            cpp_info={"libs": ["pkg"], "location": '"/fake/pkg/lib/libpkg.a"',
                     "type": '"static-library"'}),
        "conanfile.py": GenConanfile("app", "1.0").with_require("pkg/1.0"),
    })
    client.run("create pkg")
    client.run("install . -g ZigDeps")

    assert ".link_libc = true" in _target_block(
        client.load("conan_zig_deps/conan_deps.zig"), "pkg::pkg")
    assert "module.link_libc = true" in client.load("conan_zig_deps/conan_setup.zig")


def test_zigdeps_cpp_assumed_when_languages_unset():
    """ Most recipes still do not declare ``languages``, and those are assumed to be C++:
    linking the C++ runtime into a package that turns out to be pure C is harmless, while
    leaving it out of a C++ one breaks the consumer's link. Declaring ``languages = "C"``
    is what opts out. """
    client = TestClient()
    client.save({
        # No languages declared -> assumed C++
        "cpppkg/conanfile.py": GenConanfile("cpppkg", "1.0")
            .with_package_info(cpp_info={"libs": ["cpppkg"],
                                         "location": '"/fake/cpppkg/lib/libcpppkg.a"',
                                         "type": '"static-library"'}),
        # Declares itself C, so it must NOT get the C++ runtime
        "cpkg/conanfile.py": GenConanfile("cpkg", "1.0")
            .with_class_attribute('languages = "C"')
            .with_package_info(cpp_info={"libs": ["cpkg"],
                                         "location": '"/fake/cpkg/lib/libcpkg.a"',
                                         "type": '"static-library"'}),
        "conanfile.py": GenConanfile("app", "1.0")
            .with_require("cpppkg/1.0").with_require("cpkg/1.0"),
    })
    client.run("create cpppkg")
    client.run("create cpkg")
    client.run("install . -g ZigDeps")
    content = client.load("conan_zig_deps/conan_deps.zig")

    assert ".link_cpp = true" in _target_block(content, "cpppkg::cpppkg")
    assert ".link_cpp = false" in _target_block(content, "cpkg::cpkg")


def test_zigdeps_tool_requires_bindirs_exposed():
    """ Real tool recipes rarely declare cpp_info.exe, so their bindirs are what is actually
    available - exposed so a build.zig can resolve a tool without relying on PATH """
    client = TestClient()
    client.save({
        "tool/conanfile.py": GenConanfile("tool", "1.0").with_package_type("application"),
        "conanfile.py": GenConanfile("app", "1.0").with_tool_requires("tool/1.0"),
    })
    client.run("create tool")
    client.run("install . -g ZigDeps")
    content = client.load("conan_zig_deps/conan_deps.zig")

    tool_dirs = content.split("conan_tool_dirs")[1].split("conan_targets")[0]
    assert '"tool"' in tool_dirs
    assert "/bin" in tool_dirs
    # A tool_requires is build context: nothing to link, so no target for it
    assert "tool::tool" not in _targets_section(content)

    setup = client.load("conan_zig_deps/conan_setup.zig")
    assert "pub fn toolPath(" in setup
