import os
import textwrap

from conans.test.utils.tools import TestClient


def test_msbuildtoolchain_props_with_extra_flags():
    """
    Simple test checking that conantoolchain_release_x64.props is adding all the expected
    flags and preprocessor definitions
    """
    profile = textwrap.dedent("""\
    include(default)
    [settings]
    arch=x86_64
    [conf]
    tools.build:cxxflags=["--flag1", "--flag2"]
    tools.build:cflags+=["--flag3", "--flag4"]
    tools.build:sharedlinkflags+=["--flag5"]
    tools.build:exelinkflags+=["--flag6"]
    tools.build:defines+=["DEF1", "DEF2"]
    """)
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template=msbuild_lib")
    client.save({
        "myprofile": profile
    })
    # Local flow works
    client.run("install . -pr myprofile -if=install")
    toolchain = client.load(os.path.join("conan", "conantoolchain_release_x64.props"))
    expected_cl_compile = """
    <ClCompile>
      <PreprocessorDefinitions>DEF1;DEF2;%(PreprocessorDefinitions)</PreprocessorDefinitions>
      <AdditionalOptions>--flag1 --flag2 --flag3 --flag4 %(AdditionalOptions)</AdditionalOptions>"""
    expected_link = """
    <Link>
      <AdditionalOptions>--flag5 --flag6 %(AdditionalOptions)</AdditionalOptions>
    </Link>"""
    expected_resource_compile = """
    <ResourceCompile>
      <PreprocessorDefinitions>DEF1;DEF2;%(PreprocessorDefinitions)</PreprocessorDefinitions>
      <AdditionalOptions>--flag1 --flag2 --flag3 --flag4 %(AdditionalOptions)</AdditionalOptions>
    </ResourceCompile>"""
    assert expected_cl_compile in toolchain
    assert expected_link in toolchain
    assert expected_resource_compile in toolchain
