from flask import Blueprint, request, jsonify
from flask_mail import Mail, Message
from datetime import datetime
import pytz
import uuid
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.mongodb_service import save_scheduled_interview, get_interview_by_id
from utils.helpers import parse_iso_datetime, validate_schedule_data

scheduler_bp = Blueprint('scheduler', __name__, url_prefix='/api/scheduler')

mail = Mail()

UTC = pytz.utc
IST = pytz.timezone("Asia/Kolkata")

@scheduler_bp.route('/schedule', methods=['POST'])
def schedule_interview():
    """Schedule a new interview"""
    try:
        data = request.json
        
        if not validate_schedule_data(data):
            return jsonify({"error": "Missing required fields"}), 400
        
        candidate_email = data.get('candidateEmail')
        candidate_name = data.get('candidateName')
        job_description = data.get('jobDescription')
        start_time_str = data.get('startTime')
        end_time_str = data.get('endTime')
        
        # Parse times (will be in UTC)
        start_time = parse_iso_datetime(start_time_str)
        end_time = parse_iso_datetime(end_time_str)
        
        if not start_time or not end_time:
            return jsonify({"error": "Invalid date format"}), 400
        
        if start_time >= end_time:
            return jsonify({"error": "Start time must be before end time"}), 400
        
        # Generate interview ID
        interview_id = str(uuid.uuid4())
        
        # Build interview link (will be updated with actual domain on production)
        base_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
        interview_link = f"{base_url}/interviewer/index.html?id={interview_id}"
        
        # Convert to IST for email display
        start_time_ist = start_time.astimezone(IST)
        end_time_ist = end_time.astimezone(IST)
        
        start_time_display = start_time_ist.strftime('%d %b %Y, %I:%M %p IST')
        end_time_display = end_time_ist.strftime('%d %b %Y, %I:%M %p IST')
        
        # Prepare interview data
        interview_data = {
            "interview_id": interview_id,
            "candidate_name": candidate_name,
            "candidate_email": candidate_email,
            "job_description": job_description,
            "start_time": start_time,
            "end_time": end_time,
            "interview_link": interview_link,
            "interview_status": "scheduled",
            "scheduled_at": datetime.utcnow()
        }
        
        # Save to MongoDB
        mongodb_id = save_scheduled_interview(interview_data)
        
        if not mongodb_id:
            return jsonify({"error": "Failed to save interview"}), 500
        
        # Send email
        try:
            send_interview_email(candidate_name, candidate_email, interview_link, start_time_display, end_time_display)
        except Exception as e:
            print(f"Email sending error: {e}")
            # Don't fail the entire request if email fails
        
        return jsonify({
            "status": "success",
            "message": "Interview scheduled successfully",
            "interviewId": interview_id,
            "interviewLink": interview_link,
            "mongodb_id": mongodb_id
        }), 201
    
    except Exception as e:
        print(f"Scheduling error: {e}")
        return jsonify({"error": str(e)}), 500


@scheduler_bp.route('/status', methods=['GET'])
def interview_status():
    """Check interview status based on current time"""
    try:
        interview_id = request.args.get("id")
        
        if not interview_id:
            return jsonify({"status": "invalid", "message": "Interview ID required"}), 400
        
        interview = get_interview_by_id(interview_id)
        
        if not interview:
            return jsonify({"status": "not_found", "message": "Interview not found"}), 404
        
        # ✅ BLOCK REUSED / COMPLETED / ALREADY STARTED INTERVIEWS
        status = interview.get("interview_status")

        if status == "completed":
            return jsonify({
                "status": "completed",
                "message": "Interview already completed"
            }), 200
        
        if status == "started":
            return jsonify({
                "status": "already_started",
                "message": "Interview already in progress"
            }), 200


        # Get start and end times
        start_time = interview.get("start_time")
        end_time = interview.get("end_time")
        
        # Ensure they are datetime objects with UTC timezone
        if isinstance(start_time, str):
            start_time = parse_iso_datetime(start_time)
        elif isinstance(start_time, datetime) and start_time.tzinfo is None:
            start_time = UTC.localize(start_time)
        
        if isinstance(end_time, str):
            end_time = parse_iso_datetime(end_time)
        elif isinstance(end_time, datetime) and end_time.tzinfo is None:
            end_time = UTC.localize(end_time)
        
        # Get current time in UTC
        now_utc = datetime.now(UTC)
        
        # Convert to IST for logging
        now_ist = now_utc.astimezone(IST)
        start_ist = start_time.astimezone(IST)
        end_ist = end_time.astimezone(IST)
        
        print(f"[Interview Status] Current: {now_ist.strftime('%Y-%m-%d %I:%M:%S %p IST')}")
        print(f"[Interview Status] Start: {start_ist.strftime('%Y-%m-%d %I:%M:%S %p IST')}")
        print(f"[Interview Status] End: {end_ist.strftime('%Y-%m-%d %I:%M:%S %p IST')}")
        
        # Check if interview is in waiting state
        if now_utc < start_time:
            time_remaining = int((start_time - now_utc).total_seconds())
            return jsonify({
                "status": "waiting",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "start_time_ist": start_ist.strftime('%d %b %Y, %I:%M %p IST'),
                "time_remaining": time_remaining
            }), 200
        
        # Check if interview window has expired
        if now_utc > end_time:
            return jsonify({
                "status": "expired",
                "message": "Interview window has closed"
            }), 200
        
        # Interview is live
        return jsonify({
            "status": "live",
            "jobDescription": interview["job_description"],
            "candidateName": interview["candidate_name"],
            "candidateEmail": interview["candidate_email"],
            "interviewId": interview["interview_id"]
        }), 200


    
    except Exception as e:
        print(f"Status check error: {e}")
        return jsonify({"error": str(e)}), 500


@scheduler_bp.route('/get-interview-data', methods=['GET'])
def get_interview_data():
    """Get interview data"""
    try:
        interview_id = request.args.get("id")
        
        if not interview_id:
            return jsonify({"error": "Interview ID required"}), 400
        
        interview_data = get_interview_by_id(interview_id)
        
        if not interview_data:
            return jsonify({
                "status": "not_found",
                "message": "Interview not found"
            }), 404
        
        interview_data.pop("_id", None)
        
        return jsonify({
            "status": "success",
            "data": {
                "interviewId": interview_data["interview_id"],
                "candidateName": interview_data["candidate_name"],
                "candidateEmail": interview_data["candidate_email"],
                "jobDescription": interview_data["job_description"],
                "startTime": interview_data["start_time"].isoformat() if isinstance(interview_data["start_time"], datetime) else interview_data["start_time"],
                "endTime": interview_data["end_time"].isoformat() if isinstance(interview_data["end_time"], datetime) else interview_data["end_time"],
                "interviewLink": interview_data["interview_link"]
            }
        }), 200
    
    except Exception as e:
        print(f"Get interview data error: {e}")
        return jsonify({"error": str(e)}), 500


def send_interview_email(candidate_name, candidate_email, interview_link, start_time_display, end_time_display):
    """Send interview scheduling email"""
    try:
        msg = Message(
            subject='🎯 Your Interview Schedule - Action Required',
            recipients=[candidate_email],
            html=f"""
            <html>
                <body style="font-family: Arial, sans-serif; background-color: #F5F5F5; padding: 20px;">
                    <div style="max-width: 600px; margin: 0 auto; background-color: #FFFFFF; padding: 30px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
                        <div style="background: linear-gradient(135deg, #F06767 0%, #E85555 100%); padding: 30px; border-radius: 12px; text-align: center; margin-bottom: 30px;">
                            <h2 style="color: #FFFFFF; margin: 0; font-size: 28px; font-weight: 800;">🎯 Interview Invitation</h2>
                            <p style="color: #FFFFFF; margin: 10px 0 0 0; opacity: 0.95; font-size: 14px;">AI-Powered Candidate Assessment</p>
                        </div>
                        
                        <h3 style="color: #333333; font-size: 20px; margin-bottom: 15px;">Hello {candidate_name},</h3>
                        
                        <p style="color: #777777; font-size: 16px; line-height: 1.6; margin-bottom: 25px;">
                            Your interview has been scheduled! Click the button below to join at the scheduled time.
                        </p>
                        
                        <p style="text-align: center; margin: 30px 0;">
                            <a href="{interview_link}" style="background: linear-gradient(135deg, #F06767 0%, #E85555 100%); color: #FFFFFF; padding: 14px 35px; text-decoration: none; border-radius: 12px; display: inline-block; font-weight: 700; font-size: 16px; box-shadow: 0 8px 20px rgba(240, 103, 103, 0.3);">
                                🚀 Join Interview
                            </a>
                        </p>
                        
                        <hr style="border: none; border-top: 2px solid #CCCCCC; margin: 30px 0;">
                        
                        <div style="background-color: #FFE5E5; border-left: 4px solid #F06767; padding: 20px; border-radius: 8px; margin-bottom: 25px;">
                            <h3 style="color: #333333; font-size: 18px; margin: 0 0 15px 0; font-weight: 700;">📅 Interview Details:</h3>
                            <table style="width: 100%; color: #333333; font-size: 15px; line-height: 1.8;">
                                <tr>
                                    <td style="padding: 5px 0; color: #777777; font-weight: 600;">Start Time:</td>
                                    <td style="padding: 5px 0; font-weight: 700; text-align: right;">{start_time_display}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 5px 0; color: #777777; font-weight: 600;">End Time:</td>
                                    <td style="padding: 5px 0; font-weight: 700; text-align: right;">{end_time_display}</td>
                                </tr>
                            </table>
                        </div>
                        
                        <div style="background-color: #FFF9E6; border-left: 4px solid #FFA726; padding: 20px; border-radius: 8px; margin-bottom: 25px;">
                            <h4 style="color: #333333; margin: 0 0 12px 0; font-weight: 700; font-size: 16px;">⚠️ Important Tips:</h4>
                            <ul style="color: #333333; margin: 0; padding-left: 20px; line-height: 1.8; font-size: 14px;">
                                <li>Join 5 minutes early</li>
                                <li>Ensure good lighting and clear audio</li>
                                <li>Use a stable internet connection</li>
                                <li>Please do not refresh the page during the interview</li>
                            </ul>
                        </div>
                        
                        <p style="color: #777777; font-size: 14px; text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #CCCCCC;">
                            See you soon! Good luck with your interview! 🚀
                        </p>
                        
                        <p style="color: #999999; font-size: 12px; text-align: center; margin-top: 20px;">
                            © 2026 Interview Scheduling Platform. All rights reserved.
                        </p>
                    </div>
                </body>
            </html>
            """
        )
        mail.send(msg)
        print(f"✅ Email sent to {candidate_email}")
    except Exception as e:
        print(f"❌ Email error: {e}")
        raise