import platform
import textwrap

import pytest

from conan.internal.api.detect import detect_api
from conan.test.utils.tools import TestClient


class TestProfileDetectAPI:
    @pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
    @pytest.mark.tool("visual_studio", "17")
    def test_profile_detect_compiler(self):

        client = TestClient()
        tpl1 = textwrap.dedent("""
            {% set compiler, version, compiler_exe = detect_api.detect_default_compiler() %}
            {% set runtime, _ = detect_api.default_msvc_runtime(compiler) %}
            [settings]
            compiler={{compiler}}
            compiler.version={{detect_api.default_compiler_version(compiler, version)}}
            compiler.runtime={{runtime}}
            compiler.cppstd={{detect_api.default_cppstd(compiler, version)}}
            # detect_msvc_update returns the real update, like 12 for VS 17.12 so 
            # we have to convert to the setting that's 0-10
            compiler.update={{ (detect_api.detect_msvc_update(version) | int) % 10 }}

            [conf]
            tools.microsoft.msbuild:vs_version={{detect_api.default_msvc_ide_version(version)}}
            """)

        client.save({"profile1": tpl1})
        client.run("profile show -pr=profile1 --context=host")
        #FIXME: check update setting
        update = str(int(detect_api.detect_msvc_update("194")) % 10)
        expected = textwrap.dedent(f"""\
            [settings]
            compiler=msvc
            compiler.cppstd=14
            compiler.runtime=dynamic
            compiler.runtime_type=Release
            compiler.update={update}
            compiler.version=194
            [conf]
            tools.microsoft.msbuild:vs_version=17
            """)
        assert expected in client.out

    @pytest.mark.skipif(platform.system() != "Linux", reason="Only linux")
    def test_profile_detect_libc(self):
        client = TestClient()
        tpl1 = textwrap.dedent("""
            {% set compiler, version, _ = detect_api.detect_gcc_compiler() %}
            {% set libc, libc_version = detect_api.detect_libc() %}
            [settings]
            os=Linux
            compiler={{compiler}}
            compiler.version={{version}}
            [conf]
            user.confvar:libc={{libc}}
            user.confvar:libc_version={{libc_version}}
            """)

        client.save({"profile1": tpl1})
        client.run("profile show -pr=profile1 --context=host")
        libc_name, libc_version = detect_api.detect_libc()
        assert libc_name is not None
        assert libc_version is not None
        _, version, _ = detect_api.detect_gcc_compiler()
        expected = textwrap.dedent(f"""\
            [settings]
            compiler=gcc
            compiler.version={version}
            os=Linux
            [conf]
            user.confvar:libc={libc_name}
            user.confvar:libc_version={libc_version}
            """)
        assert expected in client.out

    @pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
    def test_profile_detect_darwin_sdk(self):
        client = TestClient()
        tpl1 = textwrap.dedent("""\
            [settings]
            os = "Macos"
            os.sdk_version = {{ detect_api.detect_sdk_version(sdk="macosx")  }}
            """)

        client.save({"profile1": tpl1})
        client.run("profile show -pr=profile1")
        sdk_version = detect_api.detect_sdk_version(sdk="macosx")
        assert f"os.sdk_version={sdk_version}" in client.out

@pytest.mark.parametrize("context", [None, "host", "build"])
@pytest.mark.parametrize("f", ["json", "text"])
def test_profile_show_aggregate_usecase(context, f):
    tc = TestClient(light=True)

    context_arg = f"--context {context}" if context else ""
    tc.run(f'profile show {context_arg} -s:h="os=Windows" -s:b="os=Linux" --format={f}')

    if context == "host":
        if f == "text":
            assert "Host profile:" not in tc.stdout
            assert "Host profile:" in tc.stderr
        assert "Linux" not in tc.out
    if context == "build":
        if f == "text":
            assert "Build profile:" not in tc.stdout
            assert "Build profile:" in tc.stderr
        assert "Windows" not in tc.out

    if context in (None, "host"):
        assert "Windows" in tc.out
    if context in (None, "build"):
        assert "Linux" in tc.out
