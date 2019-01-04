from conans.server.launcher import ServerLauncher

launcher = ServerLauncher()
app = launcher.ra.root_app

def main(*args):
    launcher.launch()

if __name__ == "__main__":
    main()
