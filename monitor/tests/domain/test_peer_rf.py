"""Peer RF mode and voice slot parity with adn-server downlink."""

from __future__ import annotations

from adn_monitor.domain.peer_rf import (
    RF_MODE_SIMPLEX,
    normalize_ua_voice_slot,
    peer_downlink_display_slot,
    peer_is_simplex,
    peer_rf_mode,
)


def test_peer_rf_mode_from_report_field():
    assert peer_rf_mode({"rf_mode": "simplex"}) == RF_MODE_SIMPLEX


def test_peer_rf_mode_derives_from_matching_freqs():
    peer = {"RX_FREQ": b"145625000", "TX_FREQ": b"145625000", "SLOTS": b"0"}
    assert peer_is_simplex(peer)


def test_normalize_ua_voice_slot_simplex_uses_ts2():
    peer = {"RF_MODE": "simplex"}
    assert normalize_ua_voice_slot(peer, 1) == 2


def test_peer_downlink_display_slot_simplex_static_on_ts2():
    peer = {"RF_MODE": "simplex", "TS1_STATIC": ["730"], "TS2_STATIC": []}
    assert peer_downlink_display_slot(peer, 730, 1) == 2


def test_peer_downlink_display_slot_tg_on_both_static_slots_follows_event_slot():
    """Duplex-capable hotspot with the same TG on TS1+TS2: each downlink event
    (server now delivers both independently) must chip its own real slot, not
    collapse onto SIMPLEX_VOICE_SLOT -- else the TS2 delivery overwrites the
    TS1 chip and the UI only ever shows one slot active."""
    peer = {"RF_MODE": "duplex", "TS1_STATIC": ["730"], "TS2_STATIC": ["730"]}
    assert peer_downlink_display_slot(peer, 730, 1) == 1
    assert peer_downlink_display_slot(peer, 730, 2) == 2

    peer_simplex = {"RF_MODE": "simplex", "TS1_STATIC": ["730"], "TS2_STATIC": ["730"]}
    assert peer_downlink_display_slot(peer_simplex, 730, 1) == 1
    assert peer_downlink_display_slot(peer_simplex, 730, 2) == 2
