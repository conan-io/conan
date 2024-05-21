from conan.tools.microsoft.visual import vcvars_command


def check_vs_runtime(artifact, client, vs_version, build_type, architecture="amd64",
                     static_runtime=False, subsystem=None):
    vcvars = vcvars_command(version=vs_version, architecture=architecture)
    normalized_path = artifact.replace("/", "\\")
    static = artifact.endswith(".a") or artifact.endswith(".lib")
    if not static:
        cmd = ('%s && dumpbin /nologo /dependents "%s"' % (vcvars, normalized_path))
        client.run_command(cmd)
        if subsystem:
            assert "KERNEL32.dll" in client.out
            if subsystem in ("mingw32", "mingw64"):
                assert "msvcrt.dll" in client.out
                if static_runtime:
                    assert "libstdc++-6.dll" not in client.out
                else:
                    assert "libstdc++-6.dll" in client.out
                if subsystem == "mingw32":
                    if static_runtime:
                        assert "libgcc_s_dw2-1.dll" not in client.out
                    else:
                        assert "libgcc_s_dw2-1.dll" in client.out
            elif subsystem == "msys2":
                assert "msys-2.0.dll" in client.out
                if static_runtime:
                    assert "msys-stdc++-6.dll" not in client.out
                else:
                    assert "msys-stdc++-6.dll" in client.out
            elif subsystem == "cygwin":
                assert "cygwin1.dll" in client.out
                if static_runtime:
                    assert "cygstdc++-6.dll" not in client.out
                else:
                    assert "cygstdc++-6.dll" in client.out
            elif subsystem == "ucrt64":
                assert "api-ms-win-crt-" in client.out
                if static_runtime:
                    assert "libstdc++-6.dll" not in client.out
                else:
                    assert "libstdc++-6.dll" in client.out
            elif subsystem == "clang64":
                assert "api-ms-win-crt-" in client.out
                if static_runtime:
                    assert "libunwind.dll" not in client.out
                    assert "libc++.dll" not in client.out
                else:
                    # Latest clangs from subsystems no longer depend on libunwind
                    assert "libunwind.dll" not in client.out
                    assert "libc++.dll" in client.out
            else:
                raise Exception("unknown {}".format(subsystem))
        elif static_runtime:
            assert "KERNEL32.dll" in client.out
            assert "MSVC" not in client.out
            assert "VCRUNTIME" not in client.out
        else:
            assert "KERNEL32.dll" in client.out
            if build_type == "Debug":
                assert "ucrtbased" in client.out
            else:
                assert "api-ms-win-crt-" in client.out
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
                  cxx11_abi=None, subsystem=None, extra_msg=""):
    output = str(output)
    names = names if isinstance(names, list) else [names]

    for name in names:
        if extra_msg:  # For ``conan new`` templates
            assert "{} {} {}".format(name, extra_msg, build_type) in output
        else:
            assert "{}: {}".format(name, build_type) in output
        if compiler == "msvc":
            if arch == "x86":
                assert "{} _M_IX86 defined".format(name) in output
            elif arch == "x86_64":
                assert "{} _M_X64 defined".format(name) in output
            elif arch == "armv8":
                assert "{} _M_ARM64 defined".format(name) in output
            else:
                assert arch is None, "checked don't know how to validate this architecture"

            if version:
                assert "{} _MSC_VER{}".format(name, version) in output
            if cppstd:
                assert "{} _MSVC_LANG20{}".format(name, cppstd) in output

        elif compiler in ["gcc", "clang", "apple-clang"]:
            if compiler == "gcc":
                assert "{} __GNUC__".format(name) in output
                assert "clang" not in output
                if version:  # FIXME: At the moment, the GCC version is not controlled, will change
                    major, minor = version.split(".")[0:2]
                    assert "{} __GNUC__{}".format(name, major) in output
                    assert "{} __GNUC_MINOR__{}".format(name, minor) in output
            elif compiler == "clang":
                assert "{} __clang_".format(name) in output
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

        if subsystem:
            if subsystem == "msys2":
                assert "__MSYS__" in output
                assert "__CYGWIN__" in output
                assert "MINGW" not in output
            elif subsystem in ("mingw32", "mingw64"):
                assert "__MINGW32__" in output
                assert "__CYGWIN__" not in output
                assert "__MSYS__" not in output
                if subsystem == "mingw64":
                    assert "__MINGW64__" in output
                else:
                    assert "MING64" not in output
            elif subsystem == "cygwin":
                assert "__CYGWIN__" in output
                assert "__MINGW32__" not in output
                assert "__MINGW64__" not in output
                assert "__MSYS__" not in output
            else:
                raise Exception("unknown subsystem {}".format(subsystem))
        else:
            assert "CYGWIN" not in output
            assert "MINGW" not in output
            assert "MSYS" not in output
