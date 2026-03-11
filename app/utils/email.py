import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List


def send_email(to_email: str, subject: str, html_body: str, text_body: str):
    """Send email using SMTP"""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = os.getenv('SMTP_EMAIL')
        msg['To'] = to_email

        part1 = MIMEText(text_body, 'plain')
        part2 = MIMEText(html_body, 'html')
        msg.attach(part1)
        msg.attach(part2)

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
    text_body = f"Welcome to Jobscape!\n\nVerify your email: {verify_url}\n\nThis link expires in 24 hours."
    send_email(to_email, subject, html_body, text_body)


def send_work_email_verification(to_email: str, code: str, company_name: str):
    """Send 6-digit verification code to work email"""
    subject = f"Verify your work email - {code}"
    html_body = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                <h2 style="color: #2563eb;">Verify Your Work Email</h2>
                <p>Hi {company_name},</p>
                <p>Your Jobscape work email verification code:</p>
                <div style="background-color: #f0f0f0; padding: 20px; text-align: center; border-radius: 5px; margin: 20px 0;">
                    <h1 style="font-size: 36px; letter-spacing: 8px; margin: 0; color: #2563eb; font-family: 'Courier New', monospace;">{code}</h1>
                </div>
                <p><strong>This code expires in 15 minutes.</strong></p>
                <p>If you didn't request this, please ignore this email.</p>
            </div>
        </body>
    </html>
    """
    text_body = f"Hi {company_name},\n\nYour verification code: {code}\n\nExpires in 15 minutes."
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
            <a href="{reset_url}" style="display: inline-block; padding: 10px 20px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 5px;">
                Reset Password
            </a>
            <p>Or copy this link: {reset_url}</p>
            <p>This link expires in 1 hour. If you didn't request this, please ignore this email.</p>
        </body>
    </html>
    """
    text_body = f"Reset your password: {reset_url}\n\nExpires in 1 hour."
    send_email(to_email, subject, html_body, text_body)


# ===== NEW: Feature 4.3 — Selection Round Email =====

def _send_selection_email(seeker_email: str, seeker_name: str, job, rounds: List[dict], instructions: Optional[str]):
    """Send selection process details to a shortlisted applicant."""
    rounds_html = ''
    for r in rounds:
        mode = 'Online' if r.get('is_online') else 'In-Person'
        loc = r.get('location_or_link', '')
        duration = f"{r.get('duration_minutes', '?')} min" if r.get('duration_minutes') else ''

        rounds_html += f"""
        <div style="border:1px solid #e5e7eb; border-radius:8px; padding:12px; margin-bottom:10px;">
            <strong>Round {r['number']}: {r['title']}</strong>
            <span style="background:#f5f3ff;color:#7c3aed;padding:2px 8px;border-radius:12px;font-size:12px;margin-left:8px;">
                {r['type'].title()}
            </span>
            {f'<p style="color:#6b7280;margin:4px 0">{r["description"]}</p>' if r.get('description') else ''}
            <p style="color:#6b7280;font-size:13px;margin:4px 0">
                {mode} {f'• {duration}' if duration else ''} {f'• {loc}' if loc else ''}
            </p>
        </div>"""

    instructions_html = (
        f"<p><strong>Additional Instructions:</strong> {instructions}</p>"
        if instructions else ''
    )

    html_body = f"""
    <html><body style="font-family:Arial;max-width:600px;margin:0 auto;padding:20px">
        <div style="background:linear-gradient(135deg,#7c3aed,#6d28d9);padding:24px;border-radius:12px 12px 0 0">
            <h1 style="color:white;margin:0">📋 Selection Process Details</h1>
        </div>
        <div style="border:1px solid #e5e7eb;padding:24px;border-radius:0 0 12px 12px">
            <p>Hi <strong>{seeker_name}</strong>,</p>
            <p>Here are the selection process details for
               <strong>{job.title}</strong> at <strong>{job.employer.company_name}</strong>:</p>
            {rounds_html}
            {instructions_html}
            <p style="color:#6b7280;font-size:13px">Best regards,<br>{job.employer.company_name}</p>
        </div>
    </body></html>"""

    text_body = (
        f"Selection Process for {job.title} at {job.employer.company_name}\n\n"
        + "\n".join(
            f"Round {r['number']}: {r['title']} ({r['type']})"
            for r in rounds
        )
        + (f"\n\nInstructions: {instructions}" if instructions else "")
    )

    send_email(
        to_email=seeker_email,
        subject=f"Selection Process — {job.title}",
        html_body=html_body,
        text_body=text_body
    )


def send_round_advancement_email(seeker_email: str, seeker_name: str, job_title: str, company_name: str, round_number: int, round_title: str, round_type: str, instructions: Optional[str] = None):
    """Notify candidate they've moved to the next round."""
    subject = f"Congratulations! You've advanced to Round {round_number} for {job_title}"
    
    html_body = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                <h2 style="color: #2563eb;">Good News!</h2>
                <p>Hi {seeker_name},</p>
                <p>We are pleased to inform you that you have advanced to the next stage of the selection process for the <strong>{job_title}</strong> position at <strong>{company_name}</strong>.</p>
                
                <div style="background-color: #f9fafb; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #2563eb;">
                    <h3 style="margin-top: 0;">Next Round: Round {round_number}</h3>
                    <p><strong>Title:</strong> {round_title}</p>
                    <p><strong>Type:</strong> {round_type.replace('_', ' ').title()}</p>
                    {f'<p><strong>Instructions:</strong> {instructions}</p>' if instructions else ''}
                </div>
                
                <p>The employer will contact you shortly with further details or a specific schedule.</p>
                <p>Best of luck!</p>
                <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="font-size: 12px; color: #666;">This is an automated notification from Jobscape.</p>
            </div>
        </body>
    </html>
    """
    text_body = f"Hi {seeker_name},\n\nCongratulations! You've advanced to Round {round_number} ({round_title}) for {job_title} at {company_name}.\n\nNext steps: {instructions if instructions else 'The employer will contact you shortly.'}\n\nBest of luck!"
    
    send_email(seeker_email, subject, html_body, text_body)


def send_rejection_email(seeker_email: str, seeker_name: str, job_title: str, company_name: str):
    """Send an empathetic rejection email."""
    subject = f"Update on your application for {job_title} at {company_name}"
    
    html_body = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                <p>Hi {seeker_name},</p>
                <p>Thank you for taking the time to apply for the <strong>{job_title}</strong> position at <strong>{company_name}</strong> and for sharing your background with us.</p>
                <p>We received many applications for this role, and after careful consideration, we have decided not to move forward with your candidacy at this time.</p>
                <p>This was a difficult decision, as we truly appreciate your interest in joining our team. We encourage you to keep an eye on our career page for future openings that might be a good fit for your skills and experience.</p>
                <p>We wish you all the best in your job search and your future professional endeavors.</p>
                <p>Sincerely,</p>
                <p>The {company_name} Hiring Team</p>
                <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="font-size: 12px; color: #666;">This is an automated notification from Jobscape on behalf of {company_name}.</p>
            </div>
        </body>
    </html>
    """
    text_body = f"Hi {seeker_name},\n\nThank you for taking the time to apply for the {job_title} position at {company_name} and for sharing your background with us.\n\nWe received many applications for this role, and after careful consideration, we have decided not to move forward with your candidacy at this time.\n\nThis was a difficult decision, as we truly appreciate your interest in joining our team. We encourage you to keep an eye on our career page for future openings that might be a good fit for your skills and experience.\n\nWe wish you all the best in your job search and your future professional endeavors.\n\nSincerely,\nThe {company_name} Hiring Team"
    
    send_email(seeker_email, subject, html_body, text_body)