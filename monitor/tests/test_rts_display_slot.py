# ADN Monitor - tests rts display slot
#
# Copyright (C) 2026  Rodrigo Pérez, CE5RPY <ce5rpy@qmd.cl>
#
###############################################################################
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software Foundation,
#   Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301  USA
###############################################################################

"""CTABLE timeslot chips follow peer OPTIONS static TG, not wire slot alone."""

from __future__ import annotations

from unittest.mock import MagicMock

from adn_monitor.application.monitor_controller import MonitorState
from adn_monitor.application.rts_update import rts_update_impl
from adn_monitor.application.tgstats import (
    _active_tgid_from_peer_ts,
    prune_voice_ts_not_in_static,
)


def _state_with_peer(
    *,
    peer_id: int,
    ts1_static: list[str],
    ts2_static: list[str],
) -> MonitorState:
    state = MonitorState()
    state.CTABLE = {
        "MASTERS": {
            "SYSTEM": {
                "PEERS": {
                    peer_id: {
                        "TS1_STATIC": ts1_static,
                        "TS2_STATIC": ts2_static,
                        1: {"TS": False, "TRX": ""},
                        2: {"TS": False, "TRX": ""},
                    }
                }
            }
        },
        "PEERS": {},
        "OPENBRIDGES": {},
    }
    return state


def _alias() -> MagicMock:
    alias = MagicMock()
    alias.alias_short.return_value = "HS"
    alias.alias_call.return_value = "HS"
    alias.alias_tgid.return_value = "TG"
    return alias


def test_wire_ts2_colors_ts2_when_tg_in_ts2_static() -> None:
    state = _state_with_peer(peer_id=730001, ts1_static=[], ts2_static=["73010"])
    rts_update_impl(
        "GROUP VOICE,START,TX,SYSTEM,1,730002,730002,2,73010".split(","),
        state,
        _alias(),
        lambda: "12:00",
    )
    peer = state.CTABLE["MASTERS"]["SYSTEM"]["PEERS"][730001]
    assert peer[2]["TS"] is True
    assert peer[2]["TRX"] == "TX"
    assert peer[1]["TS"] is False


def test_wire_ts2_colors_ts1_when_tg_only_in_ts1_static() -> None:
    state = _state_with_peer(peer_id=730001, ts1_static=["73010"], ts2_static=[])
    rts_update_impl(
        "GROUP VOICE,START,TX,SYSTEM,1,730002,730002,2,73010".split(","),
        state,
        _alias(),
        lambda: "12:00",
    )
    peer = state.CTABLE["MASTERS"]["SYSTEM"]["PEERS"][730001]
    assert peer[1]["TS"] is True
    assert peer[1]["TRX"] == "TX"
    assert peer[2]["TS"] is False


def test_tg_on_both_static_slots_lights_up_both_chips() -> None:
    """Duplex hotspot with the TG on TS1+TS2: adn-server delivers to it on
    both slots independently (e.g. an OBP-sourced call, always reported on
    slot 1) -- both chips must light up, not just the event's own slot."""
    state = _state_with_peer(peer_id=730001, ts1_static=["730"], ts2_static=["730"])
    rts_update_impl(
        "GROUP VOICE,START,TX,SYSTEM,1,730002,730002,1,730".split(","),
        state,
        _alias(),
        lambda: "12:00",
    )
    peer = state.CTABLE["MASTERS"]["SYSTEM"]["PEERS"][730001]
    assert peer[1]["TS"] is True
    assert peer[1]["TRX"] == "TX"
    assert peer[2]["TS"] is True
    assert peer[2]["TRX"] == "TX"


def test_transmitter_rx_uses_wire_slot_not_options() -> None:
    state = _state_with_peer(peer_id=730002, ts1_static=[], ts2_static=["73010"])
    rts_update_impl(
        "GROUP VOICE,START,RX,SYSTEM,1,730002,730002,2,73010".split(","),
        state,
        _alias(),
        lambda: "12:00",
    )
    peer = state.CTABLE["MASTERS"]["SYSTEM"]["PEERS"][730002]
    assert peer[2]["TS"] is True
    assert peer[2]["TRX"] == "RX"


def test_start_stores_announcement_flag_from_trailing_field() -> None:
    state = _state_with_peer(peer_id=730002, ts1_static=[], ts2_static=["73010"])
    rts_update_impl(
        "GROUP VOICE,START,RX,SYSTEM,1,730002,730002,2,73010,1".split(","),
        state,
        _alias(),
        lambda: "12:00",
    )
    peer = state.CTABLE["MASTERS"]["SYSTEM"]["PEERS"][730002]
    assert peer[2]["ANNOUNCEMENT"] is True


def test_start_without_trailing_field_defaults_announcement_false() -> None:
    state = _state_with_peer(peer_id=730002, ts1_static=[], ts2_static=["73010"])
    rts_update_impl(
        "GROUP VOICE,START,RX,SYSTEM,1,730002,730002,2,73010".split(","),
        state,
        _alias(),
        lambda: "12:00",
    )
    peer = state.CTABLE["MASTERS"]["SYSTEM"]["PEERS"][730002]
    assert peer[2]["ANNOUNCEMENT"] is False


def _state_with_two_peers(*, source_peer: int, dest_peer: int) -> MonitorState:
    """Two hotspots on the same MASTER -- private call from source_peer to dest_peer."""
    state = MonitorState()
    state.CTABLE = {
        "MASTERS": {
            "SYSTEM": {
                "PEERS": {
                    source_peer: {
                        "TS1_STATIC": [], "TS2_STATIC": [],
                        1: {"TS": False, "TRX": ""}, 2: {"TS": False, "TRX": ""},
                    },
                    dest_peer: {
                        "TS1_STATIC": [], "TS2_STATIC": [],
                        1: {"TS": False, "TRX": ""}, 2: {"TS": False, "TRX": ""},
                    },
                }
            }
        },
        "PEERS": {},
        "OPENBRIDGES": {},
    }
    return state


def test_private_voice_rx_start_marks_transmitting_peer() -> None:
    state = _state_with_two_peers(source_peer=730039110, dest_peer=730039101)
    rts_update_impl(
        "PRIVATE VOICE,START,RX,SYSTEM,1,730039110,7300391,2,7300392".split(","),
        state,
        _alias(),
        lambda: "12:00",
    )
    peer = state.CTABLE["MASTERS"]["SYSTEM"]["PEERS"][730039110]
    assert peer[2]["TS"] is True
    assert peer[2]["TRX"] == "RX"


def test_private_voice_start_tx_with_dest_peer_id_marks_receiving_peer() -> None:
    """Regression: monitor never showed who a private call was delivered to -- the TX
    event now carries the destination hotspot's own peer id (from SUB_MAP), letting it
    be matched directly instead of by static TG list (private destinations aren't TGs)."""
    state = _state_with_two_peers(source_peer=730039110, dest_peer=730039101)
    rts_update_impl(
        "PRIVATE VOICE,START,TX,SYSTEM,1,730039110,7300391,2,7300392,730039101".split(","),
        state,
        _alias(),
        lambda: "12:00",
    )
    dest = state.CTABLE["MASTERS"]["SYSTEM"]["PEERS"][730039101]
    assert dest[2]["TS"] is True
    assert dest[2]["TRX"] == "TX"
    source = state.CTABLE["MASTERS"]["SYSTEM"]["PEERS"][730039110]
    assert source[2]["TS"] is False


def test_private_voice_start_tx_without_dest_peer_id_touches_nothing() -> None:
    """Backward compat: an old-format event (no trailing peer id) must not crash and
    must not fall back to matching by static TG list (meaningless for a subscriber id)."""
    state = _state_with_two_peers(source_peer=730039110, dest_peer=730039101)
    rts_update_impl(
        "PRIVATE VOICE,START,TX,SYSTEM,1,730039110,7300391,2,7300392".split(","),
        state,
        _alias(),
        lambda: "12:00",
    )
    for peer in state.CTABLE["MASTERS"]["SYSTEM"]["PEERS"].values():
        assert peer[2]["TS"] is False


def test_private_voice_end_tx_with_dest_peer_id_clears_receiving_peer() -> None:
    state = _state_with_two_peers(source_peer=730039110, dest_peer=730039101)
    rts_update_impl(
        "PRIVATE VOICE,START,TX,SYSTEM,1,730039110,7300391,2,7300392,730039101".split(","),
        state,
        _alias(),
        lambda: "12:00",
    )
    dest = state.CTABLE["MASTERS"]["SYSTEM"]["PEERS"][730039101]
    assert dest[2]["TS"] is True
    rts_update_impl(
        "PRIVATE VOICE,END,TX,SYSTEM,1,730039110,7300391,2,7300392,1.23,730039101".split(","),
        state,
        _alias(),
        lambda: "12:00",
    )
    assert dest[2]["TS"] is False


def test_active_tgid_prefers_parenthesized_id_over_first_digit_run() -> None:
    assert _active_tgid_from_peer_ts({"TS": True, "TG": "CE5RPY, Rodrigo (7300391)"}) == 7300391


def test_active_tgid_falls_back_to_first_digit_run_without_parens() -> None:
    """Group-call format ("TG 7300391    Name") has no parens -- unaffected."""
    assert _active_tgid_from_peer_ts({"TS": True, "TG": "TG&nbsp;7300391&nbsp;&nbsp;&nbsp;&nbsp;Some TG"}) == 7300391


def test_private_voice_end_clears_when_dest_callsign_contains_a_digit() -> None:
    """Regression: a real ham callsign like "CE5RPY" contains a digit of its own.
    _active_tgid_from_peer_ts must extract the id from "(...)", not just the first
    digit run in the field -- otherwise a resolved callsign's embedded digit would
    be matched instead of the real id, and the chip would never clear."""
    alias = MagicMock()
    alias.alias_short.side_effect = lambda dmr_id: "CE5RPY, Rodrigo" if dmr_id == 7300391 else str(dmr_id)
    alias.alias_call.return_value = "CE5RPY"
    state = _state_with_two_peers(source_peer=730039101, dest_peer=730039110)
    rts_update_impl(
        "PRIVATE VOICE,START,TX,SYSTEM,1,730039101,7300392,2,7300391,730039110".split(","),
        state,
        alias,
        lambda: "12:00",
    )
    dest = state.CTABLE["MASTERS"]["SYSTEM"]["PEERS"][730039110]
    assert dest[2]["TS"] is True
    assert dest[2]["TG"] == "CE5RPY, Rodrigo (7300391)"
    rts_update_impl(
        "PRIVATE VOICE,END,TX,SYSTEM,1,730039101,7300392,2,7300391,1.23,730039110".split(","),
        state,
        alias,
        lambda: "12:00",
    )
    assert dest[2]["TS"] is False


def test_end_clears_cross_slot_when_static_tg_removed() -> None:
    """END must clear the slot lit at START even if OPTIONS no longer map the TG there."""
    state = _state_with_peer(peer_id=730001, ts1_static=["52090"], ts2_static=[])
    rts_update_impl(
        "GROUP VOICE,START,TX,SYSTEM,1,730002,5200386,2,52090".split(","),
        state,
        _alias(),
        lambda: "12:00",
    )
    peer = state.CTABLE["MASTERS"]["SYSTEM"]["PEERS"][730001]
    assert peer[1]["TS"] is True
    peer["TS1_STATIC"] = []
    peer["TS2_STATIC"] = []
    rts_update_impl(
        "GROUP VOICE,END,TX,SYSTEM,99,730002,5200386,2,52090".split(","),
        state,
        _alias(),
        lambda: "12:00",
    )
    assert peer[1]["TS"] is False
    assert peer[2]["TS"] is False


def test_build_tgstats_clears_active_static_tg_removed_from_options() -> None:
    state = _state_with_peer(peer_id=5200386, ts1_static=["52090"], ts2_static=[])
    peer = state.CTABLE["MASTERS"]["SYSTEM"]["PEERS"][5200386]
    peer[1]["TS"] = True
    peer[1]["TRX"] = "TX"
    peer[1]["TG"] = "TG&nbsp;52090"
    peer[1]["DEST"] = "TG 52090"
    peer["TS1_STATIC"] = []
    peer["TS2_STATIC"] = []
    prune_voice_ts_not_in_static(state, "SYSTEM", 5200386, peer)
    assert peer[1]["TS"] is False
    assert peer[1]["TRX"] == ""


def test_prune_preserves_echo_9990_live_trx_chip() -> None:
    """Echo TG is not UA dynamic; live RX/TX chips must not be cleared on build_tgstats."""
    state = _state_with_peer(peer_id=730039101, ts1_static=[], ts2_static=[])
    peer = state.CTABLE["MASTERS"]["SYSTEM"]["PEERS"][730039101]
    peer[2]["TS"] = True
    peer[2]["TRX"] = "RX"
    peer[2]["TG"] = "TG&nbsp;9990"
    peer[2]["DEST"] = "TG 9990"
    prune_voice_ts_not_in_static(state, "SYSTEM", 730039101, peer)
    assert peer[2]["TS"] is True
    assert peer[2]["TRX"] == "RX"


def test_prune_preserves_private_voice_chip_with_no_static_tg_match() -> None:
    """Regression: build_tgstats fires after every voice event, including PRIVATE VOICE
    START -- a private call's destination is a subscriber id and will never be in any
    peer's static TG list, so the un-exempted prune wiped the chip almost immediately."""
    state = _state_with_peer(peer_id=730039110, ts1_static=[], ts2_static=["7304"])
    peer = state.CTABLE["MASTERS"]["SYSTEM"]["PEERS"][730039110]
    peer[2]["TS"] = True
    peer[2]["TYPE"] = "PRIVATE VOICE"
    peer[2]["TRX"] = "RX"
    peer[2]["TG"] = "TG&nbsp;7300392"
    peer[2]["DEST"] = "TG 7300392"
    prune_voice_ts_not_in_static(state, "SYSTEM", 730039110, peer)
    assert peer[2]["TS"] is True
    assert peer[2]["TRX"] == "RX"


def test_rts_update_then_prune_keeps_private_voice_tx_chip_visible() -> None:
    """End-to-end: START,TX event followed by the build_tgstats prune it always
    triggers must not erase the just-set receiving chip."""
    state = _state_with_two_peers(source_peer=730039110, dest_peer=730039101)
    rts_update_impl(
        "PRIVATE VOICE,START,TX,SYSTEM,1,730039110,7300391,2,7300392,730039101".split(","),
        state,
        _alias(),
        lambda: "12:00",
    )
    dest = state.CTABLE["MASTERS"]["SYSTEM"]["PEERS"][730039101]
    prune_voice_ts_not_in_static(state, "SYSTEM", 730039101, dest)
    assert dest[2]["TS"] is True
    assert dest[2]["TRX"] == "TX"


def test_echo_9990_rx_tx_live_chips() -> None:
    state = _state_with_peer(peer_id=730039101, ts1_static=[], ts2_static=[])
    alias = _alias()
    rts_update_impl(
        "GROUP VOICE,START,RX,SYSTEM,1,730039101,730039101,2,9990".split(","),
        state,
        alias,
        lambda: "12:00",
    )
    peer = state.CTABLE["MASTERS"]["SYSTEM"]["PEERS"][730039101]
    assert peer[2]["TS"] is True
    assert peer[2]["TRX"] == "RX"
    rts_update_impl(
        "GROUP VOICE,START,TX,SYSTEM,2,9990,730039101,2,9990".split(","),
        state,
        alias,
        lambda: "12:00",
    )
    assert peer[2]["TS"] is True
    assert peer[2]["TRX"] == "TX"


def _state_with_echo_peer(
    *,
    echo_peer_id: int = 9990,
    ts2_static: list[str] | None = None,
) -> MonitorState:
    state = MonitorState()
    state.CTABLE = {
        "MASTERS": {
            "ECHO": {
                "PEERS": {
                    echo_peer_id: {
                        "TS1_STATIC": [],
                        "TS2_STATIC": ts2_static if ts2_static is not None else ["9990"],
                        1: {"TS": False, "TRX": ""},
                        2: {"TS": False, "TRX": ""},
                    }
                }
            }
        },
        "PEERS": {},
        "OPENBRIDGES": {},
    }
    return state


def test_echo_master_tx_downlink_shows_receiving_chip() -> None:
    """Bridge TX leg to ECHO (recording): service peer shows green/TX on wire slot."""
    state = _state_with_echo_peer()
    alias = _alias()
    rts_update_impl(
        "GROUP VOICE,START,TX,ECHO,1,730039101,730039101,2,9990".split(","),
        state,
        alias,
        lambda: "12:00",
    )
    peer = state.CTABLE["MASTERS"]["ECHO"]["PEERS"][9990]
    assert peer[2]["TS"] is True
    assert peer[2]["TRX"] == "TX"


def test_echo_master_rx_playback_shows_transmitting_chip() -> None:
    """Echo PEER playback on ECHO master: service peer shows red/RX on wire slot."""
    state = _state_with_echo_peer()
    alias = _alias()
    rts_update_impl(
        "GROUP VOICE,START,RX,ECHO,2,9990,730039101,2,9990".split(","),
        state,
        alias,
        lambda: "12:00",
    )
    peer = state.CTABLE["MASTERS"]["ECHO"]["PEERS"][9990]
    assert peer[2]["TS"] is True
    assert peer[2]["TRX"] == "RX"


def test_echo_tx_downlink_uses_wire_slot_not_static_map() -> None:
    """9990 only in TS2_STATIC must not move a TS1 bridge TX chip to slot 2."""
    state = _state_with_echo_peer(ts2_static=["9990"])
    alias = _alias()
    rts_update_impl(
        "GROUP VOICE,START,TX,ECHO,1,730039101,730039101,1,9990".split(","),
        state,
        alias,
        lambda: "12:00",
    )
    peer = state.CTABLE["MASTERS"]["ECHO"]["PEERS"][9990]
    assert peer[1]["TS"] is True
    assert peer[1]["TRX"] == "TX"
    assert peer[2]["TS"] is False


def test_rx_start_only_updates_transmitting_peer_on_aggregate_master() -> None:
    """RX must not mark every peer with the same static TG as TX (green)."""
    state = MonitorState()
    state.CTABLE = {
        "MASTERS": {
            "SYSTEM": {
                "PEERS": {
                    730001: {
                        "TS1_STATIC": [],
                        "TS2_STATIC": ["7144"],
                        1: {"TS": False, "TRX": ""},
                        2: {"TS": False, "TRX": ""},
                    },
                    730002: {
                        "TS1_STATIC": [],
                        "TS2_STATIC": ["7144"],
                        1: {"TS": False, "TRX": ""},
                        2: {"TS": False, "TRX": ""},
                    },
                }
            }
        },
        "PEERS": {},
        "OPENBRIDGES": {},
    }
    alias = _alias()
    rts_update_impl(
        "GROUP VOICE,START,RX,SYSTEM,1,730002,730002,2,7144".split(","),
        state,
        alias,
        lambda: "12:00",
    )
    assert state.CTABLE["MASTERS"]["SYSTEM"]["PEERS"][730002][2]["TS"] is True
    assert state.CTABLE["MASTERS"]["SYSTEM"]["PEERS"][730002][2]["TRX"] == "RX"
    assert state.CTABLE["MASTERS"]["SYSTEM"]["PEERS"][730001][2]["TS"] is False


def test_tx_downlink_blocked_when_peer_slot_busy_other_tg() -> None:
    """While QSO on TG 7141, downlink START for TG 71442 must not light the chip."""
    state = MonitorState()
    state.CTABLE = {
        "MASTERS": {
            "SYSTEM-2": {
                "PEERS": {
                    714002301: {
                        "TS1_STATIC": [],
                        "TS2_STATIC": ["7141", "71442"],
                        1: {"TS": False, "TRX": ""},
                        2: {"TS": False, "TRX": ""},
                    }
                }
            }
        },
        "PEERS": {},
        "OPENBRIDGES": {},
    }
    alias = _alias()
    rts_update_impl(
        "GROUP VOICE,START,RX,SYSTEM-2,1,714002301,714002301,2,7141".split(","),
        state,
        alias,
        lambda: "12:00",
    )
    rts_update_impl(
        "GROUP VOICE,START,TX,SYSTEM-2,2,730002,730002,2,71442".split(","),
        state,
        alias,
        lambda: "12:01",
    )
    peer = state.CTABLE["MASTERS"]["SYSTEM-2"]["PEERS"][714002301]
    assert peer[2]["TRX"] == "RX"
    assert "7141" in peer[2]["TG"]


def test_end_tx_blocked_when_peer_slot_busy_other_tg() -> None:
    """While QSO on TG 7141, foreign END/TX for TG 71442 must not touch the chip."""
    state = MonitorState()
    state.CTABLE = {
        "MASTERS": {
            "SYSTEM-2": {
                "PEERS": {
                    714002301: {
                        "TS1_STATIC": [],
                        "TS2_STATIC": ["7141", "71442"],
                        1: {"TS": False, "TRX": ""},
                        2: {"TS": False, "TRX": ""},
                    }
                }
            }
        },
        "PEERS": {},
        "OPENBRIDGES": {},
    }
    alias = _alias()
    rts_update_impl(
        "GROUP VOICE,START,RX,SYSTEM-2,1,714002301,714002301,2,7141".split(","),
        state,
        alias,
        lambda: "12:00",
    )
    peer = state.CTABLE["MASTERS"]["SYSTEM-2"]["PEERS"][714002301]
    assert peer[2]["TRX"] == "RX"
    assert "7141" in peer[2]["TG"]
    rts_update_impl(
        "GROUP VOICE,END,TX,SYSTEM,99,73010,7000002,2,71442,4.00".split(","),
        state,
        alias,
        lambda: "12:01",
    )
    assert peer[2]["TRX"] == "RX"
    assert peer[2]["TS"] is True
    assert "7141" in peer[2]["TG"]


def test_companion_tx_does_not_replace_own_active_qso_on_other_tg() -> None:
    """While TX on TG 7144 (RX chip), companion TX for another TG must not overwrite the slot."""
    state = MonitorState()
    state.CTABLE = {
        "MASTERS": {
            "SYSTEM-0": {
                "PEERS": {
                    730001: {
                        "TS1_STATIC": [],
                        "TS2_STATIC": ["7144", "730444"],
                        1: {"TS": False, "TRX": ""},
                        2: {"TS": False, "TRX": ""},
                    }
                }
            }
        },
        "PEERS": {},
        "OPENBRIDGES": {},
    }
    alias = _alias()
    rts_update_impl(
        "GROUP VOICE,START,RX,SYSTEM-0,1,730001,730001,2,7144".split(","),
        state,
        alias,
        lambda: "12:00",
    )
    rts_update_impl(
        "GROUP VOICE,START,TX,SYSTEM-0,2,730002,730002,2,730444".split(","),
        state,
        alias,
        lambda: "12:01",
    )
    peer = state.CTABLE["MASTERS"]["SYSTEM-0"]["PEERS"][730001]
    assert peer[2]["TS"] is True
    assert peer[2]["TRX"] == "RX"
    assert "7144" in peer[2]["TG"]


def test_companion_tx_same_static_tg_does_not_flip_local_tx_to_green() -> None:
    """Another user keying the same static TG must not turn local TX (red) into RX (green)."""
    state = MonitorState()
    state.CTABLE = {
        "MASTERS": {
            "SYSTEM-0": {
                "PEERS": {
                    730001: {
                        "TS1_STATIC": [],
                        "TS2_STATIC": ["7144", "730444"],
                        1: {"TS": False, "TRX": ""},
                        2: {"TS": False, "TRX": ""},
                    }
                }
            }
        },
        "PEERS": {},
        "OPENBRIDGES": {},
    }
    alias = _alias()
    rts_update_impl(
        "GROUP VOICE,START,RX,SYSTEM-0,1,730001,730001,2,7144".split(","),
        state,
        alias,
        lambda: "12:00",
    )
    rts_update_impl(
        "GROUP VOICE,START,TX,SYSTEM-0,2,730002,730002,2,7144".split(","),
        state,
        alias,
        lambda: "12:01",
    )
    peer = state.CTABLE["MASTERS"]["SYSTEM-0"]["PEERS"][730001]
    assert peer[2]["TRX"] == "RX"
    assert "7144" in peer[2]["TG"]
    assert peer[2]["SUB"].startswith("HS")


def test_simplex_single_mode_ua_chip_on_ts2() -> None:
    """Simplex hotspot: dynamic UA tracked on SINGLE_TS2 even when wire slot is 1."""
    state = MonitorState()
    peer_id = 730001
    state.CONFIG = {
        "SYSTEM": {
            "ENABLED": True,
            "MODE": "MASTER",
            "PEERS": {
                peer_id.to_bytes(4, "big"): {
                    "CONNECTION": "YES",
                    "CONNECTED": 0,
                    "SINGLE_MODE": True,
                    "RF_MODE": "simplex",
                    "OPTIONS": b"SINGLE=1;TIMER=10;TS2=730;",
                }
            },
        }
    }
    state.CTABLE = {
        "MASTERS": {
            "SYSTEM": {
                "PEERS": {
                    peer_id: {
                        "RF_MODE": "simplex",
                        "TS1_STATIC": [],
                        "TS2_STATIC": ["730"],
                        "SINGLE_MODE": True,
                        1: {"TS": False, "TRX": ""},
                        2: {"TS": False, "TRX": ""},
                        "SINGLE_TS1": {"TGID": "", "TO": ""},
                        "SINGLE_TS2": {"TGID": "", "TO": ""},
                    }
                }
            }
        },
        "PEERS": {},
        "OPENBRIDGES": {},
    }
    rts_update_impl(
        "GROUP VOICE,START,RX,SYSTEM,1,730001,730001,1,730444".split(","),
        state,
        _alias(),
        lambda: "12:00",
    )
    peer = state.CTABLE["MASTERS"]["SYSTEM"]["PEERS"][peer_id]
    assert peer["SINGLE_TS2"]["TGID"] == 730444
    assert peer["SINGLE_TS1"]["TGID"] == ""
