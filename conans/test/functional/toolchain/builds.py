import os

from conans import CMakeToolchain
from conans.model.ref import ConanFileReference
from conans.util.files import rmdir, load


def compile_local_workflow(testcase, client, profile, bare_cmake=False):
    # Conan local workflow
    build_directory = os.path.join(client.current_folder, "build")
    rmdir(build_directory)
    with client.chdir(build_directory):
        client.run("install .. --profile={}".format(profile))
        if bare_cmake:
            client.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE={}".format(CMakeToolchain.filename))
        else:
            client.run("build ..")
        testcase.assertIn("Using Conan toolchain", client.out)

    cmake_cache = load(os.path.join(build_directory, "CMakeCache.txt"))
    return client.out, cmake_cache, build_directory, None


def compile_cmake_workflow(testcase, client, profile):
    return compile_local_workflow(testcase, client, profile, bare_cmake=True)


def _compile_cache_workflow(testcase, client, profile, use_toolchain):
    # Compile the app in the cache
    pref = client.create(ref=ConanFileReference.loads("app/version@user/channel"), conanfile=None,
                         args=" --profile={}".format(profile))
    if use_toolchain:
        testcase.assertIn("Using Conan toolchain", client.out)

    package_layout = client.cache.package_layout(pref.ref)
    build_directory = package_layout.build(pref)
    cmake_cache = load(os.path.join(build_directory, "CMakeCache.txt"))
    return client.out, cmake_cache, build_directory, package_layout.package(pref)


def compile_cache_workflow_with_toolchain(testcase, client, profile):
    return _compile_cache_workflow(testcase, client, profile, use_toolchain=True)


def compile_cache_workflow_without_toolchain(testcase, client, profile):
    return _compile_cache_workflow(testcase, client, profile, use_toolchain=False)

