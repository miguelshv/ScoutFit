import pandas as pd
import pytest

from scoutfit.search import keep_valid_selection, search_players


def test_search_is_accent_case_and_word_order_insensitive():
    players = pd.DataFrame({"player_name": ["Álex Baena", "Kylian Mbappé", "Pedri"]})
    assert search_players(players, "BAENA alex")["player_name"].tolist() == ["Álex Baena"]
    assert search_players(players, "mbappe")["player_name"].tolist() == ["Kylian Mbappé"]
    assert len(search_players(players, "  ")) == 3
    assert search_players(players, "nonexistent").empty
    assert search_players(
        players, ".*"
    ).empty  # Search tokens are literal, not regular expressions.


def test_selection_survives_option_reordering_and_only_resets_when_invalid():
    state = {"reference": "jude"}
    assert keep_valid_selection(state, "reference", ["pedri", "jude"]) == "jude"
    assert keep_valid_selection(state, "reference", ["jude", "pedri"]) == "jude"
    assert keep_valid_selection(state, "reference", ["lamine", "pedri"]) == "lamine"
    with pytest.raises(ValueError, match="No hay opciones"):
        keep_valid_selection(state, "reference", [])
