"""
EduPro — Learner Demographics & Course Enrollment Behavior Dashboard
Run: streamlit run edupro_app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

st.set_page_config(
    page_title="EduPro Analytics",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
    [data-testid="metric-container"] { background: #F0F4FB; border-radius: 10px; padding: 12px; }
    .section-header { font-size: 13px; font-weight: 600; color: #666;
                      text-transform: uppercase; letter-spacing: 0.06em;
                      margin: 1.5rem 0 0.75rem;
                      border-bottom: 1px solid #E0E0E0; padding-bottom: 6px; }
</style>
""", unsafe_allow_html=True)

AGE_ORDER  = ["<18", "18-25", "26-35", "36-45", "45+"]
CATEGORIES = ["Technology", "Business", "Design", "Health", "Language", "Science"]
LEVELS     = ["Beginner", "Intermediate", "Advanced"]
GENDERS    = ["Male", "Female", "Non-binary"]

C_BLUE   = "#3266AD"
C_TEAL   = "#1D9E75"
C_CORAL  = "#D85A30"
C_PINK   = "#D4537E"
C_AMBER  = "#BA7517"
C_PURPLE = "#7F77DD"
CAT_COLORS    = [C_BLUE, C_TEAL, C_CORAL, C_PINK, C_AMBER, C_PURPLE]
GENDER_COLORS = [C_BLUE, C_PINK, C_PURPLE]
LEVEL_COLORS  = [C_TEAL, C_BLUE, C_CORAL]

def fig_style(ax, title=""):
    ax.set_facecolor("white")
    ax.spines[["top","right"]].set_visible(False)
    ax.spines[["left","bottom"]].set_color("#E0E0E0")
    ax.tick_params(colors="#555", labelsize=9)
    if title:
        ax.set_title(title, fontsize=11, fontweight="bold", color="#333", pad=10)

# ── Synthetic data ────────────────────────────────────────────────────────────
@st.cache_data
def generate_data(n_users=2400, seed=42):
    rng = np.random.default_rng(seed)
    course_types = ["Video", "Text", "Live", "Hybrid"]

    users = pd.DataFrame({
        "UserID": range(1, n_users+1),
        "Age":    rng.integers(15, 65, n_users),
        "Gender": rng.choice(GENDERS, n_users, p=[0.48, 0.44, 0.08]),
    })
    users["AgeGroup"] = pd.cut(users["Age"], bins=[0,17,25,35,45,100], labels=AGE_ORDER)

    n_courses = 120
    courses = pd.DataFrame({
        "CourseID":       range(1, n_courses+1),
        "CourseCategory": rng.choice(CATEGORIES, n_courses),
        "CourseType":     rng.choice(course_types, n_courses),
        "CourseLevel":    rng.choice(LEVELS, n_courses, p=[0.45, 0.35, 0.20]),
    })

    records = []
    txn_id  = 1
    for _, user in users.iterrows():
        n_enroll  = rng.integers(1, 6)
        age_bias  = (user["Age"] - 15) / 50
        lp = np.array([max(0.1, 0.6 - age_bias*0.5), 0.3, max(0.05, 0.1 + age_bias*0.5)])
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
                "TransactionDate": pd.Timestamp("2024-01-01") + pd.Timedelta(days=int(rng.integers(0, 365))),
            })
            txn_id += 1

    transactions = pd.DataFrame(records)
    return users, courses, transactions

def age_to_band(age):
    if age < 18:  return "<18"
    if age <= 25: return "18-25"
    if age <= 35: return "26-35"
    if age <= 45: return "36-45"
    return "45+"

@st.cache_data
def load_data(file):
    xl   = pd.ExcelFile(file)
    u    = xl.parse("Users")
    c    = xl.parse("Courses")
    t    = xl.parse("Transactions")
    if "AgeGroup" not in u.columns:
        u["AgeGroup"] = u["Age"].apply(age_to_band)
    return u, c, t

def merge(users, courses, transactions):
    df = (transactions
          .merge(users[["UserID","Age","Gender","AgeGroup"]], on="UserID", how="left")
          .merge(courses[["CourseID","CourseCategory","CourseType","CourseLevel"]], on="CourseID", how="left"))
    df["AgeGroup"] = pd.Categorical(df["AgeGroup"], categories=AGE_ORDER, ordered=True)
    if "TransactionDate" in df.columns:
        df["TransactionDate"] = pd.to_datetime(df["TransactionDate"])
        df["Month"] = df["TransactionDate"].dt.to_period("M").astype(str)
    return df

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎓 EduPro Analytics")
    st.markdown("---")
    uploaded = st.file_uploader("Upload dataset (Excel)", type=["xlsx","xls"],
                                help="Needs sheets: Users, Courses, Transactions")
    st.markdown("### Filters")

    if uploaded:
        u_raw, c_raw, t_raw = load_data(uploaded)
    else:
        st.info("Showing synthetic demo data. Upload your Excel file above for real data.")
        u_raw, c_raw, t_raw = generate_data()

    df_all = merge(u_raw, c_raw, t_raw)

    sel_age    = st.selectbox("Age group",       ["All"] + AGE_ORDER)
    sel_gender = st.selectbox("Gender",          ["All"] + sorted(df_all["Gender"].dropna().unique().tolist()))
    sel_cat    = st.selectbox("Course category", ["All"] + sorted(df_all["CourseCategory"].dropna().unique().tolist()))
    sel_level  = st.selectbox("Course level",    ["All"] + LEVELS)
    st.markdown("---")
    st.caption("EduPro · Learner Intelligence")

# ── Filter ────────────────────────────────────────────────────────────────────
df = df_all.copy()
if sel_age    != "All": df = df[df["AgeGroup"]      == sel_age]
if sel_gender != "All": df = df[df["Gender"]         == sel_gender]
if sel_cat    != "All": df = df[df["CourseCategory"] == sel_cat]
if sel_level  != "All": df = df[df["CourseLevel"]    == sel_level]

st.title("EduPro — Learner Demographics & Enrollment Behavior")
st.caption("Descriptive learner intelligence for data-driven education planning")

if len(df) == 0:
    st.warning("No data matches the current filters.")
    st.stop()

# ── KPIs ──────────────────────────────────────────────────────────────────────
total   = len(df)
unique  = df["UserID"].nunique()
avg_c   = round(total / max(unique, 1), 1)
top_cat = df["CourseCategory"].mode()[0] if total else "—"
top_lvl = df["CourseLevel"].mode()[0]    if total else "—"

k1,k2,k3,k4,k5 = st.columns(5)
k1.metric("Total Enrollments",     f"{total:,}")
k2.metric("Active Learners",       f"{unique:,}")
k3.metric("Avg Courses / Learner", avg_c)
k4.metric("Top Category",          top_cat)
k5.metric("Top Level",             top_lvl)

st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["👤 Demographics","📚 Course Preferences","🔥 Heatmap","📈 Behavioral Insights"])

# ── TAB 1 ─────────────────────────────────────────────────────────────────────
with tab1:
    st.markdown('<div class="section-header">Age & gender distribution</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        age_counts = df.groupby("AgeGroup", observed=True).size().reindex(AGE_ORDER, fill_value=0)
        fig, ax = plt.subplots(figsize=(5,3))
        bars = ax.bar(AGE_ORDER, age_counts.values, color=C_BLUE, alpha=0.85, width=0.6)
        ax.bar_label(bars, fontsize=8, color="#444")
        fig_style(ax, "Enrollments by Age Group")
        ax.set_ylabel("Enrollments", fontsize=9)
        st.pyplot(fig); plt.close()
        st.caption("Total enrollments per age band")

    with c2:
        gn_counts = df["Gender"].value_counts()
        gn_labels = gn_counts.index.tolist()
        gn_colors = [GENDER_COLORS[GENDERS.index(g)] if g in GENDERS else "#aaa" for g in gn_labels]
        fig, ax = plt.subplots(figsize=(5,3))
        wedges, texts, autotexts = ax.pie(
            gn_counts.values, labels=gn_labels, colors=gn_colors,
            autopct="%1.1f%%", startangle=90,
            wedgeprops=dict(width=0.55))
        for t in autotexts: t.set_fontsize(8)
        ax.set_title("Gender Participation Ratio", fontsize=11, fontweight="bold", color="#333")
        st.pyplot(fig); plt.close()
        st.caption("Share of each gender across platform")

    st.markdown('<div class="section-header">Gender breakdown by age group</div>', unsafe_allow_html=True)
    ag_gn = df.groupby(["AgeGroup","Gender"], observed=True).size().unstack(fill_value=0).reindex(AGE_ORDER, fill_value=0)
    fig, ax = plt.subplots(figsize=(8,3.5))
    x   = np.arange(len(AGE_ORDER))
    w   = 0.25
    for i, (g, col) in enumerate(zip(GENDERS, GENDER_COLORS)):
        if g in ag_gn.columns:
            ax.bar(x + i*w, ag_gn[g].values, width=w, color=col, alpha=0.85, label=g)
    ax.set_xticks(x + w); ax.set_xticklabels(AGE_ORDER)
    ax.legend(fontsize=9); fig_style(ax, "Gender × Age Group Enrollment")
    ax.set_ylabel("Enrollments", fontsize=9)
    st.pyplot(fig); plt.close()

# ── TAB 2 ─────────────────────────────────────────────────────────────────────
with tab2:
    st.markdown('<div class="section-header">Category popularity index</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        cat_counts = df["CourseCategory"].value_counts()
        fig, ax = plt.subplots(figsize=(5,3.5))
        colors = [CAT_COLORS[CATEGORIES.index(c)] if c in CATEGORIES else "#aaa" for c in cat_counts.index]
        bars = ax.barh(cat_counts.index[::-1], cat_counts.values[::-1], color=colors[::-1], alpha=0.85)
        ax.bar_label(bars, fontsize=8, color="#444")
        fig_style(ax, "Category Popularity Index")
        ax.set_xlabel("Enrollments", fontsize=9)
        st.pyplot(fig); plt.close()

    with c2:
        lv_counts = df["CourseLevel"].value_counts().reindex(LEVELS, fill_value=0)
        fig, ax = plt.subplots(figsize=(5,3.5))
        bars = ax.bar(LEVELS, lv_counts.values, color=LEVEL_COLORS, alpha=0.85, width=0.5)
        ax.bar_label(bars, fontsize=8, color="#444")
        fig_style(ax, "Course Level Preference")
        ax.set_ylabel("Enrollments", fontsize=9)
        st.pyplot(fig); plt.close()

    st.markdown('<div class="section-header">Gender vs course level</div>', unsafe_allow_html=True)
    gl = df.groupby(["Gender","CourseLevel"]).size().unstack(fill_value=0).reindex(columns=LEVELS, fill_value=0)
    fig, ax = plt.subplots(figsize=(8,3.5))
    x = np.arange(len(LEVELS)); w = 0.25
    for i, (g, col) in enumerate(zip(GENDERS, GENDER_COLORS)):
        if g in gl.index:
            ax.bar(x + i*w, gl.loc[g].values, width=w, color=col, alpha=0.85, label=g)
    ax.set_xticks(x+w); ax.set_xticklabels(LEVELS)
    ax.legend(fontsize=9); fig_style(ax, "Gender × Course Level")
    ax.set_ylabel("Enrollments", fontsize=9)
    st.pyplot(fig); plt.close()

    if "CourseType" in df.columns:
        st.markdown('<div class="section-header">Course type distribution</div>', unsafe_allow_html=True)
        ct = df["CourseType"].value_counts()
        fig, ax = plt.subplots(figsize=(5,3))
        ax.pie(ct.values, labels=ct.index, autopct="%1.1f%%",
               colors=CAT_COLORS[:len(ct)], startangle=90,
               wedgeprops=dict(width=0.55))
        ax.set_title("Course Type Split", fontsize=11, fontweight="bold", color="#333")
        st.pyplot(fig); plt.close()

# ── TAB 3 ─────────────────────────────────────────────────────────────────────
with tab3:
    st.markdown('<div class="section-header">Age group × Course category heatmap</div>', unsafe_allow_html=True)
    hm = df.groupby(["AgeGroup","CourseCategory"], observed=True).size().unstack(fill_value=0).reindex(AGE_ORDER, fill_value=0)
    fig, ax = plt.subplots(figsize=(9,3.5))
    im = ax.imshow(hm.values, cmap="Blues", aspect="auto")
    ax.set_xticks(range(len(hm.columns))); ax.set_xticklabels(hm.columns, rotation=30, ha="right", fontsize=9)
    ax.set_yticks(range(len(AGE_ORDER)));  ax.set_yticklabels(AGE_ORDER, fontsize=9)
    for i in range(hm.values.shape[0]):
        for j in range(hm.values.shape[1]):
            ax.text(j, i, str(hm.values[i,j]), ha="center", va="center", fontsize=8,
                    color="white" if hm.values[i,j] > hm.values.max()*0.6 else "#333")
    plt.colorbar(im, ax=ax, shrink=0.8)
    ax.set_title("Age Group × Course Category", fontsize=11, fontweight="bold", color="#333")
    st.pyplot(fig); plt.close()
    st.caption("Darker = higher enrollment intensity")

    st.markdown('<div class="section-header">Age group × Course level heatmap</div>', unsafe_allow_html=True)
    hm2 = df.groupby(["AgeGroup","CourseLevel"], observed=True).size().unstack(fill_value=0).reindex(AGE_ORDER, fill_value=0)
    hm2 = hm2.reindex(columns=[c for c in LEVELS if c in hm2.columns], fill_value=0)
    fig, ax = plt.subplots(figsize=(6,3.5))
    im2 = ax.imshow(hm2.values, cmap="YlGnBu", aspect="auto")
    ax.set_xticks(range(len(hm2.columns))); ax.set_xticklabels(hm2.columns, fontsize=9)
    ax.set_yticks(range(len(AGE_ORDER)));   ax.set_yticklabels(AGE_ORDER, fontsize=9)
    for i in range(hm2.values.shape[0]):
        for j in range(hm2.values.shape[1]):
            ax.text(j, i, str(hm2.values[i,j]), ha="center", va="center", fontsize=9,
                    color="white" if hm2.values[i,j] > hm2.values.max()*0.6 else "#333")
    plt.colorbar(im2, ax=ax, shrink=0.8)
    ax.set_title("Age Group × Course Level", fontsize=11, fontweight="bold", color="#333")
    st.pyplot(fig); plt.close()
    st.caption("Shows whether younger learners prefer beginner and older learners prefer advanced content")

# ── TAB 4 ─────────────────────────────────────────────────────────────────────
with tab4:
    st.markdown('<div class="section-header">Monthly enrollment trend</div>', unsafe_allow_html=True)
    if "Month" in df.columns:
        monthly = df.groupby("Month").size().reset_index(name="Enrollments").sort_values("Month")
        fig, ax = plt.subplots(figsize=(9,3))
        ax.plot(monthly["Month"], monthly["Enrollments"], color=C_BLUE, linewidth=2.5, marker="o", markersize=4)
        ax.fill_between(monthly["Month"], monthly["Enrollments"], alpha=0.12, color=C_BLUE)
        ax.set_xticks(range(len(monthly)))
        ax.set_xticklabels(monthly["Month"], rotation=45, ha="right", fontsize=8)
        fig_style(ax, "Monthly Enrollment Trend")
        ax.set_ylabel("Enrollments", fontsize=9)
        st.pyplot(fig); plt.close()

    st.markdown('<div class="section-header">Learner engagement distribution</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        cpu = df.groupby("UserID").size().reset_index(name="Count")
        fig, ax = plt.subplots(figsize=(5,3))
        ax.hist(cpu["Count"], bins=10, color=C_TEAL, alpha=0.85, edgecolor="white")
        fig_style(ax, "Courses per Learner")
        ax.set_xlabel("Number of courses", fontsize=9)
        ax.set_ylabel("Number of learners",  fontsize=9)
        st.pyplot(fig); plt.close()
        st.caption("Distribution of enrollment depth")

    with c2:
        summary = (df.groupby("CourseCategory")
                   .agg(Enrollments=("CourseID","count"), Learners=("UserID","nunique"))
                   .reset_index()
                   .sort_values("Enrollments", ascending=False))
        summary["Avg/Learner"] = (summary["Enrollments"] / summary["Learners"]).round(2)
        st.dataframe(summary.rename(columns={"CourseCategory":"Category"}),
                     use_container_width=True, hide_index=True)
        st.caption("Category-level engagement summary")

    st.markdown('<div class="section-header">Beginner vs advanced by age group</div>', unsafe_allow_html=True)
    beg = df[df["CourseLevel"]=="Beginner"]["AgeGroup"].value_counts().reindex(AGE_ORDER, fill_value=0)
    adv = df[df["CourseLevel"]=="Advanced"]["AgeGroup"].value_counts().reindex(AGE_ORDER, fill_value=0)
    x = np.arange(len(AGE_ORDER)); w = 0.35
    fig, ax = plt.subplots(figsize=(8,3.5))
    ax.bar(x-w/2, beg.values, width=w, color=C_TEAL,  alpha=0.85, label="Beginner")
    ax.bar(x+w/2, adv.values, width=w, color=C_CORAL, alpha=0.85, label="Advanced")
    ax.set_xticks(x); ax.set_xticklabels(AGE_ORDER)
    ax.legend(fontsize=9); fig_style(ax, "Beginner vs Advanced by Age Group")
    ax.set_ylabel("Enrollments", fontsize=9)
    st.pyplot(fig); plt.close()

    st.markdown('<div class="section-header">Raw data explorer</div>', unsafe_allow_html=True)
    with st.expander("View filtered dataset"):
        st.dataframe(df.head(500), use_container_width=True)
        st.caption(f"Showing first 500 of {len(df):,} rows")
