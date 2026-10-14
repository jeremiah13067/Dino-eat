"""Reusable native sprite/event runtime for the features present in Digit Dash."""
from copy import deepcopy
from pathlib import Path
import random
from audio import Audio
from graphics import Graphics
from scheduler import Scheduler, Wait, LOOP_YIELD
from semantics import number, random_between, scratch_round


class Sprite:
    def __init__(self, runtime, spec):
        self.runtime, self.spec = runtime, spec
        self.name = spec["name"]
        self.is_stage = spec["isStage"]
        self.is_clone = False
        self.x, self.y = spec.get("x", 0), spec.get("y", 0)
        self.direction = spec.get("direction", 90)
        self.rotation_style = spec.get("rotationStyle", "don't rotate")
        self.size = spec.get("size", 100)
        self.visible = spec.get("visible", True)
        self.costume = spec["currentCostume"]
        self.volume = spec["volume"]
        self.variables = {v[0]: deepcopy(v[1]) for v in spec["variables"].values()}
        self.lists = {v[0]: deepcopy(v[1]) for v in spec["lists"].values()}

    def get_var(self, name):
        return self.variables[name] if name in self.variables else self.runtime.stage.variables[name]

    def set_var(self, name, value):
        owner = self if name in self.variables else self.runtime.stage
        owner.variables[name] = value

    def change_var(self, name, amount):
        self.set_var(name, number(self.get_var(name)) + number(amount))

    def goto(self, x, y):
        self.x, self.y = self.runtime.graphics.fence(self, number(x), number(y))
        if self.visible:
            self.runtime.scheduler.redraw = True

    @property
    def visible(self):
        return self._visible

    @visible.setter
    def visible(self, value):
        self._visible = bool(value)
        self.runtime.scheduler.redraw = True

    def set_x(self, value):
        self.goto(value, self.y)

    def set_y(self, value):
        self.goto(self.x, value)

    def change_x(self, value):
        self.goto(self.x + number(value), self.y)

    def change_y(self, value):
        self.goto(self.x, self.y + number(value))

    def goto_target(self, name):
        if name == "_random_":
            # Scratch motion randomness rounds a continuous stage coordinate,
            # making the two endpoints half as likely as interior positions.
            self.goto(scratch_round(480 * (self.runtime.rng.random() - 0.5)),
                      scratch_round(360 * (self.runtime.rng.random() - 0.5)))
        elif name == "_mouse_":
            self.goto(*self.runtime.mouse)
        elif name in self.runtime.by_name:
            other = self.runtime.by_name[name]
            self.goto(other.x, other.y)

    def touching(self, name):
        return any(self.runtime.graphics.touching(self, other)
                   for other in self.runtime.sprites if other.name == name)

    def switch_costume(self, name):
        for i, costume in enumerate(self.spec["costumes"]):
            if costume["name"] == name:
                self.costume = i
                if self.visible:
                    self.runtime.scheduler.redraw = True
                return
        self.costume = (scratch_round(name) - 1) % len(self.spec["costumes"])

    def next_costume(self):
        self.costume = (self.costume + 1) % len(self.spec["costumes"])
        if self.visible:
            self.runtime.scheduler.redraw = True


class Runtime:
    def __init__(self, root=None, seed=None, audio=True):
        from project_data import TARGETS, MONITORS
        import scripts
        self.root = Path(root or Path(__file__).resolve().parent)
        self.scheduler = Scheduler()
        self.rng = random.Random(seed)
        self.graphics = Graphics(self.root)
        self.audio = Audio(self.root, enabled=audio)
        self.mouse = (0, 0)
        self.keys = set()
        self.monitors = deepcopy(MONITORS)
        # Scratch executable targets and drawing layers share the saved layer order.
        self.sprites = [Sprite(self, spec) for spec in sorted(TARGETS, key=lambda s: s["layerOrder"])]
        self.originals = list(self.sprites)
        self.by_name = {sprite.name: sprite for sprite in self.originals}
        self.stage = self.by_name["Stage"]
        self.handlers = []
        scripts.register(self)

    def on(self, name, event, key, function, hat):
        self.handlers.append((name, event, key, function, hat))

    def emit(self, event, key=None, only=None):
        started = []
        for sprite in reversed(self.sprites):
            if only is not None and sprite is not only:
                continue
            for name, kind, match, function, hat in self.handlers:
                if name == sprite.name and kind == event and (match is None or match == key):
                    started.append(self.scheduler.start(sprite, lambda s=sprite, f=function: f(self, s),
                                                        hat, restart=event == "green_flag"))
        return started

    def green_flag(self):
        # Green flag cancels threads/audio/clones, but does not restore saved positions
        # or variables unless an actual green-flag script writes them.
        self.stop_all()
        self.emit("green_flag")

    def stop_all(self):
        self.scheduler.cancel()
        self.scheduler.threads.clear()
        self.audio.stop()
        self.sprites[:] = self.originals

    def key_down(self, key):
        key = key.lower()
        self.keys.add(key)
        self.emit("key", key)

    def key_up(self, key):
        self.keys.discard(key.lower())

    def wait(self, seconds):
        self.scheduler.redraw = True
        return Wait(self.scheduler.now + max(0, number(seconds)))

    def next_frame(self):
        return LOOP_YIELD

    def play_sound(self, sprite, name):
        return self.audio.play(sprite, name, self.scheduler.now)

    def random(self, low, high):
        return random_between(self.rng, low, high)

    def create_clone(self, parent, name):
        if sum(s.is_clone for s in self.sprites) >= 300:
            return None
        original = parent if name == "_myself_" else self.by_name.get(name)
        if original is None or original.is_stage:
            return None
        clone = Sprite(self, original.spec)
        for attribute in ("x", "y", "direction", "rotation_style", "size", "visible", "costume", "volume"):
            setattr(clone, attribute, getattr(original, attribute))
        clone.variables = deepcopy(original.variables)
        clone.lists = deepcopy(original.lists)
        clone.is_clone = True
        # A Scratch clone is placed just behind its source.
        self.sprites.insert(self.sprites.index(original), clone)
        self.emit("clone_start", only=clone)
        return clone

    def delete_clone(self, sprite):
        if sprite.is_clone:
            self.scheduler.cancel(sprite)
            if sprite in self.sprites:
                self.sprites.remove(sprite)

    def step(self, dt=1 / 30):
        self.scheduler.step(dt)

    def draw(self):
        return self.graphics.render(self)
