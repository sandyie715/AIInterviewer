const API_BASE = 'http://localhost:5000';

function istToUTC(dateString) {
    return new Date(dateString).toISOString();
}

function setMinDateTime() {
    const now = new Date();

    // Adjust for local timezone so datetime-local accepts it correctly
    const localNow = new Date(now.getTime() - now.getTimezoneOffset() * 60000);

    const minDateTime = localNow.toISOString().slice(0, 16);

    document.getElementById('startTime').min = minDateTime;
    document.getElementById('endTime').min = minDateTime;
}

function validateTimes() {
    const startTimeInput = document.getElementById('startTime').value;
    const endTimeInput = document.getElementById('endTime').value;
    
    if (!startTimeInput || !endTimeInput) {
        showError('Please select both start and end times');
        return false;
    }

    const startTime = new Date(startTimeInput);
    const endTime = new Date(endTimeInput);

    if (endTime <= startTime) {
        showError('End time must be after start time');
        return false;
    }

    const durationMinutes = (endTime - startTime) / (1000 * 60);
    if (durationMinutes < 15) {
        showError('Interview duration must be at least 15 minutes');
        return false;
    }

    if (durationMinutes > 180) {
        showError('Interview duration should not exceed 3 hours');
        return false;
    }

    return true;
}

async function scheduleInterview(event) {
    event.preventDefault();

    if (!validateTimes()) return;

    const candidateName = document.getElementById('candidateName').value.trim();
    const candidateEmail = document.getElementById('candidateEmail').value.trim();
    const jobDescription = document.getElementById('jobDescription').value.trim();
    const startTimeInput = document.getElementById('startTime').value;
    const endTimeInput = document.getElementById('endTime').value;

    const startTimeUTC = istToUTC(startTimeInput);
    const endTimeUTC = istToUTC(endTimeInput);

    const scheduleBtn = document.getElementById('scheduleBtn');
    scheduleBtn.disabled = true;
    scheduleBtn.textContent = '⏳ Scheduling...';

    try {
        const response = await fetch(`${API_BASE}/api/scheduler/schedule`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                candidateName,
                candidateEmail,
                jobDescription,
                startTime: startTimeUTC,
                endTime: endTimeUTC
            })
        });

        const result = await response.json();

        if (!response.ok) throw new Error(result.error || 'Scheduling failed');

        document.getElementById('sentEmail').textContent = candidateEmail;
        document.getElementById('confirmationBox').classList.add('show');
        showSuccess(`✅ Interview scheduled! Email sent to ${candidateEmail}`);

        setTimeout(() => {
            document.getElementById('scheduleForm').reset();
            document.getElementById('confirmationBox').classList.remove('show');
            scheduleBtn.disabled = false;
            scheduleBtn.textContent = '📅 Schedule Interview';
            clearAlerts();
            setMinDateTime();
        }, 5000);

    } catch (error) {
        showError(error.message);
        scheduleBtn.disabled = false;
        scheduleBtn.textContent = '📅 Schedule Interview';
    }
}

function showError(message) {
    const errorDiv = document.getElementById('errorAlert');
    errorDiv.textContent = '❌ ' + message;
    errorDiv.style.display = 'block';
    setTimeout(() => errorDiv.style.display = 'none', 5000);
}

function showSuccess(message) {
    const successDiv = document.getElementById('successAlert');
    successDiv.textContent = message;
    successDiv.style.display = 'block';
    setTimeout(() => successDiv.style.display = 'none', 5000);
}

function clearAlerts() {
    document.getElementById('errorAlert').style.display = 'none';
    document.getElementById('successAlert').style.display = 'none';
}

document.getElementById('startTime').addEventListener('change', function() {
    const startTime = new Date(this.value);
    if (!isNaN(startTime.getTime())) {
        const endTime = new Date(startTime.getTime() + (60 * 60 * 1000));
        const year = endTime.getFullYear();
        const month = String(endTime.getMonth() + 1).padStart(2, '0');
        const day = String(endTime.getDate()).padStart(2, '0');
        const hours = String(endTime.getHours()).padStart(2, '0');
        const minutes = String(endTime.getMinutes()).padStart(2, '0');
        document.getElementById('endTime').value = `${year}-${month}-${day}T${hours}:${minutes}`;
    }
});

document.addEventListener('DOMContentLoaded', () => {
    setMinDateTime();
    clearAlerts();
});