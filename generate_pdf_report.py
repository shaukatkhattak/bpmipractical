"""
Generate Helpdesk Baltics exam PDF: one page per question — answer and screenshot(s).
Answers are computed from the event log (exam_answers.py) so they match the analysis.
"""
import os
import subprocess
import sys

try:
    from fpdf import FPDF
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "fpdf2", "-q"])
    from fpdf import FPDF

from exam_answers import compute_answers, format_answers

BASE = os.path.dirname(os.path.abspath(__file__))
SHOT = os.path.join(BASE, "screenshots")
OUT_PDF = os.path.join(BASE, "Helpdesk-Baltics-Exam.pdf")

if not os.path.isdir(SHOT) or not os.path.isfile(os.path.join(SHOT, "Q1_skipped_approved.png")):
    subprocess.run([sys.executable, os.path.join(BASE, "generate_screenshots.py")], check=True)


class ExamPDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, f"Helpdesk Baltics Exam Report  |  Page {self.page_no()}", align="C")


def question_heading(pdf, num):
    pdf.ln(4)
    pdf.set_fill_color(44, 95, 141)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"  Question {num}", new_x="LMARGIN", new_y="NEXT", fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)


def answer_block(pdf, text):
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5.5, text)
    pdf.ln(3)


def add_image(pdf, name, max_w=180):
    path = os.path.join(SHOT, name)
    if not os.path.isfile(path):
        answer_block(pdf, f"[Screenshot missing: {name}]")
        return
    pdf.ln(2)
    w = max_w
    try:
        from PIL import Image
        with Image.open(path) as im:
            iw, ih = im.size
        h = w * ih / iw
        max_h = 115
        if h > max_h:
            h = max_h
            w = h * iw / ih
    except Exception:
        h = 85
    if pdf.get_y() + h > 270:
        pdf.add_page()
    x = (210 - w) / 2
    pdf.image(path, x=x, y=pdf.get_y(), w=w, h=h)
    pdf.set_y(pdf.get_y() + h + 5)


def build_pdf():
    questions = format_answers(compute_answers())

    pdf = ExamPDF()
    pdf.set_auto_page_break(True, margin=18)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 20)
    pdf.ln(30)
    pdf.cell(0, 12, "Business Process Mining", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Helpdesk Baltics - Exam Report", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(8)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(
        0,
        6,
        "Event log: Helpdesk-Baltics.csv\n"
        "Case ID: Ticket | Activity: Status | Timestamp: Time\n"
        "Attributes: Category, Country | Closed case: trace contains Closed",
        align="C",
    )
    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 10)
    pdf.cell(0, 6, "2,000 cases | 36,972 events | 1,925 closed cases", new_x="LMARGIN", new_y="NEXT", align="C")

    for q in questions:
        pdf.add_page()
        question_heading(pdf, q["num"])
        answer_block(pdf, q["answer"])
        for img in q["images"]:
            add_image(pdf, img)

    pdf.output(OUT_PDF)
    print(f"PDF saved: {OUT_PDF}")


if __name__ == "__main__":
    build_pdf()
