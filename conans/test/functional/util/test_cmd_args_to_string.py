import os
import platform
import textwrap

import pytest

from conan.tools.build import cmd_args_to_string
from conans.test.utils.tools import TestClient
from conans.util.files import chdir
from conans.util.runners import check_output_runner


@pytest.fixture(scope="module")
def application_folder():
    t = TestClient()
    main = textwrap.dedent("""
    #include<stdio.h>
    int main(int argc, char *argv[]){
        int i;
        for(i=1;i<argc;i++){
            printf("%s\\n",argv[i]);
        }
        return 0;
    }
    """
    )

    cmake = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.15)
    project(arg_printer C)

    add_executable(arg_printer main.c)
    """)

    t.save({"CMakeLists.txt": cmake, "main.c": main})
    t.run_command("cmake . -DCMAKE_BUILD_TYPE=Release")
    if platform.system() == "Windows":
        t.run_command("cmake --build . --config Release")
    else:
        t.run_command("cmake --build .")

    if platform.system() == "Windows":
        return os.path.join(t.current_folder, "Release")
    else:
        return t.current_folder


@pytest.mark.tool("cmake")
@pytest.mark.skipif(platform.system() == "Windows", reason="Unix console parsing")
@pytest.mark.parametrize("_input, output", [
         (['.', 'foo'], '. foo'),
         (['.', 'foo with sp'], ". 'foo with sp'"),
         (['.', 'foo "with" sp'], ". 'foo \"with\" sp'"),
         (['.', '\'foo with sp\''], '. \'\'"\'"\'foo with sp\'"\'"\'\''),
         (['"."', 'foo'], '\'"."\' foo'),
         (['".', 'foo'], '\'".\' foo'),
])
def test_unix_cases(application_folder, _input, output):
    _input = ["arg_printer"] + _input
    output = "arg_printer {}".format(output)
    assert cmd_args_to_string(_input) == output

    # Check calling the exe that the arguments are the same we tried to input
    with chdir(application_folder):
        cmd_parsed_output = check_output_runner("./{}".format(output))
        interpreted_args = cmd_parsed_output.splitlines()
        real_args = _input[1:]
        assert real_args == interpreted_args
