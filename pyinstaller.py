from __future__ import print_function
import os
import platform
import subprocess
import shutil
from distutils import dir_util


def _install_pyinstaller(pyinstaller_path):
    subprocess.call("pip install pyinstaller")
    # try to install pyinstaller if not installed
    if not os.path.exists(pyinstaller_path):
        os.mkdir(pyinstaller_path)
        

def _run_bin(pyinstaller_path):
    # run the binary to test if working
    conan_bin = os.path.join(pyinstaller_path, 'dist', 'conan', 'conan')
    if platform.system() == 'Windows':
        conan_bin += '.exe'
    retcode = os.system(conan_bin)
    if retcode != 0:
        raise Exception("Binary not working")


def pyinstall(source_folder):
    pyinstaller_path = os.path.join(os.getcwd(), 'pyinstaller')
    _install_pyinstaller(pyinstaller_path)
    tmpdir = os.getcwd()
    command = "pyinstaller" # "python pyinstaller.py"
    
    try:
        shutil.rmtree(os.path.join(pyinstaller_path))
    except Exception as e:
        print("Unable to remove old folder", e)

    conan_path = os.path.join(source_folder, 'conans', 'conan.py')
    conan_server_path = os.path.join(source_folder, 'conans', 'conan_server.py')
    conan_build_info_path = os.path.join(source_folder, "conans/build_info/command.py")
    hidden = "--hidden-import=glob --hidden-import=pylint.reporters.text"
    if platform.system() != "Windows":
        hidden += " --hidden-import=setuptools.msvc"
    
    if not os.path.exists(pyinstaller_path):
        os.mkdir(pyinstaller_path)
    subprocess.call('%s -y -p %s --console %s %s'
                    % (command, source_folder, conan_path, hidden),
                    cwd=pyinstaller_path, shell=True)
    
    _run_bin(pyinstaller_path)

    subprocess.call('%s -y -p %s --console %s'
                    % (command, source_folder, conan_server_path),
                    cwd=pyinstaller_path, shell=True)

    subprocess.call('%s -y -p %s --console %s -n conan_build_info'
                    % (command, source_folder, conan_build_info_path),
                    cwd=pyinstaller_path, shell=True)

    conan_bin = os.path.join(pyinstaller_path, 'dist', 'conan')
    conan_server_folder = os.path.join(pyinstaller_path, 'dist', 'conan_server')

    conan_build_info_folder = os.path.join(pyinstaller_path, 'dist', 'conan_build_info')
    dir_util.copy_tree(conan_server_folder, conan_bin)
    dir_util.copy_tree(conan_build_info_folder, conan_bin)
    _run_bin(pyinstaller_path)

    return os.path.abspath(os.path.join(pyinstaller_path, 'dist', 'conan'))


if __name__ == "__main__":
    source_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)))
    output_folder = pyinstall(source_folder)
    print("\n**************Conan binaries created!******************\n \
    \nAppend this folder to your system PATH: '%s'\nFeel free to move the whole folder to another location." % output_folder)

