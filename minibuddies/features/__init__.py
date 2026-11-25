"""Built-in behaviors installed in their original callback order."""

def install_builtin(App, Buddy):
    from minibuddies.features import costumes, dialogue, dorothy, outfit_music, passthrough, pepero, rest, weather

    pepero.install(App, Buddy)
    weather.install(App, Buddy)
    rest.install(App, Buddy)
    dorothy.install(App, Buddy)
    passthrough.install(App)
    outfit_music.install(App)
    costumes.install(App, Buddy)
