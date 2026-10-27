"""端口自动避让：被占用时向后寻找可 bind 的端口。"""
from __future__ import annotations

import socket

from ports import can_bind, find_available_port, preferred_port


def test_preferred_port_env_and_fallback(monkeypatch):
    monkeypatch.setenv("ANY2MD_PORT", "8123")
    assert preferred_port() == 8123
    monkeypatch.setenv("ANY2MD_PORT", "not-a-port")
    assert preferred_port() == 8000
    monkeypatch.setenv("ANY2MD_PORT", "0")
    assert preferred_port() == 8000


def test_find_available_port_skips_occupied():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen(1)
        busy = int(occupied.getsockname()[1])
        found = find_available_port(start=busy, limit=8)
        assert found != busy
        assert can_bind("127.0.0.1", found)


def test_find_available_port_prefers_first_bindable(monkeypatch):
    monkeypatch.setattr(
        "ports.can_bind",
        lambda host, port: port == 8123,
    )
    assert find_available_port(start=8120, limit=10) == 8123
