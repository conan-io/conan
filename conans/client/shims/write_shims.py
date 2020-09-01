import platform
import os
import shutil

from conans.client.generators import VirtualRunEnvGenerator


def write_shims(conanfile, path, output):
    print(conanfile)
    if not conanfile.cpp_info or not conanfile.cpp_info.exes:
        return

    # Create wrappers for the executables
    wrappers_folder = os.path.join(path, '.wrappers')
    output.highlight("Create executable wrappers at '{}'".format(wrappers_folder))
    shutil.rmtree(wrappers_folder, ignore_errors=True)
    os.mkdir(wrappers_folder)

    # - I will need the environment
    env = VirtualRunEnvGenerator(conanfile)
    env.output_path = wrappers_folder

    # TODO: Need to add from teh consumer point of view
    for it in conanfile.cpp_info.lib_paths:
        env.env["DYLD_LIBRARY_PATH"].insert(0, it)
        # FIXME: Watch out! It is this same list object! env.env["LD_LIBRARY_PATH"].insert(0, it)
    # TODO: Other environment variables?

    for filename, content in env.content.items():
        with open(os.path.join(wrappers_folder, filename), 'w') as f:
            f.write(content)

    activate = deactivate = None
    if platform.system() == "Windows":
        activate = 'call "{}"\n'.format(os.path.join(wrappers_folder, 'activate_run.bat'))
        deactivate = 'call "{}"\n'.format(os.path.join(wrappers_folder, 'deactivate_run.bat'))
    else:
        activate = 'source "{}"'.format(os.path.join(wrappers_folder, 'activate_run.sh'))
        deactivate = 'source "{}"'.format(os.path.join(wrappers_folder, 'deactivate_run.sh'))

    # - and the wrappers
    for executable in conanfile.cpp_info.exes:
        path_to_exec = os.path.join(path, 'bin', executable)
        path_to_exec = path_to_exec + ".cmd" if platform.system() == "Windows" else path_to_exec  # TODO: Inspect the folder to get the actual path
        exec_wrapper_ext = ".cmd" if platform.system() == "Windows" else ""
        exec_wrapper = os.path.join(wrappers_folder, executable + exec_wrapper_ext)
        with open(exec_wrapper, 'w') as f:
            if platform.system() != "Windows":
                f.write('#!/bin/bash\n')
            f.write('echo Calling {} wrapper\n'.format(executable))
            f.write('{}\n'.format(activate))
            f.write('pushd "{}"\n'.format(os.path.dirname(path_to_exec)))
            if platform.system() == "Windows":
                f.write('call "{}" %*\n'.format(path_to_exec))
            else:
                f.write('"{}" "$@"\n'.format(path_to_exec))
            f.write('popd\n')
            f.write('{}\n'.format(deactivate))

        st = os.stat(exec_wrapper)
        os.chmod(exec_wrapper, st.st_mode | os.stat.S_IEXEC)

    # - Add this extra PATH to the environment (wrapper first!)
    conanfile.env_info.PATH.insert(0, wrappers_folder)
