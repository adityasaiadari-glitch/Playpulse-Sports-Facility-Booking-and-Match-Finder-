"""
Insights page  (Unit III: NumPy & pandas  +  Unit V: Matplotlib)

Turns bookings.json into a pandas DataFrame, analyses it with
grouping & aggregation, and draws charts that are saved as PNG images
in static/charts/ so the HTML page can show them with <img>.
"""
import os

import matplotlib
matplotlib.use("Agg")                       # draw to files, not to a window (needed on a server)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import storage
from .models import SPORTS

CHART_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "charts")

INK, MUTED, ACCENT, ACCENT2 = "#14213d", "#6b7280", "#ff6b35", "#2a9d8f"
PALETTE = ["#ff6b35", "#2a9d8f", "#264653", "#e9c46a", "#8e7dbe", "#e76f51", "#4d908e", "#b5838d"]


def bookings_dataframe():
    df = pd.DataFrame(storage.load_json("bookings.json", []))
    if df.empty:
        return df
    venues = {v["id"]: v["name"] for v in storage.load_json("venues.json", [])}
    df["date"] = pd.to_datetime(df["date"])
    df["venue"] = df["venue_id"].map(venues)
    df["sport_name"] = df["sport"].map(lambda s: SPORTS[s][0])
    df["weekday"] = df["date"].dt.day_name()
    return df


def _style(ax, title):
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold", color=INK, pad=12)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color("#d1d5db")
    ax.spines["bottom"].set_color("#d1d5db")
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(axis="y", color="#eef0f3", linewidth=0.8)
    ax.set_axisbelow(True)


def build_insights():
    """Create all charts and return summary numbers for the template."""
    os.makedirs(CHART_DIR, exist_ok=True)
    df = bookings_dataframe()
    if df.empty:
        return None
    ok = df[df["status"] == "confirmed"]

    # ---------- NumPy summary numbers ----------
    amounts = ok["amount"].to_numpy()
    ratings = np.array([r["stars"] for v in storage.load_json("venues.json", []) for r in v["reviews"]])
    summary = {
        "total_bookings": int(len(ok)),
        "revenue": int(np.sum(amounts)),
        "avg_ticket": int(np.mean(amounts)) if len(amounts) else 0,
        "avg_rating": round(float(np.mean(ratings)), 2) if len(ratings) else 0,
        "cancel_rate": round(100 * (df["status"] == "cancelled").mean(), 1),
        "busiest_hour": int(ok["hour"].mode()[0]) if len(ok) else 0,
    }

    # ---------- 1. Bar chart: bookings per sport (groupby + count) ----------
    per_sport = ok.groupby("sport_name")["id"].count().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(6.4, 3.6), dpi=110)
    ax.bar(per_sport.index, per_sport.values, color=PALETTE[:len(per_sport)], width=0.6)
    for i, val in enumerate(per_sport.values):
        ax.text(i, val + 0.4, str(val), ha="center", fontsize=9, color=INK)
    _style(ax, "Bookings by sport")
    ax.set_ylabel("Bookings", color=MUTED)
    plt.xticks(rotation=20)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "by_sport.png"))
    plt.close(fig)

    # ---------- 2. Line chart: bookings per hour of the day ----------
    per_hour = ok.groupby("hour")["id"].count().reindex(range(6, 24), fill_value=0)
    fig, ax = plt.subplots(figsize=(6.4, 3.6), dpi=110)
    ax.plot(per_hour.index, per_hour.values, color=ACCENT, marker="o", linewidth=2.2, markersize=4)
    ax.fill_between(per_hour.index, per_hour.values, color=ACCENT, alpha=0.12)
    _style(ax, "When do people play? (bookings by start hour)")
    ax.set_xticks(range(6, 24, 2))
    ax.set_xticklabels([f"{h % 12 or 12}{'am' if h < 12 else 'pm'}" for h in range(6, 24, 2)])
    ax.set_ylabel("Bookings", color=MUTED)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "by_hour.png"))
    plt.close(fig)

    # ---------- 3. Horizontal bar: revenue per venue (groupby + sum) ----------
    revenue = ok.groupby("venue")["amount"].sum().sort_values()
    fig, ax = plt.subplots(figsize=(6.4, 3.6), dpi=110)
    ax.barh(revenue.index, revenue.values, color=ACCENT2, height=0.6)
    _style(ax, "Revenue by venue (₹)")
    ax.grid(axis="x", color="#eef0f3"); ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "by_venue.png"))
    plt.close(fig)

    # ---------- 4. Pie chart: games by skill level ----------
    games = pd.DataFrame(storage.load_json("games.json", []))
    if not games.empty:
        skill_counts = games["skill"].value_counts()
        fig, ax = plt.subplots(figsize=(4.6, 3.6), dpi=110)
        wedges, labels, pcts = ax.pie(
            skill_counts.values, labels=skill_counts.index, autopct="%1.0f%%", startangle=90,
            pctdistance=0.78, colors=[ACCENT2, ACCENT, "#264653"],
            wedgeprops={"width": 0.45, "edgecolor": "white"}, textprops={"color": INK, "fontsize": 9})
        for t in pcts:                      # white percentage text on the coloured ring
            t.set_color("white"); t.set_fontweight("bold")
        ax.set_title("Open games by skill level", loc="left", fontsize=12, fontweight="bold", color=INK)
        fig.tight_layout()
        fig.savefig(os.path.join(CHART_DIR, "games_skill.png"))
        plt.close(fig)

    # ---------- Table: weekday vs weekend (pivot / aggregation) ----------
    table = (ok.assign(day_type=np.where(ok["date"].dt.weekday >= 5, "Weekend", "Weekday"))
               .groupby(["sport_name", "day_type"])["amount"].agg(["count", "mean"])
               .round(0).reset_index())
    rows = table.to_dict("records")
    return {"summary": summary, "rows": rows}
