import re

from conan.tools.microsoft.visual import vcvars_command


def check_vs_runtime(exe, client, vs_version, build_type, static, architecture="amd64"):
    vcvars = vcvars_command(version=vs_version, architecture=architecture)
    exe = exe.replace("/", "\\")
    cmd = ('%s && dumpbin /nologo /dependents "%s"' % (vcvars, exe))
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


def check_msc_ver(toolset, output):
    if toolset == "v140":
        assert "main _MSC_VER1900" in output, "Error:{}".format(output)
    elif toolset == "v141":
        version = re.search("main _MSC_VER19([0-9]*)", str(output)).group(1)
        version = int(version)
        assert 10 <= version < 20, "Error:{}".format(output)
    else:
        raise NotImplementedError()


def check_msvc_library(library, client, vs_version, build_type, static, architecture="amd64"):
    vcvars = vcvars_command(version=vs_version, architecture=architecture)
    library = library.replace("/", "\\")
    if static:
        client.run_command('{} && DUMPBIN /NOLOGO /DIRECTIVES "{}"'.format(vcvars, library))
        if build_type == "Debug":
            assert "RuntimeLibrary=MDd_DynamicDebug" in client.out, "Error:{}".format(client.out)
        else:
            assert "RuntimeLibrary=MD_DynamicRelease" in client.out, "Error:{}".format(client.out)
    else:
        client.run_command('{} && DUMPBIN /NOLOGO /DEPENDENTS "{}"'.format(vcvars, library))
        if vs_version == "15":
            if build_type == "Debug":
                assert "MSVCP140D.dll" in client.out, "Error:{}".format(client.out)
                assert "VCRUNTIME140D.dll" in client.out, "Error:{}".format(client.out)
            else:
                assert "MSVCP140.dll" in client.out, "Error:{}".format(client.out)
                assert "VCRUNTIME140.dll" in client.out, "Error:{}".format(client.out)
        else:
            raise NotImplementedError()

    client.run_command('{} && DUMPBIN /NOLOGO /HEADERS "{}"'.format(vcvars, library))
    if architecture == "amd64":
        assert "machine (x64)" in client.out, "Error:{}".format(client.out)
