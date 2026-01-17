import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_EMAIL)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

def send_verification_email(to_email: str, token: str) -> bool:
    """Send email verification link using Gmail SMTP"""
    
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("⚠️ SMTP not configured. Email not sent.")
        print(f"📧 Verification token for {to_email}: {token}")
        return False
    
    verification_url = f"{FRONTEND_URL}/verify-email?token={token}"
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = EMAIL_FROM
        msg['To'] = to_email
        msg['Subject'] = "Verify Your Jobscape Account"
        
        # HTML content
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f4f4f4; padding: 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 30px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 32px;">Welcome to Jobscape!</h1>
                        </td>
                    </tr>
                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px 30px;">
                            <h2 style="margin: 0 0 20px 0; color: #333333; font-size: 24px;">Verify Your Email Address</h2>
                            <p style="margin: 0 0 20px 0; color: #666666; font-size: 16px; line-height: 1.6;">
                                Thanks for signing up! Please verify your email address by clicking the button below:
                            </p>
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td align="center" style="padding: 20px 0;">
                                        <a href="{verification_url}" style="display: inline-block; padding: 15px 40px; background-color: #667eea; color: #ffffff; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 16px;">
                                            Verify Email
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            <p style="margin: 20px 0; color: #666666; font-size: 14px; line-height: 1.6;">
                                Or copy and paste this link into your browser:
                            </p>
                            <p style="margin: 0 0 20px 0; padding: 15px; background-color: #f8f9fa; border-radius: 5px; word-break: break-all; font-size: 14px; color: #667eea;">
                                {verification_url}
                            </p>
                            <p style="margin: 30px 0 0 0; padding-top: 30px; border-top: 1px solid #e0e0e0; color: #999999; font-size: 14px; line-height: 1.6;">
                                This link will expire in 24 hours.<br>
                                If you didn't create an account, you can safely ignore this email.
                            </p>
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f8f9fa; padding: 20px; text-align: center;">
                            <p style="margin: 0; color: #999999; font-size: 12px;">
                                © 2026 Jobscape. All rights reserved.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
        """
        
        msg.attach(MIMEText(html, 'html'))
        
        # Send email via Gmail SMTP
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
        
        print(f"✅ Verification email sent to {to_email}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        print(f"📧 Verification token for {to_email}: {token}")
        return False


def send_password_reset_email(to_email: str, token: str) -> bool:
    """Send password reset link using Gmail SMTP"""
    
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("⚠️ SMTP not configured. Email not sent.")
        print(f"📧 Reset token for {to_email}: {token}")
        return False
    
    reset_url = f"{FRONTEND_URL}/reset-password?token={token}"
    
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = EMAIL_FROM
        msg['To'] = to_email
        msg['Subject'] = "Reset Your Jobscape Password"
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f4f4f4; padding: 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background-color: #dc3545; padding: 40px 30px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 32px;">Password Reset</h1>
                        </td>
                    </tr>
                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px 30px;">
                            <h2 style="margin: 0 0 20px 0; color: #333333; font-size: 24px;">Reset Your Password</h2>
                            <p style="margin: 0 0 20px 0; color: #666666; font-size: 16px; line-height: 1.6;">
                                We received a request to reset your password. Click the button below to create a new password:
                            </p>
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td align="center" style="padding: 20px 0;">
                                        <a href="{reset_url}" style="display: inline-block; padding: 15px 40px; background-color: #dc3545; color: #ffffff; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 16px;">
                                            Reset Password
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            <p style="margin: 20px 0; color: #666666; font-size: 14px; line-height: 1.6;">
                                Or copy and paste this link:
                            </p>
                            <p style="margin: 0 0 20px 0; padding: 15px; background-color: #f8f9fa; border-radius: 5px; word-break: break-all; font-size: 14px; color: #dc3545;">
                                {reset_url}
                            </p>
                            <div style="margin: 30px 0; padding: 20px; background-color: #fff3cd; border-left: 4px solid #ffc107; border-radius: 5px;">
                                <p style="margin: 0; color: #856404; font-size: 14px; line-height: 1.6;">
                                    <strong>Security Notice:</strong><br>
                                    This link expires in 1 hour. If you didn't request a password reset, please ignore this email.
                                </p>
                            </div>
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f8f9fa; padding: 20px; text-align: center;">
                            <p style="margin: 0; color: #999999; font-size: 12px;">
                                © 2026 Jobscape. All rights reserved.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
        """
        
        msg.attach(MIMEText(html, 'html'))
        
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
        
        print(f"✅ Password reset email sent to {to_email}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        print(f"📧 Reset token for {to_email}: {token}")
        return False
