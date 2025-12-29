from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Protocol

from dmc_ai_mobility.zenoh.schemas import decode_json, encode_json

logger = logging.getLogger(__name__)


class Subscription(Protocol):
    def close(self) -> None: ...


class Session(Protocol):
    def publish(self, key: str, payload: bytes) -> None: ...
    def subscribe(self, key: str, callback: Callable[[bytes], None]) -> Subscription: ...
    def close(self) -> None: ...


class _DryRunSubscription:
    def __init__(self, key: str, on_close: Callable[[], None]) -> None:
        self._key = key
        self._on_close = on_close

    def close(self) -> None:
        self._on_close()


class DryRunSession:
    def __init__(self) -> None:
        self._subs: Dict[str, list[Callable[[bytes], None]]] = {}
        logger.info("dry-run mode enabled (no Zenoh I/O)")

    def publish(self, key: str, payload: bytes) -> None:
        logger.info("dry-run publish %s (%d bytes)", key, len(payload))
        for callback in list(self._subs.get(key, [])):
            callback(payload)

    def publish_json(self, key: str, data: Dict[str, Any]) -> None:
        self.publish(key, encode_json(data))

    def subscribe(self, key: str, callback: Callable[[bytes], None]) -> Subscription:
        self._subs.setdefault(key, []).append(callback)
        logger.info("dry-run subscribed %s", key)

        def _remove() -> None:
            callbacks = self._subs.get(key, [])
            if callback in callbacks:
                callbacks.remove(callback)
            logger.info("dry-run unsubscribed %s", key)

        return _DryRunSubscription(key, _remove)

    def subscribe_json(self, key: str, callback: Callable[[Dict[str, Any]], None]) -> Subscription:
        def _wrapped(payload: bytes) -> None:
            callback(decode_json(payload))

        return self.subscribe(key, _wrapped)

    def close(self) -> None:
        self._subs.clear()
        logger.info("dry-run session closed")


@dataclass(frozen=True)
class ZenohOpenOptions:
    config_path: Optional[Path] = None


class ZenohSession:
    def __init__(self, session: Any) -> None:
        self._session = session

    def publish(self, key: str, payload: bytes) -> None:
        pub = self._session.declare_publisher(key)
        pub.put(payload)

    def subscribe(self, key: str, callback: Callable[[bytes], None]) -> Subscription:
        def _on_sample(sample: Any) -> None:
            payload = getattr(sample, "payload", None)
            if payload is None:
                return
            data = payload.to_bytes() if hasattr(payload, "to_bytes") else bytes(payload)
            callback(data)

        sub = self._session.declare_subscriber(key, _on_sample)

        class _ZenohSubscription:
            def close(self) -> None:
                sub.undeclare()

        return _ZenohSubscription()

    def close(self) -> None:
        self._session.close()


def open_session(*, dry_run: bool, zenoh: ZenohOpenOptions) -> Session:
    if dry_run:
        return DryRunSession()

    try:
        import zenoh  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "zenoh python package is required unless --dry-run is used"
        ) from e

    if zenoh.config_path:
        cfg = zenoh.Config.from_file(str(zenoh.config_path))
        sess = zenoh.open(cfg)
    else:
        sess = zenoh.open()
    return ZenohSession(sess)
