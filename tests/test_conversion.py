import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys

import pygame
import pytest
from project_data import TARGETS
from runtime import Runtime
from scheduler import Scheduler, Wait, LOOP_YIELD
from semantics import number, compare, scratch_round, random_between

ROOT = Path(__file__).resolve().parents[1]


def advance(game, seconds):
    for _ in range(round(seconds * 30)):
        game.step()


def isolate(game, *names):
    for sprite in game.sprites:
        sprite.visible = sprite.name in ("Stage",) + names


def test_entire_project_coverage_and_registration(game):
    project = json.loads((ROOT / "reference/project.json").read_text())
    coverage = json.loads((ROOT / "coverage.json").read_text())
    original_ids = {bid for target in project["targets"] for bid in target["blocks"]}
    assert len(original_ids) == 124
    assert set(coverage["mapping"]) == original_ids
    assert len(game.handlers) == 23
    assert len(game.originals) == 9
    source_lines = (ROOT / "scripts.py").read_text().splitlines()
    for entry in coverage["mapping"].values():
        assert entry["function"] in (ROOT / "scripts.py").read_text()
    for bid, entry in coverage["mapping"].items():
        line = source_lines[entry["line"] - 1]
        if entry["role"] == "statement":
            assert bid in line
        elif entry["role"] == "event registration":
            assert line.startswith(f"def {entry['function']}(")
    analysis = json.loads((ROOT / "reference/analysis.json").read_text())
    assert not any(t["unreachable"] for t in analysis["targets"])
    assert analysis["dependencies"]


def test_assets_preserved_and_every_costume_renders(game):
    audit = json.loads((ROOT / "coverage.json").read_text())
    for filename, digest in audit["asset_sha256"].items():
        assert hashlib.sha256((ROOT / "reference" / filename).read_bytes()).hexdigest() == digest
    for sprite in game.originals:
        for index, costume in enumerate(sprite.spec["costumes"]):
            sprite.costume = index
            assert (ROOT / "assets" / costume["render"]["file"]).is_file()
            result = game.graphics.geometry(sprite)
            assert (result is None) == costume["render"]["empty"]


def test_initial_state_and_monitor_positions(game):
    assert game.stage.variables == {"Deaths": "0", "Score": "0", "Time left": "270", "my variable": 6}
    assert (game.by_name["Dinosaur1"].x, game.by_name["Dinosaur1"].y) == (-180, 0)
    assert game.by_name["Rocks"].costume == 1
    assert not game.by_name["."].visible
    assert len([s for s in game.sprites if s.is_clone]) == 1
    surface = game.draw()
    assert surface.get_size() == (480, 360)
    assert [(m["x"], m["y"]) for m in game.monitors if m["visible"]] == [(5, 3), (0, 24), (0, 45)]


@pytest.mark.parametrize("key,dx,dy", [("w", 0, 10), ("s", 0, -10), ("a", -10, 0), ("d", 10, 0)])
def test_keyboard_motion(game, key, dx, dy):
    dinosaur = game.by_name["Dinosaur1"]
    x, y = dinosaur.x, dinosaur.y
    game.key_down(key)
    game.step()
    assert (dinosaur.x, dinosaur.y) == (x + dx, y + dy)
    game.key_up(key)
    assert not game.keys


@pytest.mark.parametrize("name,points,duration", [("Apple", 1, .264125), ("Cake", 1, .264125),
                                                  ("Cheesy Puffs", 1, .264125), ("Muffin", 1, .264125),
                                                  ("Watermelon", 10, .3686622)])
def test_collect_sound_then_score(game, name, points, duration):
    isolate(game, "Dinosaur1", name)
    food, dinosaur = game.by_name[name], game.by_name["Dinosaur1"]
    dinosaur.goto(food.x, food.y)
    assert food.touching("Dinosaur1")
    old_position = (food.x, food.y)
    game.step()
    assert (food.x, food.y) != old_position
    assert number(game.stage.get_var("Score")) == 0
    dinosaur.goto(-250, 180)
    advance(game, duration - .04)
    assert number(game.stage.get_var("Score")) == 0
    advance(game, .1)
    assert number(game.stage.get_var("Score")) == points


def test_rocks_delay_death_and_time_reset_after_alert(game):
    isolate(game, "Dinosaur1", "Rocks")
    rock = game.by_name["Rocks"]
    rock.goto_target = lambda _: None
    game.by_name["Dinosaur1"].goto(rock.x, rock.y)
    game.stage.set_var("Score", 25)
    advance(game, 4.9)
    assert rock.costume == 1
    assert number(game.stage.get_var("Deaths")) == 0
    advance(game, .2)
    assert rock.costume == 0
    assert number(game.stage.get_var("Deaths")) == 1
    assert number(game.stage.get_var("Score")) == 0
    game.by_name["Dinosaur1"].goto(-250, 180)
    advance(game, .9)
    assert number(game.stage.get_var("Time left")) < 270
    advance(game, .2)
    assert number(game.stage.get_var("Time left")) == 270


def test_timeout_continues_negative_and_keeps_resetting_score(game):
    isolate(game)
    advance(game, 275)
    assert number(game.stage.get_var("Time left")) < 0
    game.stage.set_var("Score", 99)
    advance(game, 1.1)
    assert number(game.stage.get_var("Score")) == 0


def test_clone_original_behavior_and_forced_deletion_branch(game):
    isolate(game)
    clone = next(s for s in game.sprites if s.is_clone)
    clone.y = -110  # Exercise the otherwise unreachable original condition.
    advance(game, .3)
    assert clone not in game.sprites
    successor = next(s for s in game.sprites if s.is_clone)
    assert successor.y == 160
    advance(game, 16)
    assert successor in game.sprites  # y never changes naturally; no deletion.
    assert not any(t.sprite is successor for t in game.scheduler.threads)


def test_clone_local_variables_copy_but_globals_are_shared(game):
    rock = game.by_name["Rocks"]
    rock.set_var("Game over", 17)
    clone = game.create_clone(rock, "_myself_")
    assert clone.get_var("Game over") == 17
    clone.set_var("Game over", 99)
    clone.change_var("Score", 2)
    assert rock.get_var("Game over") == 17
    assert number(rock.get_var("Score")) == 2
    game.delete_clone(clone)
    assert clone not in game.sprites
    assert game.create_clone(game.stage, "_myself_") is None


def test_clone_limit(game):
    game.stop_all()
    rock = game.by_name["Rocks"]
    for _ in range(300):
        assert game.create_clone(rock, "_myself_") is not None
    assert game.create_clone(rock, "_myself_") is None
    game.stop_all()
    assert len(game.sprites) == 9


def test_restart_cancels_threads_and_only_resets_scripted_state(game):
    isolate(game)
    game.by_name["Watermelon"].goto(100, 50)
    game.by_name["Rocks"].goto(12, 34)
    game.stage.set_var("Score", 91)
    game.stage.set_var("Deaths", 6)
    old = list(game.scheduler.threads)
    game.green_flag()
    game.step()
    assert all(not t.alive for t in old)
    assert number(game.stage.get_var("Score")) == 0
    assert number(game.stage.get_var("Deaths")) == 0
    assert game.stage.get_var("Time left") == "270"
    assert (game.by_name["Watermelon"].x, game.by_name["Watermelon"].y) == (100, 50)
    assert (game.by_name["Rocks"].x, game.by_name["Rocks"].y) == (12, 34)
    assert sum(s.is_clone for s in game.sprites) == 1
    game.stop_all()
    assert not game.scheduler.threads


def test_alpha_collision_and_empty_costumes(game):
    dinosaur, apple = game.by_name["Dinosaur1"], game.by_name["Apple"]
    dinosaur.goto(0, 0)
    apple.goto(0, 0)
    assert apple.touching("Dinosaur1")
    found_transparent_overlap = False
    for x in range(-100, 150, 10):
        for y in range(-100, 150, 10):
            apple.goto(x, y)
            a, b = game.graphics.geometry(apple), game.graphics.geometry(dinosaur)
            if a[2].colliderect(b[2]) and not apple.touching("Dinosaur1"):
                found_transparent_overlap = True
                break
        if found_transparent_overlap:
            break
    assert found_transparent_overlap
    rock = game.by_name["Rocks"]
    rock.goto(0, 0)
    assert not rock.touching("Dinosaur1")
    apple.visible = False
    assert not apple.touching("Dinosaur1")


def test_sprite_fencing_and_noncentral_costume_pivot(game):
    dinosaur = game.by_name["Dinosaur1"]
    dinosaur.goto(-10000, -10000)
    rect = game.graphics.geometry(dinosaur)[2]
    assert rect.right >= 15
    assert rect.top <= 345
    watermelon = game.by_name["Watermelon"]
    watermelon.goto(0, 0)
    rect = game.graphics.geometry(watermelon)[2]
    assert rect.left > 240  # Original pivot is outside the costume, to its left.


def test_all_original_audio_decodes_and_starts_concurrently():
    runtime = Runtime(ROOT, audio=True)
    assert runtime.audio.enabled
    for sprite in runtime.originals:
        for sound in sprite.spec["sounds"]:
            loaded = runtime.audio.load(sound)
            assert abs(loaded.get_length() - sound["sampleCount"] / sound["rate"]) < .02
            play = runtime.play_sound(sprite, sound["name"])
            assert play.channel.get_busy()
            assert not play.done(runtime.scheduler.now)
            assert play.done(runtime.scheduler.now + 10)
    apple = runtime.by_name["Apple"]
    first = runtime.play_sound(apple, "Chomp")
    second = runtime.play_sound(apple, "Chomp")
    assert first.interrupted and not second.interrupted
    runtime.stop_all()
    assert not runtime.audio.active


def test_scratch_coercion_rounding_comparisons_and_random():
    assert number("abc") == number("") == number(float("nan")) == 0
    assert number(True) == 1
    assert scratch_round(-1.5) == -1 and scratch_round(1.5) == 2
    assert compare("10", 2) > 0
    assert compare("hello", "HELLO") == 0
    assert compare(" ", 0) < 0
    rng = random.Random(1)
    samples = [random_between(rng, "-100", "100") for _ in range(1000)]
    assert all(isinstance(s, int) and -100 <= s <= 100 for s in samples)


def test_reference_vm_snapshots(game):
    reference = json.loads((ROOT / "verification/scratch_vm_reference.json").read_text())
    # These snapshots use the actual Scratch WebGL renderer. None of this
    # particular movement sequence collects food; audio is tested separately.
    game.stop_all()
    game.rng.random = lambda: .5
    game.scheduler.now = 0
    game.green_flag()
    game.step()

    def compare_snapshot(snapshot):
        for name, expected in snapshot["variables"].items():
            assert game.stage.get_var(name) == expected
        for target in snapshot["targets"]:
            actual = next(s for s in game.sprites if s.name == target["name"] and s.is_clone != target["original"])
            assert (actual.x, actual.y, actual.costume, actual.visible) == (target["x"], target["y"], target["costume"], target["visible"])
        assert sorted(t.hat for t in game.scheduler.threads) == sorted(snapshot["threadHats"])

    compare_snapshot(reference["snapshots"][0])
    for key in ("d", "w", "a", "s", "d"):
        game.key_down(key)
        game.step()
        game.key_up(key)
    compare_snapshot(reference["snapshots"][1])
    for snapshot in reference["snapshots"][2:4]:
        while game.scheduler.now * 1000 < snapshot["time"] - .01:
            game.step()
        compare_snapshot(snapshot)
    game.green_flag()
    game.step()
    compare_snapshot(reference["snapshots"][4])


@pytest.mark.parametrize("name", ["Apple", "Cake", "Cheesy Puffs", "Muffin", "Watermelon", "Rocks"])
def test_reference_webgl_collision_grid(game, name):
    reference = json.loads((ROOT / "verification/scratch_vm_reference.json").read_text())
    game.by_name["Dinosaur1"].goto(0, 0)
    food = game.by_name[name]
    food.costume = 0
    for x, y, expected in reference["collisionGrid"][name]:
        food.goto(x, y)
        assert food.touching("Dinosaur1") == expected, (name, x, y)


def test_standalone_without_reference_json(tmp_path):
    # Move the sources/assets to a fresh directory without reference/project.json.
    import shutil
    for path in ROOT.glob("*.py"):
        shutil.copy2(path, tmp_path / path.name)
    shutil.copytree(ROOT / "assets", tmp_path / "assets")
    result = subprocess.run([sys.executable, str(tmp_path / "main.py"), "--headless", "--frames", "180",
                             "--screenshot", str(tmp_path / "stage.png")], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "stage.png").is_file()
