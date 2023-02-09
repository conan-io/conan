from conans.server.launcher import ServerLauncher

from conans.util.env import get_env

launcher = ServerLauncher(server_dir=get_env("CONAN_SERVER_HOME"))
app = launcher.server.root_app


def main(*args):
    launcher.launch()


if __name__ == "__main__":
    main()
