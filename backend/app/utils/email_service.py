# backend/app/utils/email_service.py
import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from app import config

class EmailService:
    """Email service using SMTP (Free Gmail)"""
    
    @staticmethod
    def generate_otp() -> str:
        """Generate 6-digit OTP"""
        return str(random.randint(100000, 999999))
    
    @staticmethod
    async def send_email(to_email: str, subject: str, body_html: str, body_text: str = None):
        """Send email via SMTP"""
        if not config.SMTP_USER or not config.SMTP_PASSWORD:
            print("⚠️ SMTP not configured. Email not sent.")
            print(f"Would have sent to {to_email}: {subject}")
            return False
        
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{config.SMTP_FROM_NAME} <{config.SMTP_FROM_EMAIL}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add text and HTML parts
            if body_text:
                part1 = MIMEText(body_text, 'plain')
                msg.attach(part1)
            
            part2 = MIMEText(body_html, 'html')
            msg.attach(part2)
            
            # Connect and send
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
                server.starttls()
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
                server.send_message(msg)
            
            print(f"✅ Email sent to {to_email}: {subject}")
            return True
        except Exception as e:
            print(f"❌ Email send error: {e}")
            return False
    
    @staticmethod
    async def send_otp_email(to_email: str, otp: str, username: str):
        """Send OTP email for password reset"""
        subject = "Your OTP for Password Reset - QR Attendance System"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    margin: 0;
                    padding: 0;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f9f9f9;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                    border-radius: 10px 10px 0 0;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 24px;
                }}
                .content {{
                    background: white;
                    padding: 30px;
                    border-radius: 0 0 10px 10px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .otp-box {{
                    background: #f0f0f0;
                    border: 2px dashed #667eea;
                    padding: 20px;
                    text-align: center;
                    font-size: 32px;
                    font-weight: bold;
                    letter-spacing: 8px;
                    color: #667eea;
                    margin: 20px 0;
                    border-radius: 5px;
                    font-family: 'Courier New', monospace;
                }}
                .warning {{
                    background: #fff3cd;
                    border-left: 4px solid #ffc107;
                    padding: 15px;
                    margin: 20px 0;
                }}
                .warning strong {{
                    color: #856404;
                }}
                .warning ul {{
                    margin: 10px 0;
                    padding-left: 20px;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #eee;
                    font-size: 12px;
                    color: #999;
                }}
                .button {{
                    display: inline-block;
                    padding: 12px 30px;
                    background: #667eea;
                    color: white;
                    text-decoration: none;
                    border-radius: 5px;
                    margin: 20px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔐 Password Reset Request</h1>
                </div>
                <div class="content">
                    <p>Hello <strong>{username}</strong>,</p>
                    <p>You have requested to reset your password for the QR Attendance System. Please use the One-Time Password (OTP) below to proceed:</p>
                    
                    <div class="otp-box">{otp}</div>
                    
                    <div class="warning">
                        <strong>⚠️ Security Notice:</strong>
                        <ul>
                            <li>This OTP is valid for <strong>{config.OTP_EXPIRE_MINUTES} minutes</strong> only</li>
                            <li>Never share this OTP with anyone</li>
                            <li>If you didn't request this, please ignore this email and your password will remain unchanged</li>
                            <li>For security, you have a maximum of {config.MAX_OTP_ATTEMPTS} attempts</li>
                        </ul>
                    </div>
                    
                    <p>After entering the OTP, you'll be able to set a new password for your account.</p>
                    
                    <p style="margin-top: 30px;">Best regards,<br><strong>QR Attendance System Team</strong></p>
                </div>
                <div class="footer">
                    <p>This is an automated email. Please do not reply.</p>
                    <p>&copy; {datetime.now().year} QR Attendance System. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text = f"""
        Password Reset Request - QR Attendance System
        
        Hello {username},
        
        Your One-Time Password (OTP) for password reset is:
        
        {otp}
        
        This OTP is valid for {config.OTP_EXPIRE_MINUTES} minutes only.
        
        Security Notice:
        - Never share this OTP with anyone
        - If you didn't request this, please ignore this email
        - You have a maximum of {config.MAX_OTP_ATTEMPTS} attempts
        
        Best regards,
        QR Attendance System Team
        """
        
        return await EmailService.send_email(to_email, subject, html, text)
    
    @staticmethod
    async def send_welcome_email(to_email: str, username: str, role: str, temp_password: str = None):
        """Send welcome email to new user"""
        subject = f"Welcome to QR Attendance System - {role.title()} Account Created"
        
        password_info = ""
        if temp_password:
            password_info = f"""
            <div style="background: #e8f5e9; padding: 20px; border-left: 4px solid #4caf50; margin: 20px 0; border-radius: 5px;">
                <strong style="color: #2e7d32;">📧 Your Login Credentials:</strong><br><br>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px 0;"><strong>Username:</strong></td>
                        <td style="padding: 8px 0;"><code style="background: #f5f5f5; padding: 4px 8px; border-radius: 3px;">{username}</code></td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;"><strong>Temporary Password:</strong></td>
                        <td style="padding: 8px 0;"><code style="background: #f5f5f5; padding: 4px 8px; border-radius: 3px;">{temp_password}</code></td>
                    </tr>
                </table>
                <p style="margin-top: 15px; color: #f57c00;">⚠️ <em>Please change your password after first login for security.</em></p>
            </div>
            """
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    margin: 0;
                    padding: 0;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f9f9f9;
                }}
                .header {{
                    background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                    border-radius: 10px 10px 0 0;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 24px;
                }}
                .content {{
                    background: white;
                    padding: 30px;
                    border-radius: 0 0 10px 10px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .role-badge {{
                    display: inline-block;
                    background: #667eea;
                    color: white;
                    padding: 5px 15px;
                    border-radius: 20px;
                    font-size: 14px;
                    font-weight: bold;
                    margin: 10px 0;
                }}
                .features {{
                    background: #f5f5f5;
                    padding: 20px;
                    border-radius: 5px;
                    margin: 20px 0;
                }}
                .features ul {{
                    margin: 10px 0;
                    padding-left: 20px;
                }}
                .features li {{
                    margin: 8px 0;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #eee;
                    font-size: 12px;
                    color: #999;
                }}
                .button {{
                    display: inline-block;
                    padding: 12px 30px;
                    background: #11998e;
                    color: white;
                    text-decoration: none;
                    border-radius: 5px;
                    margin: 20px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Welcome to QR Attendance System!</h1>
                </div>
                <div class="content">
                    <p>Hello <strong>{username}</strong>,</p>
                    <p>Congratulations! Your account has been successfully created.</p>
                    
                    <p>Your Role: <span class="role-badge">{role.upper()}</span></p>
                    
                    {password_info}
                    
                    <div class="features">
                        <p><strong>What you can do with your account:</strong></p>
                        <ul>
                            <li>✅ View and manage attendance records</li>
                            <li>📊 Generate detailed attendance reports</li>
                            <li>📈 Track attendance percentages</li>
                            <li>🔔 Receive important notifications</li>
                            <li>🔐 Secure password management</li>
                        </ul>
                    </div>
                    
                    <p style="margin-top: 30px;">If you have any questions or need assistance, please don't hesitate to contact your administrator.</p>
                    
                    <p style="margin-top: 30px;">Best regards,<br><strong>QR Attendance System Team</strong></p>
                </div>
                <div class="footer">
                    <p>This is an automated email. Please do not reply.</p>
                    <p>&copy; {datetime.now().year} QR Attendance System. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text = f"""
        Welcome to QR Attendance System!
        
        Hello {username},
        
        Your {role.title()} account has been successfully created.
        
        """
        
        if temp_password:
            text += f"""
        Your Login Credentials:
        Username: {username}
        Temporary Password: {temp_password}
        
        ⚠️ Please change your password after first login.
        """
        
        text += f"""
        
        What you can do:
        - View and manage attendance records
        - Generate detailed reports
        - Track attendance percentages
        - Receive notifications
        
        Best regards,
        QR Attendance System Team
        """
        
        return await EmailService.send_email(to_email, subject, html, text)
    
    @staticmethod
    async def send_low_attendance_alert(to_email: str, student_name: str, percentage: float, required: float):
        """Send low attendance warning email"""
        subject = f"⚠️ Low Attendance Alert - {student_name}"
        
        shortfall = required - percentage
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    margin: 0;
                    padding: 0;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f9f9f9;
                }}
                .header {{
                    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                    border-radius: 10px 10px 0 0;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 24px;
                }}
                .content {{
                    background: white;
                    padding: 30px;
                    border-radius: 0 0 10px 10px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .alert {{
                    background: #ffebee;
                    border-left: 4px solid #f44336;
                    padding: 20px;
                    margin: 20px 0;
                    border-radius: 5px;
                }}
                .stats {{
                    background: white;
                    padding: 20px;
                    border: 2px solid #f44336;
                    border-radius: 5px;
                    margin: 20px 0;
                }}
                .stat-row {{
                    display: flex;
                    justify-content: space-between;
                    padding: 10px 0;
                    border-bottom: 1px solid #eee;
                }}
                .stat-row:last-child {{
                    border-bottom: none;
                }}
                .stat-label {{
                    font-weight: bold;
                    color: #666;
                }}
                .stat-value {{
                    font-size: 18px;
                    font-weight: bold;
                }}
                .danger {{ color: #f44336; }}
                .warning {{ color: #ff9800; }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #eee;
                    font-size: 12px;
                    color: #999;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>⚠️ Low Attendance Alert</h1>
                </div>
                <div class="content">
                    <p>Dear Parent/Guardian of <strong>{student_name}</strong>,</p>
                    
                    <div class="alert">
                        <strong style="font-size: 18px;">⚠️ Attention Required!</strong><br>
                        <p style="margin-top: 10px;">The attendance percentage has fallen below the required threshold. Immediate action is needed to improve attendance.</p>
                    </div>
                    
                    <div class="stats">
                        <h3 style="margin-top: 0; color: #f44336;">📊 Attendance Statistics:</h3>
                        
                        <div class="stat-row">
                            <span class="stat-label">Current Attendance:</span>
                            <span class="stat-value danger">{percentage}%</span>
                        </div>
                        
                        <div class="stat-row">
                            <span class="stat-label">Required Attendance:</span>
                            <span class="stat-value">{required}%</span>
                        </div>
                        
                        <div class="stat-row">
                            <span class="stat-label">Shortfall:</span>
                            <span class="stat-value danger">-{shortfall:.2f}%</span>
                        </div>
                    </div>
                    
                    <div style="background: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <strong style="color: #856404;">📌 Important Note:</strong>
                        <p style="margin: 10px 0; color: #856404;">Please ensure regular attendance to meet the minimum requirement. Consistent absence may affect academic performance and eligibility for examinations.</p>
                    </div>
                    
                    <p style="margin-top: 30px;">If there are any genuine reasons for absence, please contact the class teacher or school administration.</p>
                    
                    <p style="margin-top: 30px;">Best regards,<br><strong>QR Attendance System</strong></p>
                </div>
                <div class="footer">
                    <p>This is an automated alert from QR Attendance System.</p>
                    <p>&copy; {datetime.now().year} QR Attendance System. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text = f"""
        ⚠️ LOW ATTENDANCE ALERT
        
        Dear Parent/Guardian of {student_name},
        
        ATTENTION REQUIRED!
        The attendance percentage has fallen below the required threshold.
        
        Attendance Statistics:
        - Current Attendance: {percentage}%
        - Required Attendance: {required}%
        - Shortfall: -{shortfall:.2f}%
        
        Please ensure regular attendance to meet the minimum requirement.
        Consistent absence may affect academic performance.
        
        If there are genuine reasons for absence, please contact the school.
        
        Best regards,
        QR Attendance System
        """
        
        return await EmailService.send_email(to_email, subject, html, text)
    
    @staticmethod
    async def send_attendance_report_email(to_email: str, report_data: dict):
        """Send attendance report email (for monthly/periodic reports)"""
        subject = f"Attendance Report - {report_data.get('period', 'Monthly')}"
        
        student_name = report_data.get('student_name', 'Student')
        total_days = report_data.get('total_days', 0)
        present_days = report_data.get('present_days', 0)
        absent_days = report_data.get('absent_days', 0)
        percentage = report_data.get('percentage', 0.0)
        period = report_data.get('period', 'This Month')
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                    border-radius: 10px 10px 0 0;
                }}
                .content {{
                    background: white;
                    padding: 30px;
                    border: 1px solid #ddd;
                    border-radius: 0 0 10px 10px;
                }}
                .stats-grid {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 15px;
                    margin: 20px 0;
                }}
                .stat-box {{
                    background: #f5f5f5;
                    padding: 20px;
                    border-radius: 8px;
                    text-align: center;
                }}
                .stat-value {{
                    font-size: 32px;
                    font-weight: bold;
                    color: #667eea;
                }}
                .stat-label {{
                    color: #666;
                    margin-top: 5px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📊 Attendance Report</h1>
                    <p>{period}</p>
                </div>
                <div class="content">
                    <p>Dear <strong>{student_name}</strong>,</p>
                    
                    <p>Here is your attendance summary for {period}:</p>
                    
                    <div class="stats-grid">
                        <div class="stat-box">
                            <div class="stat-value">{total_days}</div>
                            <div class="stat-label">Total Days</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-value">{present_days}</div>
                            <div class="stat-label">Present</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-value">{absent_days}</div>
                            <div class="stat-label">Absent</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-value">{percentage}%</div>
                            <div class="stat-label">Percentage</div>
                        </div>
                    </div>
                    
                    <p>Keep up the good work!</p>
                    
                    <p>Best regards,<br><strong>QR Attendance System</strong></p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text = f"""
        Attendance Report - {period}
        
        Dear {student_name},
        
        Here is your attendance summary:
        
        Total Days: {total_days}
        Present: {present_days}
        Absent: {absent_days}
        Percentage: {percentage}%
        
        Best regards,
        QR Attendance System
        """
        
        return await EmailService.send_email(to_email, subject, html, text)