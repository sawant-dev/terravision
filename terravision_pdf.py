"""
TerraVision - PDF report builder
Turns the numbers from a site analysis into a branded, downloadable PDF.
"""

from datetime import date

from fpdf import FPDF

from terravision_core import MONTHS

# Brand colours as (red, green, blue), each 0-255
NAVY = (16, 37, 66)
ORANGE = (245, 166, 35)
GREY = (110, 110, 110)
LIGHT = (240, 242, 245)
GREEN = (30, 140, 70)
AMBER = (200, 130, 0)
RED = (190, 40, 40)


def score_colour(score, buildable=True):
    """Green for good, amber for fair, red for poor."""
    if not buildable or score < 50:
        return RED
    if score < 65:
        return AMBER
    return GREEN


def section_title(pdf, text):
    """Orange bar + bold heading, used to start each section."""
    pdf.ln(2)
    pdf.set_fill_color(*ORANGE)
    pdf.rect(pdf.l_margin, pdf.get_y() + 1, 2, 6, style="F")
    pdf.set_x(pdf.l_margin + 5)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def stat_row(pdf, items):
    """A row of small label/value boxes, e.g. [("Slope", "3.1 deg"), ...]."""
    gap = 4
    width = (pdf.epw - gap * (len(items) - 1)) / len(items)
    y = pdf.get_y()
    for i, (label, value) in enumerate(items):
        x = pdf.l_margin + i * (width + gap)
        pdf.set_fill_color(*LIGHT)
        pdf.rect(x, y, width, 16, style="F")
        pdf.set_xy(x + 3, y + 2)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*GREY)
        pdf.cell(width - 6, 5, label)
        pdf.set_xy(x + 3, y + 7)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(*NAVY)
        pdf.cell(width - 6, 8, value)
    pdf.set_y(y + 19)


def bar_chart(pdf, sun):
    """Draw the 12-month sunlight chart with rectangles."""
    chart_h = 40
    top = pdf.get_y()
    bottom = top + chart_h
    max_value = 8                                   # kWh/m2/day at the top of the chart
    slot = pdf.epw / 12
    bar_w = slot * 0.6

    # light guide lines at 2, 4, 6, 8
    pdf.set_draw_color(220, 220, 220)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*GREY)
    for v in (2, 4, 6, 8):
        y = bottom - v / max_value * chart_h
        pdf.line(pdf.l_margin, y, pdf.l_margin + pdf.epw, y)
        pdf.text(pdf.l_margin - 4, y + 1, str(v))

    # one bar per month, value on top, month name below
    pdf.set_fill_color(*ORANGE)
    for i, m in enumerate(MONTHS):
        h = sun[m] / max_value * chart_h
        x = pdf.l_margin + i * slot + (slot - bar_w) / 2
        pdf.rect(x, bottom - h, bar_w, h, style="F")
        pdf.set_text_color(*NAVY)
        pdf.text(x + 0.5, bottom - h - 1.5, f"{sun[m]:.1f}")
        pdf.set_text_color(*GREY)
        pdf.text(x + 0.5, bottom + 4, m)
    pdf.set_y(bottom + 8)


def build_pdf(r):
    """r is a dictionary with all the results. Returns the PDF as bytes."""
    pdf = FPDF(format="A4")
    pdf.set_margins(18, 15, 18)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # ---- Header band ----
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, 210, 32, style="F")
    pdf.set_xy(18, 8)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, "TERRAVISION", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*ORANGE)
    pdf.cell(0, 6, "Solar Site Assessment Report")
    pdf.set_y(40)

    # ---- Site details ----
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 9, r["site_name"], new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GREY)
    pdf.cell(0, 5, f"Location: {r['lat']:.4f}, {r['lon']:.4f}   |   "
                   f"Report date: {date.today():%d %b %Y}",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # ---- Overall score box ----
    colour = score_colour(r["overall"], r["buildable"])
    y = pdf.get_y()
    pdf.set_fill_color(*colour)
    pdf.rect(pdf.l_margin, y, pdf.epw, 26, style="F")
    pdf.set_xy(pdf.l_margin + 6, y + 4)
    pdf.set_font("Helvetica", "B", 30)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(45, 18, f"{r['overall']:.0f}/100")
    pdf.set_xy(pdf.l_margin + 55, y + 6)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, "OVERALL SITE SCORE", new_x="LEFT", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 12)
    pdf.multi_cell(pdf.epw - 60, 6, r["verdict"])
    pdf.set_y(y + 30)

    stat_row(pdf, [("Sunlight score", f"{r['sun_pts']:.0f}"),
                   ("Slope score", f"{r['land_pts']:.0f}"),
                   ("Land use score", f"{r['use_pts']:.0f}")])

    # ---- Sunlight ----
    section_title(pdf, "1. Sunlight")
    bar_chart(pdf, r["sun"])
    stat_row(pdf, [("Average sunlight", f"{r['annual_sun']:.2f} kWh/m2/day"),
                   ("Expected yield", f"{r['yield_per_kwp']:,.0f} kWh/kWp/yr"),
                   ("Avg temperature", f"{r['avg_temp']:.1f} °C")])
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GREY)
    pdf.cell(0, 5, f"Best month: {r['best']}   |   Worst month: {r['worst']}",
             new_x="LMARGIN", new_y="NEXT")

    # ---- Land ----
    section_title(pdf, "2. Terrain")
    stat_row(pdf, [("Ground height", f"{r['height']:.0f} m"),
                   ("Slope", f"{r['slope']:.1f}°"),
                   ("Faces", r["facing"])])

    # ---- Land use ----
    section_title(pdf, "3. Land use")
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 6, f"{r['land_type']} (within {r['radius']} m)",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    lu = r["land_use"]
    stat_row(pdf, [("Buildings", str(lu["buildings"])), ("Water", str(lu["water"])),
                   ("Forest", str(lu["forest"])), ("Farmland", str(lu["farmland"]))])

    # ---- Footer (sits just under the content) ----
    pdf.ln(4)
    pdf.set_draw_color(*ORANGE)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + pdf.epw, pdf.get_y())
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*GREY)
    pdf.multi_cell(0, 3.5,
        "Data sources: NASA POWER (sunlight, temperature); NASA SRTM 30 m via "
        "OpenTopoData (elevation); (c) OpenStreetMap contributors (land use). "
        "This report is a desktop screening estimate based on satellite and map "
        "data. Confirm with an on-site survey before making investment decisions.")

    return bytes(pdf.output())