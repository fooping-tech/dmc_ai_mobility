from __future__ import annotations

import argparse
from pathlib import Path

from dmc_ai_mobility.core.config import load_config
from dmc_ai_mobility.core.logging import setup_logging
from dmc_ai_mobility.app.robot_node import run_robot
from dmc_ai_mobility.app.health_node import run_health


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dmc-ai-mobility")
    sub = parser.add_subparsers(dest="cmd", required=True)

    robot = sub.add_parser("robot", help="Run robot node (motor/imu/oled/camera)")
    robot.add_argument("--config", type=Path, default=Path("config.toml"))
    robot.add_argument("--robot-id", type=str, default=None)
    robot.add_argument("--dry-run", action="store_true", help="Run without Zenoh/hardware; logs I/O")
    robot.add_argument("--no-camera", action="store_true", help="Disable camera loop")
    robot.add_argument(
        "--log-all-cmd",
        action="store_true",
        help="Log every received motor/oled command (can be very noisy at high Hz).",
    )
    robot.add_argument("--log-level", type=str, default=None)

    health = sub.add_parser("health", help="Run health/heartbeat publisher")
    health.add_argument("--config", type=Path, default=Path("config.toml"))
    health.add_argument("--robot-id", type=str, default=None)
    health.add_argument("--dry-run", action="store_true")
    health.add_argument("--log-level", type=str, default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.log_level)

    if args.cmd == "robot":
        overrides = {}
        if args.robot_id:
            overrides["robot_id"] = args.robot_id
        config = load_config(args.config, overrides=overrides or None)
        return run_robot(
            config,
            dry_run=bool(args.dry_run),
            no_camera=bool(args.no_camera),
            log_all_cmd=bool(args.log_all_cmd),
        )

    if args.cmd == "health":
        overrides = {}
        if args.robot_id:
            overrides["robot_id"] = args.robot_id
        config = load_config(args.config, overrides=overrides or None)
        return run_health(config, dry_run=bool(args.dry_run))

    raise RuntimeError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
