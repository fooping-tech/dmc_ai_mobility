from __future__ import annotations

from typing import Any, Callable, Dict

from dmc_ai_mobility.zenoh.schemas import decode_json, encode_json
from dmc_ai_mobility.zenoh.session import Session, Subscription


def publish_json(session: Session, key: str, data: Dict[str, Any]) -> None:
    session.publish(key, encode_json(data))


def subscribe_json(session: Session, key: str, callback: Callable[[Dict[str, Any]], None]) -> Subscription:
    def _wrapped(payload: bytes) -> None:
        callback(decode_json(payload))

    return session.subscribe(key, _wrapped)
