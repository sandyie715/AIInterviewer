from flask import Blueprint, request, jsonify
from datetime import datetime
import json
import os
import sys
from pathlib import Path
import pytz

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.mongodb_service import save_interview_result
from services.drive_service import upload_to_drive
from utils.helpers import parse_iso_datetime

interviews_bp = Blueprint('interviews', __name__, url_prefix='/api/interviews')

# Initialize OpenAI lazily to avoid import errors
client = None

def get_openai_client():
    global client
    if client is None:
        try:
            from openai import OpenAI
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not set in environment variables")
            client = OpenAI(api_key=api_key)
            print("✅ OpenAI client initialized")
        except Exception as e:
            print(f"❌ Error initializing OpenAI: {e}")
            raise
    return client

UTC = pytz.utc
IST = pytz.timezone("Asia/Kolkata")

SYSTEM_PROMPT = """
You are an expert technical interviewer.
Generate clear, concise interview questions.
Ask only one question at a time.
Make questions specific to the job description provided.
"""

# In-memory storage for current interview session
interview_sessions = {}

@interviews_bp.route('/generate-questions', methods=['POST'])
def generate_questions():
    """Generate interview questions based on job description"""
    try:
        data = request.json
        jd_text = data.get("jd", "").strip()
        interview_id = data.get("interview_id")

        if not jd_text:
            return jsonify({"error": "Job description required"}), 400

        if not interview_id:
            return jsonify({"error": "Interview ID required"}), 400

        # 🔐 Interview status validation & atomic lock
        # This is the CRITICAL part - prevents duplicate interview starts
        from services.mongodb_service import scheduled_interviews

        update_result = scheduled_interviews.find_one_and_update(
            {
                "interview_id": interview_id,
                "interview_status": "scheduled"  # Only allow if status is "scheduled"
            },
            {
                "$set": {
                    "interview_status": "started",
                    "started_at": datetime.utcnow()
                }
            }
        )

        if not update_result:
            # Interview is already started, completed, or doesn't exist
            existing = scheduled_interviews.find_one({"interview_id": interview_id})
            
            if existing:
                current_status = existing.get("interview_status")
                if current_status == "started":
                    return jsonify({
                        "status": "already_started",
                        "message": "Interview already in progress from another session"
                    }), 403
                elif current_status == "completed":
                    return jsonify({
                        "status": "completed",
                        "message": "Interview link already used or invalid"
                    }), 403
            
            return jsonify({
                "status": "expired",
                "message": "Interview link already used or invalid"
            }), 403

        # ✅ Continue only if lock succeeded
        prompt = f"""
Based on the following Job Description, generate exactly 5 interview questions.
Questions should be technical and role-specific.
Make them clear and conversational.

Job Description:
{jd_text}

Return ONLY the numbered questions, one per line.
"""

        openai_client = get_openai_client()
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4
        )

        raw_text = response.choices[0].message.content
        questions = parse_questions(raw_text)

        interview_sessions[interview_id] = {
            "questions": questions,
            "current_index": 0,
            "qna": []
        }

        return jsonify({
            "status": "success",
            "total": len(questions),
            "questions": questions
        }), 200

    except Exception as e:
        print(f"Error generating questions: {e}")
        return jsonify({"error": str(e)}), 500



@interviews_bp.route('/next-question/<interview_id>', methods=['GET'])
def next_question(interview_id):
    """Get next interview question"""
    try:
        if interview_id not in interview_sessions:
            return jsonify({"error": "Interview session not found"}), 404
        
        session = interview_sessions[interview_id]
        current_index = session["current_index"]
        questions = session["questions"]
        
        if current_index >= len(questions):
            return jsonify({"done": True, "question": ""}), 200
        
        question = questions[current_index]
        session["current_index"] += 1
        
        return jsonify({
            "done": False,
            "question": question,
            "questionNumber": current_index + 1,
            "totalQuestions": len(questions)
        }), 200
    
    except Exception as e:
        print(f"Error getting next question: {e}")
        return jsonify({"error": str(e)}), 500


@interviews_bp.route('/submit-answer/<interview_id>', methods=['POST'])
def submit_answer(interview_id):
    """Submit answer to a question"""
    try:
        if interview_id not in interview_sessions:
            return jsonify({"error": "Interview session not found"}), 404
        
        data = request.json
        question = data.get("question")
        answer = data.get("answer")
        
        if not question or not answer:
            return jsonify({"error": "Question and answer required"}), 400
        
        session = interview_sessions[interview_id]
        session["qna"].append({
            "question": question,
            "answer": answer
        })
        
        print(f"✅ Answer saved for interview {interview_id}")
        
        return jsonify({
            "status": "success",
            "message": "Answer recorded"
        }), 200
    
    except Exception as e:
        print(f"Error submitting answer: {e}")
        return jsonify({"error": str(e)}), 500


@interviews_bp.route('/evaluate/<interview_id>', methods=['GET'])
def evaluate_interview(interview_id):
    """Get AI evaluation of interview"""
    try:
        if interview_id not in interview_sessions:
            return jsonify({"error": "Interview session not found"}), 404
        
        session = interview_sessions[interview_id]
        qna = session["qna"]
        
        if not qna:
            return jsonify({"error": "No interview data"}), 400
        
        # Prepare combined text
        combined_text = ""
        for idx, qa in enumerate(qna, start=1):
            combined_text += f"""
Q{idx}: {qa['question']}
A{idx}: {qa['answer']}
"""
        
        prompt = f"""
You are a senior technical interview evaluator.
Evaluate the candidate based on their answers.

STRICT RULES:
- Return ONLY valid JSON (no markdown, no extra text)
- All scores MUST be integers 0-10
- Recommendation MUST be: "Yes", "Maybe", or "No"

Interview:
{combined_text}

Return this JSON format exactly:
{{
  "technical_score": 0,
  "communication_score": 0,
  "overall_score": 0,
  "recommendation": "Yes",
  "feedback": "Brief evaluation"
}}
"""
        
        openai_client = get_openai_client()
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a strict evaluator. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Clean JSON response
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()
        
        result = json.loads(result_text)
        
        # Save to MongoDB
        interview_data = {
            "interview_id": interview_id,
            "timestamp": datetime.utcnow().isoformat(),
            "qna": qna,
            "evaluation": result
        }
        
        save_interview_result(interview_data)
        
        print(f"✅ Interview {interview_id} evaluated and saved")
        
        return jsonify(result), 200
    
    except Exception as e:
        print(f"Evaluation error: {e}")
        return jsonify({"error": str(e)}), 500


@interviews_bp.route('/upload-video/<interview_id>', methods=['POST'])
def upload_video(interview_id):
    """Upload interview video to Google Drive"""
    try:
        if 'video' not in request.files:
            return jsonify({"error": "No video file provided"}), 400
        
        video_file = request.files['video']
        candidate_name = request.form.get('candidate_name', 'Candidate')
        candidate_email = request.form.get('candidate_email', '')

        
        if video_file.filename == '':
            return jsonify({"error": "No selected file"}), 400
        
        file_content = video_file.read()
        filename = f"Interview_{candidate_name}_{interview_id}.webm"
        
        # Upload to Google Drive
        result = upload_to_drive(file_content, filename)

        from services.mongodb_service import scheduled_interviews

        scheduled_interviews.update_one(
            {"interview_id": interview_id},
            {
                "$set": {
                    "interview_status": "completed",
                    "completed_at": datetime.utcnow()
                }
            }
        )

        
        if result and result.get('id'):
            print(f"✅ Video uploaded to Google Drive: {result.get('id')}")
            return jsonify({
                "status": "success",
                "message": "Video uploaded successfully",
                "file_id": result.get('id'),
                "file_link": result.get('link')
            }), 200

        else:
            return jsonify({
                "status": "error",
                "message": "Failed to upload video to Google Drive"
            }), 500
    
    except Exception as e:
        print(f"Error uploading video: {e}")
        return jsonify({"error": str(e)}), 500


@interviews_bp.route('/cleanup/<interview_id>', methods=['POST'])
def cleanup_session(interview_id):
    """Clean up interview session from memory"""
    try:
        if interview_id in interview_sessions:
            del interview_sessions[interview_id]
            print(f"✅ Cleaned up session for interview {interview_id}")
        
        return jsonify({"status": "success"}), 200
    
    except Exception as e:
        print(f"Error cleaning up session: {e}")
        return jsonify({"error": str(e)}), 500


def parse_questions(raw_text):
    """Parse raw text into questions list"""
    raw_questions = raw_text.split("\n")
    questions = []
    
    for q in raw_questions:
        q = q.strip()
        if not q:
            continue
        
        # Remove numbering
        for i in range(len(q)):
            if q[i].isdigit():
                continue
            if q[i] in '.):- ':
                q = q[i+1:].strip()
                break
        
        if q:
            questions.append(q)
    
    return questions[:5]  # Limit to 5 questions