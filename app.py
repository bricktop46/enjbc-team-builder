"""Eltham North Jets Basketball Club — Team Builder Dashboard."""

import streamlit as st
import pandas as pd
import os

from config import (
    ADMIN_EMAILS,
    AGE_GROUPS,
    AGE_GROUPS_BOYS,
    AGE_GROUPS_GIRLS,
    DEFAULT_COURTS,
    DEFAULT_TIME_SLOTS,
    DEFAULT_TRAINING_DAYS,
    EMAIL_TEMPLATE,
    GENDER_PREFIX,
    GRADING_GROUPS,
    TEAM_SIZE_MAX,
    TEAM_SIZE_MIN,
    TEAM_SIZE_WARNING,
    COL_PROFILE_ID,
    COL_FIRST_NAME,
    COL_LAST_NAME,
    COL_PREFERRED_NAME,
    COL_DOB,
    COL_GENDER,
    COL_PLAYER_NUMBER,
    COL_REQUESTS,
    COL_FEEDBACK,
    COL_COACHING_INTEREST,
    COL_PARENT1_FIRST,
    COL_PARENT1_LAST,
    COL_PARENT1_MOBILE,
    COL_PARENT1_EMAIL,
    COL_ACCOUNT_EMAIL,
    COL_ACCOUNT_MOBILE,
    SAVE_FILE,
    MASTER_PARTICIPANTS_FILE,
    COMPLIANCE_FILE,
)
from utils import (
    load_participants,
    enrich_participants,
    generate_team_name,
    get_players_by_group,
    save_state,
    load_state,
    detect_coach_clashes,
    load_previous_teams,
)
from stats_engine import (
    load_all_stats,
    calculate_player_stats,
    calculate_team_rank,
    calculate_elo_ratings,
    build_grade_elo_ranges,
    get_player_summary,
)

# --- Page Config ---
st.set_page_config(
    page_title="ENJBC Team Builder",
    page_icon="🏀",
    layout="wide",
)


# --- Session State Initialization ---
def init_session_state():
    defaults = {
        "authenticated": False,
        "user_email": "",
        "participants_df": None,
        "previous_season_df": None,
        "player_stats": None,
        "season": "Autumn",
        "year": 2026,
        "team_assignments": {},  # {profile_id: team_name}
        "team_details": {},  # {team_name: {coach_name, coach_phone, ...}}
        "play_up": {},  # {profile_id: True/False}
        "custom_courts": [],
        "previous_teams": {},  # {profile_id: previous_team_name}
        "signoff_block": "Justin Capicchiano - President ENJBC - ph 0409172392\nVincent Cannuli - Operations Manager ENJBC - ph 0402609261",
        "first_game_info": "Saturday TBC, time/venue to be confirmed once fixture is released.",
        "birth_cert_sighted": {},  # {profile_id: True/False}
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


init_session_state()

# --- Auto-load saved state on startup ---
if not st.session_state.get("_state_loaded"):
    _saved = load_state()
    if _saved:
        import io as _io
        for _key, _val in _saved.items():
            if _val is not None:
                # Restore DataFrames from serialised CSV
                if isinstance(_val, dict) and _val.get("__dataframe__"):
                    _val = pd.read_csv(_io.StringIO(_val["csv"]))
                st.session_state[_key] = _val
    st.session_state["_state_loaded"] = True


# --- Authentication ---
import hashlib
import json as auth_json

CREDENTIALS_FILE = "credentials.json"

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def load_credentials():
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, "r") as f:
            return auth_json.load(f)
    return {}

def save_credentials(creds):
    with open(CREDENTIALS_FILE, "w") as f:
        auth_json.dump(creds, f, indent=2)

def credentials_exist():
    creds = load_credentials()
    return len(creds) > 0

def login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("assets/logo.jpg", width=200)
        st.title("Eltham North Jets — Team Builder")

        creds = load_credentials()

        if not creds:
            # First-time setup
            st.markdown("### 🔐 Create Your Account")
            st.info("No accounts exist yet. Create the first admin account below.")
            new_username = st.text_input("Choose a username:")
            new_password = st.text_input("Choose a password:", type="password")
            confirm_password = st.text_input("Confirm password:", type="password")

            if st.button("Create Account"):
                if not new_username.strip():
                    st.error("Username cannot be empty.")
                elif len(new_password) < 6:
                    st.error("Password must be at least 6 characters.")
                elif new_password != confirm_password:
                    st.error("Passwords do not match.")
                else:
                    creds[new_username.strip().lower()] = {
                        "password_hash": hash_password(new_password),
                        "role": "admin"
                    }
                    save_credentials(creds)
                    st.success("✅ Account created! Please log in.")
                    st.rerun()
        else:
            # Login
            st.markdown("### Login")
            username = st.text_input("Username:")
            password = st.text_input("Password:", type="password")

            col_login, col_register = st.columns(2)
            with col_login:
                if st.button("Login"):
                    user_key = username.strip().lower()
                    if user_key in creds and creds[user_key]["password_hash"] == hash_password(password):
                        st.session_state.authenticated = True
                        st.session_state.user_email = user_key
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")
            with col_register:
                if st.button("➕ Add User"):
                    st.session_state.show_register = True

            # Registration form
            if st.session_state.get("show_register", False):
                st.markdown("---")
                st.markdown("#### Add New User")
                reg_username = st.text_input("New username:", key="reg_user")
                reg_password = st.text_input("New password:", type="password", key="reg_pass")
                reg_confirm = st.text_input("Confirm password:", type="password", key="reg_confirm")
                admin_user = st.text_input("Your admin username (to authorise):", key="auth_user")
                admin_pass = st.text_input("Your admin password:", type="password", key="auth_pass")

                if st.button("Register New User"):
                    auth_key = admin_user.strip().lower()
                    if auth_key not in creds or creds[auth_key]["password_hash"] != hash_password(admin_pass):
                        st.error("Admin credentials invalid — cannot authorise.")
                    elif not reg_username.strip():
                        st.error("Username cannot be empty.")
                    elif len(reg_password) < 6:
                        st.error("Password must be at least 6 characters.")
                    elif reg_password != reg_confirm:
                        st.error("Passwords do not match.")
                    elif reg_username.strip().lower() in creds:
                        st.error("Username already exists.")
                    else:
                        creds[reg_username.strip().lower()] = {
                            "password_hash": hash_password(reg_password),
                            "role": "admin"
                        }
                        save_credentials(creds)
                        st.success(f"✅ User '{reg_username.strip()}' created!")
                        st.session_state.show_register = False
                        st.rerun()


# --- Sidebar Navigation ---
def sidebar():
    st.sidebar.image("assets/logo.jpg", width=120)
    st.sidebar.title("ENJBC Team Builder")
    st.sidebar.caption(f"Logged in: {st.session_state.user_email}")
    st.sidebar.divider()

    page = st.sidebar.radio(
        "Navigation",
        ["🏠 Dashboard", "📁 Upload Data", "👥 Team Builder", "📊 Player Stats", "🏟️ Court Plan", "📧 Email Generator", "🛡️ Compliance", "⚙️ Settings"],
    )

    st.sidebar.divider()
    if st.sidebar.button("💾 Save Progress"):
        save_current_state()
        st.sidebar.success("Saved!")

    if st.sidebar.button("📂 Load Progress"):
        load_saved_state()
        st.sidebar.success("Loaded!")
        st.rerun()

    # --- Backup Download/Upload ---
    st.sidebar.divider()
    st.sidebar.caption("💾 Backup")

    # Download backup
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r") as _f:
            st.sidebar.download_button(
                "⬇️ Download Backup",
                data=_f.read(),
                file_name="team_builder_backup.json",
                mime="application/json",
            )

    # Upload backup to restore
    backup_file = st.sidebar.file_uploader("⬆️ Restore from backup", type=["json"], key="backup_upload")
    if backup_file:
        import io as _io
        backup_data = backup_file.read().decode("utf-8")
        with open(SAVE_FILE, "w") as _f:
            _f.write(backup_data)
        load_saved_state()
        st.sidebar.success("✅ Backup restored!")
        st.rerun()

    st.sidebar.divider()
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.rerun()

    return page


# --- Save / Load ---
def save_current_state():
    """Save all application state including DataFrames to persistent storage."""
    state = {
        "team_assignments": st.session_state.team_assignments,
        "team_details": st.session_state.team_details,
        "play_up": st.session_state.play_up,
        "custom_courts": st.session_state.custom_courts,
        "signoff_block": st.session_state.signoff_block,
        "first_game_info": st.session_state.first_game_info,
        "season": st.session_state.season,
        "year": st.session_state.year,
        "birth_cert_sighted": st.session_state.birth_cert_sighted,
        "participants_df": st.session_state.participants_df,
        "player_stats": st.session_state.get("player_stats"),
        "previous_teams": st.session_state.get("previous_teams", {}),
    }
    save_state(state)


def load_saved_state():
    """Load all saved state including DataFrames on startup."""
    state = load_state()
    if state:
        for key, val in state.items():
            if val is not None:
                st.session_state[key] = val


# --- Page: Dashboard ---
def page_dashboard():
    st.header("🏠 Dashboard")
    st.markdown(f"**Season:** {st.session_state.season} {st.session_state.year}")

    df = st.session_state.participants_df

    if df is None:
        st.info("👋 Welcome! Start by uploading your participants file on the **Upload Data** page.")
        return

    players_df = df[df["Role"] == "Player"] if "Role" in df.columns else df

    # --- Key Metrics ---
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Players", len(players_df))
    with col2:
        boys = len(players_df[players_df[COL_GENDER] == "Male"])
        st.metric("Boys", boys)
    with col3:
        girls = len(players_df[players_df[COL_GENDER] == "Female"])
        st.metric("Girls", girls)
    with col4:
        assigned = sum(1 for t in st.session_state.team_assignments.values() if t != "Unassigned")
        st.metric("Players Assigned", assigned)

    st.divider()

    # --- Progress Tracker ---
    st.subheader("📊 Drafting Progress")

    # Calculate progress per age group
    from config import AGE_GROUPS_BOYS, AGE_GROUPS_GIRLS, GENDER_PREFIX
    progress_data = []
    total_groups = 0
    completed_groups = 0

    for gender, age_groups in [("Male", AGE_GROUPS_BOYS), ("Female", AGE_GROUPS_GIRLS)]:
        for ag in age_groups:
            if ag.startswith("Over"):
                continue
            group_players = players_df[
                (players_df[COL_GENDER] == gender) &
                (players_df.get("Calculated Age Group", pd.Series()) == ag)
            ] if "Calculated Age Group" in players_df.columns else pd.DataFrame()

            if len(group_players) == 0:
                continue

            total_groups += 1
            group_pids = [str(p) for p in group_players[COL_PROFILE_ID].values]
            assigned_count = sum(1 for pid in group_pids if st.session_state.team_assignments.get(pid, "Unassigned") != "Unassigned")
            pct = int((assigned_count / len(group_players)) * 100) if len(group_players) > 0 else 0

            prefix = GENDER_PREFIX.get(gender, "X")
            age_num = ag.replace("U", "")
            label = f"{prefix}{age_num}"

            if pct == 100:
                completed_groups += 1
                status = "✅"
            elif pct > 0:
                status = "🔶"
            else:
                status = "⬜"

            progress_data.append({
                "Group": label,
                "Players": len(group_players),
                "Assigned": assigned_count,
                "Progress": f"{pct}%",
                "Status": status,
            })

    if progress_data:
        st.caption(f"**{completed_groups}/{total_groups}** age groups fully drafted")
        st.progress(completed_groups / total_groups if total_groups > 0 else 0)

        col1, col2 = st.columns(2)
        boys_progress = [p for p in progress_data if p["Group"].startswith("B")]
        girls_progress = [p for p in progress_data if p["Group"].startswith("G")]

        with col1:
            st.markdown("**Boys**")
            for p in boys_progress:
                st.write(f"{p['Status']} {p['Group']}: {p['Assigned']}/{p['Players']} ({p['Progress']})")
        with col2:
            st.markdown("**Girls**")
            for p in girls_progress:
                st.write(f"{p['Status']} {p['Group']}: {p['Assigned']}/{p['Players']} ({p['Progress']})")

    st.divider()

    # --- Compliance Summary ---
    st.subheader("🛡️ Compliance Status")
    if st.session_state.previous_season_df is not None:
        prev_ids = set(st.session_state.previous_season_df[COL_PROFILE_ID].astype(str))
        current_ids = set(players_df[COL_PROFILE_ID].astype(str))
        new_ids = current_ids - prev_ids
        sighted = sum(1 for pid in new_ids if st.session_state.birth_cert_sighted.get(pid, False))
        outstanding = len(new_ids) - sighted
        if outstanding > 0:
            st.warning(f"⚠️ {outstanding} new player(s) still need birth certificate verification")
        else:
            st.success("✅ All birth certificates verified")
    else:
        st.info("Upload a previous season file to enable compliance tracking")

    # --- Player Search ---
    st.divider()
    st.subheader("🔍 Quick Player Search")
    search_term = st.text_input("Search by name", placeholder="Type a player's name...", key="dashboard_search")
    if search_term and len(search_term) >= 2:
        matches = players_df[
            players_df[COL_FIRST_NAME].str.contains(search_term, case=False, na=False) |
            players_df[COL_LAST_NAME].str.contains(search_term, case=False, na=False)
        ]
        if matches.empty:
            st.caption("No players found.")
        else:
            for _, p in matches.head(10).iterrows():
                pid = str(p[COL_PROFILE_ID])
                name = f"{p[COL_FIRST_NAME]} {p[COL_LAST_NAME]}"
                age_group = p.get("Calculated Age Group", "?")
                gender = p.get(COL_GENDER, "?")
                team = st.session_state.team_assignments.get(pid, "Unassigned")
                prev = st.session_state.previous_teams.get(pid, "N/A")
                st.write(f"**{name}** | {gender} {age_group} | Team: {team} | Prev: {prev}")


# --- Page: Upload Data ---
def page_upload():
    st.header("📁 Upload Participants Data")

    col1, col2 = st.columns(2)
    with col1:
        st.session_state.season = st.selectbox("Season", ["Autumn", "Spring"], index=0)
    with col2:
        st.session_state.year = st.number_input("Year", min_value=2020, max_value=2035, value=2026)

    # --- Previous Season File (verified baseline) ---
    st.subheader("1️⃣ Previous Season File (verified baseline)")
    st.caption("This is your completed season file where all birth certificates have been sighted. Leave blank if this is your first season.")

    prev_uploaded = st.file_uploader(
        "Upload Previous Season Participants (CSV or XLSX)",
        type=["csv", "xlsx"],
        key="prev_season_upload",
    )

    if prev_uploaded:
        prev_df = load_participants(prev_uploaded)
        st.session_state.previous_season_df = prev_df
        st.success(f"✅ Previous season: {len(prev_df)} verified players loaded")
    elif st.session_state.previous_season_df is not None:
        st.info(f"ℹ️ Previous season file loaded ({len(st.session_state.previous_season_df)} players)")

    st.divider()

    # --- Current Season File (active working file) ---
    st.subheader("2️⃣ Current Season File (active)")
    st.caption("This is the file you're building teams from for the upcoming season.")

    uploaded = st.file_uploader(
        "Upload Current Season Participants (CSV or XLSX)",
        type=["csv", "xlsx"],
        key="current_season_upload",
    )

    if uploaded:
        df = load_participants(uploaded)
        df = enrich_participants(df, st.session_state.season, st.session_state.year)
        st.session_state.participants_df = df
        st.success(f"✅ Current season: {len(df)} participants loaded")
        save_current_state()

        # Summary
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Players", len(df[df["Role"] == "Player"]) if "Role" in df.columns else len(df))
        with col2:
            boys = len(df[df[COL_GENDER] == "Male"])
            st.metric("Boys", boys)
        with col3:
            girls = len(df[df[COL_GENDER] == "Female"])
            st.metric("Girls", girls)

        # Age group breakdown
        st.subheader("Age Group Breakdown")
        players_only = df[df["Role"] == "Player"] if "Role" in df.columns else df
        summary = players_only.groupby([COL_GENDER, "Calculated Age Group"]).size().unstack(fill_value=0)
        st.dataframe(summary, use_container_width=True)

        # Auto-detect new players
        if st.session_state.previous_season_df is not None:
            prev_ids = set(st.session_state.previous_season_df[COL_PROFILE_ID].astype(str))
            current_ids = set(df[COL_PROFILE_ID].astype(str))
            new_ids = current_ids - prev_ids
            new_player_count = len(new_ids)
            if new_player_count > 0:
                st.warning(f"⚠️ {new_player_count} new player(s) detected — birth certificate verification required. See 🛡️ Compliance page.")
            else:
                st.success("✅ All players exist in previous season file — no new verifications needed.")

    elif st.session_state.participants_df is not None:
        df = st.session_state.participants_df
        st.info(f"ℹ️ Using previously loaded data ({len(df)} participants)")

    # Competitions file upload (for previous team reference)
    st.divider()
    st.subheader("3️⃣ Competitions File (optional — for previous team data)")
    comp_file = st.file_uploader(
        "Upload Competitions file (XLSX)",
        type=["xlsx"],
        key="comp_upload",
    )
    if comp_file:
        prev = load_previous_teams(comp_file)
        st.session_state.previous_teams = prev
        st.success(f"✅ Loaded previous team data for {len(prev)} players")
    elif st.session_state.previous_teams:
        st.info(f"ℹ️ Previous team data loaded for {len(st.session_state.previous_teams)} players")

    # Grade Statistics upload
    st.divider()
    st.subheader("4️⃣ Grade Statistics (for ELO ratings)")
    st.caption("Upload one or more grade statistics CSVs. These are used to calculate player ELO ratings for balanced team drafting.")

    stats_files = st.file_uploader(
        "Upload Grade Statistics CSV(s)",
        type=["csv"],
        key="stats_upload",
        accept_multiple_files=True,
    )
    if stats_files:
        from stats_engine import calculate_elo_ratings, calculate_player_stats, load_all_stats
        all_stats = []
        for sf in stats_files:
            sdf = pd.read_csv(sf)
            all_stats.append(sdf)
        combined_stats = pd.concat(all_stats, ignore_index=True)
        player_stats = calculate_player_stats(combined_stats)
        elo_df = calculate_elo_ratings(player_stats)
        # Merge player names from stats data if available
        if "First Name" not in elo_df.columns:
            name_cols = [c for c in ["Profile ID", "First Name", "Last Name"] if c in combined_stats.columns]
            if len(name_cols) == 3:
                names = combined_stats[name_cols].drop_duplicates(subset=["Profile ID"])
                elo_df = elo_df.merge(names, on="Profile ID", how="left")
        st.session_state.player_stats = elo_df
        st.success(f"✅ Loaded {len(stats_files)} stats file(s) — ELO calculated for {len(elo_df)} players")
        display_cols = [c for c in ["Profile ID", "First Name", "Last Name", "Current ELO", "Assessment"] if c in elo_df.columns]
        st.dataframe(elo_df[display_cols].head(20) if display_cols else elo_df.head(20), use_container_width=True)
        save_current_state()
    elif st.session_state.get("player_stats") is not None:
        st.info(f"ℹ️ Stats loaded for {len(st.session_state.player_stats)} players")


# --- Page: Team Builder ---
def page_team_builder():
    st.header("👥 Team Builder")

    df = st.session_state.participants_df
    if df is None:
        st.warning("Please upload participants data first.")
        return

    # Filter to players only
    df = df[df["Role"] == "Player"].copy()

    # Load player stats for ready reckoner
    import glob
    stats_files = glob.glob(os.path.join(os.path.dirname(__file__), 'grade_statistics*.csv'))
    player_stats_lookup = {}
    if st.session_state.get("player_stats") is not None:
        elo_data = st.session_state.player_stats
        for _, row in elo_data.iterrows():
            player_stats_lookup[row["Profile ID"]] = {
                "elo": row.get("Current ELO", "N/A"),
                "ppg": row.get("PPG Regular", 0),
                "total_pts": row.get("Total Points", 0),
            }
    elif stats_files:
        raw_stats = load_all_stats(stats_files)
        p_stats = calculate_player_stats(raw_stats)
        elo_data = calculate_elo_ratings(p_stats)
        # Build lookup: {profile_id: {elo, ppg, total_points}}
        latest = p_stats[p_stats["Season Order"] == p_stats["Season Order"].max()]
        merged = latest.merge(elo_data[["Profile ID", "Current ELO"]], on="Profile ID", how="left")
        for _, row in merged.iterrows():
            player_stats_lookup[row["Profile ID"]] = {
                "elo": row.get("Current ELO", "N/A"),
                "ppg": row.get("PPG Regular", 0),
                "total_pts": row.get("Total Points", 0),
            }

    # Filters
    col1, col2 = st.columns(2)
    with col1:
        gender = st.selectbox("Gender", ["Male", "Female"])
    with col2:
        age_options = AGE_GROUPS_BOYS if gender == "Male" else AGE_GROUPS_GIRLS
        age_group = st.selectbox("Age Group", age_options)

    # Get players for this group
    players = get_players_by_group(df, gender, age_group)

    # Check for play-up players coming into this group
    play_up_into = []
    if age_group != "U08":
        lower_idx = AGE_GROUPS.index(age_group) - 1
        lower_group = AGE_GROUPS[lower_idx]
        lower_players = get_players_by_group(df, gender, lower_group)
        for _, p in lower_players.iterrows():
            pid = str(p[COL_PROFILE_ID])
            if st.session_state.play_up.get(pid):
                play_up_into.append(p)

    st.subheader(f"{GENDER_PREFIX.get(gender, '')}{age_group.replace('U', '')} — {len(players)} players" +
                 (f" (+{len(play_up_into)} playing up)" if play_up_into else ""))

    # Determine number of teams
    total_players = len(players) + len(play_up_into)
    # Remove players who are playing UP out of this group
    playing_up_out = [
        idx for idx, p in players.iterrows()
        if st.session_state.play_up.get(str(p[COL_PROFILE_ID]))
    ]
    effective_players = total_players - len(playing_up_out)

    suggested_teams = max(1, round(effective_players / TEAM_SIZE_MAX))
    st.caption(f"Suggested teams: {suggested_teams} (based on {effective_players} effective players, target {TEAM_SIZE_MIN}-{TEAM_SIZE_MAX} per team)")

    # Show players table with assignment controls
    st.divider()

    # Build team options
    prefix = GENDER_PREFIX.get(gender, "X")
    age_num = age_group.replace("U", "").replace("Over 18", "18+")
    num_teams = st.number_input("Number of teams", min_value=1, max_value=15, value=suggested_teams, key=f"num_teams_{gender}_{age_group}")

    team_options = ["Unassigned"] + [f"{prefix}{age_num}.{i}" for i in range(1, num_teams + 1)]

    # --- Auto-Draft Button ---
    st.divider()
    col_draft1, col_draft2, col_draft3 = st.columns([1, 1, 2])
    with col_draft1:
        auto_draft = st.button("🎯 Auto-Draft Teams", key=f"autodraft_{gender}_{age_group}")
    with col_draft2:
        reset_draft = st.button("🔄 Reset Draft", key=f"resetdraft_{gender}_{age_group}")
    with col_draft3:
        st.caption("Auto-Draft: keeps previous teams together, fills by ELO. Reset: clears all assignments for this group.")

    if reset_draft:
        # Reset all players in this group to Unassigned
        reset_players = players[~players.index.isin(playing_up_out)].copy()
        if play_up_into:
            play_up_df = pd.DataFrame(play_up_into)
            reset_players = pd.concat([reset_players, play_up_df], ignore_index=True)
        reset_players = reset_players.drop_duplicates(subset=[COL_PROFILE_ID], keep="first").reset_index(drop=True)
        for idx, p in reset_players.iterrows():
            pid = str(p[COL_PROFILE_ID])
            st.session_state.team_assignments[pid] = "Unassigned"
            # Force the widget to show "Unassigned" on rerun
            widget_key = f"assign_{gender}_{age_group}_{idx}_{pid}"
            st.session_state[widget_key] = "Unassigned"
        save_current_state()
        st.rerun()

    if auto_draft and num_teams > 0:
        import re
        from collections import Counter, defaultdict

        # Get all players for this view
        draft_players = players[~players.index.isin(playing_up_out)].copy()
        if play_up_into:
            play_up_df = pd.DataFrame(play_up_into)
            draft_players = pd.concat([draft_players, play_up_df], ignore_index=True)
        draft_players = draft_players.drop_duplicates(subset=[COL_PROFILE_ID], keep="first").reset_index(drop=True)

        teams_in_draft = team_options[1:]  # Exclude "Unassigned"
        target_size = len(draft_players) // num_teams

        # Step 1: Group players by their previous team
        prev_team_groups = defaultdict(list)  # {prev_team: [(pid, elo), ...]}
        no_prev_team = []  # Players with no previous team data

        for _, p in draft_players.iterrows():
            pid = str(p[COL_PROFILE_ID])
            elo_val = player_stats_lookup.get(pid, {}).get("elo", 0)
            if not isinstance(elo_val, (int, float)):
                elo_val = 0
            prev = st.session_state.previous_teams.get(pid, "")
            if prev and prev not in ("Not available", "N/A", ""):
                prev_team_groups[prev].append((pid, elo_val))
            else:
                no_prev_team.append((pid, elo_val))

        # Step 2: Assign legacy groups to new teams, keeping them intact
        # Sort legacy groups by size (largest first) so biggest groups get placed first
        sorted_groups = sorted(prev_team_groups.items(), key=lambda x: -len(x[1]))

        team_rosters = {t: [] for t in teams_in_draft}  # {team_name: [(pid, elo), ...]}

        for prev_team_name, group_players in sorted_groups:
            # Find the team with fewest players that can fit this group
            # (or the team with most capacity)
            best_team = min(teams_in_draft, key=lambda t: len(team_rosters[t]))

            # If the group is too big for one team, split minimally
            max_capacity = target_size + 2  # Allow slight overflow
            if len(group_players) <= max_capacity - len(team_rosters[best_team]):
                # Fits — assign entire group together
                team_rosters[best_team].extend(group_players)
            else:
                # Group too large — fill best team, overflow to next emptiest
                remaining = list(group_players)
                remaining.sort(key=lambda x: -x[1])  # Sort by ELO within group
                while remaining:
                    best_team = min(teams_in_draft, key=lambda t: len(team_rosters[t]))
                    spots = max(1, (target_size + 1) - len(team_rosters[best_team]))
                    team_rosters[best_team].extend(remaining[:spots])
                    remaining = remaining[spots:]

        # Step 3: Distribute remaining players (no prev team) by ELO snake draft
        no_prev_team.sort(key=lambda x: -x[1])  # Highest ELO first
        for pid, elo_val in no_prev_team:
            # Assign to team with fewest players (balances numbers)
            best_team = min(teams_in_draft, key=lambda t: len(team_rosters[t]))
            team_rosters[best_team].append((pid, elo_val))

        # Step 4: Rank teams by average ELO (strongest = .1, weakest = .N)
        team_avg_elo = {}
        for team_name, roster in team_rosters.items():
            elos = [e for _, e in roster if e > 0]
            team_avg_elo[team_name] = sum(elos) / len(elos) if elos else 0

        # Sort teams by avg ELO descending and re-map to .1, .2, .3 etc.
        ranked_teams = sorted(teams_in_draft, key=lambda t: -team_avg_elo[t])
        team_remap = {}  # {old_team_name: new_team_name}
        for new_rank, old_team in enumerate(ranked_teams, 1):
            new_team_name = f"{prefix}{age_num}.{new_rank}"
            team_remap[old_team] = new_team_name

        # Step 5: Write assignments to session state with ranked team names
        # Also build a pid->index map matching display order for widget keys
        draft_pid_order = {str(p[COL_PROFILE_ID]): idx for idx, p in draft_players.iterrows()}
        for old_team_name, roster in team_rosters.items():
            new_team_name = team_remap[old_team_name]
            for pid, _ in roster:
                st.session_state.team_assignments[pid] = new_team_name
                # Force the widget to show the new team on rerun
                idx = draft_pid_order.get(pid, 0)
                widget_key = f"assign_{gender}_{age_group}_{idx}_{pid}"
                st.session_state[widget_key] = new_team_name

        # Summary
        kept_together = sum(len(g) for _, g in sorted_groups if len(g) > 1)
        save_current_state()
        st.rerun()

    # Player table
    st.subheader("Assign Players to Teams")

    # Combine regular players (minus play-up out) with play-up in
    display_players = players[~players.index.isin(playing_up_out)].copy()
    if play_up_into:
        play_up_df = pd.DataFrame(play_up_into)
        play_up_df["_play_up"] = True
        display_players["_play_up"] = False
        display_players = pd.concat([display_players, play_up_df], ignore_index=True)
    else:
        display_players["_play_up"] = False

    # Deduplicate by Profile ID (keep first occurrence)
    display_players = display_players.drop_duplicates(subset=[COL_PROFILE_ID], keep="first").reset_index(drop=True)

    # Add ELO column from stats lookup
    display_players["ELO"] = display_players[COL_PROFILE_ID].apply(
        lambda pid: player_stats_lookup.get(pid, {}).get("elo", 0)
    )

    for idx, player in display_players.iterrows():
        pid = str(player[COL_PROFILE_ID])
        key_suffix = f"{gender}_{age_group}_{idx}_{pid}"
        pname = f"{player[COL_FIRST_NAME]} {player[COL_LAST_NAME]}"
        preferred = player.get(COL_PREFERRED_NAME, "")
        display_name = f"{pname}" + (f" ({preferred})" if pd.notna(preferred) and preferred else "")

        # Flags
        flags = []
        if player.get("_play_up"):
            flags.append("⬆️ Playing Up")
        requests_text = player.get(COL_REQUESTS, "")
        feedback_text = player.get(COL_FEEDBACK, "")
        has_request = pd.notna(requests_text) and str(requests_text).strip()
        has_feedback = pd.notna(feedback_text) and str(feedback_text).strip()
        if has_request:
            flags.append(" ")
        if has_feedback:
            flags.append("💬")
        coaching = player.get(COL_COACHING_INTEREST, "")
        if pd.notna(coaching) and str(coaching).strip().lower() not in ("", "no", "nan"):
            flags.append("🧑‍🏫")

        # Previous team
        prev_team = st.session_state.previous_teams.get(pid, "Not available")
        seasons_left = player.get("Seasons Remaining", "?")
        seasons_str = f"⏳ Last season" if seasons_left == 1 else f"⏳ {seasons_left} seasons left"

        # Stats lookup
        p_stats_info = player_stats_lookup.get(pid, {})
        elo_val = p_stats_info.get("elo", "N/A")
        ppg_val = p_stats_info.get("ppg", "N/A")
        total_pts_val = p_stats_info.get("total_pts", "N/A")
        elo_display = f"{elo_val:.0f}" if isinstance(elo_val, (int, float)) else "N/A"
        ppg_display = f"{ppg_val:.1f}" if isinstance(ppg_val, (int, float)) else "N/A"
        pts_display = f"{total_pts_val:.0f}" if isinstance(total_pts_val, (int, float)) else "N/A"

        col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
        with col1:
            st.write(f"**{display_name}** {' '.join(flags)}")
            st.caption(f"Prev: {prev_team} | {seasons_str} | ELO: {elo_display} | PPG: {ppg_display} | Pts: {pts_display}")
        with col2:
            current = st.session_state.team_assignments.get(pid, "Unassigned")
            current_idx = team_options.index(current) if current in team_options else 0
            widget_key = f"assign_{key_suffix}"
            assignment = st.selectbox(
                "Team", team_options, index=current_idx,
                key=widget_key, label_visibility="collapsed"
            )
            st.session_state.team_assignments[pid] = assignment
        with col3:
            st.caption(f"#{player.get(COL_PLAYER_NUMBER, 'N/A')} | Age: {player.get('Calculated Age', '?')}")
        with col4:
            if not player.get("_play_up"):
                if st.checkbox("⬆️", key=f"playup_{key_suffix}", value=st.session_state.play_up.get(pid, False)):
                    st.session_state.play_up[pid] = True
                else:
                    st.session_state.play_up[pid] = False

        # Show requests/feedback as expandable detail under the player
        if has_request or has_feedback:
            with st.expander(f"📋 Requests/Feedback for {pname}", expanded=False):
                if has_request:
                    st.markdown(f"**Request:** {requests_text}")
                if has_feedback:
                    st.markdown(f"**Feedback:** {feedback_text}")

    # Team summary
    st.divider()
    st.subheader("Team Summary")
    for team in team_options[1:]:  # Skip "Unassigned"
        team_pids = [
            pid for pid, t in st.session_state.team_assignments.items() if t == team
        ]
        count = len(team_pids)
        if count < TEAM_SIZE_MIN:
            icon = "🔴"
        elif count > TEAM_SIZE_MAX:
            icon = "🟡" if count == TEAM_SIZE_WARNING else "🔴"
        else:
            icon = "🟢"

        with st.expander(f"{icon} **{team}**: {count} players", expanded=False):
            team_player_rows = display_players[
                display_players[COL_PROFILE_ID].astype(str).isin(team_pids)
            ]
            if team_player_rows.empty:
                st.caption("No players assigned yet.")
            else:
                for _, p in team_player_rows.iterrows():
                    pname = f"{p[COL_FIRST_NAME]} {p[COL_LAST_NAME]}"
                    prev = st.session_state.previous_teams.get(str(p[COL_PROFILE_ID]), "N/A")
                    singlet = p.get(COL_PLAYER_NUMBER, "")
                    singlet_str = f"#{singlet}" if pd.notna(singlet) and str(singlet).strip() else ""
                    st.write(f"• {pname} {singlet_str} — prev: {prev}")

    # Unassigned
    unassigned_pids = [
        pid for pid, t in st.session_state.team_assignments.items() if t == "Unassigned"
    ]
    unassigned_in_group = display_players[
        display_players[COL_PROFILE_ID].astype(str).isin(unassigned_pids)
    ]
    if not unassigned_in_group.empty:
        with st.expander(f"⚪ **Unassigned**: {len(unassigned_in_group)} players", expanded=False):
            for _, p in unassigned_in_group.iterrows():
                pname = f"{p[COL_FIRST_NAME]} {p[COL_LAST_NAME]}"
                st.write(f"• {pname}")

    # Team Balance View
    st.divider()
    st.subheader("⚖️ Team Balance")
    balance_data = []
    for team in team_options[1:]:
        team_pids = [pid for pid, t in st.session_state.team_assignments.items() if t == team]
        team_rows = display_players[display_players[COL_PROFILE_ID].astype(str).isin(team_pids)]
        if not team_rows.empty and "ELO" in team_rows.columns:
            avg_elo = team_rows["ELO"].mean()
            min_elo = team_rows["ELO"].min()
            max_elo = team_rows["ELO"].max()
        else:
            avg_elo = min_elo = max_elo = 0
        balance_data.append({"Team": team, "Players": len(team_pids), "Avg ELO": round(avg_elo, 1), "Min ELO": round(min_elo, 1), "Max ELO": round(max_elo, 1)})
    if balance_data:
        balance_df = pd.DataFrame(balance_data)
        if balance_df["Avg ELO"].sum() > 0:
            st.dataframe(balance_df, use_container_width=True, hide_index=True)
            spread = balance_df["Avg ELO"].max() - balance_df["Avg ELO"].min()
            if spread < 20:
                st.success(f"✅ Teams are well balanced (ELO spread: {spread:.1f})")
            elif spread < 50:
                st.warning(f"⚠️ Moderate imbalance (ELO spread: {spread:.1f})")
            else:
                st.error(f"🔴 Significant imbalance (ELO spread: {spread:.1f})")
        else:
            st.caption("No ELO data available — upload stats to see balance.")

    # Team details (coach, manager)
    st.divider()
    st.subheader("Coach & Team Manager Details")
    for team in team_options[1:]:
        with st.expander(f"📝 {team}"):
            details = st.session_state.team_details.get(team, {})
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Coach**")
                details["coach_name"] = st.text_input("Coach Name", value=details.get("coach_name", ""), key=f"coach_{team}")
                details["coach_phone"] = st.text_input("Coach Phone", value=details.get("coach_phone", ""), key=f"cphone_{team}")
                details["coach_email"] = st.text_input("Coach Email", value=details.get("coach_email", ""), key=f"cemail_{team}")
                details["coach_wwc"] = st.text_input("Coach WWC Number", value=details.get("coach_wwc", ""), key=f"cwwc_{team}")
            with c2:
                st.markdown("**Team Manager**")
                details["manager_name"] = st.text_input("Manager Name", value=details.get("manager_name", ""), key=f"mgr_{team}")
                details["manager_phone"] = st.text_input("Manager Phone", value=details.get("manager_phone", ""), key=f"mphone_{team}")
                details["manager_email"] = st.text_input("Manager Email", value=details.get("manager_email", ""), key=f"memail_{team}")
                details["manager_wwc"] = st.text_input("Manager WWC Number", value=details.get("manager_wwc", ""), key=f"mwwc_{team}")

            st.session_state.team_details[team] = details

    # --- Export Teams to Excel ---
    st.divider()
    st.subheader("📥 Export Team List to Excel")
    if st.button("Generate Excel Export", key="export_teams_xlsx"):
        export_df_rows = []
        for pid, team_name in st.session_state.team_assignments.items():
            if team_name == "Unassigned":
                continue
            player_row = df[df[COL_PROFILE_ID].astype(str) == str(pid)]
            if player_row.empty:
                continue
            p = player_row.iloc[0]
            export_df_rows.append({
                "Team": team_name,
                "First Name": p[COL_FIRST_NAME],
                "Last Name": p[COL_LAST_NAME],
                "DOB": p.get(COL_DOB, ""),
                "Gender": p.get(COL_GENDER, ""),
                "Singlet #": p.get(COL_PLAYER_NUMBER, ""),
                "Parent/Guardian": f"{p.get(COL_PARENT1_FIRST, '')} {p.get(COL_PARENT1_LAST, '')}".strip(),
                "Parent Mobile": p.get(COL_PARENT1_MOBILE, ""),
                "Parent Email": p.get(COL_PARENT1_EMAIL, ""),
                "Coach": st.session_state.team_details.get(team_name, {}).get("coach_name", ""),
                "Team Manager": st.session_state.team_details.get(team_name, {}).get("manager_name", ""),
            })

        if not export_df_rows:
            st.warning("No players assigned to teams yet.")
        else:
            export_df = pd.DataFrame(export_df_rows)
            # Sort: extract age number and team number from team name (e.g. B12.1 -> 12, 1)
            import re
            def team_sort_key(t):
                m = re.match(r'[BG](\d+)\.(\d+)', t)
                return (int(m.group(1)), int(m.group(2))) if m else (99, 99)

            export_df["_sort"] = export_df["Team"].apply(team_sort_key)
            export_df = export_df.sort_values("_sort").drop(columns=["_sort"])

            boys_df = export_df[export_df["Gender"] == "Male"].drop(columns=["Gender"])
            girls_df = export_df[export_df["Gender"] == "Female"].drop(columns=["Gender"])

            from io import BytesIO
            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                if not boys_df.empty:
                    boys_df.to_excel(writer, sheet_name="Boys", index=False)
                if not girls_df.empty:
                    girls_df.to_excel(writer, sheet_name="Girls", index=False)
            output.seek(0)

            st.download_button(
                label="⬇️ Download Team List (.xlsx)",
                data=output.getvalue(),
                file_name=f"ENJBC_Teams_{st.session_state.season}_{st.session_state.year}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            st.success("✅ Export ready!")


# --- Page: Player Stats ---
def page_player_stats():
    st.header("📊 Player Statistics & ELO Ratings")

    # Load stats files
    import glob
    stats_files = glob.glob(os.path.join(os.path.dirname(__file__), 'grade_statistics*.csv'))

    if not stats_files and st.session_state.get("player_stats") is None:
        st.warning("No grade statistics files found. Please upload them on the Upload Data page.")
        return

    with st.spinner("Calculating player statistics..."):
        raw_stats = load_all_stats(stats_files)
        player_stats = calculate_player_stats(raw_stats)
        player_stats = calculate_team_rank(player_stats)
        elo_df = calculate_elo_ratings(player_stats)

    st.success(f"✅ Loaded {len(stats_files)} seasons | {len(elo_df)} players rated")

    # Tabs for different views
    tab1, tab2, tab3 = st.tabs(["🏆 ELO Rankings", "👤 Player Lookup", "📈 Grading Analysis"])

    with tab1:
        st.subheader("Player ELO Rankings")

        # Merge ELO with latest season stats
        latest_season = player_stats[player_stats["Season Order"] == player_stats["Season Order"].max()]
        rankings = latest_season.merge(elo_df[["Profile ID", "Current ELO", "Trend", "Seasons Played", "Grade Journey", "Assessment"]], on="Profile ID", how="left")

        # Filter by gender and age group
        col1, col2 = st.columns(2)
        with col1:
            selected_gender = st.selectbox("Gender", ["BOYS", "GIRLS"], key="stats_gender")
        with col2:
            gender_filtered = rankings[rankings["Grade Gender"] == selected_gender]
            age_groups_available = sorted(gender_filtered["Grade Age Group"].dropna().unique())
            selected_age = st.selectbox("Age Group", ["All"] + age_groups_available, key="stats_age")

        rankings = gender_filtered
        if selected_age != "All":
            rankings = rankings[rankings["Grade Age Group"] == selected_age]

        # Display
        display_cols = ["Player Name", "Current ELO", "Trend", "Grade Played", "Grade Journey",
                        "Assessment", "PPG Regular", "Weighted PPG", "Total Games",
                        "Team Rank", "PPG vs Team Avg %", "Seasons Played"]
        display_df = rankings[[c for c in display_cols if c in rankings.columns]].sort_values("Current ELO", ascending=False)
        st.dataframe(display_df, use_container_width=True, hide_index=True)

    with tab2:
        st.subheader("Player Lookup")

        # Search
        all_players = elo_df.merge(
            player_stats[["Profile ID", "Player Name"]].drop_duplicates(),
            on="Profile ID", how="left"
        )
        player_names = sorted(all_players["Player Name"].dropna().unique())
        selected_player = st.selectbox("Search Player", player_names, key="player_search")

        if selected_player:
            pid = all_players[all_players["Player Name"] == selected_player]["Profile ID"].iloc[0]
            summary = get_player_summary(pid, player_stats, elo_df)

            if summary:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Current ELO", summary["current_elo"])
                with col2:
                    st.metric("Trend", summary["trend"])
                with col3:
                    st.metric("PPG (Regular)", summary["latest_ppg"])
                with col4:
                    st.metric("Weighted PPG", summary["latest_wppg"])

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Latest Grade", summary["latest_grade"] or "N/A")
                with col2:
                    st.metric("Team Rank", summary["team_rank"] or "N/A")
                with col3:
                    st.metric("vs Team Avg", f"{summary['ppg_vs_team']}%" if summary["ppg_vs_team"] else "N/A")
                with col4:
                    st.metric("Seasons Played", summary["seasons_played"])

                # History table
                st.subheader("Season History")
                history_df = pd.DataFrame(summary["history"])
                st.dataframe(history_df, use_container_width=True, hide_index=True)

    with tab3:
        st.subheader("Grading Analysis")
        st.caption("Players flagged as potentially over-graded or under-graded based on ELO vs grade average")

        # Build grade ELO ranges
        grade_ranges = build_grade_elo_ranges(player_stats, elo_df)

        # Filter
        col1, col2 = st.columns(2)
        with col1:
            selected_gender2 = st.selectbox("Gender", ["BOYS", "GIRLS"], key="grading_gender")
        with col2:
            gender_filtered_ranges = {k: v for k, v in grade_ranges.items()
                                       if any(selected_gender2.lower() in str(player_stats[(player_stats["Grade Age Group"] == k) & (player_stats["Grade Gender"] == selected_gender2)]["Grade Gender"].values).lower() for _ in [1])}
            age_groups_available2 = sorted(grade_ranges.keys())
            selected_age2 = st.selectbox("Age Group", age_groups_available2, key="grading_age")

        if selected_age2 and selected_age2 in grade_ranges:
            grade_elos = grade_ranges[selected_age2]

            # Get players in this age group and gender
            latest = player_stats[
                (player_stats["Season Order"] == player_stats["Season Order"].max()) &
                (player_stats["Grade Age Group"] == selected_age2) &
                (player_stats["Grade Gender"] == selected_gender2)
            ]
            merged = latest.merge(elo_df[["Profile ID", "Current ELO"]], on="Profile ID", how="left")

            under_graded = []
            over_graded = []
            correctly_graded = []

            for _, row in merged.iterrows():
                grade = row["Grade Played"]
                elo = row["Current ELO"]
                if pd.isna(elo) or grade not in grade_elos:
                    continue

                avg, std = grade_elos[grade]
                std = std if pd.notna(std) and std > 0 else 20  # Default std

                if elo > avg + std:
                    under_graded.append(row)
                elif elo < avg - std:
                    over_graded.append(row)
                else:
                    correctly_graded.append(row)

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Under-graded ⬆️", len(under_graded))
            with col2:
                st.metric("Correctly Graded ✅", len(correctly_graded))
            with col3:
                st.metric("Over-graded ⬇️", len(over_graded))

            if under_graded:
                st.subheader("⬆️ Under-graded (should move up)")
                ug_df = pd.DataFrame(under_graded)[["Player Name", "Grade Played", "Current ELO", "PPG Regular", "Weighted PPG", "PPG vs Team Avg %"]]
                st.dataframe(ug_df.sort_values("Current ELO", ascending=False), use_container_width=True, hide_index=True)

            if over_graded:
                st.subheader("⬇️ Over-graded (may struggle)")
                og_df = pd.DataFrame(over_graded)[["Player Name", "Grade Played", "Current ELO", "PPG Regular", "Weighted PPG", "PPG vs Team Avg %"]]
                st.dataframe(og_df.sort_values("Current ELO"), use_container_width=True, hide_index=True)


# --- Page: Court Plan ---
def page_court_plan():
    st.header("🏟️ Court Plan & Training Schedule")

    df = st.session_state.participants_df
    if df is None:
        st.warning("Please upload participants data first.")
        return

    all_courts = DEFAULT_COURTS + st.session_state.custom_courts

    # Add custom court
    with st.expander("➕ Add a new court"):
        new_court = st.text_input("Court name")
        if st.button("Add Court") and new_court.strip():
            if new_court not in all_courts:
                st.session_state.custom_courts.append(new_court.strip())
                st.success(f"Added: {new_court}")
                st.rerun()

    all_courts = DEFAULT_COURTS + st.session_state.custom_courts

    # Available courts selector
    if "available_courts" not in st.session_state:
        st.session_state.available_courts = list(all_courts)

    with st.expander("✅ Select Available Courts This Season"):
        st.caption("Uncheck courts that are not available. Only checked courts will appear in the grid.")
        updated_available = []
        for court in all_courts:
            checked = st.checkbox(court, value=(court in st.session_state.available_courts), key=f"avail_{court}")
            if checked:
                updated_available.append(court)
        st.session_state.available_courts = updated_available

    # Use only available courts from here on
    active_courts = [c for c in all_courts if c in st.session_state.available_courts]
    all_teams = sorted(set(
        t for t in st.session_state.team_assignments.values() if t != "Unassigned"
    ))

    if not all_teams:
        st.info("No teams assigned yet. Build teams first.")
        return

    # --- Visual Grid: Courts vs Time Slots (per day) ---
    st.subheader("📅 Visual Court Map")
    st.caption("Each court is split into two halves. Assign up to 2 teams per court per time slot.")

    selected_day = st.selectbox("Select Day", DEFAULT_TRAINING_DAYS, key="grid_day")

    # Build grid data: rows = time slots, columns = courts (showing both halves)
    grid_data = {}
    for time_slot in DEFAULT_TIME_SLOTS:
        row = {}
        for court in active_courts:
            assigned = []
            for team in all_teams:
                td = st.session_state.team_details.get(team, {})
                if td.get("training_day") == selected_day and td.get("training_time") == time_slot and td.get("court") == court:
                    half = td.get("court_half", "A")
                    assigned.append(f"{team} ({half})")
            row[court] = " | ".join(assigned) if assigned else "—"
        grid_data[time_slot] = row

    grid_df = pd.DataFrame(grid_data).T
    grid_df.index.name = "Time Slot"

    st.dataframe(grid_df, use_container_width=True, height=250)

    # Export court plan
    col_exp1, col_exp2 = st.columns([1, 3])
    with col_exp1:
        csv_export = grid_df.to_csv()
        st.download_button("📥 Export Court Plan (CSV)", data=csv_export, file_name=f"court_plan_{selected_day}.csv", mime="text/csv")
    with col_exp2:
        # Show available slots count
        total_slots = len(DEFAULT_TIME_SLOTS) * len(active_courts) * 2  # 2 halves per court
        used_slots = sum(1 for team in all_teams if st.session_state.team_details.get(team, {}).get("training_day") == selected_day and st.session_state.team_details.get(team, {}).get("court"))
        st.metric("Available Slots", f"{total_slots - used_slots}/{total_slots}", delta=f"{used_slots} used")

    # Synergy check: teams at same time slot
    st.subheader("🤝 Age Group Synergy Check")
    for time_slot in DEFAULT_TIME_SLOTS:
        teams_at_time = []
        for team in all_teams:
            td = st.session_state.team_details.get(team, {})
            if td.get("training_day") == selected_day and td.get("training_time") == time_slot:
                teams_at_time.append(team)
        if len(teams_at_time) > 1:
            # Extract age groups
            age_groups_at_time = set()
            for t in teams_at_time:
                # Parse age from team name e.g. B10.1 -> 10
                import re
                match = re.search(r'[BG](\d+)', t)
                if match:
                    age_groups_at_time.add(match.group(1))
            if len(age_groups_at_time) == 1:
                st.success(f"✅ **{time_slot}**: {', '.join(teams_at_time)} — same age group training together!")
            else:
                st.info(f"ℹ️ **{time_slot}**: {', '.join(teams_at_time)} — mixed age groups ({', '.join(sorted(age_groups_at_time))})")

    # --- Team Assignment List (original functionality) ---
    st.divider()
    st.subheader("📝 Assign Training Details per Team")

    # Column headers
    hcol1, hcol2, hcol3, hcol4, hcol5 = st.columns([2, 2, 2, 2, 1])
    with hcol1:
        st.markdown("**Team**")
    with hcol2:
        st.markdown("**Day**")
    with hcol3:
        st.markdown("**Time**")
    with hcol4:
        st.markdown("**Court**")
    with hcol5:
        st.markdown("**Half**")

    for team in all_teams:
        details = st.session_state.team_details.get(team, {})
        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])
        with col1:
            st.write(f"**{team}**")
        with col2:
            day_options = [""] + DEFAULT_TRAINING_DAYS
            current_day = details.get("training_day", "")
            day_idx = day_options.index(current_day) if current_day in day_options else 0
            details["training_day"] = st.selectbox(
                "Day", day_options, index=day_idx, key=f"day_{team}", label_visibility="collapsed"
            )
        with col3:
            time_options = [""] + DEFAULT_TIME_SLOTS
            current_time = details.get("training_time", "")
            time_idx = time_options.index(current_time) if current_time in time_options else 0
            details["training_time"] = st.selectbox(
                "Time", time_options, index=time_idx, key=f"time_{team}", label_visibility="collapsed"
            )
        with col4:
            court_options = [""] + active_courts
            current_court = details.get("court", "")
            court_idx = court_options.index(current_court) if current_court in court_options else 0
            details["court"] = st.selectbox(
                "Court", court_options, index=court_idx, key=f"court_{team}", label_visibility="collapsed"
            )
        with col5:
            half_options = ["A", "B"]
            current_half = details.get("court_half", "A")
            half_idx = half_options.index(current_half) if current_half in half_options else 0
            details["court_half"] = st.selectbox(
                "Half", half_options, index=half_idx, key=f"half_{team}", label_visibility="collapsed"
            )

        # Grading group
        grading_options = [""] + GRADING_GROUPS
        current_grading = details.get("grading_group", "")
        grading_idx = grading_options.index(current_grading) if current_grading in grading_options else 0
        details["grading_group"] = st.selectbox(
            f"Grading Group for {team}", grading_options, index=grading_idx, key=f"grade_{team}"
        )

        st.session_state.team_details[team] = details

    # Coach clash detection
    st.divider()
    st.subheader("⚠️ Coach Clash Detection")
    clashes = detect_coach_clashes(st.session_state.team_details)
    if clashes:
        for coach, teams in clashes:
            st.warning(f"**{coach}** is assigned to multiple teams: {', '.join(teams)}")
    else:
        st.success("No coach clashes detected.")


# --- Page: Email Generator ---
def page_email_generator():
    st.header("📧 Email Generator")

    df = st.session_state.participants_df
    if df is None:
        st.warning("Please upload participants data first.")
        return

    all_teams = sorted(set(
        t for t in st.session_state.team_assignments.values() if t != "Unassigned"
    ))

    if not all_teams:
        st.info("No teams assigned yet. Build teams first.")
        return

    selected_team = st.selectbox("Select Team", all_teams)
    details = st.session_state.team_details.get(selected_team, {})

    # Build player list
    team_pids = [
        pid for pid, t in st.session_state.team_assignments.items() if t == selected_team
    ]
    team_players_df = df[df[COL_PROFILE_ID].astype(str).isin(team_pids)]

    player_lines = []
    for _, p in team_players_df.iterrows():
        name = f"{p[COL_FIRST_NAME]} {p[COL_LAST_NAME]}"
        email = p.get(COL_PARENT1_EMAIL, p.get(COL_ACCOUNT_EMAIL, ""))
        phone = p.get(COL_PARENT1_MOBILE, p.get(COL_ACCOUNT_MOBILE, ""))
        if pd.notna(email) and pd.notna(phone):
            player_lines.append(f"{name} - {email} ({phone})")
        elif pd.notna(email):
            player_lines.append(f"{name} - {email}")
        else:
            player_lines.append(name)

    player_list_str = "\n".join(player_lines)

    # Generate email
    email_body = EMAIL_TEMPLATE.format(
        season=st.session_state.season,
        year=st.session_state.year,
        coach_name=details.get("coach_name", "TBC"),
        first_game_info=st.session_state.first_game_info,
        training_time=details.get("training_time", "TBC"),
        training_day=details.get("training_day", "TBC"),
        court=details.get("court", "TBC"),
        player_list=player_list_str,
        signoff_block=st.session_state.signoff_block,
    )

    st.subheader(f"Email for {selected_team}")
    st.text_area("Email Body", value=email_body, height=500, key=f"email_{selected_team}")

    # Recipients
    st.subheader("Recipients")
    recipients = []
    for _, p in team_players_df.iterrows():
        email = p.get(COL_PARENT1_EMAIL, "")
        if pd.notna(email) and str(email).strip():
            recipients.append(str(email).strip())
        acct_email = p.get(COL_ACCOUNT_EMAIL, "")
        if pd.notna(acct_email) and str(acct_email).strip() and str(acct_email).strip() != str(email).strip():
            recipients.append(str(acct_email).strip())

    st.code("; ".join(set(recipients)))

    # Subject line
    subject = f"Team Placement - {selected_team} | {st.session_state.season} {st.session_state.year}"
    st.text_input("Subject Line", value=subject, key=f"subject_{selected_team}")

    # Export
    import urllib.parse
    col1, col2, col3 = st.columns(3)
    with col1:
        # Build mailto link
        to_addresses = ";".join(set(recipients))
        mailto_params = urllib.parse.urlencode({
            "subject": subject,
            "body": email_body,
        }, quote_via=urllib.parse.quote)
        mailto_link = f"mailto:{to_addresses}?{mailto_params}"
        st.markdown(
            f'<a href="{mailto_link}" target="_blank">'
            f'<button style="background-color:#4CAF50;color:white;padding:0.5rem 1rem;'
            f'border:none;border-radius:4px;cursor:pointer;font-size:1rem;">'
            f'📨 Open in Email Client</button></a>',
            unsafe_allow_html=True,
        )
    with col2:
        if st.button("📋 Copy Email to Clipboard", key=f"copy_{selected_team}"):
            st.write("Use Ctrl+A in the text area above, then Ctrl+C")
    with col3:
        st.download_button(
            "⬇️ Download as .txt",
            data=email_body,
            file_name=f"email_{selected_team}.txt",
            mime="text/plain",
        )


# --- Page: Compliance ---
def page_compliance():
    st.header("🛡️ Compliance — Birth Certificate Verification")

    prev_df = st.session_state.previous_season_df
    curr_df = st.session_state.participants_df

    if curr_df is None:
        st.warning("Please upload the **Current Season** file on the Upload Data page first.")
        return

    if prev_df is None:
        st.info("No previous season file uploaded. All players in the current file will be treated as needing verification.")
        st.caption("If this is your first season using the app, upload the current file as both Previous and Current on the Upload Data page to mark everyone as verified.")
        # Treat all current players as new
        new_players = curr_df.copy()
    else:
        # Compare: anyone in current NOT in previous = new player
        prev_ids = set(prev_df[COL_PROFILE_ID].astype(str))
        curr_df_copy = curr_df.copy()
        curr_df_copy[COL_PROFILE_ID] = curr_df_copy[COL_PROFILE_ID].astype(str)
        new_players = curr_df_copy[~curr_df_copy[COL_PROFILE_ID].isin(prev_ids)]

    # Filter to players only
    if "Role" in new_players.columns:
        new_players = new_players[new_players["Role"] == "Player"]

    if new_players.empty:
        st.success("✅ All players in the current season file exist in the previous season. No new verifications needed.")
        return

    # Build display
    display_rows = []
    for _, p in new_players.iterrows():
        pid = str(p[COL_PROFILE_ID])
        sighted = st.session_state.birth_cert_sighted.get(pid, False)
        raw_phone = p.get(COL_PARENT1_MOBILE, "")
        # Format phone: convert float like 432530377.0 to "0432530377"
        if pd.notna(raw_phone) and str(raw_phone).strip():
            phone_str = str(int(float(raw_phone))) if '.' in str(raw_phone) else str(raw_phone).strip()
            if not phone_str.startswith("0"):
                phone_str = "0" + phone_str
        else:
            phone_str = ""
        display_rows.append({
            "Profile ID": pid,
            "Player Name": f"{p[COL_FIRST_NAME]} {p[COL_LAST_NAME]}",
            "DOB": p.get(COL_DOB, ""),
            "Gender": p.get(COL_GENDER, ""),
            "Parent/Guardian": f"{p.get(COL_PARENT1_FIRST, '')} {p.get(COL_PARENT1_LAST, '')}".strip(),
            "Parent Mobile": phone_str,
            "Parent Email": p.get(COL_PARENT1_EMAIL, ""),
            "Sighted": sighted,
        })

    # Summary metrics
    sighted_count = sum(1 for r in display_rows if r["Sighted"])
    outstanding = len(display_rows) - sighted_count

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🆕 New Players", len(display_rows))
    with col2:
        st.metric("✅ Sighted", sighted_count)
    with col3:
        st.metric("⏳ Outstanding", outstanding)

    if outstanding == 0:
        st.success("🎉 All new players have had their birth certificates verified!")

    st.divider()

    # Filter view
    show_filter = st.radio("Show", ["⏳ Outstanding only", "✅ Sighted only", "All"], horizontal=True)

    if show_filter == "⏳ Outstanding only":
        filtered = [r for r in display_rows if not r["Sighted"]]
    elif show_filter == "✅ Sighted only":
        filtered = [r for r in display_rows if r["Sighted"]]
    else:
        filtered = display_rows

    # Checkboxes for each player
    st.markdown("**Tick to confirm birth certificate has been sighted:**")
    for row in filtered:
        pid = row["Profile ID"]
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(
                f"**{row['Player Name']}** — DOB: {row['DOB']} | Gender: {row['Gender']}  \n"
                f"📞 {row['Parent/Guardian']}: {row['Parent Mobile']} | ✉️ {row['Parent Email']}"
            )
        with col2:
            checked = st.checkbox(
                "Sighted ✓",
                value=row["Sighted"],
                key=f"bc_{pid}",
            )
            if checked != st.session_state.birth_cert_sighted.get(pid, False):
                st.session_state.birth_cert_sighted[pid] = checked
                save_current_state()

    # Export outstanding report
    outstanding_rows = [r for r in display_rows if not r["Sighted"]]
    if outstanding_rows:
        st.divider()
        st.subheader("📥 Export Outstanding Report")
        report_df = pd.DataFrame(outstanding_rows).drop(columns=["Sighted"])
        st.dataframe(report_df, use_container_width=True, hide_index=True)

        csv_data = report_df.to_csv(index=False)
        st.download_button(
            "⬇️ Download Outstanding Report (.csv)",
            data=csv_data,
            file_name="birth_cert_outstanding.csv",
            mime="text/csv",
        )


# --- Page: Settings ---
def page_settings():
    st.header("⚙️ Settings")

    st.subheader("Season Configuration")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.season = st.selectbox("Season", ["Autumn", "Spring"],
                                                index=0 if st.session_state.season == "Autumn" else 1,
                                                key="settings_season")
    with col2:
        st.session_state.year = st.number_input("Year", min_value=2020, max_value=2035,
                                                 value=st.session_state.year, key="settings_year")

    st.subheader("Email Sign-off Block")
    st.session_state.signoff_block = st.text_area(
        "Sign-off (appears at bottom of all emails)",
        value=st.session_state.signoff_block,
        height=100,
    )

    st.subheader("First Game Information")
    st.session_state.first_game_info = st.text_input(
        "First game details (used in email template)",
        value=st.session_state.first_game_info,
    )

    st.subheader("Export All Teams (CSV)")
    if st.session_state.participants_df is not None and st.session_state.team_assignments:
        df = st.session_state.participants_df.copy()
        df["Assigned Team"] = df[COL_PROFILE_ID].astype(str).map(st.session_state.team_assignments).fillna("Unassigned")

        export_cols = [COL_FIRST_NAME, COL_LAST_NAME, COL_GENDER, "Calculated Age Group",
                       "Assigned Team", COL_PLAYER_NUMBER, COL_PARENT1_EMAIL, COL_PARENT1_MOBILE]
        export_df = df[[c for c in export_cols if c in df.columns]]

        st.download_button(
            "⬇️ Download Team Assignments CSV",
            data=export_df.to_csv(index=False),
            file_name=f"team_assignments_{st.session_state.season}_{st.session_state.year}.csv",
            mime="text/csv",
        )
    else:
        st.info("Upload data and assign teams to enable export.")


# --- Main Router ---
def main():
    if not st.session_state.authenticated:
        login_page()
        return

    page = sidebar()

    if page == "🏠 Dashboard":
        page_dashboard()
    elif page == "📁 Upload Data":
        page_upload()
    elif page == "👥 Team Builder":
        page_team_builder()
    elif page == "📊 Player Stats":
        page_player_stats()
    elif page == "🏟️ Court Plan":
        page_court_plan()
    elif page == "📧 Email Generator":
        page_email_generator()
    elif page == "🛡️ Compliance":
        page_compliance()
    elif page == "⚙️ Settings":
        page_settings()


if __name__ == "__main__":
    main()
