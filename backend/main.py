import logging
import os
import smtplib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, field_validator

load_dotenv()

logger = logging.getLogger("enquiry_mailer")

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
OWNER_EMAIL = os.getenv("OWNER_EMAIL", SMTP_USER)
FROM_NAME = os.getenv("FROM_NAME", "Kapi Dwaja Exports")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
SHEETS_WEBHOOK_URL = os.getenv("SHEETS_WEBHOOK_URL", "")

COMPANY_NAME = "Kapi Dwaja Exports"
COMPANY_EMAIL = "export@kapidwaja.com"
COMPANY_PHONE = "+91 63052 74646"

BACKEND_DIR = os.path.dirname(__file__)
LOGO_PATH = os.path.join(BACKEND_DIR, "logo.png")
CATALOGUE_PATH = os.path.join(BACKEND_DIR, "..", "assets", "Kapi-Dwaja-Exports-Catalogue-2026.pdf")
LOGO_CID = "companylogo"

app = FastAPI(title="Enquiry Mailer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["POST"],
    allow_headers=["*"],
)


class QuoteRequest(BaseModel):
    first_name: str
    last_name: str
    company: str
    email: EmailStr
    phone: str
    country: str
    buyer_type: Optional[str] = ""
    product: str
    quantity: Optional[str] = ""
    incoterm: Optional[str] = ""
    message: Optional[str] = ""

    @field_validator("first_name", "last_name", "company", "phone", "country", "product")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v.strip()


class SampleRequest(BaseModel):
    name: str
    company: str
    email: EmailStr
    phone: str
    product: str
    address: str
    purpose: Optional[str] = ""

    @field_validator("name", "company", "phone", "product", "address")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v.strip()


def rows_to_html_table(rows: list[tuple[str, str]]) -> str:
    body_rows = "".join(
        f'<tr><td style="padding:8px 14px;font-weight:600;border:1px solid #e0ddd5;background:#faf8f4;white-space:nowrap;">{label}</td>'
        f'<td style="padding:8px 14px;border:1px solid #e0ddd5;">{value or "-"}</td></tr>'
        for label, value in rows
    )
    return (
        '<table style="border-collapse:collapse;width:100%;font-family:\'DM Sans\',Arial,sans-serif;'
        f'font-size:14px;color:#2b2b2b;">{body_rows}</table>'
    )


def owner_email_html(heading: str, rows: list[tuple[str, str]]) -> str:
    table = rows_to_html_table(rows)
    return f"""
    <div style="font-family:'DM Sans',Arial,sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:#1f3d2b;padding:20px 24px;">
        <h1 style="color:#ffffff;font-size:18px;margin:0;">{heading}</h1>
      </div>
      <div style="padding:20px 24px;background:#ffffff;">
        {table}
      </div>
      <div style="padding:14px 24px;background:#faf8f4;color:#777;font-size:12px;">
        Sent automatically from the {COMPANY_NAME} website enquiry form.
      </div>
    </div>
    """


def customer_email_html(name: str, rows: list[tuple[str, str]]) -> str:
    table = rows_to_html_table(rows)
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;margin:0 auto;border-collapse:collapse;border:1px solid #e0ddd5;font-family:'DM Sans',Arial,sans-serif;">
      <tr>
        <td align="center" bgcolor="#1f3d2b" style="background:#1f3d2b;padding:20px 24px;">
          <img src="cid:{LOGO_CID}" alt="{COMPANY_NAME}" width="48" height="48" style="height:48px;width:48px;border-radius:8px;vertical-align:middle;background:#000000;display:inline-block;">
          <span style="color:#ffffff;font-size:20px;font-weight:700;vertical-align:middle;margin-left:10px;">{COMPANY_NAME}</span>
        </td>
      </tr>
      <tr>
        <td bgcolor="#ffffff" style="padding:24px;background:#ffffff;">
        <p style="font-size:15px;color:#2b2b2b;">Hi {name},</p>
        <p style="font-size:15px;color:#2b2b2b;">
          Thank you for reaching out to {COMPANY_NAME}. Our export manager will respond within
          <strong>24 hours</strong>.
        </p>
        <p style="font-size:15px;color:#2b2b2b;">Here are your order details:</p>
        {table}
        <p style="font-size:14px;color:#2b2b2b;margin-top:18px;">
          A copy of our product catalogue is attached to this email for your reference.
        </p>
        </td>
      </tr>
      <tr>
        <td bgcolor="#faf8f4" style="padding:20px 24px;background:#faf8f4;border-top:1px solid #e0ddd5;font-size:13px;color:#444;">
          <div style="font-weight:700;color:#1f3d2b;font-size:15px;margin-bottom:6px;">{COMPANY_NAME}</div>
          <div>Email: <a href="mailto:{COMPANY_EMAIL}" style="color:#1f3d2b;">{COMPANY_EMAIL}</a></div>
          <div>Phone: {COMPANY_PHONE}</div>
        </td>
      </tr>
    </table>
    """


def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    inline_logo: bool = False,
    attach_pdf: bool = False,
    from_email: str = OWNER_EMAIL,
) -> None:
    if not SMTP_USER or not SMTP_PASSWORD:
        raise HTTPException(status_code=500, detail="Mail server is not configured.")

    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["From"] = f"{FROM_NAME} <{from_email}>"
    msg["Reply-To"] = OWNER_EMAIL
    msg["To"] = to_email

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(html_body, "html"))
    msg.attach(alt)

    if inline_logo and os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f:
            logo = MIMEImage(f.read())
            logo.add_header("Content-ID", f"<{LOGO_CID}>")
            logo.add_header("Content-Disposition", "inline", filename="logo.png")
            msg.attach(logo)

    if attach_pdf and os.path.exists(CATALOGUE_PATH):
        with open(CATALOGUE_PATH, "rb") as f:
            part = MIMEApplication(f.read(), _subtype="pdf")
            part.add_header(
                "Content-Disposition", "attachment", filename="Kapi-Dwaja-Exports-Catalogue-2026.pdf"
            )
            msg.attach(part)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(from_email, [to_email], msg.as_string())


_mail_executor = ThreadPoolExecutor(max_workers=4)


def send_both_emails(owner_call, customer_call) -> None:
    owner_future = _mail_executor.submit(owner_call)
    customer_future = _mail_executor.submit(customer_call)
    owner_future.result()
    customer_future.result()


SHEET_COLUMNS = [
    "name", "company", "email", "phone", "country", "buyer_type",
    "product", "quantity", "incoterm", "address", "purpose", "message",
]


def log_to_sheet(request_type: str, fields: dict) -> None:
    """Append one row to the Google Sheet via an Apps Script Web App webhook.
    Best-effort: logs a warning and does not raise if the sheet is unreachable,
    so a broken webhook never blocks the actual enquiry email flow."""
    if not SHEETS_WEBHOOK_URL:
        return
    row = {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "type": request_type}
    row.update({col: fields.get(col, "") for col in SHEET_COLUMNS})
    try:
        requests.post(SHEETS_WEBHOOK_URL, json=row, timeout=10)
    except requests.RequestException as exc:
        logger.warning("Failed to log %s enquiry to Google Sheet: %s", request_type, exc)


@app.post("/api/quote")
def submit_quote(payload: QuoteRequest):
    rows = [
        ("Name", f"{payload.first_name} {payload.last_name}"),
        ("Company", payload.company),
        ("Email", payload.email),
        ("Phone / WhatsApp", payload.phone),
        ("Country", payload.country),
        ("Buyer Type", payload.buyer_type),
        ("Product(s) of Interest", payload.product),
        ("Quantity Required", payload.quantity),
        ("Preferred Incoterm", payload.incoterm),
        ("Message", payload.message),
    ]

    send_both_emails(
        lambda: send_email(
            OWNER_EMAIL,
            f"New Quote Request - {payload.company}",
            owner_email_html("New Quote Request", rows),
            from_email=SMTP_USER,
        ),
        lambda: send_email(
            payload.email,
            "We've received your quote request",
            customer_email_html(payload.first_name, rows),
            inline_logo=True,
            attach_pdf=True,
        ),
    )
    log_to_sheet("Quote Request", {
        "name": f"{payload.first_name} {payload.last_name}",
        "company": payload.company,
        "email": payload.email,
        "phone": payload.phone,
        "country": payload.country,
        "buyer_type": payload.buyer_type,
        "product": payload.product,
        "quantity": payload.quantity,
        "incoterm": payload.incoterm,
        "message": payload.message,
    })
    return {"status": "ok"}


@app.post("/api/sample")
def submit_sample(payload: SampleRequest):
    rows = [
        ("Name", payload.name),
        ("Company", payload.company),
        ("Email", payload.email),
        ("WhatsApp", payload.phone),
        ("Product for Sample", payload.product),
        ("Delivery Address", payload.address),
        ("Purpose / Note", payload.purpose),
    ]

    send_both_emails(
        lambda: send_email(
            OWNER_EMAIL,
            f"New Sample Request - {payload.company}",
            owner_email_html("New Sample Request", rows),
            from_email=SMTP_USER,
        ),
        lambda: send_email(
            payload.email,
            "We've received your sample request",
            customer_email_html(payload.name, rows),
            inline_logo=True,
            attach_pdf=True,
        ),
    )
    log_to_sheet("Sample Request", {
        "name": payload.name,
        "company": payload.company,
        "email": payload.email,
        "phone": payload.phone,
        "product": payload.product,
        "address": payload.address,
        "purpose": payload.purpose,
    })
    return {"status": "ok"}
