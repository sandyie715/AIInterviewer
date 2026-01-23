import os
import sys
from pathlib import Path
from flask import Flask
from flask_cors import CORS
from flask_mail import Mail
from dotenv import load_dotenv

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

load_dotenv()

app = Flask(__name__)
CORS(app)

# Configure Email
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', True)
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')

# Initialize Mail
mail = Mail(app)

# Import blueprints (after app initialization)
from routes.scheduler import scheduler_bp
from routes.interviews import interviews_bp

# Register blueprints
app.register_blueprint(scheduler_bp)
app.register_blueprint(interviews_bp)

@app.route('/api/health', methods=['GET'])
def health():
    return {'status': 'ok', 'message': 'Backend is running'}, 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)