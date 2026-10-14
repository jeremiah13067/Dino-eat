"""Native concurrent WAV playback with per-sprite sound restart semantics."""
from dataclasses import dataclass
import pygame


@dataclass
class Playback:
    end: float
    channel: object = None
    interrupted: bool = False

    def done(self, now):
        return self.interrupted or now + 1e-9 >= self.end


class Audio:
    def __init__(self, root, enabled=True):
        self.root = root
        self.enabled = enabled
        self.loaded = {}
        self.active = {}
        self.error = None
        if enabled:
            try:
                if not pygame.mixer.get_init():
                    pygame.mixer.init(frequency=48000, size=-16, channels=2, buffer=512)
                pygame.mixer.set_num_channels(32)
            except pygame.error as error:
                self.enabled = False
                self.error = str(error)

    def load(self, sound):
        filename = sound["md5ext"]
        if filename not in self.loaded:
            self.loaded[filename] = pygame.mixer.Sound(str(self.root / "assets" / filename))
        return self.loaded[filename]

    def play(self, sprite, name, now):
        sound = next(s for s in sprite.spec["sounds"] if s["name"] == name)
        key = (id(sprite), name)
        previous = self.active.get(key)
        if previous:
            previous.interrupted = True
            if previous.channel:
                previous.channel.stop()
        channel = None
        if self.enabled:
            wav = self.load(sound)
            channel = pygame.mixer.find_channel(True)
            channel.set_volume(sprite.volume / 100)
            channel.play(wav)
        playback = Playback(now + sound["sampleCount"] / sound["rate"], channel)
        self.active[key] = playback
        return playback

    def stop(self):
        for playback in self.active.values():
            playback.interrupted = True
            if playback.channel:
                playback.channel.stop()
        self.active.clear()
