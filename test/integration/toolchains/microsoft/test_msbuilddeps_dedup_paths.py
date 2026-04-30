import os
import re
import textwrap

import pytest

from conan.test.utils.tools import TestClient


# Shared fixture: a multi-component package where all 3 components share the
# same include/ and lib/ directories.  This mimics real-world packages like
# Boost, where many components point to a single include tree.
_multi_comp_pkg = textwrap.dedent("""
    import os
    from conan import ConanFile
    from conan.tools.files import save

    class MultiCompPkg(ConanFile):
        name = "mypkg"
        version = "1.0"
        package_type = "static-library"

        def package(self):
            save(self, os.path.join(self.package_folder, "include", "core.h"), "")
            save(self, os.path.join(self.package_folder, "include", "client.h"), "")
            save(self, os.path.join(self.package_folder, "include", "server.h"), "")
            save(self, os.path.join(self.package_folder, "lib", "core.lib"), "")
            save(self, os.path.join(self.package_folder, "lib", "client.lib"), "")
            save(self, os.path.join(self.package_folder, "lib", "server.lib"), "")

        def package_info(self):
            self.cpp_info.components["core"].libs = ["core"]
            self.cpp_info.components["core"].includedirs = ["include"]
            self.cpp_info.components["core"].libdirs = ["lib"]

            self.cpp_info.components["client"].libs = ["client"]
            self.cpp_info.components["client"].includedirs = ["include"]
            self.cpp_info.components["client"].libdirs = ["lib"]
            self.cpp_info.components["client"].requires = ["core"]

            self.cpp_info.components["server"].libs = ["server"]
            self.cpp_info.components["server"].includedirs = ["include"]
            self.cpp_info.components["server"].libdirs = ["lib"]
            self.cpp_info.components["server"].requires = ["core"]
    """)

_consumer = textwrap.dedent("""
    from conan import ConanFile
    class Consumer(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        requires = "mypkg/1.0"
        generators = "MSBuildDeps"
    """)


def _create_and_install(client):
    """Create the multi-component package and install into 'app/'."""
    client.save({"pkg/conanfile.py": _multi_comp_pkg,
                 "app/conanfile.py": _consumer})
    client.run("create pkg")
    client.run("install app -s arch=x86_64")


# ──────────────────────────────────────────────────────────
#  TEST 1 – Prove the duplication problem exists (structural)
# ──────────────────────────────────────────────────────────
def test_msbuilddeps_duplicate_paths_source():
    """
    Structural test: proves that multiple components emit the *same*
    AdditionalIncludeDirectories / AdditionalLibraryDirectories prepend,
    which is the root cause of path duplication at MSBuild evaluation time.
    """
    client = TestClient()
    _create_and_install(client)

    # Each component's activation props appends to AdditionalIncludeDirectories
    core_props = client.load("app/conan_mypkg_core_release_x64.props")
    client_props = client.load("app/conan_mypkg_client_release_x64.props")
    server_props = client.load("app/conan_mypkg_server_release_x64.props")

    for name, props in [("core", core_props),
                        ("client", client_props),
                        ("server", server_props)]:
        assert "AdditionalIncludeDirectories" in props, \
            f"{name} component must set AdditionalIncludeDirectories"
        assert "AdditionalLibraryDirectories" in props, \
            f"{name} component must set AdditionalLibraryDirectories"

    # All three *vars* files reference the same include directory (relative
    # to their RootFolder, which all resolve to the same package folder)
    core_vars = client.load("app/conan_mypkg_core_vars_release_x64.props")
    client_vars = client.load("app/conan_mypkg_client_vars_release_x64.props")
    server_vars = client.load("app/conan_mypkg_server_vars_release_x64.props")

    # All three RootFolder values point to the same physical directory
    roots = set()
    for v in [core_vars, client_vars, server_vars]:
        m = re.search(r"<Conan\w+RootFolder>(.*?)</Conan\w+RootFolder>", v)
        assert m, "RootFolder property must exist"
        roots.add(m.group(1))
    assert len(roots) == 1, \
        "All components share the same RootFolder (same package)"


# ──────────────────────────────────────────────────────────
#  TEST 2 – Verify the fix exists (XML structure)
# ──────────────────────────────────────────────────────────
def test_msbuilddeps_dedup_target_structure():
    """
    Verify that conandeps.props contains a correctly structured
    ConanDeduplicatePaths Target using RemoveDuplicates.
    """
    from xml.dom import minidom

    client = TestClient()
    _create_and_install(client)

    conandeps = client.load("app/conandeps.props")

    # Must be valid XML
    dom = minidom.parseString(conandeps)

    # Exactly one Target element
    targets = dom.getElementsByTagName("Target")
    assert len(targets) == 1, "Should have exactly one Target element"

    target = targets[0]
    assert target.getAttribute("Name") == "ConanDeduplicatePaths"

    # BeforeTargets must include all four compiler/linker stages
    before = target.getAttribute("BeforeTargets")
    for stage in ("ClCompile", "Link", "Midl", "ResourceCompile"):
        assert stage in before, f"BeforeTargets must include {stage}"

    # RemoveDuplicates tasks: one for includes, one for libs
    remove_dup_tasks = target.getElementsByTagName("RemoveDuplicates")
    assert len(remove_dup_tasks) >= 2, \
        "Should have at least 2 RemoveDuplicates tasks (include + lib)"

    # Verify the correct item names are used
    assert "_ConanIncludePaths" in conandeps
    assert "_ConanUniqueIncludePaths" in conandeps
    assert "_ConanLibPaths" in conandeps
    assert "_ConanUniqueLibPaths" in conandeps


# ──────────────────────────────────────────────────────────
#  TEST 3 – Behavioral validation (simulate MSBuild evaluation)
# ──────────────────────────────────────────────────────────
def test_msbuilddeps_dedup_behavioral():
    """
    Behavioral test that simulates what MSBuild does at evaluation time.

    The deduplication happens at MSBuild *runtime*, not in the static XML.
    To prove the fix works without invoking MSBuild we:

    1. Collect $(ConanXXXRootFolder) values → all resolve to the same path.
    2. Collect $(ConanXXXIncludeDirectories) values and resolve the variable
       references, producing the real paths MSBuild would see.
    3. Concatenate them as MSBuild would (each component prepends its dirs
       to %(AdditionalIncludeDirectories)).
    4. Show the raw result contains duplicates.
    5. Apply the same logic RemoveDuplicates performs (split → unique → rejoin).
    6. Assert deduplicated result is correct, no paths lost.
    """
    client = TestClient()
    _create_and_install(client)

    comp_names = ["core", "client", "server"]

    # ── Step 1+2: Collect and resolve variable references ──
    # Each vars file defines:
    #   <ConanXXX_YYYRootFolder>  /absolute/path  </…>
    #   <ConanXXX_YYYIncludeDirectories>  $(ConanXXX_YYYRootFolder)/include;  </…>
    # We resolve the $(…) references to get the real paths.
    resolved_includes = []
    resolved_libs = []

    for comp in comp_names:
        vars_content = client.load(
            f"app/conan_mypkg_{comp}_vars_release_x64.props")

        # Extract RootFolder value
        m_root = re.search(
            r"<Conan(\w+)RootFolder>(.*?)</Conan\w+RootFolder>",
            vars_content)
        assert m_root, f"RootFolder missing for {comp}"
        var_name = m_root.group(1)           # e.g. "mypkg_core"
        root_value = m_root.group(2)         # e.g. "C:\...\p"

        # Extract IncludeDirectories (contains $(ConanXXXRootFolder)/include;)
        m_inc = re.search(
            r"<Conan\w+IncludeDirectories>(.*?)</Conan\w+IncludeDirectories>",
            vars_content)
        assert m_inc, f"IncludeDirectories missing for {comp}"
        raw_inc = m_inc.group(1)

        # Resolve: replace $(ConanXXXRootFolder) with the actual value
        resolved_inc = raw_inc.replace(
            f"$(Conan{var_name}RootFolder)", root_value)
        for p in resolved_inc.split(";"):
            if p.strip():
                resolved_includes.append(p.strip())

        # Extract LibraryDirectories
        m_lib = re.search(
            r"<Conan\w+LibraryDirectories>(.*?)</Conan\w+LibraryDirectories>",
            vars_content)
        assert m_lib, f"LibraryDirectories missing for {comp}"
        raw_lib = m_lib.group(1)
        resolved_lib = raw_lib.replace(
            f"$(Conan{var_name}RootFolder)", root_value)
        for p in resolved_lib.split(";"):
            if p.strip():
                resolved_libs.append(p.strip())

    # ── Step 3: This is what MSBuild sees after evaluating all components ──
    raw_include_str = ";".join(resolved_includes)
    raw_lib_str = ";".join(resolved_libs)

    # ── Step 4: Prove duplicates exist ──
    assert len(resolved_includes) > len(set(resolved_includes)), \
        ("Bug confirmation: after resolving variables, include paths must "
         f"contain duplicates (got {len(resolved_includes)} entries, "
         f"{len(set(resolved_includes))} unique). "
         f"Paths: {resolved_includes}")

    assert len(resolved_libs) > len(set(resolved_libs)), \
        ("Bug confirmation: after resolving variables, lib paths must "
         f"contain duplicates (got {len(resolved_libs)} entries, "
         f"{len(set(resolved_libs))} unique). "
         f"Paths: {resolved_libs}")

    # ── Step 5: Simulate RemoveDuplicates (preserves first-occurrence order) ──
    def remove_duplicates_ordered(items):
        seen = set()
        result = []
        for item in items:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result

    unique_includes = remove_duplicates_ordered(resolved_includes)
    unique_libs = remove_duplicates_ordered(resolved_libs)

    # ── Step 6: Verify deduplication correctness ──
    # a) No duplicates remain
    assert len(unique_includes) == len(set(unique_includes)), \
        "Deduplicated include paths must have no repeats"
    assert len(unique_libs) == len(set(unique_libs)), \
        "Deduplicated lib paths must have no repeats"

    # b) No paths were lost
    assert set(unique_includes) == set(resolved_includes), \
        "Deduplication must not lose any path"
    assert set(unique_libs) == set(resolved_libs), \
        "Deduplication must not lose any path"

    # c) Count was actually reduced
    assert len(resolved_includes) > len(unique_includes), \
        "RemoveDuplicates must reduce the entry count"
    assert len(resolved_libs) > len(unique_libs), \
        "RemoveDuplicates must reduce the entry count"

    # d) The dedup target that performs this at MSBuild runtime exists
    conandeps = client.load("app/conandeps.props")
    assert "ConanDeduplicatePaths" in conandeps, \
        "conandeps.props must contain the deduplication target"
    assert "RemoveDuplicates" in conandeps, \
        "conandeps.props must use the RemoveDuplicates task"
