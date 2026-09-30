"""
🎓 Student Attendance Tracker  -  ONE FILE PROJECT  (Python + Streamlit + JSON)
=================================================================================
This single file contains everything: the app, the sample data and the theme.

WHAT THE APP DOES
  1. Takes student name, roll number, subject, total classes and attended classes
  2. Calculates attendance % = (classes attended / total classes) x 100
  3. Saves everything in a local JSON file (no database)
  4. Shows saved records in a table, with search, filters and download
  5. Lets you edit and delete records, and shows simple charts

HOW TO RUN ON YOUR COMPUTER (Windows)
  1. Save this file as  attendance_tracker.py  inside a folder
  2. Open Command Prompt in that folder and install the libraries:
         python -m pip install streamlit pandas plotly
  3. Start the app (do NOT press F5 in IDLE):
         python -m streamlit run attendance_tracker.py
  4. Open http://localhost:8501 if the browser does not open by itself

FILES THE APP CREATES BY ITSELF (you do not need to make them)
  attendance_data.json    - the local JSON storage. The first time, it is filled with
                            sample students. Set SEED_SAMPLE_DATA = False below, or delete
                            the file, to start with an empty tracker.
  .streamlit/config.toml  - purple theme colors (used from the next start)

requirements.txt  (needed only for deployment - create a file with these 3 lines)
  streamlit>=1.35.0
  pandas>=2.0.0
  plotly>=5.18.0

HOW TO DEPLOY ON STREAMLIT COMMUNITY CLOUD
  1. Create a free GitHub account and a new PUBLIC repository (e.g. attendance-tracker)
  2. Upload two files to it: attendance_tracker.py and requirements.txt
  3. Go to https://share.streamlit.io and sign in with GitHub
  4. Click "Create app" -> choose your repository, branch "main",
     main file path "attendance_tracker.py" -> click "Deploy"
  5. After a minute you get a public link to share
  Note: the disk on Streamlit Cloud is temporary, so new records can disappear when the
  app restarts. Use the "Download JSON" button in the View tab to keep a backup.
"""

import json
import os
import re
import uuid
from datetime import datetime
from html import escape

import pandas as pd
import plotly.express as px
import streamlit as st

# ------------------------------------------------------------------
# 0. SAFETY CHECK  (this app must be started with "streamlit run")
# ------------------------------------------------------------------
# If you press F5 in IDLE you only get warnings. This check explains what to do.
from streamlit.runtime.scriptrunner import get_script_run_ctx

try:
    _ctx = get_script_run_ctx(suppress_warning=True)
except TypeError:  # older Streamlit versions
    _ctx = get_script_run_ctx()

if _ctx is None:
    print("=" * 60)
    print("This is a Streamlit web app, so it cannot run from IDLE (F5).")
    print("Open Command Prompt and run these two lines:")
    print()
    print("    cd " + os.path.dirname(os.path.abspath(__file__)))
    print("    python -m streamlit run " + os.path.basename(__file__))
    print("=" * 60)
    raise SystemExit

# ------------------------------------------------------------------
# 1. SETTINGS
# ------------------------------------------------------------------
st.set_page_config(page_title="Student Attendance Tracker", page_icon="🎓", layout="wide")

# The JSON file is stored next to app.py (works locally and on Streamlit Cloud)
BASE_FOLDER = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_FOLDER, "attendance_data.json")

REQUIRED = 75    # minimum attendance % required by most colleges
WARNING = 65     # between 65 and 75 is "borderline"
MAX_CLASSES = 500

# Text shown in the Status column
STATUS_OK = "✅ Eligible"
STATUS_WARN = "⚠️ Borderline"
STATUS_LOW = "❌ Shortage"
STATUS_COLORS = {STATUS_OK: "#20C997", STATUS_WARN: "#FFA94D", STATUS_LOW: "#FF6B6B"}

# The fields saved for every record (this is our "structure")
FIELDS = ["id", "student_name", "roll_number", "subject",
          "total_classes", "classes_attended", "attendance_percentage", "last_updated"]


# ---- sample data: saved to attendance_data.json the first time you run the app ----
SEED_SAMPLE_DATA = True   # change to False if you want to start with an empty tracker
SAMPLE_ROWS = [
    # (student name, roll number, subject, total classes, classes attended)
    ("Ravi Kumar", "21CSE001", "Data Structures", 40, 36),
    ("Ravi Kumar", "21CSE001", "DBMS", 38, 27),
    ("Sneha Reddy", "21CSE002", "Data Structures", 40, 28),
    ("Sneha Reddy", "21CSE002", "Python Programming", 35, 34),
    ("Arjun Varma", "21CSE003", "DBMS", 38, 22),
    ("Meena Sharma", "21CSE004", "Operating Systems", 42, 39),
]


def make_theme_file():
    """Creates .streamlit/config.toml once, so default widget colors are purple."""
    path = os.path.join(BASE_FOLDER, ".streamlit", "config.toml")
    if not os.path.exists(path):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as file:
                file.write('[theme]\nbase = "light"\nprimaryColor = "#6C5CE7"\n'
                           'backgroundColor = "#F7F8FF"\nsecondaryBackgroundColor = "#ECEEFF"\n'
                           'textColor = "#2D3047"\n')
        except OSError:
            pass   # not important if it cannot be created


# ------------------------------------------------------------------
# 2. JSON FUNCTIONS  (read and write the local file)
# ------------------------------------------------------------------
def load_records():
    """Read all records from the JSON file. Returns an empty list if there is no file yet."""
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        st.error("⚠️ The data file could not be read. It may be damaged.")
        return []


def save_records(records):
    """Write all records into the JSON file."""
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(records, file, indent=4, ensure_ascii=False)


# ------------------------------------------------------------------
# 3. CALCULATION FUNCTIONS
# ------------------------------------------------------------------
def calculate_percentage(attended, total):
    """Attendance % = (classes attended / total classes) x 100"""
    if total <= 0:
        return 0.0
    return round((attended / total) * 100, 2)


def get_status(percentage):
    """Decide the status from the percentage."""
    if percentage >= REQUIRED:
        return STATUS_OK
    if percentage >= WARNING:
        return STATUS_WARN
    return STATUS_LOW


def get_advice(attended, total):
    """Tell the student how many classes they can miss, or must attend, to stay at 75%."""
    percentage = calculate_percentage(attended, total)
    if percentage >= REQUIRED:
        # largest y such that attended / (total + y) >= 75%   (integer maths, no rounding errors)
        can_miss = (100 * attended - REQUIRED * total) // REQUIRED
        return f"🎉 You can still miss {can_miss} class(es) and stay at {REQUIRED}% or above."
    # smallest x such that (attended + x) / (total + x) >= 75%
    top = REQUIRED * total - 100 * attended
    need = -((-top) // (100 - REQUIRED))   # rounds up
    return f"📢 Attend the next {need} class(es) in a row to reach {REQUIRED}%."


def build_record(name, roll, subject, total, attended, record_id=None):
    """Create one record (a Python dictionary) in the structure we save in JSON."""
    return {
        "id": record_id or str(uuid.uuid4())[:8],
        "student_name": " ".join(name.split()),
        "roll_number": roll.strip().upper(),
        "subject": " ".join(subject.split()),
        "total_classes": int(total),
        "classes_attended": int(attended),
        "attendance_percentage": calculate_percentage(attended, total),
        "last_updated": datetime.now().strftime("%d %b %Y, %I:%M %p"),
    }


def create_sample_file():
    """Fill the JSON file with the sample students (only used when the file does not exist)."""
    sample = []
    for number, (name, roll, subject, total, attended) in enumerate(SAMPLE_ROWS, start=1):
        sample.append(build_record(name, roll, subject, total, attended, record_id=f"demo{number:04d}"))
    save_records(sample)


# ------------------------------------------------------------------
# 4. VALIDATION  (returns a list of problems; empty list = all good)
# ------------------------------------------------------------------
def validate_inputs(name, roll, subject, total, attended, records, ignore_id=None):
    errors = []
    name, roll, subject = name.strip(), roll.strip(), subject.strip()

    if not name:
        errors.append("Student name cannot be empty.")
    elif not re.fullmatch(r"[A-Za-z][A-Za-z .'-]*", name):
        errors.append("Student name can contain only letters, spaces and . ' -")

    if not roll:
        errors.append("Roll number cannot be empty.")
    elif not re.fullmatch(r"[A-Za-z0-9/-]+", roll):
        errors.append("Roll number can contain only letters, numbers, - and /")

    if not subject:
        errors.append("Subject name cannot be empty.")
    elif len(subject) < 2:
        errors.append("Subject name is too short.")

    if total <= 0:
        errors.append("Total number of classes must be greater than 0.")
    if attended > total:
        errors.append("Classes attended cannot be greater than total classes.")

    # the same roll number + subject should be saved only once
    for record in records:
        same_student = record["roll_number"].lower() == roll.lower()
        same_subject = record["subject"].lower() == " ".join(subject.split()).lower()
        if same_student and same_subject and record["id"] != ignore_id:
            errors.append("A record for this roll number and subject already exists. Use the ✏️ Edit tab to change it.")
            break
    return errors


# ------------------------------------------------------------------
# 5. TABLE HELPERS  (turn records into a pandas table)
# ------------------------------------------------------------------
def records_to_dataframe(records):
    """Convert the list of dictionaries into a table and add the Status column."""
    df = pd.DataFrame(records, columns=FIELDS)
    # always recalculate, so the numbers are correct even if the file was edited by hand
    df["attendance_percentage"] = [calculate_percentage(a, t)
                                   for a, t in zip(df["classes_attended"], df["total_classes"])]
    df["status"] = df["attendance_percentage"].map(get_status)
    return df


def show_table(df):
    """Show a clean table with a colorful progress bar for the attendance %."""
    table = df[["roll_number", "student_name", "subject", "total_classes",
                "classes_attended", "attendance_percentage", "status"]].copy()
    table.columns = ["Roll No", "Student Name", "Subject", "Total Classes",
                     "Classes Attended", "Attendance (%)", "Status"]
    st.dataframe(
        table, hide_index=True,
        column_config={
            "Attendance (%)": st.column_config.ProgressColumn(
                "Attendance (%)", min_value=0, max_value=100, format="%.2f"),
        },
    )


def card_html(css_class, title, value, note=""):
    """One colorful summary card."""
    return (f'<div class="card {css_class}"><h4>{title}</h4>'
            f'<h2>{value}</h2><small>{note}</small></div>')


def result_card(record):
    """Big colorful card that shows the calculated attendance percentage."""
    pct = record["attendance_percentage"]
    status = get_status(pct)
    css = {STATUS_OK: "good", STATUS_WARN: "warn", STATUS_LOW: "bad"}[status]
    advice = get_advice(record["classes_attended"], record["total_classes"])
    st.markdown(
        f"""
        <div class="result {css}">
            <div class="result-small">{escape(record['student_name'])} ({escape(record['roll_number'])})
                 &nbsp;•&nbsp; {escape(record['subject'])}</div>
            <div class="result-big">{pct:.2f}%</div>
            <div class="result-small">{record['classes_attended']} attended out of {record['total_classes']} classes
                 &nbsp;•&nbsp; <b>{status}</b></div>
            <div class="result-small" style="margin-top:8px;">{advice}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------------
# 6. STYLE  (colors for the banner, cards and result box)
# ------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* ---------- clean light look (same on every computer) ---------- */
    .stApp { background: #F7F8FF; }
    header[data-testid="stHeader"] { background: transparent; }
    .stApp, .stApp p, .stApp label, .stApp span, .stApp li,
    .stApp h1, .stApp h2, .stApp h3, .stApp h4 { color: #2D3047; }
    input, textarea, div[data-baseweb="select"] > div, div[data-baseweb="input"],
    [data-testid="stNumberInput"] button {
        background-color: #FFFFFF !important; color: #2D3047 !important; border-color: #D9DEFF !important;
    }
    div[data-baseweb="popover"] *, div[data-baseweb="menu"] * { color: #2D3047 !important; }
    div[data-baseweb="popover"] > div, div[data-baseweb="menu"], div[data-baseweb="popover"] ul {
        background-color: #FFFFFF !important;
    }
    span[data-baseweb="tag"] { background-color: #6C5CE7 !important; }
    span[data-baseweb="tag"] * { color: #FFFFFF !important; }
    div[data-testid="stForm"] {
        background: #FFFFFF; border: 2px solid #D9DEFF; border-radius: 18px;
        box-shadow: 0 4px 16px rgba(108, 92, 231, 0.12);
    }
    .stButton button, div[data-testid="stFormSubmitButton"] button,
    div[data-testid="stDownloadButton"] button {
        background: linear-gradient(90deg, #6C5CE7, #339AF0, #20C997) !important;
        color: #FFFFFF !important; border: none !important; border-radius: 12px; font-weight: 700;
    }
    .stButton button *, div[data-testid="stFormSubmitButton"] button *,
    div[data-testid="stDownloadButton"] button * { color: #FFFFFF !important; }
    button[data-baseweb="tab"][aria-selected="true"] p { color: #6C5CE7 !important; font-weight: 800; }

    .banner {
        background: linear-gradient(90deg, #6C5CE7, #339AF0, #20C997);
        padding: 24px; border-radius: 20px; text-align: center; margin-bottom: 20px;
        box-shadow: 0 8px 24px rgba(108, 92, 231, 0.3);
    }
    .banner h1 { color: white !important; margin: 0; font-size: 2.3rem; }
    .banner p { color: white !important; margin: 6px 0 0 0; font-size: 1.05rem; opacity: 0.95; }

    .card { border-radius: 16px; padding: 16px 10px; text-align: center; color: white;
            box-shadow: 0 4px 14px rgba(0,0,0,0.15); margin-bottom: 14px; }
    .card h4 { margin: 0; color: white !important; font-size: 1rem; opacity: .92; }
    .card h2 { margin: 6px 0 2px 0; color: white !important; font-size: 1.9rem; }
    .card small { color: white !important; opacity: .9; }
    .c1 { background: linear-gradient(135deg, #845EF7, #CC5DE8); }
    .c2 { background: linear-gradient(135deg, #339AF0, #4263EB); }
    .c3 { background: linear-gradient(135deg, #20C997, #12B886); }
    .c4 { background: linear-gradient(135deg, #FFA94D, #FF6B6B); }

    .result { border-radius: 20px; padding: 22px; text-align: center; color: white; margin-top: 14px;
              box-shadow: 0 6px 20px rgba(0,0,0,0.18); }
    .result-big { font-size: 3.4rem; font-weight: 800; line-height: 1.1; color: white; }
    .result-small { font-size: 1.05rem; color: white; }
    .good { background: linear-gradient(135deg, #20C997, #12B886); }
    .warn { background: linear-gradient(135deg, #FFA94D, #F59F00); }
    .bad  { background: linear-gradient(135deg, #FF6B6B, #F06595); }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------
# 7. SESSION STATE + PAGE HEADER
# ------------------------------------------------------------------
if "message" not in st.session_state:
    st.session_state.message = None        # message shown after save / update / delete
if "last_result" not in st.session_state:
    st.session_state.last_result = None    # last saved record (for the result card)
if "form_version" not in st.session_state:
    st.session_state.form_version = 0      # changing this number gives a fresh, empty form


def flash(text):
    st.session_state.message = text


st.markdown(
    '<div class="banner"><h1>🎓 Student Attendance Tracker</h1>'
    '<p>Record attendance • Calculate percentage automatically • Track shortages</p></div>',
    unsafe_allow_html=True,
)

if st.session_state.message:
    st.success(st.session_state.message)
    st.session_state.message = None

# Create the theme file and the sample JSON file if they do not exist yet
make_theme_file()
if SEED_SAMPLE_DATA and not os.path.exists(DATA_FILE):
    create_sample_file()

# Load data and show summary cards
records = load_records()
df = records_to_dataframe(records)

total_records = len(df)
total_students = df["roll_number"].nunique()
average = df["attendance_percentage"].mean() if total_records else 0.0
shortage_count = int((df["attendance_percentage"] < REQUIRED).sum()) if total_records else 0

c1, c2, c3, c4 = st.columns(4)
c1.markdown(card_html("c1", "📚 Records", total_records, "saved in JSON file"), unsafe_allow_html=True)
c2.markdown(card_html("c2", "🧑‍🎓 Students", total_students, "unique roll numbers"), unsafe_allow_html=True)
c3.markdown(card_html("c3", "📊 Average Attendance", f"{average:.1f}%", "of all records"), unsafe_allow_html=True)
c4.markdown(card_html("c4", f"🚨 Below {REQUIRED}%", shortage_count, "need attention"), unsafe_allow_html=True)

# ------------------------------------------------------------------
# 8. TABS
# ------------------------------------------------------------------
tab_add, tab_view, tab_edit, tab_charts = st.tabs(
    ["➕ Add Attendance", "📋 View Records", "✏️ Edit / Delete", "📈 Analysis"]
)

# ---------- ADD (custom form) ----------
with tab_add:
    st.subheader("➕ Enter attendance details")
    v = st.session_state.form_version   # used in the widget keys so the form can be cleared

    with st.form("attendance_form"):
        left, right = st.columns(2)
        name = left.text_input("👤 Student Name", placeholder="e.g. Ravi Kumar", key=f"name_{v}")
        roll = right.text_input("🎫 Roll Number", placeholder="e.g. 21CSE001", key=f"roll_{v}")
        subject = left.text_input("📘 Subject Name", placeholder="e.g. Data Structures", key=f"subject_{v}")
        total = right.number_input("🏫 Total Number of Classes", min_value=0, max_value=MAX_CLASSES,
                                   step=1, value=0, key=f"total_{v}")
        attended = left.number_input("✅ Number of Classes Attended", min_value=0, max_value=MAX_CLASSES,
                                     step=1, value=0, key=f"attended_{v}")
        right.info("📐 Attendance % = (Classes Attended ÷ Total Classes) × 100")
        submitted = st.form_submit_button("💾 Save & Calculate")

    if submitted:
        problems = validate_inputs(name, roll, subject, total, attended, records)
        if problems:
            for problem in problems:
                st.error("❌ " + problem)
        else:
            new_record = build_record(name, roll, subject, total, attended)
            records.append(new_record)
            save_records(records)
            st.session_state.last_result = new_record
            st.session_state.form_version += 1      # clears the form
            flash("✅ Attendance saved successfully!")
            st.rerun()

    if st.session_state.last_result:
        st.markdown("#### 🎯 Result")
        result_card(st.session_state.last_result)

# ---------- VIEW ----------
with tab_view:
    st.subheader("📋 Saved attendance records")
    if df.empty:
        st.info("No records yet. Add your first record in the ➕ tab.")
    else:
        f1, f2, f3 = st.columns(3)
        search = f1.text_input("🔎 Search by name or roll number")
        subjects = f2.multiselect("📘 Subject", sorted(df["subject"].unique()))
        statuses = f3.multiselect("🚦 Status", [STATUS_OK, STATUS_WARN, STATUS_LOW])

        view = df.copy()
        if search.strip():
            text = search.strip()
            view = view[view["student_name"].str.contains(text, case=False, regex=False)
                        | view["roll_number"].str.contains(text, case=False, regex=False)]
        if subjects:
            view = view[view["subject"].isin(subjects)]
        if statuses:
            view = view[view["status"].isin(statuses)]

        view = view.sort_values(["roll_number", "subject"])
        if view.empty:
            st.warning("😕 No records match your search or filters.")
        else:
            show_table(view)
            st.caption(f"Showing {len(view)} of {len(df)} records")

        # backup buttons
        d1, d2, _ = st.columns([1, 1, 3])
        d1.download_button("⬇️ Download JSON", json.dumps(records, indent=4, ensure_ascii=False),
                           file_name="attendance_data.json", mime="application/json")
        d2.download_button("⬇️ Download CSV", df.drop(columns=["id"]).to_csv(index=False).encode("utf-8-sig"),
                           file_name="attendance_data.csv", mime="text/csv")

# ---------- EDIT / DELETE ----------
with tab_edit:
    st.subheader("✏️ Edit or 🗑️ delete a record")
    if df.empty:
        st.info("Nothing to edit yet.")
    else:
        ordered = df.sort_values(["roll_number", "subject"])
        labels = {row["id"]: f"{row['roll_number']}  |  {row['student_name']}  |  {row['subject']}  ({row['attendance_percentage']:.2f}%)"
                  for _, row in ordered.iterrows()}
        selected_id = st.selectbox("Choose a record", list(labels.keys()), format_func=lambda i: labels[i])
        old = next(r for r in records if r["id"] == selected_id)

        # the key has the record id, so the form refreshes when another record is chosen
        with st.form(f"edit_form_{selected_id}"):
            left, right = st.columns(2)
            new_name = left.text_input("👤 Student Name", value=old["student_name"])
            new_roll = right.text_input("🎫 Roll Number", value=old["roll_number"])
            new_subject = left.text_input("📘 Subject Name", value=old["subject"])
            new_total = right.number_input("🏫 Total Number of Classes", min_value=0, max_value=MAX_CLASSES,
                                           step=1, value=int(old["total_classes"]))
            new_attended = left.number_input("✅ Number of Classes Attended", min_value=0, max_value=MAX_CLASSES,
                                             step=1, value=int(old["classes_attended"]))
            update_clicked = st.form_submit_button("💾 Update Record")

        if update_clicked:
            problems = validate_inputs(new_name, new_roll, new_subject, new_total, new_attended,
                                       records, ignore_id=selected_id)
            if problems:
                for problem in problems:
                    st.error("❌ " + problem)
            else:
                updated = build_record(new_name, new_roll, new_subject, new_total, new_attended, selected_id)
                records = [updated if r["id"] == selected_id else r for r in records]
                save_records(records)
                st.session_state.last_result = updated
                flash("✅ Record updated!")
                st.rerun()

        st.markdown("---")
        sure = st.checkbox("I am sure I want to delete this record")
        if st.button("🗑️ Delete Record"):
            if sure:
                records = [r for r in records if r["id"] != selected_id]
                save_records(records)
                st.session_state.last_result = None
                flash("🗑️ Record deleted.")
                st.rerun()
            else:
                st.error("Please tick the confirmation box first.")

# ---------- ANALYSIS ----------
with tab_charts:
    st.subheader("📈 Attendance analysis")
    if df.empty:
        st.info("Add some records to see charts.")
    else:
        left, right = st.columns(2)

        # chart 1: average attendance of each subject
        with left:
            by_subject = df.groupby("subject", as_index=False)["attendance_percentage"].mean()
            fig1 = px.bar(by_subject, x="subject", y="attendance_percentage", color="subject",
                          labels={"subject": "Subject", "attendance_percentage": "Average Attendance (%)"},
                          title="📚 Average Attendance by Subject")
            fig1.add_hline(y=REQUIRED, line_dash="dash", line_color="#FF6B6B",
                           annotation_text=f"{REQUIRED}% required")
            fig1.update_layout(showlegend=False, yaxis_range=[0, 100])
            st.plotly_chart(fig1)

        # chart 2: how many records are eligible / borderline / shortage
        with right:
            by_status = df["status"].value_counts().reset_index()
            by_status.columns = ["status", "count"]
            fig2 = px.pie(by_status, names="status", values="count", hole=0.45,
                          color="status", color_discrete_map=STATUS_COLORS,
                          title="🚦 Attendance Status")
            st.plotly_chart(fig2)

        # student report: overall attendance of one student
        st.markdown("#### 🧑‍🎓 Student report")
        students = df.drop_duplicates("roll_number").sort_values("roll_number")
        choices = {row["roll_number"]: f"{row['roll_number']}  |  {row['student_name']}"
                   for _, row in students.iterrows()}
        chosen_roll = st.selectbox("Choose a student", list(choices.keys()), format_func=lambda r: choices[r])
        one = df[df["roll_number"] == chosen_roll]
        overall = calculate_percentage(one["classes_attended"].sum(), one["total_classes"].sum())
        css = {STATUS_OK: "c3", STATUS_WARN: "c4", STATUS_LOW: "c4"}[get_status(overall)]
        r1, r2 = st.columns([1, 2])
        r1.markdown(card_html(css, "Overall Attendance", f"{overall:.2f}%",
                              f"{one['classes_attended'].sum()} of {one['total_classes'].sum()} classes"),
                    unsafe_allow_html=True)
        with r2:
            show_table(one)

        # students who need attention
        st.markdown(f"#### 🚨 Records below {REQUIRED}%")
        low = df[df["attendance_percentage"] < REQUIRED].sort_values("attendance_percentage")
        if low.empty:
            st.success("🎉 Everyone is above the required attendance!")
        else:
            show_table(low)
