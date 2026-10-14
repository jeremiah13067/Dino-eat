import os
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame
from runtime import Runtime


@pytest.fixture(scope="session", autouse=True)
def sdl():
    pygame.display.init()
    pygame.font.init()
    pygame.display.set_mode((480, 360))
    yield
    pygame.quit()


@pytest.fixture
def game():
    runtime = Runtime(ROOT, seed=42, audio=False)
    runtime.green_flag()
    runtime.step()
    yield runtime
    runtime.stop_all()
