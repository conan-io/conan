from conan.tools.microsoft.visual import vcvars_command


def check_vs_runtime(artifact, client, vs_version, build_type, architecture="amd64",
                     static_runtime=False):
    vcvars = vcvars_command(version=vs_version, architecture=architecture)
    normalized_path = artifact.replace("/", "\\")
    static = artifact.endswith(".a") or artifact.endswith(".lib")
    if not static:
        cmd = ('%s && dumpbin /nologo /dependents "%s"' % (vcvars, normalized_path))
        client.run_command(cmd)
        if static_runtime:
            assert "KERNEL32.dll" in client.out
            assert "MSVC" not in client.out
            assert "VCRUNTIME" not in client.out
        else:
            if vs_version in ["15", "16", "17"]:  # UCRT
                debug = "D" if build_type == "Debug" else ""
                assert "MSVCP140{}.dll".format(debug) in client.out
                assert "VCRUNTIME140{}.dll".format(debug) in client.out
            else:
                raise NotImplementedError()
    else:  # A static library cannot be checked the same
        client.run_command('{} && DUMPBIN /NOLOGO /DIRECTIVES "{}"'.format(vcvars, artifact))
        if build_type == "Debug":
            assert "RuntimeLibrary=MDd_DynamicDebug" in client.out
        else:
            assert "RuntimeLibrary=MD_DynamicRelease" in client.out


def check_exe_run(output, names, compiler, version, build_type, arch, cppstd, definitions=None,
                  cxx11_abi=None):
    output = str(output)
    names = names if isinstance(names, list) else [names]

    for name in names:
        assert "{}: {}".format(name, build_type) in output
        if compiler == "msvc":
            if arch == "x86":
                assert "{} _M_IX86 defined".format(name) in output
            elif arch == "x86_64":
                assert "{} _M_X64 defined".format(name) in output
            else:
                assert arch is None, "checked don't know how to validate this architecture"

            if version:
                assert "{} _MSC_VER{}".format(name, version) in output
            if cppstd:
                assert "{} _MSVC_LANG20{}".format(name, cppstd) in output

        elif compiler in ["gcc", "clang", "apple-clang"]:
            if compiler == "gcc":
                assert "{} __GNUC__".format(name) in output
                if version:  # FIXME: At the moment, the GCC version is not controlled, will change
                    major, minor = version.split(".")[0:2]
                    assert "{} __GNUC__{}".format(name, major) in output
                    assert "{} __GNUC_MINOR__{}".format(name, minor) in output
            elif compiler == "clang":
                assert "{} __clang__".format(name) in output
                if version:
                    major, minor = version.split(".")[0:2]
                    assert "{} __clang_major__{}".format(name, major) in output
                    assert "{} __clang_minor__{}".format(name, minor) in output
            elif compiler == "apple-clang":
                assert "{} __apple_build_version__".format(name) in output
                if version:
                    major, minor = version.split(".")[0:2]
                    assert "{} __apple_build_version__{}{}".format(name, major, minor) in output
            if arch == "x86":
                assert "{} __i386__ defined".format(name) in output
            elif arch == "x86_64":
                assert "{} __x86_64__ defined".format(name) in output
            elif arch == "armv8":
                assert "{} __aarch64__ defined".format(name) in output
            else:
                assert arch is None, "checked don't know how to validate this architecture"

            if cppstd:
                cppstd_value = {"98": "199711",
                                "11": "201103",
                                "14": "201402",
                                "17": "201703"}[cppstd]
                assert "{} __cplusplus{}".format(name, cppstd_value) in output

            if cxx11_abi is not None:
                assert "{} _GLIBCXX_USE_CXX11_ABI {}".format(name, cxx11_abi) in output

        if definitions:
            for k, v in definitions.items():
                assert "{}: {}".format(k, v) in output
