"""Peer RF mode and voice slot parity with adn-server downlink."""

from __future__ import annotations

from adn_monitor.domain.peer_rf import (
    RF_MODE_SIMPLEX,
    normalize_ua_voice_slot,
    peer_downlink_display_slot,
    peer_downlink_display_slots,
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


def test_peer_downlink_display_slots_static_on_one_dynamic_multi_on_other():
    """SINGLE=0 dynamic keying (UA_MULTI_TS2) on the slot opposite a static
    match: both slots must light up."""
    peer = {
        "RF_MODE": "duplex",
        "TS1_STATIC": ["730"],
        "TS2_STATIC": [],
        "UA_MULTI_TS2": [{"TGID": "730", "TO": ""}],
    }
    assert peer_downlink_display_slots(peer, 730, 2) == [1, 2]


def test_peer_downlink_display_slots_static_on_one_dynamic_single_on_other():
    """SINGLE=1 exclusive session (SINGLE_TS2) on the slot opposite a static
    match: both slots must light up."""
    peer = {
        "RF_MODE": "duplex",
        "TS1_STATIC": ["730"],
        "TS2_STATIC": [],
        "SINGLE_TS2": {"TGID": "730", "TO": ""},
    }
    assert peer_downlink_display_slots(peer, 730, 2) == [1, 2]


def test_peer_downlink_display_slots_static_on_one_no_dynamic_elsewhere():
    """Plain single-static case (no dynamic activity on the other slot) must
    stay single-slot -- this is the case a naive event_slot-mismatch heuristic
    would wrongly treat as dual-slot."""
    peer = {"RF_MODE": "duplex", "TS1_STATIC": ["730"], "TS2_STATIC": []}
    assert peer_downlink_display_slots(peer, 730, 2) == [1]


def test_peer_downlink_display_slots_dynamic_multi_on_both_no_static():
    """No static OPTIONS match at all -- TG independently keyed (SINGLE=0)
    dynamic on both slots -- must still light up both."""
    peer = {
        "RF_MODE": "duplex",
        "TS1_STATIC": [],
        "TS2_STATIC": [],
        "UA_MULTI_TS1": [{"TGID": "730", "TO": ""}],
        "UA_MULTI_TS2": [{"TGID": "730", "TO": ""}],
    }
    assert peer_downlink_display_slots(peer, 730, 2) == [1, 2]


def test_peer_downlink_display_slots_dynamic_multi_on_one_no_static():
    """Dynamic (SINGLE=0) on only one slot, no static anywhere -- must stay
    single-slot, following the event."""
    peer = {
        "RF_MODE": "duplex",
        "TS1_STATIC": [],
        "TS2_STATIC": [],
        "UA_MULTI_TS2": [{"TGID": "730", "TO": ""}],
    }
    assert peer_downlink_display_slots(peer, 730, 2) == [2]


def test_peer_downlink_display_slots_simplex_ignores_dynamic_other_slot():
    """Simplex hardware can't genuinely be on two slots at once -- the
    dynamic-other-slot check must not apply."""
    peer = {
        "RF_MODE": "simplex",
        "TS1_STATIC": ["730"],
        "TS2_STATIC": [],
        "UA_MULTI_TS2": [{"TGID": "730", "TO": ""}],
    }
    assert peer_downlink_display_slots(peer, 730, 1) == [2]
