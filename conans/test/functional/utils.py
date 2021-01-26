import re

from conan.tools.microsoft.visual import vcvars_command


def check_vs_runtime(artifact, client, vs_version, build_type, static, architecture="amd64"):
    executable = artifact.endswith(".exe")
    vcvars = vcvars_command(version=vs_version, architecture=architecture)
    normalized_path = artifact.replace("/", "\\")

    if executable or not static:
        cmd = ('%s && dumpbin /nologo /dependents "%s"' % (vcvars, normalized_path))
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

    if not executable:
        if static:
            client.run_command('{} && DUMPBIN /NOLOGO /DIRECTIVES "{}"'.format(vcvars, artifact))
            if build_type == "Debug":
                assert "RuntimeLibrary=MDd_DynamicDebug" in client.out, "Error:{}"
                       .format(client.out)
            else:
                assert "RuntimeLibrary=MD_DynamicRelease" in client.out, "Error:{}"
                       .format(client.out)

        client.run_command('{} && DUMPBIN /NOLOGO /HEADERS "{}"'.format(vcvars, artifact))
        if architecture == "amd64":
            assert "machine (x64)" in client.out, "Error:{}".format(client.out)


def check_msc_ver(toolset, output):
    if toolset == "v140":
        assert "main _MSC_VER1900" in output, "Error:{}".format(output)
    elif toolset == "v141":
        version = re.search("main _MSC_VER19([0-9]*)", str(output)).group(1)
        version = int(version)
        assert 10 <= version < 20, "Error:{}".format(output)
    else:
        raise NotImplementedError()
