"""Digit Dash -- native Python conversion of the supplied Scratch project."""
import argparse
import os
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--headless", action="store_true", help="Use SDL's offscreen drivers")
    parser.add_argument("--frames", type=int, default=0, help="Exit after N frames (0: interactive)")
    parser.add_argument("--screenshot", type=Path, help="Save the last logical stage frame")
    parser.add_argument("--mute", action="store_true")
    parser.add_argument("--seed", type=int)
    args = parser.parse_args(argv)
    if args.headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
    os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    import pygame
    from runtime import Runtime
    pygame.display.init()
    pygame.font.init()
    pygame.display.set_caption("Digit Dash | WASD to move | F5 restart | Esc stop")
    window = pygame.display.set_mode((960, 720), pygame.RESIZABLE)
    pygame.key.set_repeat(500, 33)
    clock = pygame.time.Clock()
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    runtime = Runtime(root, seed=args.seed, audio=not args.mute)
    if runtime.audio.error:
        print(f"Audio device unavailable; continuing with sound timing: {runtime.audio.error}", file=sys.stderr)
    runtime.green_flag()
    running, frames = True, 0
    try:
        while running:
            dt = 1 / 30 if args.headless else clock.tick(30) / 1000
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_F5:
                        runtime.green_flag()
                    elif event.key == pygame.K_ESCAPE:
                        runtime.stop_all()
                    else:
                        runtime.key_down(pygame.key.name(event.key))
                elif event.type == pygame.KEYUP:
                    runtime.key_up(pygame.key.name(event.key))
                elif event.type == pygame.WINDOWFOCUSLOST:
                    runtime.keys.clear()
            runtime.step(dt)
            stage = runtime.draw()
            width, height = window.get_size()
            scale = min(width / 480, height / 360)
            size = (max(1, round(480 * scale)), max(1, round(360 * scale)))
            offset = ((width - size[0]) // 2, (height - size[1]) // 2)
            mx, my = pygame.mouse.get_pos()
            runtime.mouse = ((mx - offset[0]) / scale - 240, 180 - (my - offset[1]) / scale)
            window.fill((30, 30, 36))
            window.blit(pygame.transform.smoothscale(stage, size), offset)
            pygame.display.flip()
            frames += 1
            if args.frames and frames >= args.frames:
                running = False
        if args.screenshot:
            args.screenshot.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(runtime.draw(), str(args.screenshot))
    finally:
        runtime.stop_all()
        pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
