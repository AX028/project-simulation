"""Command-line experience for the simulation framework."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .combat import run_encounter
from .content import CLASS_DEFINITIONS, ENEMY_DEFINITIONS, create_character, create_enemy
from .decision import UtilityDecisionPolicy
from .models import EncounterState, GameState, SimulationError, WorldConfig
from .persistence import load_game, save_game
from .world import WorldStore, generate_world


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="project-simulation", description="Deterministic fantasy RPG simulation"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("classes", help="list playable classes")
    sub.add_parser("enemies", help="list enemies")
    play = sub.add_parser("play", help="run a complete encounter")
    play.add_argument("--class", dest="class_id", choices=CLASS_DEFINITIONS, default="barbarian")
    play.add_argument("--name", default="Adventurer")
    play.add_argument("--enemy", choices=ENEMY_DEFINITIONS, default="goblin")
    play.add_argument("--level", type=int, default=1)
    play.add_argument("--seed", type=int, default=42)
    play.add_argument("--save", type=Path)
    play.add_argument("--world", type=Path)
    replay = sub.add_parser("replay", help="replay from saved campaign metadata")
    replay.add_argument("save", type=Path)
    replay.add_argument("--enemy", choices=ENEMY_DEFINITIONS, default="goblin")
    inspect = sub.add_parser("inspect", help="inspect a save without running it")
    inspect.add_argument("save", type=Path)
    world = sub.add_parser("world", help="generate and store a headless world")
    world.add_argument("path", type=Path)
    world.add_argument("--seed", type=int, default=42)
    world.add_argument("--width", type=int, default=64)
    world.add_argument("--height", type=int, default=64)
    world.add_argument("--chunk-size", type=int, default=16)
    return parser


def _play(args: argparse.Namespace, state: GameState | None = None) -> int:
    player = state.player if state else create_character(args.class_id, args.name, args.seed)
    seed = state.seed if state else args.seed
    enemy = create_enemy(
        args.enemy, args.level if hasattr(args, "level") else player.level, seed + 1
    )
    encounter = EncounterState({player.actor_id: player, enemy.actor_id: enemy})
    result = run_encounter(encounter, UtilityDecisionPolicy(), seed)
    for event in result.events:
        print(event)
    winner = result.state.actors.get(result.winner_id or "")
    print(f"Winner: {winner.name if winner else 'none'} after {result.rounds} rounds")
    if result.winner_id == player.actor_id:
        player.experience += enemy.experience_reward
        while player.experience >= player.level * 100:
            player.experience -= player.level * 100
            player.level += 1
            print(f"{player.name} reached level {player.level}!")
    if getattr(args, "world", None):
        world = generate_world(WorldConfig(), seed)
        WorldStore.write(world, args.world)
    if getattr(args, "save", None):
        save_game(
            GameState(
                seed,
                result.rounds,
                player,
                str(args.world) if args.world else None,
                encounter.event_memory,
            ),
            args.save,
        )
        print(f"Saved campaign to {args.save}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "classes":
            for key in CLASS_DEFINITIONS:
                print(key)
            return 0
        if args.command == "enemies":
            for key, definition in ENEMY_DEFINITIONS.items():
                print(f"{key}\t{definition[0]}")
            return 0
        if args.command == "world":
            world = generate_world(WorldConfig(args.width, args.height, args.chunk_size), args.seed)
            WorldStore.write(world, args.path)
            print(f"Stored {args.width}x{args.height} world at {args.path}")
            return 0
        if args.command == "inspect":
            state = load_game(args.save)
            print(
                json.dumps(
                    {
                        "name": state.player.name,
                        "class": state.player.class_id,
                        "level": state.player.level,
                        "turn": state.turn,
                        "seed": state.seed,
                    },
                    indent=2,
                )
            )
            return 0
        if args.command == "replay":
            state = load_game(args.save)
            replay_args = argparse.Namespace(
                enemy=args.enemy, level=state.player.level, save=None, world=None
            )
            return _play(replay_args, state)
        return _play(args)
    except (SimulationError, OSError, ValueError) as exc:
        print(f"error: {exc}")
        return 2
