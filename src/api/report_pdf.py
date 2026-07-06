"""Generate professional staffing approval PDF reports."""

from __future__ import annotations

import json
import unicodedata
from io import BytesIO

from fpdf import FPDF


def _pdf_text(value: object, fallback: str = "-") -> str:
    """Normalize text for core Helvetica fonts (latin-1 only)."""
    text = str(value if value not in (None, "") else fallback)
    replacements = {
        "\u2014": "-",  # em dash
        "\u2013": "-",  # en dash
        "\u2022": "-",  # bullet
        "\u00d7": "x",  # multiplication sign
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("latin-1", errors="replace").decode("latin-1")


class StaffingReportPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, "Staffing Approval Report", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(100, 100, 100)
        self.cell(
            0,
            6,
            _pdf_text("Staffing Copilot - Internal Staffing Decision Record"),
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.set_text_color(0, 0, 0)
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

    def section_title(self, title: str):
        self.set_font("Helvetica", "B", 12)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 8, _pdf_text(title), new_x="LMARGIN", new_y="NEXT", fill=True)
        self.ln(2)

    def body_text(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 5, _pdf_text(text))
        self.ln(2)

    def label_value(self, label: str, value: str):
        self.set_font("Helvetica", "B", 10)
        self.cell(45, 6, _pdf_text(label) + ":", new_x="RIGHT")
        self.set_font("Helvetica", "", 10)
        self.cell(0, 6, _pdf_text(value), new_x="LMARGIN", new_y="NEXT")


def build_report_pdf(report: dict) -> bytes:
    profile = json.loads(report.get("employee_profile") or "{}")
    breakdown = json.loads(report.get("score_breakdown") or "[]")
    skills = json.loads(report.get("required_skills") or "[]")

    pdf = StaffingReportPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.section_title("1. Employee Profile")
    pdf.label_value("Name", report["employee_name"])
    pdf.label_value("Employee ID", str(report["employee_id"]))
    pdf.label_value("Title", profile.get("title", "-"))
    pdf.label_value("Department", profile.get("department", "-"))
    pdf.label_value("Location", profile.get("location", "-"))
    pdf.label_value("Experience", f"{profile.get('years_experience', '-')} years")
    pdf.label_value("Available from", profile.get("available_from", "-"))
    pdf.label_value("Skills", ", ".join(profile.get("skills", [])))
    pdf.label_value("German fluency", profile.get("german_fluency", "-"))
    pdf.label_value("Match score", str(report["total_score"]))
    pdf.ln(2)

    pdf.section_title("2. Why This Employee Is the Right Fit")
    pdf.body_text(report.get("justification") or "No fit summary recorded.")

    pdf.section_title("3. Transparent Scoring Breakdown")
    for item in breakdown:
        pts = item.get("weighted_points", item.get("points", 0))
        raw = item.get("raw_score")
        weight = item.get("weight_percent")
        extra = f" (raw {raw} x {weight}%)" if raw is not None else ""
        pdf.body_text(f"- {item['rule']}: +{pts}{extra} - {item['detail']}")

    pdf.section_title("4. Approval Record")
    pdf.label_value("Approved by", report["approved_by"])
    pdf.label_value("Approved at", report["approved_at"])
    pdf.label_value("Report ID", str(report["id"]))
    council = (report.get("works_council_notification") or "").strip()
    if council:
        pdf.label_value(
            "Betriebsrat notification required?",
            {
                "yes": "Yes",
                "no": "No",
                "unsure": "Unsure",
                "already_notified": "Already notified",
            }[council],
        )
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Manager approval notes:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    notes = (report.get("manager_notes") or "").strip() or "No additional notes provided."
    pdf.multi_cell(0, 5, _pdf_text(notes))
    pdf.ln(2)

    pdf.section_title("5. Original Staffing Request")
    pdf.body_text(report.get("client_message") or "-")
    if skills:
        pdf.label_value("Required skills", ", ".join(skills))
    if report.get("location"):
        pdf.label_value("Location", report["location"])
    if report.get("needed_by"):
        pdf.label_value("Needed by", report["needed_by"])

    buffer = BytesIO()
    pdf.output(buffer)
    return buffer.getvalue()
