"""Original costumes, pivot-aware drawing, alpha collisions and Scratch monitors."""
from pathlib import Path
import math
import pygame
from semantics import text


class Graphics:
    def __init__(self, root):
        self.root = Path(root)
        self.images = {}
        self.transforms = {}
        self.collision_masks = {}
        self.stage_mask = pygame.mask.Mask((480, 360), fill=True)
        self.stage = pygame.Surface((480, 360), pygame.SRCALPHA)
        self.font = pygame.font.SysFont("Helvetica,Arial,DejaVu Sans", 12, bold=True)

    def costume(self, sprite):
        return sprite.spec["costumes"][sprite.costume]

    def image(self, sprite):
        costume = self.costume(sprite)
        render = costume["render"]
        if render["empty"]:
            return None
        filename = render["file"]
        if filename not in self.images:
            self.images[filename] = pygame.image.load(str(self.root / "assets" / filename)).convert_alpha()
        ratio = sprite.size / 100 / costume.get("bitmapResolution", 1)
        angle = 90 - sprite.direction if sprite.rotation_style == "all around" else 0
        flip = sprite.rotation_style == "left-right" and sprite.direction < 0
        key = (filename, ratio, angle, flip)
        if key not in self.transforms:
            width, height = render["width"] * ratio, render["height"] * ratio
            surface = pygame.transform.smoothscale(self.images[filename],
                                                   (max(1, round(width)), max(1, round(height))))
            if flip:
                surface = pygame.transform.flip(surface, True, False)
            if angle:
                surface = pygame.transform.rotate(surface, angle)
            self.transforms[key] = (surface, pygame.mask.from_surface(surface, 0))
        return self.transforms[key]

    def geometry(self, sprite):
        rendered = self.image(sprite)
        if rendered is None:
            return None
        surface, mask = rendered
        costume = self.costume(sprite)
        render = costume["render"]
        ratio = sprite.size / 100 / costume.get("bitmapResolution", 1)
        offset = pygame.Vector2((render["width"] / 2 - costume["rotationCenterX"]) * ratio,
                                (render["height"] / 2 - costume["rotationCenterY"]) * ratio)
        if sprite.rotation_style == "left-right" and sprite.direction < 0:
            offset.x *= -1
        if sprite.rotation_style == "all around":
            offset.rotate_ip(sprite.direction - 90)
        center = pygame.Vector2(240 + sprite.x, 180 - sprite.y) + offset
        rect = surface.get_rect()
        rect.topleft = (math.floor(center.x - rect.width / 2 + 0.5),
                        math.floor(center.y - rect.height / 2 + 0.5))
        return surface, mask, rect

    def fence(self, sprite, x, y):
        costume = self.costume(sprite)
        render = costume["render"]
        ratio = sprite.size / 100 / costume.get("bitmapResolution", 1)
        width, height = render["width"] * ratio, render["height"] * ratio
        cx, cy = costume["rotationCenterX"] * ratio, costume["rotationCenterY"] * ratio
        points = [pygame.Vector2(px, py) for px in (-cx, width - cx) for py in (cy, cy - height)]
        if sprite.rotation_style == "all around":
            points = [p.rotate(90 - sprite.direction) for p in points]
        elif sprite.rotation_style == "left-right" and sprite.direction < 0:
            points = [pygame.Vector2(-p.x, p.y) for p in points]
        left, right = sprite.x + min(p.x for p in points), sprite.x + max(p.x for p in points)
        bottom, top = sprite.y + min(p.y for p in points), sprite.y + max(p.y for p in points)
        inset = min(15, math.floor(min(right - left, top - bottom) / 2))
        sx, sy = 240 - inset, 180 - inset
        dx, dy = x - sprite.x, y - sprite.y
        if right + dx < -sx:
            x = math.ceil(sprite.x - (sx + right))
        elif left + dx > sx:
            x = math.floor(sprite.x + (sx - left))
        if top + dy < -sy:
            y = math.ceil(sprite.y - (sy + top))
        elif bottom + dy > sy:
            y = math.floor(sprite.y + (sy - bottom))
        return x, y

    def touching(self, sprite, other):
        if not sprite.visible or not other.visible or sprite is other:
            return False
        a, b = self.collision_geometry(sprite), self.collision_geometry(other)
        if not a or not b:
            return False
        mask_a, rect_a = a
        mask_b, rect_b = b
        if not rect_a.colliderect(rect_b):
            return False
        offset = (rect_b.x - rect_a.x, rect_b.y - rect_a.y)
        if pygame.Rect(0, 0, 480, 360).contains(rect_a.clip(rect_b)):
            return mask_a.overlap(mask_b, offset) is not None
        overlap = mask_a.overlap_mask(mask_b, offset)
        return overlap.overlap(self.stage_mask, (-rect_a.x, -rect_a.y)) is not None

    def collision_geometry(self, sprite):
        costume = self.costume(sprite)
        render = costume["render"]
        if render["empty"]:
            return None
        data = render.get("collision")
        # Every project script retains size=100, direction=90, and integer
        # positions. These masks preserve Scratch's exact integer sampling of
        # the original texture, including fractional/outside rotation centers.
        if data and sprite.size == 100 and sprite.direction == 90 and sprite.x % 1 == 0 and sprite.y % 1 == 0:
            filename = data["file"]
            if filename not in self.collision_masks:
                surface = pygame.image.load(str(self.root / "assets" / filename))
                self.collision_masks[filename] = pygame.mask.from_surface(surface, 0)
            mask = self.collision_masks[filename]
            x, y = data["offset"]
            return mask, pygame.Rect(240 + sprite.x + x, 180 - sprite.y + y, *mask.get_size())
        _, mask, rect = self.geometry(sprite)
        return mask, rect

    def render(self, runtime):
        self.stage.fill("white")
        for sprite in runtime.sprites:
            if sprite.visible:
                geometry = self.geometry(sprite)
                if geometry:
                    self.stage.blit(geometry[0], geometry[2])
        for monitor in runtime.monitors:
            if not monitor["visible"]:
                continue
            name = monitor["params"]["VARIABLE"]
            owner = runtime.by_name.get(monitor["spriteName"] or "Stage")
            label = name if monitor["spriteName"] is None else f"{owner.name}: {name}"
            caption = self.font.render(label, True, (87, 94, 117))
            value = self.font.render(text(owner.get_var(name)), True, "white")
            value_width = max(40, value.get_width() + 10)
            x, y = monitor["x"], monitor["y"]
            box = pygame.Rect(x, y, caption.get_width() + value_width + 17, 21)
            pygame.draw.rect(self.stage, (234, 237, 244), box, border_radius=5)
            pygame.draw.rect(self.stage, (185, 190, 203), box, width=1, border_radius=5)
            self.stage.blit(caption, (x + 5, y + 3))
            orange = pygame.Rect(box.right - value_width - 5, y + 3, value_width, 15)
            pygame.draw.rect(self.stage, (255, 140, 26), orange, border_radius=4)
            self.stage.blit(value, value.get_rect(center=orange.center))
        return self.stage
