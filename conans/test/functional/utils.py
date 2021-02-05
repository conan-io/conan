from conan.tools.microsoft.visual import vcvars_command


def check_vs_runtime(exe, client, vs_version, build_type, static, architecture="amd64"):
    vcvars = vcvars_command(version=vs_version, architecture=architecture)
    exe = exe.replace("/", "\\")
    cmd = ('%s && dumpbin /dependents "%s"' % (vcvars, exe))
    client.run_command(cmd)

    if static:
        assert "KERNEL32.dll" in client.out, "Error:{}".format(client.out)
        assert "MSVC" not in client.out, "Error:{}".format(client.out)
        assert "VCRUNTIME" not in client.out, "Error:{}".format(client.out)
    else:
        if vs_version == "15":
            if build_type == "Debug":
                assert "MSVCP140D.dll" in client.out, "Error:{}".format(client.out)
                assert "VCRUNTIME140D.dll" in client.out, "Error:{}".format(client.out)
            else:
                assert "MSVCP140.dll" in client.out, "Error:{}".format(client.out)
                assert "VCRUNTIME140.dll" in client.out, "Error:{}".format(client.out)
        else:
            raise NotImplementedError()


def check_exe_run(output, names, compiler, version, build_type, arch, cppstd, definitions=None):
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

            assert "{} _MSC_VER{}".format(name, version.replace(".", "")) in output
            assert "{} _MSVC_LANG20{}".format(name, cppstd) in output

        elif compiler == "gcc":
            assert "{} __GNUC__".format(name) in output

            if arch == "x86":
                assert "{} __i386__ defined".format(name) in output
            elif arch == "x86_64":
                assert "{} __x86_64__ defined".format(name) in output
            else:
                assert arch is None, "checked don't know how to validate this architecture"

            if version:  # FIXME: At the moment, the GCC version is not controlled, will change
                major, minor = version.split(".")[0:2]
                assert "{} __GNUC__{}".format(name, major) in output
                assert "{} __GNUC_MINOR__{}".format(name, minor) in output
            if cppstd:
                cppstd_value = {"98": "199711",
                                "11": "201103",
                                "14": "201402",
                                "17": "201703"}[cppstd]
                assert "{} __cplusplus{}".format(name, cppstd_value) in output

        if definitions:
            for k, v in definitions.items():
                assert "{}: {}".format(k, v) in output
