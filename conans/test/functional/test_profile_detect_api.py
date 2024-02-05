import textwrap

import pytest

from conan.internal.api import detect_api
from conans.test.utils.tools import TestClient


class TestProfileDetectAPI:
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
            compiler.update={{detect_api.detect_msvc_update(version)}}

            [conf]
            tools.microsoft.msbuild:vs_version={{detect_api.default_msvc_ide_version(version)}}
            """)

        client.save({"profile1": tpl1})
        client.run("profile show -pr=profile1")
        update = detect_api.detect_msvc_update("193")
        expected = textwrap.dedent(f"""\
            Host profile:
            [settings]
            compiler=msvc
            compiler.cppstd=14
            compiler.runtime=dynamic
            compiler.runtime_type=Release
            compiler.update={update}
            compiler.version=193
            [conf]
            tools.microsoft.msbuild:vs_version=17
            """)
        assert expected in client.out
