"""Play speech and effects on top of one pet's frame sequence."""

from minibuddies.effects import PluginEffectOverlay


class ActionPlayback:
    def __init__(self, pet, events):
        self.pet = pet
        self.events = {beat.at: beat for beat in events}
        self.overlay = None
        self.bubble = None

    def advance(self, tick, opening_speech=""):
        pet = self.pet
        beat = self.events.pop(tick, None)
        speech = (beat.speech if beat else "") or opening_speech
        if speech:
            previous = pet.bubble
            pet.say(speech, min(pet.t, 120))
            if pet.bubble is not previous:
                self.bubble = pet.bubble
        if beat and beat.effect:
            if self.overlay is None:
                self.overlay = PluginEffectOverlay([pet], pet.app.on_top)
            self.overlay.show_effect(pet, None, beat.effect, tick)
        if self.overlay is not None:
            self.overlay.advance(tick)
            if not self.overlay.bursts:
                self.overlay.close()
                self.overlay = None

    def close(self):
        if self.overlay is not None:
            self.overlay.close()
        if self.bubble is not None and self.pet.bubble is self.bubble:
            self.bubble.close()
            self.pet.bubble = None
