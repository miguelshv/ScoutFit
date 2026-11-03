"""Candidate constraints never change the population used to fit/compute statistics."""

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CandidateFilters:
    include_teams: tuple[int, ...] = ()
    exclude_teams: tuple[int, ...] = ()
    min_minutes: float = 0
    max_minutes: float = 5000

    def __post_init__(self):
        if (
            not np.isfinite([self.min_minutes, self.max_minutes]).all()
            or self.min_minutes < 0
            or self.max_minutes < self.min_minutes
        ):
            raise ValueError("El intervalo de minutos de candidatos no es válido")

    def to_dict(self):
        return asdict(self)


def filter_candidates(frame: pd.DataFrame, filters: CandidateFilters | None):
    if filters is None:
        return frame
    mask = frame["minutes"].between(filters.min_minutes, filters.max_minutes)
    if filters.include_teams:
        mask &= frame["team_id"].isin(filters.include_teams)
    if filters.exclude_teams:
        mask &= ~frame["team_id"].isin(filters.exclude_teams)
    return frame.loc[mask]
