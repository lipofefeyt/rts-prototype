"""Headless AI-vs-AI soak test: simulates a full match at full speed (no window,
no rendering) and watches for incoherent behaviour via InvariantChecker.

Defaults to ~2 simulated minutes (quick smoke tier). Set SOAK_FRAMES to run a
longer soak locally, e.g. for a 30-simulated-minute nightly check:
    SOAK_FRAMES=108000 pytest tests/test_soak.py
"""
import os

import pygame

import main
from ai import AIController
from tests.invariants import InvariantChecker

SOAK_FRAMES = int(os.environ.get("SOAK_FRAMES", 60 * 60 * 2))   # 2 simulated minutes at 60 fps


class _DualAI:
    """Drives both teams' AIControllers — no human input needed for the soak test."""
    def __init__(self, team0_ai: AIController, team1_ai: AIController):
        self.team0_ai = team0_ai
        self.team1_ai = team1_ai

    def update(self, dt: float) -> None:
        self.team0_ai.update(dt)
        self.team1_ai.update(dt)


def test_ai_vs_ai_soak_no_incoherent_behaviour():
    state = main.init_game_state("normal", map_seed=4874)
    units, buildings = state['units'], state['buildings']
    gold, lumber = state['gold'], state['lumber']
    corpses, projectiles, float_texts = state['corpses'], state['projectiles'], state['float_texts']
    upgrades, game_map, fog = state['upgrades'], state['game_map'], state['fog']
    selected, selected_building = state['selected'], state['selected_building']
    unit_sprites, war2_sheets = state['unit_sprites'], state['war2_sheets']
    font = pygame.font.Font(None, 16)

    def sprite(t, team):
        return unit_sprites.get((t, team), unit_sprites[('footman', team % 2)])

    def sheet(t, team):
        return war2_sheets.get((t, team))

    team1_ai = state['ai']   # built by init_game_state for team 1
    team0_ai = AIController(
        team=0, buildings=buildings, units=units, gold=gold, lumber=lumber,
        game_map=game_map, enemy_sprite=sprite('footman', 0),
        worker_sprite=sprite('worker', 0), sheets=war2_sheets, difficulty="normal",
    )
    ai = _DualAI(team0_ai, team1_ai)

    checker = InvariantChecker(stuck_after=10.0)
    attack_alert = elapsed = 0.0
    dt = 1 / 60
    game_over = None

    for frame in range(SOAK_FRAMES):
        (units, buildings, corpses, projectiles, selected, selected_building,
         attack_alert, elapsed, game_over) = main.simulate_frame(
            dt, units, buildings, gold, lumber, corpses, projectiles, float_texts,
            upgrades, ai, game_map, fog, selected, selected_building, attack_alert,
            elapsed, font, lambda *_: None, sprite, sheet)

        checker.check(frame, dt, units, buildings, gold, lumber)

        if game_over:
            break

    # The match should still have a going concern on at least one side — it
    # didn't instantly implode from a setup bug.
    assert len(buildings) > 1
