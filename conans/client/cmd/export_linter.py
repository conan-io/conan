import json
import os
import sys

import platform

from conans.client.output import Color
from conans.errors import ConanException
from subprocess import PIPE, Popen
from conans import __path__ as root_path


def conan_linter(conanfile_path, out):
    if getattr(sys, 'frozen', False):
        out.info("No linter available. Use a pip installed conan for recipe linting")
        return
    apply_lint = os.environ.get("CONAN_RECIPE_LINTER", True)
    if not apply_lint or apply_lint == "False":
        return

    dir_path = os.path.dirname(root_path[0]).replace("\\", "/")
    dirname = os.path.dirname(conanfile_path).replace("\\", "/")
    hook = '--init-hook="import sys;sys.path.extend([\'%s\', \'%s\'])"' % (dirname, dir_path)

    try:
        py3_msgs = None
        msgs, py3_msgs = _normal_linter(conanfile_path, hook)
    except Exception as e:
        out.warn("Failed pylint: %s" % e)
    else:
        if py3_msgs:
            out.writeln("Python 3 incompatibilities\n    ERROR: %s"
                        % "\n    ERROR: ".join(py3_msgs),
                        front=Color.BRIGHT_MAGENTA)
        if msgs:
            out.writeln("Linter warnings\n    WARN: %s" % "\n    WARN: ".join(msgs),
                        front=Color.MAGENTA)
        pylint_werr = os.environ.get("CONAN_PYLINT_WERR", None)
        if pylint_werr and (py3_msgs or msgs):
            raise ConanException("Package recipe has linter errors. Please fix them.")


def _runner(args):
    command = ["pylint",  "--output-format=json"] + args
    command = " ".join(command)
    shell = True if platform.system() != "Windows" else False
    proc = Popen(command, shell=shell, bufsize=10, stdout=PIPE, stderr=PIPE)
    stdout, _ = proc.communicate()
    return json.loads(stdout.decode("utf-8")) if stdout else {}


def _normal_linter(conanfile_path, hook):
    args = ["--py3k", "--enable=all", "--reports=no", "--disable=no-absolute-import", "--persistent=no", 
            "--load-plugins=conans.pylint_plugin",
            hook, '"%s"' % conanfile_path]
    pylintrc = os.environ.get("CONAN_PYLINTRC", None)
    if pylintrc:
        if not os.path.exists(pylintrc):
            raise ConanException("File %s defined by PYLINTRC doesn't exist" % pylintrc)
        args.append('--rcfile="%s"' % pylintrc)

    output_json = _runner(args)

    def _accept_message(msg):
        symbol = msg.get("symbol")

        if symbol in ("bare-except", "broad-except"):  # No exception type(s) specified
            return False
        if symbol == "import-error" and msg.get("column") > 3:  # Import of a conan python package
            return False

        return True

    result = []
    py3msgs = []
    for msg in output_json:
        if msg.get("type") in ("warning", "error"):
            message_id = msg.get("symbol")
            if message_id in ("print-statement", "dict-iter-method"):
                py3msgs.append("Py3 incompatibility. Line %s: %s"
                               % (msg.get("line"), msg.get("message")))
            elif _accept_message(msg):
                result.append("Linter. Line %s: %s" % (msg.get("line"), msg.get("message")))

    return result, py3msgs
