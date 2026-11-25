"""Launch MiniBuddies from its existing script entry point."""

from minibuddies.runtime import install_crash_handlers


def main():
    install_crash_handlers()
    from minibuddies.app import App
    from minibuddies.ui.picker import first_run_pick

    first_run_pick()
    App().run()


if __name__ == "__main__":
    main()
