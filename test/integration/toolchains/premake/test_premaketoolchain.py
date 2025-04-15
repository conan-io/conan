import textwrap

from conan.test.utils.tools import TestClient
from conan.tools.premake.toolchain import PremakeToolchain


def test_extra_flags_via_conf():
    profile = textwrap.dedent(
        """
        [settings]
        os=Linux
        arch=x86_64
        compiler=gcc
        compiler.version=9
        compiler.cppstd=17
        compiler.cstd=11
        compiler.libcxx=libstdc++
        build_type=Release

        [buildenv]
        CFLAGS=-flag00 -other=val0
        CXXFLAGS=-flag01 -other=val1
        LDFLAGS=-flag02 -other=val2

        [conf]
        tools.build:cxxflags=["-flag1", "-flag2"]
        tools.build:cflags=["-flag3", "-flag4"]
        tools.build:sharedlinkflags+=["-flag5"]
        tools.build:exelinkflags+=["-flag6"]
        tools.build:defines=["define1=0"]
   """
    )
    t = TestClient()
    t.save({"conanfile.txt": "[generators]\nPremakeToolchain", "profile": profile})

    t.run("install . -pr:a=profile")
    content = t.load(PremakeToolchain.filename)
    print(content)
    assert 'cppdialect "c++17"' in content
    # assert 'cdialect "99"' in content # TODO

    assert (
        """
        filter {"files:**.c"}
            buildoptions { "-flag00", "-other=val0", "-flag3", "-flag4" }
        filter {}
        """
        in content
    )

    assert (
        """
        filter {"files:**.cpp", "**.cxx", "**.cc"}
            buildoptions { "-flag01", "-other=val1", "-flag1", "-flag2" }
        filter {}
        """
        in content
    )

    assert 'linkoptions { "-flag02", "-other=val2", "-flag5", "-flag6" }' in content

    # assert "cpp_args = ['-flag0', '-other=val', '-m64', '-flag1', '-flag2', '-Ddefine1=0', '-D_GLIBCXX_USE_CXX11_ABI=0']" in content
    # assert "c_args = ['-flag0', '-other=val', '-m64', '-flag3', '-flag4', '-Ddefine1=0']" in content
    # assert "c_link_args = ['-flag0', '-other=val', '-m64', '-flag5', '-flag6']" in content
    # assert "cpp_link_args = ['-flag0', '-other=val', '-m64', '-flag5', '-flag6']" in content
