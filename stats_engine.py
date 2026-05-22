"""Player ranking and statistics engine for ENJBC Team Builder.

Builds an ELO-style rating system based on historical grade statistics.
Accounts for:
- Grade difficulty (A grade scoring worth more than D grade)
- Points per game weighted by grade
- Multi-season trends
- Players playing in multiple teams
- Grading vs regular season performance
"""

import pandas as pd
import numpy as np
import glob
import os
import re
from config import COL_PROFILE_ID


# --- Grade Difficulty Multipliers ---
# Higher grade = much harder to score, exponential gap between tiers
# A grade is elite — scoring there is worth significantly more
GRADE_MULTIPLIERS = {
    "A": 2.00,
    "B": 1.50,
    "B1": 1.50,
    "B2": 1.30,
    "B3": 1.15,
    "B4": 1.05,
    "C": 0.80,
    "C1": 0.80,
    "C2": 0.65,
    "C3": 0.55,
    "D": 0.45,
    "D1": 0.45,
    "D2": 0.35,
    "D3": 0.30,
}

# Season ordering for trend analysis
SEASON_ORDER = {
    "Spring 2024": 1,
    "Autumn 2025": 2,
    "Spring 2025": 3,
    "Autumn 2026": 4,
}

# Base ELO rating
BASE_ELO = 1000
K_FACTOR = 50  # How much a season can shift the ELO


def extract_grade_letter(grade_str: str) -> str:
    """Extract the grade letter/number from a full grade string.
    e.g., 'Saturday U10 Boys B3' -> 'B3'
    """
    if "Grading" in str(grade_str):
        return None  # Skip grading rounds for grade extraction

    # Match the grade suffix (A, B1, B2, C1, D2, etc.)
    match = re.search(r'([A-D]\d?)\s*$', str(grade_str))
    if match:
        return match.group(1)
    return None


def get_grade_multiplier(grade_str: str) -> float:
    """Get the difficulty multiplier for a grade."""
    grade_letter = extract_grade_letter(grade_str)
    if grade_letter and grade_letter in GRADE_MULTIPLIERS:
        return GRADE_MULTIPLIERS[grade_letter]
    return 1.0  # Default for grading rounds


def is_grading_round(grade_str: str) -> bool:
    """Check if a row is from a grading round."""
    return "Grading" in str(grade_str)


def load_all_stats(file_paths: list = None) -> pd.DataFrame:
    """Load and combine all stats CSV files."""
    if file_paths is None:
        file_paths = glob.glob(os.path.join(os.path.dirname(__file__), 'grade_statistics*.csv'))

    dfs = []
    for f in file_paths:
        df = pd.read_csv(f)
        dfs.append(df)

    combined = pd.concat(dfs, ignore_index=True)
    return combined


def calculate_player_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate comprehensive stats per player per season.

    Returns a DataFrame with one row per player-season including:
    - Total/grading/regular season points & games
    - Points per game (overall, grading, regular)
    - Weighted points per game (adjusted for grade difficulty)
    - Team rank (where they sit in their team's scoring)
    """
    results = []

    for (pid, season), group in df.groupby(["Profile ID", "Season"]):
        player_name = f"{group['First Name'].iloc[0]} {group['Last Name'].iloc[0]}"
        teams = group["Team"].unique().tolist()

        # Split grading vs regular season
        grading = group[group["Grade"].apply(is_grading_round)]
        regular = group[~group["Grade"].apply(is_grading_round)]

        # Combined stats
        total_games = group["Games Played"].sum()
        total_points = group["Total Points"].sum()
        total_fouls = group["Total Fouls"].sum()

        # Grading stats
        grading_games = grading["Games Played"].sum()
        grading_points = grading["Total Points"].sum()

        # Regular season stats
        regular_games = regular["Games Played"].sum()
        regular_points = regular["Total Points"].sum()

        # Points per game
        ppg_total = total_points / total_games if total_games > 0 else 0
        ppg_grading = grading_points / grading_games if grading_games > 0 else 0
        ppg_regular = regular_points / regular_games if regular_games > 0 else 0

        # Weighted PPG (grade difficulty adjusted) - use regular season grade
        weighted_points = 0
        weighted_games = 0
        for _, row in group.iterrows():
            multiplier = get_grade_multiplier(row["Grade"])
            games = row["Games Played"] if pd.notna(row["Games Played"]) else 0
            points = row["Total Points"] if pd.notna(row["Total Points"]) else 0
            weighted_points += points * multiplier
            weighted_games += games

        wppg = weighted_points / weighted_games if weighted_games > 0 else 0

        # Grade played (regular season)
        regular_grades = [extract_grade_letter(g) for g in regular["Grade"].unique() if extract_grade_letter(g)]
        grade_played = regular_grades[0] if regular_grades else None

        # Fouls per game
        fpg = total_fouls / total_games if total_games > 0 else 0

        results.append({
            "Profile ID": pid,
            "Player Name": player_name,
            "Season": season,
            "Season Order": SEASON_ORDER.get(season, 0),
            "Teams": ", ".join(teams),
            "Num Teams": len(teams),
            "Grade Played": grade_played,
            "Grade Age Group": group["Grade Age Group"].iloc[0] if "Grade Age Group" in group.columns else None,
            "Grade Gender": group["Grade Gender"].iloc[0] if "Grade Gender" in group.columns else None,
            "Total Games": total_games,
            "Total Points": total_points,
            "Total Fouls": total_fouls,
            "Grading Games": grading_games,
            "Grading Points": grading_points,
            "Regular Games": regular_games,
            "Regular Points": regular_points,
            "PPG Total": round(ppg_total, 2),
            "PPG Grading": round(ppg_grading, 2),
            "PPG Regular": round(ppg_regular, 2),
            "Weighted PPG": round(wppg, 2),
            "Fouls Per Game": round(fpg, 2),
            "Multi Team": len(teams) > 1,
        })

    return pd.DataFrame(results)


def calculate_team_rank(player_stats: pd.DataFrame) -> pd.DataFrame:
    """Add team rank — where the player sits in their team's scoring."""
    df = player_stats.copy()
    df["Team Rank"] = None
    df["Team Size"] = None
    df["Team PPG Avg"] = None
    df["PPG vs Team Avg %"] = None

    for (season, team), group in df.groupby(["Season", "Teams"]):
        if len(group) > 0:
            sorted_group = group.sort_values("PPG Regular", ascending=False)
            for rank, (idx, _) in enumerate(sorted_group.iterrows(), 1):
                df.at[idx, "Team Rank"] = rank
                df.at[idx, "Team Size"] = len(group)

            team_avg = group["PPG Regular"].mean()
            for idx, row in group.iterrows():
                df.at[idx, "Team PPG Avg"] = round(team_avg, 2)
                if team_avg > 0:
                    df.at[idx, "PPG vs Team Avg %"] = round(((row["PPG Regular"] - team_avg) / team_avg) * 100, 1)
                else:
                    df.at[idx, "PPG vs Team Avg %"] = 0

    return df


def calculate_elo_ratings(player_stats: pd.DataFrame) -> pd.DataFrame:
    """Calculate ELO-style ratings for each player based on their historical performance.

    Improvements:
    - Age-group aware: ELO calculated within age group + gender cohorts
    - Grade ceiling: A player's ELO cannot exceed the ceiling for their grade tier
    - Grade-scaled K-factor: Lower grades have reduced K so dominance in D/C doesn't
      inflate ELO to the same level as A grade players
    - Multi-team bonus retained for players demonstrating higher capability
    """
    # --- Grade hierarchy and ceilings ---
    # Defines the maximum ELO a player can reach while playing in each grade.
    # CRITICAL: Each grade's ceiling must be BELOW the next grade up's floor.
    # This guarantees grade hierarchy is always respected in rankings.
    GRADE_CEILINGS = {
        "A": 1400,
        "B": 1140,
        "B1": 1140,
        "B2": 1070,
        "B3": 1035,
        "B4": 1005,
        "C": 985,
        "C1": 985,
        "C2": 955,
        "C3": 925,
        "D": 895,
        "D1": 895,
        "D2": 865,
        "D3": 835,
    }

    # --- Grade floors ---
    # Minimum ELO for players in each grade. Being selected for a grade is
    # itself evidence of ability. Floors ensure NO player in a higher grade
    # can rank below a player in a lower grade's ceiling.
    GRADE_FLOORS = {
        "A": 1150,
        "B": 1080,
        "B1": 1080,
        "B2": 1040,
        "B3": 1010,
        "B4": 990,
        "C": 960,
        "C1": 960,
        "C2": 930,
        "C3": 900,
        "D": 870,
        "D1": 870,
        "D2": 840,
        "D3": 810,
    }

    # K-factor scaled by grade — lower grades have less ELO volatility
    GRADE_K_FACTOR = {
        "A": 50,
        "B": 45,
        "B1": 45,
        "B2": 42,
        "B3": 40,
        "B4": 38,
        "C": 35,
        "C1": 35,
        "C2": 32,
        "C3": 30,
        "D": 25,
        "D1": 25,
        "D2": 22,
        "D3": 20,
    }

    # Get expected wPPG per grade+age group+gender (cohort average)
    cohort_averages = player_stats.groupby(
        ["Grade Played", "Grade Age Group", "Grade Gender"]
    )["Weighted PPG"].mean().to_dict()

    # Fallback: grade-only averages
    grade_averages = player_stats.groupby("Grade Played")["Weighted PPG"].mean().to_dict()

    # Calculate ELO per player
    player_elos = {}
    player_history = {}

    # Process seasons in order
    sorted_stats = player_stats.sort_values("Season Order")

    for _, row in sorted_stats.iterrows():
        pid = row["Profile ID"]
        season = row["Season"]
        wppg = row["Weighted PPG"]
        grade = row["Grade Played"]
        age_group = row.get("Grade Age Group", None)
        gender = row.get("Grade Gender", None)
        games = row["Total Games"]
        multi_team = row["Multi Team"]

        # Initialize ELO if new player
        if pid not in player_elos:
            player_elos[pid] = BASE_ELO
            player_history[pid] = []

        current_elo = player_elos[pid]

        # Expected performance for their cohort (grade + age group + gender)
        cohort_key = (grade, age_group, gender)
        expected_wppg = cohort_averages.get(cohort_key, grade_averages.get(grade, wppg))

        # Performance delta (how much better/worse than cohort average)
        if expected_wppg > 0:
            performance_ratio = (wppg - expected_wppg) / expected_wppg
        else:
            performance_ratio = 0

        # Games confidence factor (more games = more reliable)
        confidence = min(1.0, games / 10)

        # Multi-team bonus (playing in 2 teams shows higher capability)
        multi_bonus = 1.1 if multi_team else 1.0

        # Grade-scaled K-factor
        k = GRADE_K_FACTOR.get(grade, K_FACTOR)

        # ELO adjustment
        elo_change = k * performance_ratio * confidence * multi_bonus
        new_elo = current_elo + elo_change

        # Apply grade ceiling — cannot exceed the ceiling for the grade you played in
        ceiling = GRADE_CEILINGS.get(grade, 1400)
        if new_elo > ceiling:
            new_elo = ceiling

        # Apply grade floor — being selected for a grade is evidence of ability
        # A bottom-of-A player should still rank above top-of-C2
        floor = GRADE_FLOORS.get(grade, 800)
        if new_elo < floor:
            new_elo = floor

        player_elos[pid] = new_elo
        player_history[pid].append({
            "Season": season,
            "ELO": round(new_elo, 1),
            "ELO Change": round(elo_change, 1),
            "Grade": grade,
            "WPPG": wppg,
        })

    # Build final ELO DataFrame
    elo_records = []
    for pid, history in player_history.items():
        latest = history[-1]
        trend = "Steady"
        if len(history) >= 2:
            recent_change = latest["ELO"] - history[-2]["ELO"]
            if recent_change > 15:
                trend = "Rising ↑"
            elif recent_change < -15:
                trend = "Declining ↓"

        # --- Generate assessment comment ---
        current_grade = latest["Grade"]
        current_elo = latest["ELO"]
        ceiling = GRADE_CEILINGS.get(current_grade, 1400)
        floor = GRADE_FLOORS.get(current_grade, 800)

        # Season history summary (e.g. "D2 → D1 → D1 → C2")
        grade_journey = " → ".join([str(h["Grade"]) for h in history if h["Grade"] and str(h["Grade"]) != "nan"])

        # Assessment logic
        if current_elo >= ceiling:
            comment = f"At {current_grade} ceiling — strong candidate to move up next season"
        elif current_elo <= floor:
            comment = f"At {current_grade} floor — may be struggling at this level, monitor closely"
        elif current_elo >= ceiling - 20:
            comment = f"Near {current_grade} ceiling — approaching readiness for higher grade"
        elif current_elo <= floor + 20:
            comment = f"Near {current_grade} floor — at risk of being over-graded"
        elif trend == "Rising ↑":
            comment = f"Improving in {current_grade} — trending upward, reassess next season"
        elif trend == "Declining ↓":
            comment = f"Declining in {current_grade} — may need support or grade adjustment"
        else:
            comment = f"Stable in {current_grade} — correctly graded"

        elo_records.append({
            "Profile ID": pid,
            "Current ELO": current_elo,
            "Seasons Played": len(history),
            "Trend": trend,
            "Grade Journey": grade_journey,
            "Assessment": comment,
            "History": history,
        })

    return pd.DataFrame(elo_records)


def get_grading_recommendation(player_elo: float, grade_elo_ranges: dict) -> str:
    """Recommend if a player is over/under/correctly graded.

    Args:
        player_elo: The player's current ELO
        grade_elo_ranges: Dict of {grade: (avg_elo, std_elo)} for their age group
    """
    recommendations = []
    for grade, (avg, std) in sorted(grade_elo_ranges.items(), key=lambda x: -x[1][0]):
        lower = avg - std
        upper = avg + std
        if lower <= player_elo <= upper:
            recommendations.append((grade, "Correctly Graded ✅"))
        elif player_elo > upper:
            recommendations.append((grade, "Under-graded ⬆️"))
        else:
            recommendations.append((grade, "Over-graded ⬇️"))

    return recommendations


def build_grade_elo_ranges(player_stats: pd.DataFrame, elo_df: pd.DataFrame) -> dict:
    """Build average ELO ranges per grade per age group.

    Returns: {age_group: {grade: (mean_elo, std_elo)}}
    """
    # Merge latest season stats with ELO
    latest_season = player_stats[player_stats["Season Order"] == player_stats["Season Order"].max()]
    merged = latest_season.merge(elo_df[["Profile ID", "Current ELO"]], on="Profile ID", how="left")

    ranges = {}
    for age_group, group in merged.groupby("Grade Age Group"):
        grade_ranges = {}
        for grade, g_group in group.groupby("Grade Played"):
            if len(g_group) >= 2:
                grade_ranges[grade] = (g_group["Current ELO"].mean(), g_group["Current ELO"].std())
        ranges[age_group] = grade_ranges

    return ranges


def get_player_summary(profile_id: str, player_stats: pd.DataFrame, elo_df: pd.DataFrame) -> dict:
    """Get a complete summary for a single player."""
    p_stats = player_stats[player_stats["Profile ID"] == profile_id].sort_values("Season Order")
    p_elo = elo_df[elo_df["Profile ID"] == profile_id]

    if p_stats.empty:
        return None

    latest = p_stats.iloc[-1]

    return {
        "name": latest["Player Name"],
        "current_elo": p_elo.iloc[0]["Current ELO"] if not p_elo.empty else BASE_ELO,
        "trend": p_elo.iloc[0]["Trend"] if not p_elo.empty else "New",
        "seasons_played": len(p_stats),
        "latest_grade": latest["Grade Played"],
        "latest_ppg": latest["PPG Regular"],
        "latest_wppg": latest["Weighted PPG"],
        "career_avg_wppg": round(p_stats["Weighted PPG"].mean(), 2),
        "team_rank": latest.get("Team Rank"),
        "ppg_vs_team": latest.get("PPG vs Team Avg %"),
        "multi_team_seasons": p_stats["Multi Team"].sum(),
        "history": p_stats[["Season", "Grade Played", "PPG Regular", "Weighted PPG", "Total Games"]].to_dict("records"),
    }
