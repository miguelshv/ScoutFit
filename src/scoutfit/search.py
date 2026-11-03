"""Search and selection state, independent of Streamlit for regression tests."""

import unicodedata
from collections.abc import MutableMapping, Sequence

import pandas as pd


def normalized_name(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(char)
    )


def search_players(profiles: pd.DataFrame, query: str) -> pd.DataFrame:
    tokens = normalized_name(query).split()
    if not tokens:
        return profiles
    names = profiles["player_name"].map(normalized_name)
    mask = names.map(lambda name: all(token in name for token in tokens))
    return profiles.loc[mask]


def keep_valid_selection(state: MutableMapping, key: str, options: Sequence):
    """Preserve the choice while valid; never hard-code a player on rerun."""
    if not len(options):
        raise ValueError("No hay opciones disponibles")
    if state.get(key) not in options:
        state[key] = options[0]
    return state[key]
