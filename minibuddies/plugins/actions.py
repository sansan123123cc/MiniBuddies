"""Play movement, speech, and effects over one pet's frame sequence."""

from minibuddies.effects import PluginEffectOverlay
from minibuddies.plugins.motion import apply_motion, compile_motion, grounded_actor
from minibuddies.plugins.scenes import SPEECH_TICKS


def close_action_bubble(pet, bubble):
    if bubble is not None and pet.bubble is bubble:
        bubble.close()
        pet.bubble = None


class ActionPlayback:
    def __init__(self, pet, events):
        self.pet = pet
        self.events = {beat.at: beat for beat in events}
        self.motion = (compile_motion({pet.char: grounded_actor(pet)}, {pet.char: events})[pet.char]
                       if any(beat.move or beat.turn for beat in events) else None)
        self.tracks_position = self.motion is not None and self.motion.displaces()
        self.tick = 0
        self.overlay = None
        self.bubble = None

    def advance(self, tick, opening_speech=""):
        pet = self.pet
        self.tick = tick
        if self.motion is not None:
            apply_motion(pet, self.motion, tick)
        beat = self.events.pop(tick, None)
        speech = (beat.speech if beat else "") or opening_speech
        if beat and beat.dismiss_speech:
            close_action_bubble(pet, self.bubble)
            self.bubble = None
        elif speech:
            previous = pet.bubble
            pet.say(speech, min(pet.t, SPEECH_TICKS))
            if pet.bubble is not previous:
                self.bubble = pet.bubble
        if beat and beat.effect:
            if self.overlay is None:
                self.overlay = PluginEffectOverlay([pet], pet.app.on_top, track_positions=self.tracks_position)
            self.overlay.show_effect(pet, None, beat.effect, tick)
        if self.overlay is not None:
            self.overlay.advance(tick)
            if not self.overlay.bursts:
                self.overlay.close()
                self.overlay = None

    def close(self):
        if self.motion and self.motion.pose(self.tick).lift and self.pet.surface is not None and self.pet.drag is None:
            self.pet.stand_on(self.pet.surface)
        if self.overlay is not None:
            self.overlay.close()
        close_action_bubble(self.pet, self.bubble)
