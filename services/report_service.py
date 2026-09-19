"""
Report Service
-----------------
Generates PDF reports, CSV exports, QR codes, and barcodes for a
validation record. QR codes deliberately avoid embedding personal data -
they reference the Validation ID, status, confidence, and timestamp only.
"""
import os
import csv
import io
import json
import qrcode
import barcode
from barcode.writer import ImageWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

STATUS_COLORS = {
    "VERIFIED": colors.HexColor("#1e8e3e"),
    "NEEDS CUSTOMER CONFIRMATION": colors.HexColor("#1a73e8"),
    "SUSPICIOUS": colors.HexColor("#e8710a"),
    "FAKE ADDRESS": colors.HexColor("#d93025"),
}


def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def generate_pdf_report(record, reports_dir: str) -> str:
    _ensure_dir(reports_dir)
    file_path = os.path.join(reports_dir, f"{record.validation_id}_report.pdf")

    doc = SimpleDocTemplate(file_path, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleStyle", parent=styles["Heading1"], fontSize=18)
    status_style = ParagraphStyle(
        "StatusStyle", parent=styles["Heading2"],
        textColor=STATUS_COLORS.get(record.final_status, colors.black)
    )

    story = [
        Paragraph("AddressGuard AI - Validation Report", title_style),
        Spacer(1, 6),
        Paragraph(f"Validation ID: {record.validation_id}", styles["Normal"]),
        Paragraph(f"Generated: {record.updated_at.isoformat()}", styles["Normal"]),
        Spacer(1, 14),
        Paragraph(record.final_status, status_style),
        Paragraph(f"Confidence Score: {record.confidence_score}%", styles["Normal"]),
        Paragraph(f"Risk Level: {record.risk_level}", styles["Normal"]),
        Spacer(1, 10),
        Paragraph("Recommendation", styles["Heading3"]),
        Paragraph(record.recommendation, styles["Normal"]),
        Spacer(1, 10),
        Paragraph("Reasons", styles["Heading3"]),
    ]
    for r in (record.reasons or ["None"]):
        story.append(Paragraph(r, styles["Normal"]))

    story.append(Spacer(1, 10))
    story.append(Paragraph("Problems Detected", styles["Heading3"]))
    for p in (record.problems or ["None detected."]):
        story.append(Paragraph(p, styles["Normal"]))

    story.append(Spacer(1, 10))
    story.append(Paragraph("Parsed Address", styles["Heading3"]))
    addr_rows = [["Field", "Value"]] + [
        [k.replace("_", " ").title(), str(v) if v else "-"] for k, v in (record.working_address or {}).items()
    ]
    table = Table(addr_rows, colWidths=[150, 300])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f3f4")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dadce0")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(table)

    doc.build(story)
    return file_path


def generate_csv_report(record, reports_dir: str) -> str:
    _ensure_dir(reports_dir)
    file_path = os.path.join(reports_dir, f"{record.validation_id}_report.csv")

    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Validation ID", record.validation_id])
        writer.writerow(["Verification Result", record.final_status])
        writer.writerow(["Confidence", record.confidence_score])
        writer.writerow(["Risk", record.risk_level])
        writer.writerow(["Timestamp", record.updated_at.isoformat()])
        writer.writerow([])
        writer.writerow(["Reasons"])
        for r in (record.reasons or []):
            writer.writerow([r])
        writer.writerow([])
        writer.writerow(["Problems"])
        for p in (record.problems or []):
            writer.writerow([p])
        writer.writerow([])
        writer.writerow(["Recommendation", record.recommendation])
        writer.writerow([])
        writer.writerow(["Field", "Value"])
        for k, v in (record.working_address or {}).items():
            writer.writerow([k, v])

    return file_path


def generate_qr_code(record, reports_dir: str, public_base_url: str) -> str:
    _ensure_dir(reports_dir)
    file_path = os.path.join(reports_dir, f"{record.validation_id}_qr.png")

    payload = {
        "validation_id": record.validation_id,
        "status": record.final_status,
        "confidence": record.confidence_score,
        "timestamp": record.updated_at.isoformat(),
        "verify_url": f"{public_base_url}/api/history/{record.validation_id}",
    }
    img = qrcode.make(json.dumps(payload))
    img.save(file_path)
    return file_path


def generate_barcode(record, reports_dir: str) -> str:
    _ensure_dir(reports_dir)
    file_path_base = os.path.join(reports_dir, f"{record.validation_id}_barcode")

    code128 = barcode.get_barcode_class("code128")
    barcode_id = record.validation_id.replace("-", "")
    instance = code128(barcode_id, writer=ImageWriter())
    saved_path = instance.save(file_path_base)
    return saved_path
