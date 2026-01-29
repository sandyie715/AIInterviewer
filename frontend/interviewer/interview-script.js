const API_BASE = 'http://localhost:5000';
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const recognition = new SpeechRecognition();
recognition.continuous = true;
recognition.interimResults = true;
recognition.lang = 'en-US';

let interviewData = null;
let interviewStartTime = null;
let mediaRecorder = null;
let recordedChunks = [];
let isListening = false;
let currentTranscript = '';
let timerInterval = null;
let videoBlob = null;
let recordedStream = null;
let waitingInterval = null;
let currentQuestion = '';

document.addEventListener('DOMContentLoaded', async () => {
    const params = new URLSearchParams(window.location.search);
    const interviewId = params.get("id");

    if (!interviewId) {
        showError("Invalid interview link");
        return;
    }

    try {
        const statusResponse = await fetch(`${API_BASE}/api/scheduler/status?id=${interviewId}`);
        const statusData = await statusResponse.json();

        console.log('[DEBUG] Status Response:', statusData);

        // ✅ CRITICAL FIX: Check for already-used interviews FIRST
        // These should be checked BEFORE checking time window
        if (statusData.status === "completed") {
            document.body.innerHTML = `
                <div style="height:100vh;display:flex;align-items:center;justify-content:center;
                background:#030712;color:white;text-align:center;">
                    <div>
                        <div style="font-size:48px;margin-bottom:20px;">✅</div>
                        <h2 style="color:#FFFFFF;">Interview Already Completed</h2>
                        <p style="color:#94a3b8;margin-top:10px;">
                            Thank you for attending. Our team will get back to you shortly.
                        </p>
                    </div>
                </div>
            `;
            return;
        }

        if (statusData.status === "already_started") {
            document.body.innerHTML = `
                <div style="height:100vh;display:flex;align-items:center;justify-content:center;
                background:#030712;color:white;text-align:center;">
                    <div>
                        <div style="font-size:48px;margin-bottom:20px;">⚠️</div>
                        <h2 style="color:#FFFFFF;">Interview Already Started</h2>
                        <p style="color:#94a3b8;margin-top:10px;">
                            This interview is already in progress from another device or window.
                        </p>
                        <p style="color:#94a3b8;margin-top:15px; font-size: 14px;">
                            If you think this is an error, please contact your recruiter.
                        </p>
                    </div>
                </div>
            `;
            return;
        }

        // Now check time-based status (waiting, expired, live)
        if (statusData.status === "waiting") {
            showWaitingScreen(new Date(statusData.start_time), statusData.start_time_ist);
            return;
        }

        if (statusData.status === "expired") {
            document.body.innerHTML = `
                <div style="height: 100vh; display: flex; align-items: center; justify-content: center; background: #030712; color: white; text-align: center;">
                    <div>
                        <div style="font-size: 40px; margin-bottom: 20px;">⏰</div>
                        <h2 style="color:#FFFFFF;">Interview window has closed</h2>
                        <p style="color: #94a3b8; margin-top: 10px;">Please contact your recruiter to reschedule</p>
                    </div>
                </div>
            `;
            return;
        }

        if (statusData.status === "live") {
            interviewData = {
                interviewId: statusData.interviewId,
                candidateName: statusData.candidateName,
                candidateEmail: statusData.candidateEmail,
                jobDescription: statusData.jobDescription
            };
            await initializeInterview();
        }
    } catch (error) {
        console.error('[ERROR] Status check failed:', error);
        showError('Failed to validate session');
    }
});

async function initializeInterview() {
    document.getElementById('waitingScreen').classList.remove('active');
    document.getElementById('interviewSection').classList.add('active');

    await startCamera();
    await generateQuestions();
    interviewStartTime = Date.now();
    startInterviewTimer();
    setupSpeechRecognition();
    await loadNextQuestion();
}

function showWaitingScreen(startTime, startTimeIST) {
    document.getElementById('waitingScreen').classList.add('active');
    if (startTimeIST) {
        // Update the scheduled time display with coral color
        const timeDisplay = document.getElementById('scheduledTimeDisplay');
        timeDisplay.textContent = startTimeIST;
        timeDisplay.style.color = '#F06767';
        timeDisplay.style.fontWeight = '700';
    }
    
    updateWaitingCountdown(startTime);
    waitingInterval = setInterval(() => {
        const now = new Date();
        if (now >= startTime) {
            clearInterval(waitingInterval);
            window.location.reload();
        }
        updateWaitingCountdown(startTime);
    }, 1000);
}

function updateWaitingCountdown(startTime) {
    const now = new Date();
    const diff = startTime - now;

    if (diff <= 0) {
        document.getElementById('waitingCountdown').textContent = '00:00:00';
        return;
    }

    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((diff % (1000 * 60)) / 1000);

    // Update countdown with coral color theme
    const countdownElement = document.getElementById('waitingCountdown');
    countdownElement.textContent = 
        `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    countdownElement.style.color = '#FFFFFF';
    countdownElement.style.textShadow = '0 0 30px rgba(240, 103, 103, 0.4)';
}

async function startCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { width: { ideal: 1280 }, height: { ideal: 720 } },
            audio: true
        });

        recordedStream = stream;
        document.getElementById('cameraFeed').srcObject = stream;
        startRecording(stream);
    } catch (error) {
        showError('Camera access denied');
    }
}

function startRecording(stream) {
    try {
        mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                recordedChunks.push(event.data);
            }
        };
        mediaRecorder.onstop = () => {
            videoBlob = new Blob(recordedChunks, { type: 'video/webm' });
        };
        mediaRecorder.start();
    } catch (error) {
        console.error('Recording error:', error);
    }
}

function setupSpeechRecognition() {
    recognition.onstart = () => {
        document.getElementById('micButton').classList.add('listening');
        document.getElementById('micStatus').textContent = 'Listening...';
        isListening = true;
    };

    recognition.onresult = (event) => {
        let interimTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
                currentTranscript += transcript + ' ';
            } else {
                interimTranscript += transcript;
            }
        }
        const displayText = currentTranscript + interimTranscript;
        document.getElementById('transcriptionDisplay').textContent = displayText || 'Listening...';
        
        if (displayText) {
            document.getElementById('nextBtn').disabled = false;
        }
    };

    recognition.onend = () => {
        document.getElementById('micButton').classList.remove('listening');
        document.getElementById('micStatus').textContent = 'Click to Speak';
        isListening = false;
    };
}

function toggleListening() {
    if (isListening) {
        recognition.stop();
    } else {
        currentTranscript = '';
        document.getElementById('transcriptionDisplay').textContent = 'Speak now...';
        recognition.start();
    }
}

async function generateQuestions() {
    try {
        const response = await fetch(`${API_BASE}/api/interviews/generate-questions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                jd: interviewData.jobDescription,
                interview_id: interviewData.interviewId
            })
        });
        const result = await response.json();
        
        console.log('[DEBUG] Generate Questions Response:', result);
        
        // ✅ Handle case where interview was already started
        if (result.status === "already_started") {
            document.body.innerHTML = `
                <div style="height:100vh;display:flex;align-items:center;justify-content:center;
                background:#030712;color:white;text-align:center;">
                    <div>
                        <div style="font-size:48px;margin-bottom:20px;">⚠️</div>
                        <h2 style="color:#FFFFFF;">Interview Already Started</h2>
                        <p style="color:#94a3b8;margin-top:10px;">
                            This interview is already in progress from another device or window.
                        </p>
                        <p style="color:#94a3b8;margin-top:15px; font-size: 14px;">
                            If you think this is an error, please contact your recruiter.
                        </p>
                    </div>
                </div>
            `;
            return;
        }
        
        // ✅ Handle case where interview was already completed
        if (result.status === "completed") {
            document.body.innerHTML = `
                <div style="height:100vh;display:flex;align-items:center;justify-content:center;
                background:#030712;color:white;text-align:center;">
                    <div>
                        <div style="font-size:48px;margin-bottom:20px;">✅</div>
                        <h2 style="color:#FFFFFF;">Interview Already Completed</h2>
                        <p style="color:#94a3b8;margin-top:10px;">
                            Thank you for attending. Our team will get back to you shortly.
                        </p>
                    </div>
                </div>
            `;
            return;
        }

        if (result.status === "success") {
            console.log('Questions generated:', result.total);
        } else {
            showError(result.message || 'Failed to generate questions');
        }
    } catch (error) {
        console.error('[ERROR] Generate questions failed:', error);
        showError('Failed to generate questions');
    }
}

async function loadNextQuestion() {
    try {
        const response = await fetch(`${API_BASE}/api/interviews/next-question/${interviewData.interviewId}`);
        const data = await response.json();

        if (data.done) {
            await endInterview();
            return;
        }

        currentQuestion = data.question;
        document.getElementById('questionLabel').textContent = `Question ${data.questionNumber} of ${data.totalQuestions}`;
        document.getElementById('questionText').textContent = currentQuestion;
        document.getElementById('transcriptionDisplay').textContent = 'Click microphone and speak...';
        document.getElementById('nextBtn').disabled = true;
        currentTranscript = '';

        speakQuestion(currentQuestion);
    } catch (error) {
        console.error('[ERROR] Load next question failed:', error);
        showError('Failed to load question');
    }
}

function speakQuestion(question) {
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(question);
        utterance.rate = 0.95;
        window.speechSynthesis.speak(utterance);
    }
}

async function submitAnswer() {
    try {
        const answer = currentTranscript.trim() || 'No answer provided';
        await fetch(`${API_BASE}/api/interviews/submit-answer/${interviewData.interviewId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question: currentQuestion,
                answer: answer
            })
        });
        if (isListening) recognition.stop();
        await loadNextQuestion();
    } catch (error) {
        console.error('[ERROR] Submit answer failed:', error);
    }
}

async function endInterview() {
    if (isListening) recognition.stop();
    if (recordedStream) recordedStream.getTracks().forEach(track => track.stop());
    if (mediaRecorder && mediaRecorder.state === 'recording') mediaRecorder.stop();
    if (timerInterval) clearInterval(timerInterval);

    document.getElementById('interviewSection').classList.remove('active');
    document.getElementById('feedbackSection').classList.add('active');

    // Wait for recording to finish
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Upload video
    if (videoBlob) {
        await uploadVideo();
    }

    // Get evaluation
    await getEvaluation();
}

async function uploadVideo() {
    try {
        const formData = new FormData();
        formData.append('video', videoBlob, `interview_${interviewData.interviewId}.webm`);
        formData.append('candidate_name', interviewData.candidateName);
        formData.append('candidate_email', interviewData.candidateEmail);

        const response = await fetch(`${API_BASE}/api/interviews/upload-video/${interviewData.interviewId}`, {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        console.log('Video upload:', result.status);
    } catch (error) {
        console.error('Video upload error:', error);
    }
}

async function getEvaluation() {
    try {
        // Update loading spinner with coral theme
        const loadingDiv = document.getElementById('loadingFeedback');
        loadingDiv.innerHTML = `
            <div class="loading-spinner"></div>
            <p style="font-weight: 600; color: #777777;">Generating AI Evaluation...</p>
        `;
        
        const response = await fetch(`${API_BASE}/api/interviews/evaluate/${interviewData.interviewId}`);
        const evaluation = await response.json();
        displayFeedback(evaluation);
    } catch (error) {
        document.getElementById('loadingFeedback').innerHTML = `
            <p style="color: #ef4444; font-weight: 600;">Unable to retrieve scores</p>
        `;
    }
}

function displayFeedback(evaluation) {
    document.getElementById('loadingFeedback').style.display = 'none';
    document.getElementById('feedbackContent').style.display = 'block';

    // Update scores with coral theme
    document.getElementById('technicalScore').textContent = `${evaluation.technical_score}/10`;
    document.getElementById('communicationScore').textContent = `${evaluation.communication_score}/10`;
    document.getElementById('overallScore').textContent = `${evaluation.overall_score}/10`;

    const recBox = document.getElementById('recommendationBox');
    const recType = evaluation.recommendation.toLowerCase();
    recBox.className = `recommendation ${recType}`;
    recBox.innerHTML = `<h3>Recommendation: ${evaluation.recommendation}</h3><p>${evaluation.feedback}</p>`;

    document.getElementById('feedbackText').textContent = evaluation.feedback;
}

function startInterviewTimer() {
    timerInterval = setInterval(() => {
        const elapsed = Date.now() - interviewStartTime;
        const minutes = Math.floor(elapsed / 60000);
        const seconds = Math.floor((elapsed % 60000) / 1000);
        document.getElementById('interviewTimer').textContent =
            `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    }, 1000);
}

function showError(message) {
    document.body.innerHTML = `
        <div style="height: 100vh; display: flex; align-items: center; justify-content: center; background: #030712; color: white; text-align: center;">
            <div style="max-width: 400px;">
                <div style="font-size: 40px; margin-bottom: 20px;">⚠️</div>
                <h2 style="color:#FFFFFF;">${message}</h2>
                <button onclick="location.reload()" style="margin-top: 25px; padding: 12px 28px; border-radius: 12px; border: none; background: linear-gradient(135deg, #F06767 0%, #E85555 100%); color: #FFFFFF; cursor: pointer; font-weight: 700; font-size: 16px; box-shadow: 0 8px 20px rgba(240, 103, 103, 0.3); transition: all 0.3s ease;" onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform='translateY(0)'">Retry</button>
            </div>
        </div>
    `;
}