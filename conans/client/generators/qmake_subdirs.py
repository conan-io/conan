from conans.model import Generator

class QmakeSubDirsGenerator(Generator):
    @property
    def filename(self):
        return "conan_subdirs.pri"

    @property
    def content(self):
        return "#todo"