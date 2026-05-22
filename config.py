"""Configuration constants for the Eltham North Jets Team Builder."""

# --- Admin Access ---
ADMIN_EMAILS = [
    "president@enjbc.org.au",
    "vice.president@enjbc.org.au",
    "secretary@enjbc.org.au",
    "operations@enjbc.org.au",
    "compliance@enjbc.org.au",
]

# --- Age Groups (differ by gender) ---
AGE_GROUPS_BOYS = ["U08", "U10", "U12", "U14", "U16", "U18", "Over 18"]
AGE_GROUPS_GIRLS = ["U08", "U10", "U12", "U14", "U16", "U19", "Over 19"]
AGE_GROUPS = ["U08", "U10", "U12", "U14", "U16", "U18", "U19", "Over 18"]  # Combined for reference

# Season cutoff dates (month, day) - age is calculated as of this date
# Autumn: age at 30 June determines age group
# Spring: age at 31 December determines age group
SEASON_CUTOFFS = {
    "Autumn": (6, 30),   # 30 June
    "Spring": (12, 31),  # 31 December
}

# --- Team Configuration ---
TEAM_SIZE_MIN = 7
TEAM_SIZE_MAX = 8
TEAM_SIZE_WARNING = 9  # Undesirable

GENDER_PREFIX = {"Male": "B", "Female": "G"}

# --- Courts (constants + ability to add custom) ---
DEFAULT_COURTS = [
    "DVSC Court 1",
    "DVSC Court 2",
    "DVSC Court 3",
    "DVSC Court 5",
    "DVSC Court 6",
    "DVSC Court 8",
    "DCCC",
    "CBS Court 3",
    "Parade Court 1",
    "Parade Court 2",
]

# --- Grading Groups ---
MAX_GRADING_GROUPS = 5
GRADING_GROUPS = [f"Group {i}" for i in range(1, MAX_GRADING_GROUPS + 1)]

# --- Training Time Slots ---
DEFAULT_TIME_SLOTS = [
    "4:15-5:15pm",
    "5-6pm",
    "6-7pm",
    "7-8pm",
]

DEFAULT_TRAINING_DAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
]

# --- Email Template ---
EMAIL_TEMPLATE = """Hi Players and Families,
Thank you for your patience whilst we finalised teams. It is with great pleasure I introduce your coach for {season} {year}, {coach_name}. Thank you for volunteering your time and effort to develop and mentor one of our fabulous Jets teams.

Key Information
• First Game: {first_game_info}
• Training: {training_time} {training_day} at {court}

Your Team Members & Contact Details:
{player_list}

• Uniforms: Order via: https://fiddes.com.au/product-tag/eltham-north/
• Team Manager: Please advise via return email if you would like to be our Team Manager! This is a mandatory role for all teams. Teams must have a TM in place prior to round one.

Actions:
• Review the Behaviour and Zero-Tolerance policies on our website: https://www.enjbc.org.au/info-policies.

Kind Regards,
{signoff_block}"""

# --- Key Columns from Participants CSV ---
COL_PROFILE_ID = "Profile ID"
COL_FIRST_NAME = "First Name"
COL_LAST_NAME = "Last Name"
COL_PREFERRED_NAME = "Preferred Name"
COL_DOB = "Date of Birth"
COL_GENDER = "Gender"
COL_PLAYER_NUMBER = "Player Number"
COL_NEW_TO_CLUB = "New To Club"
COL_NEW_TO_ASSOCIATION = "New To Association"
COL_SCHOOL = "School Details"
COL_SCHOOL_YEAR = "School Year"
COL_REQUESTS = "Please add your requests or any information you would like the club to consider or be aware of"
COL_FEEDBACK = "Any feedback you would like to provide the club"
COL_COACHING_INTEREST = "Are you parent or player interested in coaching"
COL_PARENT1_FIRST = "Parent/Guardian1 First Name"
COL_PARENT1_LAST = "Parent/Guardian1 Last Name"
COL_PARENT1_MOBILE = "Parent/Guardian1 Mobile Number"
COL_PARENT1_EMAIL = "Parent/Guardian1 Email"
COL_PARENT2_FIRST = "Parent/Guardian2 First Name"
COL_PARENT2_LAST = "Parent/Guardian2 Last Name"
COL_PARENT2_MOBILE = "Parent/Guardian2 Mobile Number"
COL_PARENT2_EMAIL = "Parent/Guardian2 Email"
COL_ACCOUNT_EMAIL = "Account Holder Email"
COL_ACCOUNT_MOBILE = "Account Holder Mobile"

# --- Save File ---
SAVE_FILE = "team_builder_state.json"
MASTER_PARTICIPANTS_FILE = "master_participants.csv"
COMPLIANCE_FILE = "compliance_state.json"
