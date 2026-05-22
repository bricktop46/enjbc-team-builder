"""Utility functions for the Eltham North Jets Team Builder."""

import json
import os
from datetime import date, datetime

import pandas as pd

from config import (
    AGE_GROUPS,
    AGE_GROUPS_BOYS,
    AGE_GROUPS_GIRLS,
    COL_DOB,
    COL_GENDER,
    COL_PROFILE_ID,
    GENDER_PREFIX,
    SAVE_FILE,
    SEASON_CUTOFFS,
)


def calculate_age(dob: date, cutoff_date: date) -> int:
    """Calculate age as of a cutoff date."""
    years = cutoff_date.year - dob.year
    if (cutoff_date.month, cutoff_date.day) < (dob.month, dob.day):
        years -= 1
    return years


def determine_age_group(age: int, gender: str = "Male") -> str:
    """Determine age group based on age and gender.
    Boys max out at U18, Girls max out at U19.
    """
    if age < 8:
        return "U08"
    elif age < 10:
        return "U10"
    elif age < 12:
        return "U12"
    elif age < 14:
        return "U14"
    elif age < 16:
        return "U16"
    elif gender == "Male":
        if age < 18:
            return "U18"
        else:
            return "Over 18"
    else:  # Female
        if age < 19:
            return "U19"
        else:
            return "Over 19"


def get_cutoff_date(season: str, year: int) -> date:
    """Get the cutoff date for a given season and year."""
    month, day = SEASON_CUTOFFS[season]
    return date(year, month, day)


def load_participants(file) -> pd.DataFrame:
    """Load participants from an uploaded CSV or Excel file."""
    if hasattr(file, "name") and file.name.endswith(".xlsx"):
        df = pd.read_excel(file)
    else:
        df = pd.read_csv(file)

    # Parse date of birth
    if COL_DOB in df.columns:
        df[COL_DOB] = pd.to_datetime(df[COL_DOB], dayfirst=True, errors="coerce")

    return df


def enrich_participants(df: pd.DataFrame, season: str, year: int) -> pd.DataFrame:
    """Add calculated columns: age, age_group, team_name_prefix, seasons_remaining."""
    cutoff = get_cutoff_date(season, year)

    df = df.copy()
    df["Calculated Age"] = df[COL_DOB].apply(
        lambda dob: calculate_age(dob.date(), cutoff) if pd.notna(dob) else None
    )
    df["Calculated Age Group"] = df.apply(
        lambda row: determine_age_group(row["Calculated Age"], row[COL_GENDER])
        if pd.notna(row["Calculated Age"]) else "Unknown",
        axis=1,
    )

    # Gender prefix for team naming
    df["Gender Prefix"] = df[COL_GENDER].map(GENDER_PREFIX).fillna("X")

    # Seasons remaining in current age group
    df["Seasons Remaining"] = df.apply(
        lambda row: calculate_seasons_remaining(row[COL_DOB], row["Calculated Age Group"], season, year)
        if pd.notna(row[COL_DOB]) and row["Calculated Age Group"] != "Unknown" else None,
        axis=1,
    )

    return df


def calculate_seasons_remaining(dob, current_age_group: str, current_season: str, current_year: int) -> int:
    """Calculate how many seasons a player has left in their current age group.
    Two seasons per year: Autumn (cutoff 30 June), Spring (cutoff 31 Dec).
    """
    if isinstance(dob, pd.Timestamp):
        dob = dob.date()

    # Get the upper age limit for this group
    age_limits = {"U08": 8, "U10": 10, "U12": 12, "U14": 14, "U16": 16, "U18": 18, "U19": 19, "Over 18": 99, "Over 19": 99}
    max_age = age_limits.get(current_age_group, 99)
    if max_age == 99:
        return 99  # No limit for Over 18

    # Count future seasons (including current) where player is still under the limit
    seasons_left = 0
    check_season = current_season
    check_year = current_year

    for _ in range(20):  # Max 20 seasons lookahead (10 years)
        cutoff = get_cutoff_date(check_season, check_year)
        age_at_cutoff = calculate_age(dob, cutoff)
        if age_at_cutoff < max_age:
            seasons_left += 1
        else:
            break
        # Move to next season
        if check_season == "Autumn":
            check_season = "Spring"
        else:
            check_season = "Autumn"
            check_year += 1

    return seasons_left


def generate_team_name(gender: str, age_group: str, team_number: int) -> str:
    """Generate team name like B12.1, G10.2."""
    prefix = GENDER_PREFIX.get(gender, "X")
    age_num = age_group.replace("U", "").replace("Over 18", "18+")
    return f"{prefix}{age_num}.{team_number}"


def get_players_by_group(df: pd.DataFrame, gender: str, age_group: str) -> pd.DataFrame:
    """Filter players by gender and age group."""
    mask = (df[COL_GENDER] == gender) & (df["Calculated Age Group"] == age_group)
    return df[mask].copy()


def save_state(state: dict, filepath: str = SAVE_FILE):
    """Save application state to JSON."""

    def convert(obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    with open(filepath, "w") as f:
        json.dump(state, f, default=convert, indent=2)


def load_state(filepath: str = SAVE_FILE) -> dict:
    """Load application state from JSON."""
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return {}


def detect_coach_clashes(team_details: dict) -> list:
    """Find coaches assigned to multiple teams."""
    coach_teams = {}
    for team_id, details in team_details.items():
        coach = details.get("coach_name", "").strip()
        if coach and coach.lower() not in ("", "vacant", "tbc"):
            coach_teams.setdefault(coach, []).append(team_id)

    return [(coach, teams) for coach, teams in coach_teams.items() if len(teams) > 1]


def load_previous_teams(competitions_file) -> dict:
    """Load previous team assignments from the Competitions file.
    Looks for 'Previous Team 2025 Spring' column in boys/girls sheets.
    Returns a dict of {profile_id: previous_team_name}.
    """
    previous_teams = {}
    try:
        xl = pd.ExcelFile(competitions_file)
        for sheet in xl.sheet_names:
            if "Boys" in sheet or "Girls" in sheet:
                df = xl.parse(sheet)
                if COL_PROFILE_ID not in df.columns:
                    continue
                # Find the previous team column
                prev_cols = [c for c in df.columns if "Previous" in str(c)]
                if not prev_cols:
                    continue
                prev_col = prev_cols[0]
                for _, row in df.iterrows():
                    pid = str(row[COL_PROFILE_ID])
                    val = row.get(prev_col, "")
                    if pd.notna(val) and str(val).strip():
                        previous_teams[pid] = str(val).strip()
    except Exception:
        pass
    return previous_teams
