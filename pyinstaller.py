import os
import platform
import shutil
import subprocess
from distutils import dir_util

from conans import __version__
from conans.util.files import save


def _install_pyinstaller(pyinstaller_path):
    subprocess.call("pip install pyinstaller", shell=True)
    # try to install pyinstaller if not installed
    if not os.path.exists(pyinstaller_path):
        os.mkdir(pyinstaller_path)


def _run_bin(pyinstaller_path):
    # run the binary to test if working
    conan_bin = os.path.join(pyinstaller_path, 'dist', 'conan', 'conan')
    if platform.system() == 'Windows':
        conan_bin = '"' + conan_bin + '.exe' + '"'
    retcode = os.system(conan_bin)
    if retcode != 0:
        raise Exception("Binary not working")


def _windows_version_file(version):
    template = """# UTF-8
#
# For more details about fixed file info 'ffi' see:
# http://msdn.microsoft.com/en-us/library/ms646997.aspx
VSVersionInfo(
  ffi=FixedFileInfo(
    # filevers and prodvers should be always a tuple with four items: (1, 2, 3, 4)
    # Set not needed items to zero 0.
    filevers={version_tuple},
    prodvers={version_tuple},
    # Contains a bitmask that specifies the valid bits 'flags'r
    mask=0x3f,
    # Contains a bitmask that specifies the Boolean attributes of the file.
    flags=0x0,
    # The operating system for which this file was designed.
    # 0x4 - NT and there is no need to change it.
    OS=0x4,
    # The general type of file.
    # 0x1 - the file is an application.
    fileType=0x1,
    # The function of the file.
    # 0x0 - the function is not defined for this fileType
    subtype=0x0,
    # Creation date and time stamp.
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'000004b0',
        [StringStruct(u'Comments', u'This executable was created with pyinstaller'),
        StringStruct(u'CompanyName', u'JFrog'),
        StringStruct(u'FileDescription', u'Conan C, C++ Open Source Package Manager'),
        StringStruct(u'FileVersion', u'{version}'),
        StringStruct(u'LegalCopyright', u'Copyright 2020 JFrog'),
        StringStruct(u'ProductName', u'Conan'),
        StringStruct(u'ProductVersion', u'{version}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [0, 1200])])
  ]
)"""
    if "-" in version:
        version, _ = version.split("-")
    version_tuple = tuple([int(v) for v in version.split(".")] + [0])
    return template.format(version=version, version_tuple=version_tuple)


def pyinstall(source_folder):
    pyinstaller_path = os.path.join(os.getcwd(), 'pyinstaller')
    _install_pyinstaller(pyinstaller_path)
    command = "pyinstaller"  # "python pyinstaller.py"

    try:
        shutil.rmtree(os.path.join(pyinstaller_path))
    except Exception as e:
        print("Unable to remove old folder", e)

    conan_path = os.path.join(source_folder, 'conans', 'conan.py')
    conan_server_path = os.path.join(source_folder, 'conans', 'conan_server.py')
    conan_build_info_path = os.path.join(source_folder, "conans/build_info/command.py")
    hidden = ("--hidden-import=glob "  # core stdlib
              "--hidden-import=pathlib "
              "--hidden-import=distutils.dir_util "
              # The conan.tools integration
              "--hidden-import=conan.tools.microsoft "
              "--hidden-import=conan.tools.gnu --hidden-import=conan.tools.cmake "
              "--hidden-import=conan.tools.meson --hidden-import=conan.tools.apple "
              "--hidden-import=conan.tools.build --hidden-import=conan.tools.env "
              "--hidden-import=conan.tools.files --hidden-import=conan.tools.gnu "
              "--hidden-import=conan.tools.google --hidden-import=conan.tools.intel "
              "--hidden-import=conan.tools.layout --hidden-import=conan.tools.premake "
              "--hidden-import=conan.tools.qbs --hidden-import=conan.tools.scm")
    if platform.system() != "Windows":
        hidden += " --hidden-import=setuptools.msvc"
        win_ver = ""
    else:
        win_ver_file = os.path.join(pyinstaller_path, 'windows-version-file')
        content = _windows_version_file(__version__)
        save(win_ver_file, content)
        win_ver = "--version-file \"%s\"" % win_ver_file

    if not os.path.exists(pyinstaller_path):
        os.mkdir(pyinstaller_path)
    subprocess.call('%s -y -p "%s" --console "%s" %s %s'
                    % (command, source_folder, conan_path, hidden, win_ver),
                    cwd=pyinstaller_path, shell=True)

    _run_bin(pyinstaller_path)

    subprocess.call('%s -y -p "%s" --console "%s" %s'
                    % (command, source_folder, conan_server_path, win_ver),
                    cwd=pyinstaller_path, shell=True)

    subprocess.call('%s -y -p "%s" --console "%s" -n conan_build_info %s'
                    % (command, source_folder, conan_build_info_path, win_ver),
                    cwd=pyinstaller_path, shell=True)

    conan_bin = os.path.join(pyinstaller_path, 'dist', 'conan')
    conan_server_folder = os.path.join(pyinstaller_path, 'dist', 'conan_server')

    conan_build_info_folder = os.path.join(pyinstaller_path, 'dist', 'conan_build_info')
    dir_util.copy_tree(conan_server_folder, conan_bin)
    dir_util.copy_tree(conan_build_info_folder, conan_bin)
    _run_bin(pyinstaller_path)

    return os.path.abspath(os.path.join(pyinstaller_path, 'dist', 'conan'))


if __name__ == "__main__":
    src_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)))
    output_folder = pyinstall(src_folder)
    print("\n**************Conan binaries created!******************\n"
          "\nAppend this folder to your system PATH: '%s'\n"
          "Feel free to move the whole folder to another location." % output_folder)
