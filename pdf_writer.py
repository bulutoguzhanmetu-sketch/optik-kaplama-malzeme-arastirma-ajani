"""Üretilen rapor metnini reportlab ile PDF'e döker."""
import re
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

import config

_SECTION_HEADERS = {"giriş", "bulgular", "sonuç", "kaynakça"}


def _slugify(text, max_len=40):
    slug = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip().lower()
    slug = re.sub(r"[\s_-]+", "_", slug)
    return slug[:max_len] or "rapor"


def write_report_pdf(topic, report_text):
    styles = getSampleStyleSheet()
    heading_style = styles["Heading2"]
    body_style = styles["BodyText"]
    title_style = styles["Title"]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{_slugify(topic)}.pdf"
    output_path = config.OUTPUT_DIR / filename

    doc = SimpleDocTemplate(str(output_path), pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    elements = [Paragraph(topic, title_style), Spacer(1, 0.5 * cm)]

    for raw_line in report_text.splitlines():
        line = raw_line.strip()
        if not line:
            elements.append(Spacer(1, 0.2 * cm))
            continue
        stripped_header = line.strip("#* ").rstrip(":").lower()
        if stripped_header in _SECTION_HEADERS:
            elements.append(Spacer(1, 0.3 * cm))
            elements.append(Paragraph(stripped_header.capitalize(), heading_style))
        else:
            elements.append(Paragraph(line, body_style))

    doc.build(elements)
    return output_path
