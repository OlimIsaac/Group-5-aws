from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
from django.http import HttpResponse


def generate_patient_report(user, frames):
    """Return an HttpResponse with PDF containing summary for given frames."""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    c.setFont("Helvetica", 14)
    c.drawString(50, height - 50, f"Patient Report for {user.username}")
    y = height - 80
    for frame in frames[:50]:
        line = f"{frame.timestamp}: PPI={frame.peak_pressure_index}, contact={frame.contact_area_percentage:.1f}%"
        c.setFont("Helvetica", 10)
        c.drawString(50, y, line)
        y -= 12
        if y < 50:
            c.showPage()
            y = height - 50
    c.save()
    buffer.seek(0)
    return HttpResponse(buffer, content_type='application/pdf')
