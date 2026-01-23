from datetime import datetime
import pytz

UTC = pytz.utc

def parse_iso_datetime(date_string):
    """Parse ISO format datetime string to UTC"""
    try:
        if isinstance(date_string, datetime):
            if date_string.tzinfo is None:
                return UTC.localize(date_string)
            return date_string.astimezone(UTC)
        
        # Handle Z timezone indicator
        if date_string.endswith('Z'):
            date_string = date_string.replace('Z', '+00:00')

        # Parse ISO format
        dt = datetime.fromisoformat(date_string)

        # Add UTC if no timezone info
        if dt.tzinfo is None:
            dt = UTC.localize(dt)

        return dt.astimezone(UTC)

    except Exception as e:
        print(f"❌ Datetime parse error: {e}")
        return None


def validate_schedule_data(data):
    """Validate interview scheduling data"""
    required_fields = {
        'candidateName': str,
        'candidateEmail': str,
        'jobDescription': str,
        'startTime': str,
        'endTime': str
    }
    
    for field, field_type in required_fields.items():
        if field not in data:
            print(f"Missing field: {field}")
            return False
        
        if not isinstance(data[field], field_type):
            print(f"Invalid type for {field}")
            return False
        
        if isinstance(data[field], str) and not data[field].strip():
            print(f"Empty field: {field}")
            return False
    
    return True


def validate_email(email):
    """Validate email format"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def get_time_remaining(start_time, current_time=None):
    """Get remaining time in seconds until interview start"""
    if current_time is None:
        current_time = datetime.now(UTC)
    
    if isinstance(start_time, str):
        start_time = parse_iso_datetime(start_time)
    
    if start_time.tzinfo is None:
        start_time = UTC.localize(start_time)
    
    difference = start_time - current_time
    return max(0, int(difference.total_seconds()))