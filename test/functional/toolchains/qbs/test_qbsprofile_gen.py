import os
import platform
import textwrap
import pytest

from conan.test.utils.tools import TestClient
from conans.util.files import load


def exe_suffix():
    return '.exe' if platform.system() == 'Windows' else ''


COMPILER_MAP = {
    'gcc': ('gcc', 'g++'),
    'clang': ('clang', 'clang++')
}


@pytest.mark.parametrize('compiler, version, system', [
    ('gcc', '13', 'Linux'),
    ('clang', '15', 'Linux'),
])
def test_toolchain_from_path(compiler, version, system):
    client = TestClient()
    path = client.current_folder

    profile = textwrap.dedent(f'''
    [settings]
    compiler={compiler}
    compiler.version={version}
    compiler.libcxx=libstdc++
    os={system}
    [buildenv]
    PATH={path}
    ''')

    cc, cxx = COMPILER_MAP[compiler]

    conanfile = textwrap.dedent('''
    from conan import ConanFile
    class Recipe(ConanFile):
        settings = "compiler", "os"
        name = "mylib"
        version = "0.1"
    ''')

    client.save({cc + exe_suffix(): ''})
    client.save({cxx + exe_suffix(): ''})
    client.save({'profile': profile})
    client.save({'conanfile.py': conanfile})
    client.run('install . -pr:a=profile -g QbsProfile')

    settings_path = os.path.join(client.current_folder, 'qbs_settings.txt')
    assert os.path.exists(settings_path)

    settings_content = load(settings_path)
    assert f'qbs.toolchainType:{compiler}' in settings_content
    toolchain_path = client.current_folder.replace('\\', '/')
    assert f'cpp.toolchainInstallPath:{toolchain_path}' in settings_content
    assert f'cpp.compilerName:{cxx}' in settings_content
    assert f'cpp.cCompilerName:{cc}' in settings_content
    assert f'cpp.cxxCompilerName:{cxx}' in settings_content


@pytest.mark.parametrize('compiler, version, system, cc, cxx', [
    ('gcc', '13', 'Linux', 'gcc', 'g++'),
    ('clang', '15', 'Linux', 'clang', 'clang++'),
])
def test_toolchain_from_conf(compiler, version, system, cc, cxx):
    profile = textwrap.dedent(f'''
    [settings]
    compiler={compiler}
    compiler.version={version}
    compiler.libcxx=libstdc++
    os={system}
    [conf]
    tools.build:compiler_executables ={{"c": "/opt/bin/{cc}", "cpp": "/opt/bin/{cxx}"}}
    ''')

    conanfile = textwrap.dedent('''
    from conan import ConanFile
    class Recipe(ConanFile):
        settings = "compiler", "os"
        name = "mylib"
        version = "0.1"
    ''')

    client = TestClient()
    client.save({'profile': profile})
    client.save({'conanfile.py': conanfile})
    client.run('install . -pr:a=profile -g QbsProfile')

    settings_path = os.path.join(client.current_folder, 'qbs_settings.txt')
    assert os.path.exists(settings_path)

    settings_content = load(settings_path)
    assert f'qbs.toolchainType:{compiler}' in settings_content
    assert 'cpp.toolchainInstallPath:/opt/bin' in settings_content
    assert f'cpp.compilerName:{cxx}' in settings_content
    assert f'cpp.cCompilerName:{cc}' in settings_content
    assert f'cpp.cxxCompilerName:{cxx}' in settings_content


@pytest.mark.parametrize('compiler, version, system, cc, cxx', [
    ('gcc', '13', 'Linux', 'gcc', 'g++'),
    ('clang', '15', 'Linux', 'clang', 'clang++'),
])
def test_toolchain_from_env(compiler, version, system, cc, cxx):
    profile = textwrap.dedent(f'''
    [settings]
    compiler={compiler}
    compiler.version={version}
    compiler.libcxx=libstdc++
    os={system}
    [buildenv]
    CC=/opt/bin/{cc}
    CXX=/opt/bin/{cxx}
    ''')

    conanfile = textwrap.dedent('''
    from conan import ConanFile
    class Recipe(ConanFile):
        settings = "compiler", "os"
        name = "mylib"
        version = "0.1"
    ''')

    client = TestClient()
    client.save({'profile': profile})
    client.save({'conanfile.py': conanfile})
    client.run('install . -pr:a=profile -g QbsProfile')

    settings_path = os.path.join(client.current_folder, 'qbs_settings.txt')
    assert os.path.exists(settings_path)

    settings_content = load(settings_path)
    assert f'qbs.toolchainType:{compiler}' in settings_content
    assert 'cpp.toolchainInstallPath:/opt/bin' in settings_content
    assert f'cpp.compilerName:{cxx}' in settings_content
    assert f'cpp.cCompilerName:{cc}' in settings_content
    assert f'cpp.cxxCompilerName:{cxx}' in settings_content


@pytest.mark.parametrize('system, compiler, version, build_type, arch, cppstd', [
    ('Linux', 'gcc', '13', 'Release', 'x86_64', '17'),
    ('Linux', 'gcc', '13', 'Debug', 'x86_64', '14'),
    ('Linux', 'gcc', '13', 'Debug', 'x86', '20'),
    ('Linux', 'gcc', '13', 'Release', 'avr', '11'),
])
def test_options_from_settings(system, compiler, version, build_type, arch, cppstd):
    client = TestClient()

    cc, cxx = COMPILER_MAP[compiler]

    profile = textwrap.dedent(f'''
    [settings]
    arch={arch}
    build_type={build_type}
    compiler={compiler}
    compiler.version={version}
    compiler.libcxx=libstdc++
    compiler.cppstd={cppstd}
    os={system}
    [conf]
    tools.build:compiler_executables ={{"c": "/opt/bin/{cc}", "cpp": "/opt/bin/{cxx}"}}
    ''')

    conanfile = textwrap.dedent('''
    from conan import ConanFile
    class Recipe(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        name = "mylib"
        version = "0.1"
    ''')

    client.save({'profile': profile})
    client.save({'conanfile.py': conanfile})
    client.run('install . -pr:a=profile -g QbsProfile')

    settings_path = os.path.join(client.current_folder, 'qbs_settings.txt')
    assert os.path.exists(settings_path)
    settings_content = load(settings_path)

    assert f'qbs.architecture:{arch}' in settings_content
    build_variant = build_type.lower()
    assert f'qbs.buildVariant:{build_variant}' in settings_content
    target_platform = system.lower()
    assert f'qbs.targetPlatform:{target_platform}' in settings_content
    assert 'cpp.cxxLanguageVersion:c++' + cppstd in settings_content
    # TODO: cpp.runtimeLibrary (MSVC only)


def test_options_from_conf():
    client = TestClient()

    profile = textwrap.dedent('''
    [settings]
    arch=x86_64
    build_type=Release
    compiler=gcc
    compiler.version=13
    compiler.libcxx=libstdc++
    compiler.cppstd=17
    os=Linux
    [conf]
    tools.build:compiler_executables ={"c": "/opt/bin/gcc", "cpp": "/opt/bin/g++"}
    tools.build:cflags=['-Dfoo', '-Dbar']
    tools.build:cxxflags=['-Dfoo', '-Dbaz']
    tools.build:sharedlinkflags=['-s']
    tools.build:exelinkflags=['-Wl,-s']
    ''')

    conanfile = textwrap.dedent('''
    from conan import ConanFile
    class Recipe(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        name = "mylib"
        version = "0.1"
    ''')

    client.save({'profile': profile})
    client.save({'conanfile.py': conanfile})
    client.run('install . -pr:a=profile -g QbsProfile')

    settings_path = os.path.join(client.current_folder, 'qbs_settings.txt')
    assert os.path.exists(settings_path)
    settings_content = load(settings_path)

    assert "cpp.cFlags:['-Dfoo', '-Dbar']" in settings_content
    assert "cpp.cxxFlags:['-Dfoo', '-Dbaz']" in settings_content
    assert "cpp.linkerFlags:['-s']" in settings_content
    assert "cpp.driverLinkerFlags:['-s']" in settings_content


def test_options_extra():
    client = TestClient()

    profile = textwrap.dedent('''
    [settings]
    arch=x86_64
    build_type=Release
    compiler=gcc
    compiler.version=13
    compiler.libcxx=libstdc++
    compiler.cppstd=17
    os=Linux
    [conf]
    tools.build:compiler_executables ={"c": "/opt/bin/gcc", "cpp": "/opt/bin/g++"}
    ''')

    conanfile = textwrap.dedent('''
    from conan import ConanFile
    from conan.tools.qbs import QbsProfile
    class Recipe(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        name = "mylib"
        version = "0.1"

        def generate(self):
            profile = QbsProfile(self)
            profile.extra_cflags=['-Dfoo', '-Dbar']
            profile.extra_cxxflags=['-Dfoo', '-Dbaz']
            profile.extra_defines=['FOO', 'QUX']
            profile.extra_sharedlinkflags=['-s']
            profile.extra_exelinkflags=['-Wl,-s']
            profile.generate()
    ''')

    client.save({'profile': profile})
    client.save({'conanfile.py': conanfile})
    client.run('install . -pr:a=profile')

    settings_path = os.path.join(client.current_folder, 'qbs_settings.txt')
    assert os.path.exists(settings_path)
    settings_content = load(settings_path)

    assert "cpp.cFlags:['-Dfoo', '-Dbar']" in settings_content
    assert "cpp.cxxFlags:['-Dfoo', '-Dbaz']" in settings_content
    assert "cpp.defines:['FOO', 'QUX']" in settings_content
    assert "cpp.linkerFlags:['-s']" in settings_content
    assert "cpp.driverLinkerFlags:['-s']" in settings_content


def test_sysroot():
    client = TestClient()

    profile = textwrap.dedent('''
    [settings]
    arch=x86_64
    build_type=Release
    compiler=gcc
    compiler.version=13
    compiler.libcxx=libstdc++
    compiler.cppstd=17
    os=Linux
    [conf]
    tools.build:compiler_executables ={"c": "/opt/bin/gcc", "cpp": "/opt/bin/g++"}
    tools.build:sysroot=\\opt\\usr\\local
    ''')

    conanfile = textwrap.dedent('''
    from conan import ConanFile
    class Recipe(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        name = "mylib"
        version = "0.1"
    ''')

    client.save({'profile': profile})
    client.save({'conanfile.py': conanfile})
    client.run('install . -pr:a=profile -g QbsProfile')

    settings_path = os.path.join(client.current_folder, 'qbs_settings.txt')
    assert os.path.exists(settings_path)
    settings_content = load(settings_path)

    assert "qbs.sysroot:/opt/usr/local" in settings_content
