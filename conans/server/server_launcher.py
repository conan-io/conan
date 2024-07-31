import os

from conans.server.launcher import ServerLauncher


launcher = ServerLauncher(server_dir=os.environ.get("CONAN_SERVER_HOME"))
app = launcher.server.root_app


def main(*args):
    launcher.launch()


if __name__ == "__main__":
    main()
