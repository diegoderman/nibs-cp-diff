"""
report.py

Generates a self-contained HTML report summarising what's been collected
vs what's expected, from files already produced by earlier pipeline stages:
  - participants.csv         (per-visit: has_mri, on_REDCap, dates, demographics)
  - scan_overview.csv        (per-scan: subject, session, run, ScanType, demographics)
  - missing_mri_scans.csv    (expected visits with no matching scan)
  - scans_not_in_master.csv  (converted scans with no matching master entry)

Answers three questions:
  1. How many subjects have each scan type?
  2. Who is missing scans, and when were they expected?
  3. Who has a converted scan but isn't in the master/REDCap sheet?

Standalone - run `python report.py` any time after the `convert` stage has
produced the files above. Doesn't touch any pipeline state, just reads.
"""
import base64
import io
import logging
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import pandas as pd
import numpy as np
from config import (
    PARTICIPANTS_CSV, SCAN_OVERVIEW_PATH, MISSING_MRI_PATH, EXTRA_SCANS_PATH, REPORT_DIR,
)

log = logging.getLogger(__name__)


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=120)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("utf-8")



def _scan_type_chart_for_session(df_session: pd.DataFrame, session_label: str) -> str:
    if df_session.empty:
        return ""
    counts = df_session.groupby("ScanType")["subject"].nunique().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(4, 3.2))
    counts.plot(kind="bar", ax=ax, color="#4C72B0")
    ax.set_ylabel("Subjects")
    ax.set_title(f"Session {session_label}")
    ax.set_xlabel("")
    plt.xticks(rotation=30, ha="right")
    return _fig_to_base64(fig)

 
def _scan_type_table_for_session(df_session: pd.DataFrame) -> pd.DataFrame:
    if df_session.empty:
        return pd.DataFrame()
    table = (
        df_session.groupby("ScanType")
        .agg(n_subjects=("subject", "nunique"), n_scans=("subject", "size"))
        .reset_index()
        .sort_values("n_subjects", ascending=False)
    )
    any_row = pd.DataFrame([{
        "ScanType": "ANY",
        "n_subjects": df_session["subject"].nunique(),
        "n_scans": len(df_session),
    }])
    return pd.concat([table, any_row], ignore_index=True)
 

 
 
def _waterfall_chart(participants: pd.DataFrame) -> str:
    """
    One point per subject/session: y-axis is an anonymised subject index
    (numbered ticks only, no subject IDs), x-axis is session (1-3).
      red   = on REDCap/master, but no matching scan (has_mri=False)
      blue  = has a converted scan, but not on REDCap (on_REDCap=False)
      black = everything else (matched as expected)
    """
    df = participants.copy()
 
    # unify session number: REDCap rows use expected_visit_number (1,2,3);
    # unmatched-scan rows (on_REDCap=False) have no expected_visit_number,
    # so fall back to their actual scan session (e.g. "001" -> 1)

    df["SESSION"] = df["SESSION"].astype(int)

    def _status(row):
        if row["on_REDCap"] and not row["has_mri"]:
            return "red"
        if (not row["on_REDCap"]) and row["has_mri"]:
            return "blue"
        return "black"
 
    df["color"] = df.apply(_status, axis=1)
 
    subjects_sorted = sorted(df["subject"].unique())
    df["y"] = df["subject"]


    fig_height = max(4, len(subjects_sorted) * 0.18)
    fig, ax = plt.subplots(figsize=(6, fig_height))
    ax.scatter(df["SESSION"], df["y"], c=df["color"], s=24, zorder=3)
    ax.set_xlabel("Session")
    ax.set_ylabel("Subject")
    ax.set_xticks(sorted(df["SESSION"].unique()))
    #ax.set_yticks(range(1, len(subjects_sorted) + 1))
    #ax.set_yticklabels(range(1, len(subjects_sorted) + 1), fontsize=6)
    ax.invert_yaxis()
    ax.grid(axis="both", linestyle=":", alpha=0.4, zorder=0)
    ax.set_title("Data completeness by subject and session")
 
    legend_elems = [
        Line2D([0], [0], marker="o", color="w", label="On REDCap, no scan",
               markerfacecolor="red", markersize=6),
        Line2D([0], [0], marker="o", color="w", label="Scan, not on REDCap",
               markerfacecolor="blue", markersize=6),
        Line2D([0], [0], marker="o", color="w", label="Matched as expected",
               markerfacecolor="black", markersize=6),
    ]
    ax.legend(handles=legend_elems, loc="upper right", fontsize=7, framealpha=0.9)
 
    return _fig_to_base64(fig)
 


def _df_to_html(df: pd.DataFrame, empty_message="None - nothing to show here.") -> str:
    if df is None or df.empty:
        return f"<p><em>{empty_message}</em></p>"
    return df.to_html(index=False, classes="data-table", border=0, na_rep="-")


def generate_report():
    participants = pd.read_csv(PARTICIPANTS_CSV, index_col=False)
    scan_overview = pd.read_csv(SCAN_OVERVIEW_PATH, index_col=False)
    missing = pd.read_csv(MISSING_MRI_PATH, index_col=False)
    extra = pd.read_csv(EXTRA_SCANS_PATH, index_col=False)

    participants["SESSION"] = participants['expected_session'].fillna(participants['session'])
    scan_overview["SESSION"] = scan_overview['expected_session'].fillna(scan_overview['session'])


    n_subjects_master = participants.loc[participants["on_REDCap"], "subject"].nunique()
    n_subjects_scanned = scan_overview["subject"].nunique()
    n_scans_total = len(scan_overview)
    n_missing = len(missing)
    n_extra = len(extra)
 
    def img_block(img_b64: str) -> str:
        return f'<div class="charts"><img src="data:image/png;base64,{img_b64}"></div>' if img_b64 else ""
 
    # --- scan types, one column per session ---
    session_cols_html = ""
    if not scan_overview.empty:
        for session in sorted(scan_overview["SESSION"].dropna().unique()):
            sub = scan_overview[scan_overview["SESSION"] == session]
            img = _scan_type_chart_for_session(sub, session)
            table = _scan_type_table_for_session(sub)
            session_cols_html += f"""
            <div class="session-col">
              <h3>Session {session}</h3>
              {img_block(img)}
              {_df_to_html(table)}
            </div>
            """
    else:
        session_cols_html = "<p><em>No converted scans yet.</em></p>"
 
    # --- waterfall / completeness plot ---
    waterfall_img = _waterfall_chart(participants) if not participants.empty else ""
 
    missing_table = (
        missing[["subject", "expected_session", "mri_date", "age_at_mri", "sex", "group"]]
        .sort_values("mri_date")
        if not missing.empty else missing
    )
    extra_table = extra[["subject", "session"]] if not extra.empty else extra
 
    html = f"""
    <html>
    <head>
    <meta charset="utf-8">
    <title>NIBS-CP MRI data report - {datetime.now():%Y-%m-%d}</title>
    <style>
        body {{ font-family: -apple-system, Arial, sans-serif; margin: 40px; color: #222; }}
        h1 {{ font-size: 1.6em; }}
        h2 {{ margin-top: 2.5em; border-bottom: 2px solid #eee; padding-bottom: 4px; }}
        h3 {{ margin-bottom: 4px; }}
        .summary-grid {{ display: flex; gap: 20px; flex-wrap: wrap; margin: 20px 0; }}
        .summary-card {{ background: #f7f7f9; border-radius: 8px; padding: 16px 24px; min-width: 160px; }}
        .summary-card .value {{ font-size: 1.8em; font-weight: 700; }}
        .summary-card .label {{ color: #666; font-size: 0.9em; }}
        table.data-table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
        table.data-table th, table.data-table td {{ border-bottom: 1px solid #eee; padding: 6px 10px; text-align: left; font-size: 0.92em; }}
        table.data-table th {{ background: #fafafa; }}
        img {{ max-width: 100%; }}
        .charts {{ display: flex; gap: 30px; flex-wrap: wrap; margin: 10px 0 20px; }}
        .session-grid {{ display: flex; gap: 24px; align-items: flex-start; }}
        .session-col {{ flex: 1; min-width: 220px; }}
    </style>
    </head>
    <body>
    <h1>NIBS-CP MRI data report</h1>
    <p>Generated {datetime.now():%Y-%m-%d %H:%M}</p>
 
    <div class="summary-grid">
        <div class="summary-card"><div class="value">{n_subjects_master}</div><div class="label">Subjects in REDCap</div></div>
        <div class="summary-card"><div class="value">{n_subjects_scanned}</div><div class="label">Subjects with a converted scan</div></div>
        <div class="summary-card"><div class="value">{n_scans_total}</div><div class="label">Converted scans (all types)</div></div>
        <div class="summary-card"><div class="value">{n_missing}</div><div class="label">Expected visits missing a scan</div></div>
        <div class="summary-card"><div class="value">{n_extra}</div><div class="label">Scans not in REDCap</div></div>
    </div>
 
    <h2>Scan types collected, by session</h2>
    <div class="session-grid">
        {session_cols_html}
    </div>
 
    <h2>Data completeness overview</h2>
    {img_block(waterfall_img)}
 
    <h2>Missing scans</h2>
    {_df_to_html(missing_table, "No missing scans - everyone in REDCap has all expected visits.")}
 
    <h2>Scans not in REDCap</h2>
    <p>Converted scans with no matching subject/visit in the master sheet - check for ID mismatches or entries not yet logged.</p>
    {_df_to_html(extra_table, "None - every converted scan matches a REDCap entry.")}
 
    </body>
    </html>
    """
 
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORT_DIR / f"report_{datetime.now():%Y%m%d_%H%M%S}.html"
    latest_path = REPORT_DIR / "report_latest.html"
    out_path.write_text(html, encoding="utf-8")
    latest_path.write_text(html, encoding="utf-8")
 
    log.info("Report written to %s (and report_latest.html)", out_path)
    return out_path
 
 
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    generate_report()
