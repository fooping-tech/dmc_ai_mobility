#!/usr/bin/env python3
"""Launch examples/remote_zenoh_ui.py headlessly and save a screenshot.

This is for CI/headless environments (e.g. Raspberry Pi without X11).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--robot-id", default="rasp-zero-01")
    p.add_argument("--out", default="remote_ui.png")
    p.add_argument("--zenoh-config", default="", help="Optional path to zenoh json5")
    p.add_argument(
        "--connect",
        action="append",
        default=[],
        help='Connect endpoint override (repeatable), e.g. --connect "tcp/192.168.1.10:7447"',
    )
    p.add_argument("--mode", default="peer")
    p.add_argument("--delay", type=float, default=2.0, help="Seconds to wait before taking screenshot")
    args = p.parse_args(argv)

    # Try to run without an X server.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    # Import the UI module from examples.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))
    import remote_zenoh_ui as ui  # type: ignore

    zenoh_cfg = Path(args.zenoh_config) if args.zenoh_config else None
    open_session = ui._build_session_opener(
        config_path=zenoh_cfg, mode=str(args.mode), connect_endpoints=list(args.connect)
    )

    app = QApplication(sys.argv[:1])
    bridge = ui._Bridge()
    client = ui.ZenohClient(open_session=open_session, robot_id=str(args.robot_id), bridge=bridge, print_publish=False)
    win = ui.MainWindow(client=client, bridge=bridge, args=argparse.Namespace(robot_id=args.robot_id, print_pub=False, print_pub_motor_all=False, print_motor_period=False), ui_config=ui._load_ui_config(Path("config.toml") if Path("config.toml").exists() else None))

    win.show()

    out_path = Path(args.out).resolve()

    def _shot() -> None:
        # Grab only the window contents.
        pm = win._win.grab()
        pm.save(str(out_path))
        app.quit()

    QTimer.singleShot(int(max(0.1, float(args.delay)) * 1000), _shot)
    rc = int(app.exec())
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
