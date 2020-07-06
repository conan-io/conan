import calendar
import os
import shutil
import time

from conans.model import Generator
from conans.model.manifest import FileTreeManifest
from conans.paths import BUILD_INFO_DEPLOY
from conans.util.files import mkdir, md5sum
import textwrap


class ExecutableWrapperGenerator(Generator):

    @property
    def filename(self):
        return None

    @property
    def content(self):
        # For each dependency, for each executable, create a wrapper file that populates the
        #   environment, executes the original program and restores the environment.

        # FIXME: I know there is a BR called 'cmake' and virtualenv generator is in place
        return {'cmake.sh': textwrap.dedent("""
            source activate.sh
            echo Calling CMake wrapper with 'cmake "@$"'
            shift
            cmake "$@"
            source deactivate.sh
        """)}
