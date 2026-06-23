"""
EduPro — Learner Demographics & Course Enrollment Behavior Dashboard
Uses only built-in Streamlit charts (no matplotlib, no plotly)
"""
import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="EduPro Analytics", page_icon="🎓", layout="wide")

st.markdown("""
<style>
.block-container { padding-top: 1.5rem; }
.section-header {
    font-size: 13px; font-weight: 600; color: #666;
    text-transform: uppercase; letter-spacing: 0.06em;
    margin: 1.5rem 0 0.75rem;
    border-bottom: 1px solid #E0E0E0; padding-bottom: 6px;
}
</style>
""", unsafe_allow_html=True)

AGE_ORDER  = ["<18", "18-25", "26-35", "36-45", "45+"]
CATEGORIES = ["Technology", "Business", "Design", "Health", "Language", "Science"]
LEVELS     = ["Beginner", "Intermediate", "Advanced"]
GENDERS    = ["Male", "Female", "Non-binary"]

# ── Synthetic data ────────────────────────────────────────────────────────────
@st.cache_data
def generate_data(n_users=2400, seed=42):
    rng = np.random.default_rng(seed)
    course_types = ["Video", "Text", "Live", "Hybrid"]

    users = pd.DataFrame({
        "UserID": range(1, n_users + 1),
        "Age":    rng.integers(15, 65, n_users),
        "Gender": rng.choice(GENDERS, n_users, p=[0.48, 0.44, 0.08]),
    })
    users["AgeGroup"] = pd.cut(
        users["Age"], bins=[0, 17, 25, 35, 45, 100], labels=AGE_ORDER
    )

    n_courses = 120
    courses = pd.DataFrame({
        "CourseID":       range(1, n_courses + 1),
        "CourseCategory": rng.choice(CATEGORIES, n_courses),
        "CourseType":     rng.choice(course_types, n_courses),
        "CourseLevel":    rng.choice(LEVELS, n_courses, p=[0.45, 0.35, 0.20]),
    })

    records = []
    txn_id = 1
    for _, user in users.iterrows():
        n_enroll = rng.integers(1, 6)
        age_bias = (user["Age"] - 15) / 50
        lp = np.array([max(0.1, 0.6 - age_bias * 0.5), 0.3,
                       max(0.05, 0.1 + age_bias * 0.5)])
        lp /= lp.sum()
        preferred = rng.choice(LEVELS, p=lp)
        pool = courses[courses["CourseLevel"] == preferred]
        if len(pool) == 0:
            pool = courses
        chosen = pool.sample(min(n_enroll, len(pool)), random_state=int(txn_id))
        for _, course in chosen.iterrows():
            records.append({
                "TransactionID":   txn_id,
                "UserID":          user["UserID"],
                "CourseID":        course["CourseID"],
                "TransactionDate": pd.Timestamp("2024-01-01") + pd.Timedelta(
                    days=int(rng.integers(0, 365))),
            })
            txn_id += 1
    return users, courses, pd.DataFrame(records)

def age_to_band(age):
    if age < 18:  return "<18"
    if age <= 25: return "18-25"
    if age <= 35: return "26-35"
    if age <= 45: return "36-45"
    return "45+"

@st.cache_data
def load_data(file):
    xl = pd.ExcelFile(file)
    u  = xl.parse("Users")
    c  = xl.parse("Courses")
    t  = xl.parse("Transactions")
    if "AgeGroup" not in u.columns:
        u["AgeGroup"] = u["Age"].apply(age_to_band)
    return u, c, t

def merge(users, courses, transactions):
    df = (transactions
          .merge(users[["UserID", "Age", "Gender", "AgeGroup"]], on="UserID", how="left")
          .merge(courses[["CourseID", "CourseCategory", "CourseType", "CourseLevel"]],
                 on="CourseID", how="left"))
    df["AgeGroup"] = pd.Categorical(df["AgeGroup"], categories=AGE_ORDER, ordered=True)
    if "TransactionDate" in df.columns:
        df["TransactionDate"] = pd.to_datetime(df["TransactionDate"])
        df["Month"] = df["TransactionDate"].dt.to_period("M").astype(str)
    return df

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎓 EduPro Analytics")
    st.markdown("---")
    uploaded = st.file_uploader(
        "Upload dataset (Excel)", type=["xlsx", "xls"],
        help="Needs sheets: Users, Courses, Transactions"
    )
    st.markdown("### Filters")
    if uploaded:
        u_raw, c_raw, t_raw = load_data(uploaded)
    else:
        st.info("Showing synthetic demo data. Upload your Excel file for real data.")
        u_raw, c_raw, t_raw = generate_data()

    df_all = merge(u_raw, c_raw, t_raw)

    sel_age    = st.selectbox("Age group",       ["All"] + AGE_ORDER)
    sel_gender = st.selectbox("Gender",          ["All"] + GENDERS)
    sel_cat    = st.selectbox("Course category", ["All"] + CATEGORIES)
    sel_level  = st.selectbox("Course level",    ["All"] + LEVELS)
    st.markdown("---")
    st.caption("EduPro · Learner Intelligence Dashboard")

# ── Filter ────────────────────────────────────────────────────────────────────
df = df_all.copy()
if sel_age    != "All": df = df[df["AgeGroup"]      == sel_age]
if sel_gender != "All": df = df[df["Gender"]         == sel_gender]
if sel_cat    != "All": df = df[df["CourseCategory"] == sel_cat]
if sel_level  != "All": df = df[df["CourseLevel"]    == sel_level]

st.title("🎓 EduPro — Learner Demographics & Enrollment Behavior")
st.caption("Descriptive learner intelligence for data-driven education planning")

if len(df) == 0:
    st.warning("No data matches the current filters. Please adjust your selections.")
    st.stop()

# ── KPIs ──────────────────────────────────────────────────────────────────────
total    = len(df)
unique   = df["UserID"].nunique()
avg_c    = round(total / max(unique, 1), 1)
top_cat  = df["CourseCategory"].mode()[0] if total else "—"
top_lvl  = df["CourseLevel"].mode()[0]    if total else "—"

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("📊 Total Enrollments",     f"{total:,}")
k2.metric("👤 Active Learners",       f"{unique:,}")
k3.metric("📚 Avg Courses / Learner", avg_c)
k4.metric("🏆 Top Category",          top_cat)
k5.metric("⭐ Top Level",             top_lvl)

st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "👤 Demographics",
    "📚 Course Preferences",
    "🔥 Heatmap Analysis",
    "📈 Behavioral Insights"
])

# ── TAB 1 — DEMOGRAPHICS ─────────────────────────────────────────────────────
with tab1:
    st.markdown('<div class="section-header">Age Distribution</div>', unsafe_allow_html=True)
    age_counts = (df.groupby("AgeGroup", observed=True)
                  .size().reindex(AGE_ORDER, fill_value=0)
                  .reset_index(name="Enrollments"))
    st.bar_chart(age_counts.set_index("AgeGroup"), use_container_width=True, height=300)

    st.markdown('<div class="section-header">Gender Participation</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        gn = df["Gender"].value_counts().reset_index()
        gn.columns = ["Gender", "Count"]
        st.bar_chart(gn.set_index("Gender"), use_container_width=True, height=250)
        st.caption("Gender enrollment count")
    with c2:
        gn_pct = df["Gender"].value_counts(normalize=True).mul(100).round(1)
        st.dataframe(
            gn_pct.reset_index().rename(columns={"Gender": "Gender", "proportion": "Share %"}),
            use_container_width=True, hide_index=True
        )
        total_m = df[df["Gender"]=="Male"].shape[0]
        total_f = df[df["Gender"]=="Female"].shape[0]
        total_nb = df[df["Gender"]=="Non-binary"].shape[0]
        st.metric("Male",       f"{total_m:,}",  f"{round(total_m/total*100,1)}%")
        st.metric("Female",     f"{total_f:,}",  f"{round(total_f/total*100,1)}%")
        st.metric("Non-binary", f"{total_nb:,}", f"{round(total_nb/total*100,1)}%")

    st.markdown('<div class="section-header">Gender × Age Group</div>', unsafe_allow_html=True)
    ag_gn = (df.groupby(["AgeGroup", "Gender"], observed=True)
               .size().unstack(fill_value=0)
               .reindex(AGE_ORDER, fill_value=0))
    st.bar_chart(ag_gn, use_container_width=True, height=320)

# ── TAB 2 — COURSE PREFERENCES ───────────────────────────────────────────────
with tab2:
    st.markdown('<div class="section-header">Category Popularity Index</div>', unsafe_allow_html=True)
    cat_counts = (df["CourseCategory"].value_counts()
                  .reindex(CATEGORIES, fill_value=0)
                  .reset_index())
    cat_counts.columns = ["Category", "Enrollments"]
    st.bar_chart(cat_counts.set_index("Category"), use_container_width=True, height=300)

    st.markdown('<div class="section-header">Course Level Preference</div>', unsafe_allow_html=True)
    lv = (df["CourseLevel"].value_counts()
          .reindex(LEVELS, fill_value=0)
          .reset_index())
    lv.columns = ["Level", "Enrollments"]
    st.bar_chart(lv.set_index("Level"), use_container_width=True, height=250)

    st.markdown('<div class="section-header">Gender × Course Level</div>', unsafe_allow_html=True)
    gl = (df.groupby(["CourseLevel", "Gender"])
            .size().unstack(fill_value=0)
            .reindex(LEVELS, fill_value=0))
    st.bar_chart(gl, use_container_width=True, height=300)

    if "CourseType" in df.columns:
        st.markdown('<div class="section-header">Course Type Distribution</div>', unsafe_allow_html=True)
        ct = df["CourseType"].value_counts().reset_index()
        ct.columns = ["Type", "Count"]
        st.bar_chart(ct.set_index("Type"), use_container_width=True, height=250)

# ── TAB 3 — HEATMAP ──────────────────────────────────────────────────────────
with tab3:
    st.markdown('<div class="section-header">Age Group × Course Category Heatmap</div>',
                unsafe_allow_html=True)
    hm = (df.groupby(["AgeGroup", "CourseCategory"], observed=True)
            .size().unstack(fill_value=0)
            .reindex(AGE_ORDER, fill_value=0))
    
    # Style heatmap as colored dataframe
    def color_cells(val, max_val):
        intensity = val / max_val if max_val > 0 else 0
        r = int(255 - intensity * 100)
        g = int(255 - intensity * 120)
        b = int(255 - intensity * 50)
        return f"background-color: rgb({r},{g},{b})"

    max_val = hm.values.max()
    styled = hm.style.applymap(lambda v: color_cells(v, max_val)).format("{:.0f}")
    st.dataframe(styled, use_container_width=True)
    st.caption("Darker = higher enrollment intensity")

    st.markdown('<div class="section-header">Age Group × Course Level Heatmap</div>',
                unsafe_allow_html=True)
    hm2 = (df.groupby(["AgeGroup", "CourseLevel"], observed=True)
             .size().unstack(fill_value=0)
             .reindex(AGE_ORDER, fill_value=0)
             .reindex(columns=[c for c in LEVELS if c in
                               df["CourseLevel"].unique()], fill_value=0))
    max_val2 = hm2.values.max()
    styled2 = hm2.style.applymap(lambda v: color_cells(v, max_val2)).format("{:.0f}")
    st.dataframe(styled2, use_container_width=True)
    st.caption("Shows skill level preference by age group")

    st.markdown('<div class="section-header">Age Group × Category — Bar View</div>',
                unsafe_allow_html=True)
    st.bar_chart(hm, use_container_width=True, height=350)

# ── TAB 4 — BEHAVIORAL INSIGHTS ──────────────────────────────────────────────
with tab4:
    if "Month" in df.columns:
        st.markdown('<div class="section-header">Monthly Enrollment Trend</div>',
                    unsafe_allow_html=True)
        monthly = (df.groupby("Month").size()
                   .reset_index(name="Enrollments")
                   .sort_values("Month"))
        st.line_chart(monthly.set_index("Month"), use_container_width=True, height=280)

    st.markdown('<div class="section-header">Courses per Learner Distribution</div>',
                unsafe_allow_html=True)
    cpu = df.groupby("UserID").size().value_counts().sort_index().reset_index()
    cpu.columns = ["Courses Enrolled", "Number of Learners"]
    st.bar_chart(cpu.set_index("Courses Enrolled"), use_container_width=True, height=250)
    st.caption("How many courses each learner has enrolled in")

    st.markdown('<div class="section-header">Category Engagement Summary</div>',
                unsafe_allow_html=True)
    summary = (df.groupby("CourseCategory")
               .agg(Enrollments=("CourseID", "count"),
                    Learners=("UserID", "nunique"))
               .reset_index()
               .sort_values("Enrollments", ascending=False))
    summary["Avg / Learner"] = (summary["Enrollments"] / summary["Learners"]).round(2)
    st.dataframe(summary.rename(columns={"CourseCategory": "Category"}),
                 use_container_width=True, hide_index=True)

    st.markdown('<div class="section-header">Beginner vs Advanced by Age Group</div>',
                unsafe_allow_html=True)
    beg = (df[df["CourseLevel"] == "Beginner"]["AgeGroup"]
           .value_counts().reindex(AGE_ORDER, fill_value=0))
    adv = (df[df["CourseLevel"] == "Advanced"]["AgeGroup"]
           .value_counts().reindex(AGE_ORDER, fill_value=0))
    bv = pd.DataFrame({"Beginner": beg, "Advanced": adv})
    st.bar_chart(bv, use_container_width=True, height=300)
    st.caption("Compares beginner vs advanced enrollment counts across age groups")

    st.markdown('<div class="section-header">Raw Data Explorer</div>',
                unsafe_allow_html=True)
    with st.expander("View filtered dataset"):
        st.dataframe(df.head(500), use_container_width=True)
        st.caption(f"Showing first 500 of {len(df):,} rows")
