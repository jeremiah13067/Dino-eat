"""Reproduce native verification evidence using already captured Scratch data."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"


def main():
    import pygame
    from PIL import Image, ImageChops, ImageStat
    from runtime import Runtime

    evidence = ROOT / "verification"
    evidence.mkdir(exist_ok=True)
    subprocess.run([sys.executable, "-m", "compileall", "-q", "-x", r"node_modules|\.venv", str(ROOT)], check=True)
    subprocess.run([sys.executable, "-m", "pytest", str(ROOT / "tests"), "-q",
                    f"--junitxml={evidence / 'test_results.xml'}"], check=True)
    subprocess.run([sys.executable, str(ROOT / "main.py"), "--headless", "--frames", "1800",
                    "--seed", "10", "--screenshot", str(evidence / "one_minute.png")], check=True)
    pygame.display.init()
    pygame.font.init()
    pygame.display.set_mode((480, 360))
    game = Runtime(ROOT, audio=False)
    game.rng.random = lambda: .5
    game.green_flag()
    game.step()
    pygame.image.save(game.draw(), str(evidence / "python_initial.png"))
    original = json.loads((evidence / "scratch_vm_reference.json").read_text())
    game.by_name["Dinosaur1"].goto(0, 0)
    collisions = {}
    for name, probes in original["collisionGrid"].items():
        sprite = game.by_name[name]
        sprite.costume = 0
        details = []
        for x, y, expected in probes:
            sprite.goto(x, y)
            actual = sprite.touching("Dinosaur1")
            if expected != actual:
                details.append([x, y, expected, actual])
        collisions[name] = {"samples": len(probes), "mismatches": len(details), "details": details}
    (evidence / "collision_comparison.json").write_text(json.dumps(collisions, indent=2))
    game.stop_all()
    pygame.quit()
    scratch = Image.open(evidence / "scratch_initial.png").convert("RGB")
    native = Image.open(evidence / "python_initial.png").convert("RGB")
    comparison = Image.new("RGB", (960, 360))
    comparison.paste(scratch, (0, 0))
    comparison.paste(native, (480, 0))
    comparison.save(evidence / "visual_comparison.png")
    native.paste(scratch.crop((0, 0, 110, 70)), (0, 0))
    means = ImageStat.Stat(ImageChops.difference(scratch, native)).mean
    summary = {"python": sys.version, "pygame_ce": pygame.version.ver,
               "collision_probes": sum(v["samples"] for v in collisions.values()),
               "collision_mismatches": sum(v["mismatches"] for v in collisions.values()),
               "visual_channel_mean_absolute_errors": means,
               "visual_mean_absolute_error": sum(means) / 3,
               "visual_excluded_rectangle": [0, 0, 110, 70],
               "sustained_rendered_frames": 1800,
               "reference_engine": original["engine"], "reference_renderer": original["renderer"]}
    (evidence / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    assert summary["collision_mismatches"] == 0


if __name__ == "__main__":
    main()
