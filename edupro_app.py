"""
EduPro — Learner Demographics & Course Enrollment Behavior Dashboard
Run: streamlit run edupro_app.py
Expects an Excel file with three sheets: Users, Courses, Transactions
"""

import streamlit as st
import pandas as pd
try:
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
except ImportError:
    import subprocess
    subprocess.run(["pip", "install", "plotly"], check=True)
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
import numpy as np

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EduPro Analytics",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Theme colours ─────────────────────────────────────────────────────────────
C_BLUE   = "#3266AD"
C_TEAL   = "#1D9E75"
C_CORAL  = "#D85A30"
C_PINK   = "#D4537E"
C_AMBER  = "#BA7517"
C_PURPLE = "#7F77DD"
CAT_COLORS = [C_BLUE, C_TEAL, C_CORAL, C_PINK, C_AMBER, C_PURPLE]
GENDER_COLORS = [C_BLUE, C_PINK, C_PURPLE]
LEVEL_COLORS  = [C_TEAL, C_BLUE, C_CORAL]

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
    [data-testid="metric-container"] { background: #F8F9FB; border-radius: 10px; padding: 12px 16px; }
    .section-header { font-size: 13px; font-weight: 600; color: #888; text-transform: uppercase;
                      letter-spacing: 0.06em; margin: 1.5rem 0 0.75rem; border-bottom: 1px solid #E5E7EB;
                      padding-bottom: 6px; }
    .stTabs [data-baseweb="tab"] { font-size: 14px; }
</style>
""", unsafe_allow_html=True)

AGE_ORDER = ["<18", "18-25", "26-35", "36-45", "45+"]

# ── Synthetic data generator (used when no file is uploaded) ──────────────────
@st.cache_data
def generate_synthetic_data(n_users=2400, seed=42):
    rng = np.random.default_rng(seed)
    categories = ["Technology", "Business", "Design", "Health", "Language", "Science"]
    levels = ["Beginner", "Intermediate", "Advanced"]
    age_bands = ["<18", "18-25", "26-35", "36-45", "45+"]
    genders = ["Male", "Female", "Non-binary"]
    course_types = ["Video", "Text", "Live", "Hybrid"]

    # Users
    users = pd.DataFrame({
        "UserID": range(1, n_users + 1),
        "UserName": [f"User_{i}" for i in range(1, n_users + 1)],
        "Age": rng.integers(15, 65, n_users),
        "Gender": rng.choice(genders, n_users, p=[0.48, 0.44, 0.08]),
    })
    users["AgeGroup"] = pd.cut(
        users["Age"],
        bins=[0, 17, 25, 35, 45, 100],
        labels=age_bands,
    )

    # Courses
    n_courses = 120
    courses = pd.DataFrame({
        "CourseID": range(1, n_courses + 1),
        "CourseName": [f"Course_{i}" for i in range(1, n_courses + 1)],
        "CourseCategory": rng.choice(categories, n_courses),
        "CourseType": rng.choice(course_types, n_courses),
        "CourseLevel": rng.choice(levels, n_courses, p=[0.45, 0.35, 0.20]),
    })

    # Transactions — younger users skew beginner, older skew advanced
    records = []
    txn_id = 1
    for _, user in users.iterrows():
        n_enroll = rng.integers(1, 6)
        age_bias = (user["Age"] - 15) / 50  # 0 → 1
        lvl_probs = [max(0.1, 0.6 - age_bias * 0.5),
                     0.3,
                     max(0.05, 0.1 + age_bias * 0.5)]
        lvl_probs = np.array(lvl_probs)
        lvl_probs /= lvl_probs.sum()
        preferred_lvl = rng.choice(levels, p=lvl_probs)
        pool = courses[courses["CourseLevel"] == preferred_lvl]
        if len(pool) == 0:
            pool = courses
        chosen = pool.sample(min(n_enroll, len(pool)), random_state=int(txn_id))
        for _, course in chosen.iterrows():
            records.append({
                "TransactionID": txn_id,
                "UserID": user["UserID"],
                "CourseID": course["CourseID"],
                "TransactionDate": pd.Timestamp("2024-01-01") + pd.Timedelta(days=int(rng.integers(0, 365))),
            })
            txn_id += 1

    transactions = pd.DataFrame(records)
    return users, courses, transactions


# ── Data loader ───────────────────────────────────────────────────────────────
def age_to_band(age):
    if age < 18:   return "<18"
    if age <= 25:  return "18-25"
    if age <= 35:  return "26-35"
    if age <= 45:  return "36-45"
    return "45+"


@st.cache_data
def load_data(uploaded_file):
    xl = pd.ExcelFile(uploaded_file)
    users = xl.parse("Users")
    courses = xl.parse("Courses")
    transactions = xl.parse("Transactions")
    if "AgeGroup" not in users.columns:
        users["AgeGroup"] = users["Age"].apply(age_to_band)
    return users, courses, transactions


def merge_data(users, courses, transactions):
    df = (
        transactions
        .merge(users[["UserID", "Age", "Gender", "AgeGroup"]], on="UserID", how="left")
        .merge(courses[["CourseID", "CourseCategory", "CourseType", "CourseLevel"]], on="CourseID", how="left")
    )
    df["AgeGroup"] = pd.Categorical(df["AgeGroup"], categories=AGE_ORDER, ordered=True)
    if "TransactionDate" in df.columns:
        df["TransactionDate"] = pd.to_datetime(df["TransactionDate"])
        df["Month"] = df["TransactionDate"].dt.to_period("M").astype(str)
    return df


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎓 EduPro Analytics")
    st.markdown("---")

    uploaded_file = st.file_uploader(
        "Upload your dataset (Excel)",
        type=["xlsx", "xls"],
        help="File must contain three sheets: Users, Courses, Transactions",
    )

    st.markdown("### Filters")

    if uploaded_file:
        users_raw, courses_raw, transactions_raw = load_data(uploaded_file)
    else:
        st.info("Using synthetic demo data. Upload your Excel file above to analyse real data.")
        users_raw, courses_raw, transactions_raw = generate_synthetic_data()

    df_all = merge_data(users_raw, courses_raw, transactions_raw)

    age_opts   = ["All"] + AGE_ORDER
    gender_opts = ["All"] + sorted(df_all["Gender"].dropna().unique().tolist())
    cat_opts   = ["All"] + sorted(df_all["CourseCategory"].dropna().unique().tolist())
    level_opts = ["All"] + ["Beginner", "Intermediate", "Advanced"]

    sel_age    = st.selectbox("Age group", age_opts)
    sel_gender = st.selectbox("Gender", gender_opts)
    sel_cat    = st.selectbox("Course category", cat_opts)
    sel_level  = st.selectbox("Course level", level_opts)

    st.markdown("---")
    st.caption("EduPro · Learner Intelligence Dashboard")


# ── Apply filters ─────────────────────────────────────────────────────────────
df = df_all.copy()
if sel_age    != "All": df = df[df["AgeGroup"]       == sel_age]
if sel_gender != "All": df = df[df["Gender"]          == sel_gender]
if sel_cat    != "All": df = df[df["CourseCategory"]  == sel_cat]
if sel_level  != "All": df = df[df["CourseLevel"]     == sel_level]


# ── Header ────────────────────────────────────────────────────────────────────
st.title("Learner Demographics & Enrollment Behavior")
st.caption("Descriptive learner intelligence for data-driven education planning")

if len(df) == 0:
    st.warning("No data matches the current filters. Please adjust your selections.")
    st.stop()


# ── KPI row ───────────────────────────────────────────────────────────────────
total_enrollments = len(df)
unique_learners   = df["UserID"].nunique()
avg_courses       = round(total_enrollments / max(unique_learners, 1), 1)
top_category      = df["CourseCategory"].mode()[0] if not df.empty else "—"
top_level         = df["CourseLevel"].mode()[0] if not df.empty else "—"
gender_ratio      = df["Gender"].value_counts(normalize=True).mul(100).round(1).to_dict()

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Enrollments",    f"{total_enrollments:,}")
k2.metric("Active Learners",      f"{unique_learners:,}")
k3.metric("Avg Courses / Learner", avg_courses)
k4.metric("Top Category",         top_category)
k5.metric("Top Level",            top_level)


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "👤 Demographics",
    "📚 Course Preferences",
    "🔥 Heatmap Analysis",
    "📈 Behavioral Insights",
])


# ─────────────────────────── TAB 1 — DEMOGRAPHICS ───────────────────────────
with tab1:
    st.markdown('<div class="section-header">Age distribution</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        age_counts = df.groupby("AgeGroup", observed=True).size().reset_index(name="Enrollments")
        fig = px.bar(
            age_counts, x="AgeGroup", y="Enrollments",
            color_discrete_sequence=[C_BLUE],
            labels={"AgeGroup": "Age group", "Enrollments": "Enrollments"},
        )
        fig.update_layout(showlegend=False, plot_bgcolor="white", height=300,
                          margin=dict(t=20, b=20, l=20, r=20))
        fig.update_traces(marker_line_width=0)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Enrollments by age band")

    with c2:
        gender_counts = df["Gender"].value_counts().reset_index()
        gender_counts.columns = ["Gender", "Count"]
        fig2 = px.pie(
            gender_counts, names="Gender", values="Count",
            hole=0.6, color_discrete_sequence=GENDER_COLORS,
        )
        fig2.update_layout(showlegend=True, height=300, margin=dict(t=20, b=20, l=20, r=20))
        fig2.update_traces(textinfo="percent+label")
        st.plotly_chart(fig2, use_container_width=True)
        st.caption("Gender participation ratio")

    st.markdown('<div class="section-header">Gender breakdown by age group</div>', unsafe_allow_html=True)
    age_gender = (
        df.groupby(["AgeGroup", "Gender"], observed=True)
        .size().reset_index(name="Count")
    )
    fig3 = px.bar(
        age_gender, x="AgeGroup", y="Count", color="Gender",
        barmode="group", color_discrete_sequence=GENDER_COLORS,
        labels={"AgeGroup": "Age group", "Count": "Enrollments"},
    )
    fig3.update_layout(plot_bgcolor="white", height=320, margin=dict(t=20, b=20, l=20, r=20))
    st.plotly_chart(fig3, use_container_width=True)


# ──────────────────── TAB 2 — COURSE PREFERENCES ────────────────────────────
with tab2:
    st.markdown('<div class="section-header">Category popularity index</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        cat_counts = df["CourseCategory"].value_counts().reset_index()
        cat_counts.columns = ["Category", "Enrollments"]
        fig = px.bar(
            cat_counts, x="Enrollments", y="Category", orientation="h",
            color="Category", color_discrete_sequence=CAT_COLORS,
        )
        fig.update_layout(showlegend=False, plot_bgcolor="white", height=340,
                          margin=dict(t=20, b=20, l=20, r=20),
                          yaxis=dict(categoryorder="total ascending"))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Most popular course categories")

    with c2:
        level_counts = df["CourseLevel"].value_counts().reindex(
            ["Beginner", "Intermediate", "Advanced"]).reset_index()
        level_counts.columns = ["Level", "Enrollments"]
        fig2 = px.bar(
            level_counts, x="Level", y="Enrollments",
            color="Level", color_discrete_sequence=LEVEL_COLORS,
        )
        fig2.update_layout(showlegend=False, plot_bgcolor="white", height=340,
                           margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig2, use_container_width=True)
        st.caption("Course level preference distribution")

    st.markdown('<div class="section-header">Gender vs course level</div>', unsafe_allow_html=True)
    gl = df.groupby(["Gender", "CourseLevel"]).size().reset_index(name="Count")
    gl["CourseLevel"] = pd.Categorical(gl["CourseLevel"],
                                        categories=["Beginner", "Intermediate", "Advanced"],
                                        ordered=True)
    fig3 = px.bar(
        gl.sort_values("CourseLevel"), x="CourseLevel", y="Count", color="Gender",
        barmode="group", color_discrete_sequence=GENDER_COLORS,
        labels={"CourseLevel": "Course level", "Count": "Enrollments"},
    )
    fig3.update_layout(plot_bgcolor="white", height=320, margin=dict(t=20, b=20, l=20, r=20))
    st.plotly_chart(fig3, use_container_width=True)

    st.markdown('<div class="section-header">Course type distribution</div>', unsafe_allow_html=True)
    if "CourseType" in df.columns:
        ct = df["CourseType"].value_counts().reset_index()
        ct.columns = ["Type", "Count"]
        fig4 = px.pie(ct, names="Type", values="Count", hole=0.5,
                      color_discrete_sequence=CAT_COLORS)
        fig4.update_layout(height=300, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig4, use_container_width=True)


# ─────────────────────────── TAB 3 — HEATMAP ────────────────────────────────
with tab3:
    st.markdown('<div class="section-header">Age group × Course category heatmap</div>', unsafe_allow_html=True)

    hm_data = (
        df.groupby(["AgeGroup", "CourseCategory"], observed=True)
        .size().unstack(fill_value=0)
    )
    hm_data = hm_data.reindex(AGE_ORDER, fill_value=0)

    fig = px.imshow(
        hm_data,
        labels=dict(x="Course category", y="Age group", color="Enrollments"),
        color_continuous_scale="Blues",
        aspect="auto",
        text_auto=True,
    )
    fig.update_layout(height=380, margin=dict(t=20, b=20, l=20, r=20))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Darker = higher enrollment intensity. Reveals which age segments prefer which categories.")

    st.markdown('<div class="section-header">Age group × Course level heatmap</div>', unsafe_allow_html=True)
    hm2 = (
        df.groupby(["AgeGroup", "CourseLevel"], observed=True)
        .size().unstack(fill_value=0)
    )
    hm2 = hm2.reindex(AGE_ORDER, fill_value=0)
    cols_order = [c for c in ["Beginner", "Intermediate", "Advanced"] if c in hm2.columns]
    hm2 = hm2[cols_order]

    fig2 = px.imshow(
        hm2, labels=dict(x="Course level", y="Age group", color="Enrollments"),
        color_continuous_scale="Teal", aspect="auto", text_auto=True,
    )
    fig2.update_layout(height=320, margin=dict(t=20, b=20, l=20, r=20))
    st.plotly_chart(fig2, use_container_width=True)
    st.caption("Shows whether younger learners gravitate to beginner content and older learners to advanced.")


# ──────────────────── TAB 4 — BEHAVIORAL INSIGHTS ───────────────────────────
with tab4:
    st.markdown('<div class="section-header">Monthly enrollment trend</div>', unsafe_allow_html=True)

    if "Month" in df.columns:
        monthly = df.groupby("Month").size().reset_index(name="Enrollments")
        monthly = monthly.sort_values("Month")
        fig = px.line(
            monthly, x="Month", y="Enrollments",
            markers=True, color_discrete_sequence=[C_BLUE],
        )
        fig.update_layout(plot_bgcolor="white", height=280, margin=dict(t=20, b=20, l=20, r=20))
        fig.update_traces(line_width=2.5)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("TransactionDate column not found — monthly trend unavailable.")

    st.markdown('<div class="section-header">Learner engagement distribution</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        courses_per_user = df.groupby("UserID").size().reset_index(name="CoursesEnrolled")
        fig2 = px.histogram(
            courses_per_user, x="CoursesEnrolled", nbins=10,
            color_discrete_sequence=[C_TEAL],
            labels={"CoursesEnrolled": "Courses per learner", "count": "Number of learners"},
        )
        fig2.update_layout(showlegend=False, plot_bgcolor="white", height=280,
                           margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig2, use_container_width=True)
        st.caption("Distribution of enrollment depth across learners")

    with c2:
        top_cats = (
            df.groupby("CourseCategory").agg(
                Enrollments=("CourseID", "count"),
                UniqueUsers=("UserID", "nunique"),
            ).reset_index()
            .sort_values("Enrollments", ascending=False)
        )
        top_cats["AvgPerUser"] = (top_cats["Enrollments"] / top_cats["UniqueUsers"]).round(2)
        st.dataframe(
            top_cats.rename(columns={
                "CourseCategory": "Category",
                "UniqueUsers": "Unique Learners",
                "AvgPerUser": "Avg Courses / Learner",
            }),
            use_container_width=True,
            hide_index=True,
        )
        st.caption("Category-level engagement summary")

    st.markdown('<div class="section-header">Beginner vs advanced learner profile</div>', unsafe_allow_html=True)
    beg = df[df["CourseLevel"] == "Beginner"]["AgeGroup"].value_counts().reindex(AGE_ORDER, fill_value=0)
    adv = df[df["CourseLevel"] == "Advanced"]["AgeGroup"].value_counts().reindex(AGE_ORDER, fill_value=0)

    fig3 = go.Figure()
    fig3.add_trace(go.Bar(name="Beginner", x=AGE_ORDER, y=beg.values,
                           marker_color=C_TEAL, opacity=0.85))
    fig3.add_trace(go.Bar(name="Advanced", x=AGE_ORDER, y=adv.values,
                           marker_color=C_CORAL, opacity=0.85))
    fig3.update_layout(barmode="group", plot_bgcolor="white", height=300,
                        margin=dict(t=20, b=20, l=20, r=20),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02))
    st.plotly_chart(fig3, use_container_width=True)
    st.caption("Compares beginner vs advanced enrollment counts across age groups")

    st.markdown('<div class="section-header">Raw data explorer</div>', unsafe_allow_html=True)
    with st.expander("View filtered dataset"):
        st.dataframe(df.head(500), use_container_width=True)
        st.caption(f"Showing first 500 of {len(df):,} rows")
