from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from dmc_ai_mobility.core.config import RobotConfig
from dmc_ai_mobility.core.timing import PeriodicSleeper, wall_clock_ms
from dmc_ai_mobility.zenoh import keys
from dmc_ai_mobility.zenoh.pubsub import publish_json
from dmc_ai_mobility.zenoh.session import ZenohOpenOptions, open_session

logger = logging.getLogger(__name__)


def run_health(config: RobotConfig, *, dry_run: bool) -> int:
    session = open_session(
        dry_run=dry_run,
        zenoh=ZenohOpenOptions(config_path=Path(config.zenoh.config_path) if config.zenoh.config_path else None),
    )

    stop_event = threading.Event()
    started = time.monotonic()
    sleeper = PeriodicSleeper(1.0)
    key = keys.health_state(config.robot_id)

    logger.info("health node started (robot_id=%s)", config.robot_id)
    try:
        while not stop_event.is_set():
            publish_json(
                session,
                key,
                {"uptime_s": time.monotonic() - started, "ts_ms": wall_clock_ms()},
            )
            sleeper.sleep()
    except KeyboardInterrupt:
        logger.info("shutdown requested")
    finally:
        stop_event.set()
        session.close()
    return 0
