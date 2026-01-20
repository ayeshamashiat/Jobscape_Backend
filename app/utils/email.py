import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional


def send_email(to_email: str, subject: str, html_body: str, text_body: str):
    """Send email using SMTP"""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = os.getenv('SMTP_EMAIL')
        msg['To'] = to_email

        # Attach both plain text and HTML versions
        part1 = MIMEText(text_body, 'plain')
        part2 = MIMEText(html_body, 'html')

        msg.attach(part1)
        msg.attach(part2)

        # Send email
        with smtplib.SMTP(os.getenv('EMAIL_HOST'), int(os.getenv('EMAIL_PORT'))) as server:
            server.starttls()
            server.login(os.getenv('SMTP_EMAIL'), os.getenv('SMTP_PASSWORD'))
            server.send_message(msg)

        print(f"✅ Email sent to {to_email}")

    except Exception as e:
        print(f"❌ Email send failed: {e}")
        raise


def send_verification_email(to_email: str, token: str):
    """Send account email verification link"""
    frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
    verify_url = f"{frontend_url}/verify-email/confirm?token={token}"

    subject = "Verify your Jobscape account"

    html_body = f"""
    <html>
        <body style="font-family: Arial, sans-serif;">
            <h2>Welcome to Jobscape!</h2>
            <p>Please verify your email address by clicking the button below:</p>
            <a href="{verify_url}" style="display: inline-block; padding: 10px 20px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 5px;">
                Verify Email
            </a>
            <p>Or copy this link: {verify_url}</p>
            <p>This link expires in 24 hours.</p>
        </body>
    </html>
    """

    text_body = f"""
    Welcome to Jobscape!

    Please verify your email address by visiting: {verify_url}

    This link expires in 24 hours.
    """

    send_email(to_email, subject, html_body, text_body)


# ===== NEW: Work Email Verification =====

def send_work_email_verification(to_email: str, code: str, company_name: str):
    """
    Send 6-digit verification code to work email
    """
    subject = f"Verify your work email - {code}"

    html_body = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                <h2 style="color: #2563eb;">Verify Your Work Email</h2>

                <p>Hi {company_name},</p>

                <p>Thank you for registering on <strong>Jobscape</strong>!</p>

                <p>To complete your registration and verify your company email, please use the verification code below:</p>

                <div style="background-color: #f0f0f0; padding: 20px; text-align: center; border-radius: 5px; margin: 20px 0;">
                    <h1 style="font-size: 36px; letter-spacing: 8px; margin: 0; color: #2563eb; font-family: 'Courier New', monospace;">{code}</h1>
                </div>

                <p><strong>This code expires in 15 minutes.</strong></p>

                <p>If you didn't request this verification, please ignore this email.</p>

                <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">

                <p style="color: #666; font-size: 12px;">
                    This email was sent to {to_email} because you registered a company account on Jobscape.
                </p>
            </div>
        </body>
    </html>
    """

    text_body = f"""
    Verify Your Work Email

    Hi {company_name},

    Thank you for registering on Jobscape!

    Your verification code is: {code}

    This code expires in 15 minutes.

    If you didn't request this verification, please ignore this email.

    ---
    This email was sent to {to_email}
    """

    send_email(to_email, subject, html_body, text_body)


def send_password_reset_email(to_email: str, token: str):
    """Send password reset link"""
    frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
    reset_url = f"{frontend_url}/reset-password?token={token}"

    subject = "Reset your Jobscape password"

    html_body = f"""
    <html>
        <body style="font-family: Arial, sans-serif;">
            <h2>Password Reset Request</h2>
            <p>Click the button below to reset your password:</p>
            <a href="{reset_url}" style="display: inline-block; padding: 10px 20px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 5px;">
                Reset Password
            </a>
            <p>Or copy this link: {reset_url}</p>
            <p>This link expires in 1 hour.</p>
            <p>If you didn't request this, please ignore this email.</p>
        </body>
    </html>
    """

    text_body = f"""
    Password Reset Request

    Click this link to reset your password: {reset_url}

    This link expires in 1 hour.

    If you didn't request this, please ignore this email.
    """

    send_email(to_email, subject, html_body, text_body)