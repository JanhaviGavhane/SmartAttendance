

// ===== GET PAGE ELEMENTS =====

const startButton = document.getElementById("startAttendance");
const stopButton = document.getElementById("stopAttendance");

const status = document.getElementById("status");
const voiceMessage = document.getElementById("voiceMessage");
const detectedText = document.getElementById("detectedText");

const rollNumberList = document.getElementById("rollNumberList");
const presentCount = document.getElementById("presentCount");
const emptyMessage = document.getElementById("emptyMessage");

const studentFile = document.getElementById("studentFile");
const fileName = document.getElementById("fileName");
const exportButton = document.getElementById("exportAttendance");

const saveButton = document.getElementById("saveAttendance");
const attendanceDate = document.getElementById("attendanceDate");
const attendanceMessage = document.getElementById("attendanceMessage");
const studentCountInfo = document.getElementById("studentCountInfo");

const totalCount = document.getElementById("totalCount");
const presentLiveCount = document.getElementById("presentLiveCount");
const absentLiveCount = document.getElementById("absentLiveCount");

const absentMessage = document.getElementById("absentMessage");
const absentList = document.getElementById("absentList");


// ===== ATTENDANCE DATA =====

let presentRollNumbers = [];
let attendanceRunning = false;

// Uploaded student list (from the server / Students page)
let studentList = [];
let studentMap = {};   // roll -> student {roll, name}
let sessionSaved = false;
let lastSavedRolls = [];
let sessionOriginalFilename = "";   // name of the file uploaded for THIS session

// Attendance mode + per-session state. Declared at the top (before the
// INIT block) so resetSessionState() can safely assign them when the
// page first loads.
let attendanceMode = "file_upload";   // 'file_upload' | 'class_strength'
let classStrength = 0;

// Unique identity for the CURRENT attendance run. A fresh uuid is issued
// every time a new session begins (page load / file upload / Start), and
// sent with the save payload. The backend treats this as the session key,
// so two genuine sessions with the same minute-precision date/time/
// subject/lecture_type never overwrite each other, while re-saving the
// SAME run still updates that one session (no duplicate sessions).
let sessionUuid = "";

function newSessionUuid() {

    if (window.crypto && typeof window.crypto.randomUUID === "function") {

        return window.crypto.randomUUID();
    }

    return "sess-" + Date.now().toString(36) + "-" +
        Math.random().toString(36).slice(2, 12);
}



// ===== VOICE ATTENDANCE (VOSK) =====
//
// Instead of the browser's built-in speech recognition (which
// converted single digits incorrectly), audio is recorded with the
// MediaRecorder API and sent to our own Flask server where Vosk
// recognizes the roll number OFFLINE.
//
// The session keeps recording automatically:
//   1. Start Attendance is clicked ONCE.
//   2. A student says a roll number.
//   3. The audio is sent to the server, Vosk recognizes it.
//   4. The roll number is marked Present.
//   5. Listening starts again automatically for the next student.
//   6. This repeats until Stop Attendance is clicked.

let mediaStream = null;
let audioContext = null;
let analyser = null;
let recorder = null;
let mediaChunks = [];

let cycleStartedAt = 0;
let voiceHeard = false;
let silenceSince = null;

// Copy of the analyser data (avoid allocating every frame)
let analyserData = null;

// Thresholds. Tuned for reliable single-roll-number speech: a slightly
// lower speech floor catches quieter voices, and a touch more silence
// wait prevents the clip from being cut mid-intake before Vosk parses it.
const SPEECH_THRESHOLD = 0.015;  // min volume to count as speech
const SILENCE_MS = 1200;         // silent time before we cut the clip
const MAX_CLIP_MS = 4000;        // never let one clip run too long


// ============================================
// ===== FILE UPLOAD ==========================
// ============================================

if (studentFile) {

    studentFile.addEventListener("change", function () {

        if (studentFile.files.length > 0) {

            sessionOriginalFilename =
                studentFile.files[0].name;

            fileName.textContent =
                studentFile.files[0].name;

            // Upload the new student list to the server
            uploadStudentList(studentFile.files[0]);

        } else {

            sessionOriginalFilename = "";

            fileName.textContent =
                "No file selected";
        }
    });
}


// ============================================
// ===== STUDENT LIST MANAGEMENT ==============
// ============================================

function showMessage(text, type) {

    if (!attendanceMessage) {
        return;
    }

    attendanceMessage.style.display = "block";

    attendanceMessage.className = "message-banner " + (type || "");

    attendanceMessage.textContent = text;
}

function clearMessage() {

    if (!attendanceMessage) {
        return;
    }

    attendanceMessage.style.display = "none";
    attendanceMessage.textContent = "";
}

function currentDateStr() {

    const now = new Date();

    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, "0");
    const d = String(now.getDate()).padStart(2, "0");

    return y + "-" + m + "-" + d;
}

function loadStudentList() {

    fetch("/api/students")
        .then(function (res) {
            return res.json();
        })
        .then(function (data) {

            studentList = (data.students || [])
                .sort(function (a, b) {
                    return a.roll - b.roll;
                });

            studentMap = {};

            studentList.forEach(function (s) {

                studentMap[s.roll] = s;
            });

            if (studentCountInfo) {

                studentCountInfo.innerHTML =
                    "Using uploaded list: <strong>" +
                    studentList.length +
                    " student(s)</strong>.";

                if (studentList.length === 0) {

                    studentCountInfo.textContent =
                        "No student list uploaded yet.";
                }
            }

            if (totalCount) {

                totalCount.textContent =
                    studentList.length;
            }

            updateAbsentList();

        })
        .catch(function (error) {

            console.log("Load students error:", error);
        });
}

function uploadStudentList(file) {

    const formData = new FormData();

    // Session-specific upload: the file populates ONLY the current
    // attendance session's student list. It does not replace the
    // permanent Students/master data and never auto-carries over to a
    // later session or page reload.
    formData.append("file", file);

    fetch("/session/students", {
        method: "POST",
        body: formData
    })
        .then(function (res) {
            return res.json();
        })
        .then(function (data) {

            if (data.success) {

                // New file for this session => start this session clean.
                resetSessionState();

                // No conversation detected yet.
                detectedText.textContent =
                    "Waiting to hear roll numbers...";

                // The session's source of truth is exactly this file.
                studentList = (data.students || [])
                    .sort(function (a, b) {
                        return a.roll - b.roll;
                    });

                studentMap = {};

                studentList.forEach(function (s) {

                    studentMap[s.roll] = s;
                });

                if (studentCountInfo) {

                    studentCountInfo.innerHTML =
                        "Using uploaded list: <strong>" +
                        studentList.length +
                        " student(s)</strong>.";
                }

                if (totalCount) {
                    totalCount.textContent = studentList.length;
                }

                showMessage(
                    "Student list loaded (" + studentList.length +
                    " students). You can now start attendance.",
                    "success"
                );

                updateAbsentList();

            } else {

                showMessage(
                    data.error || "Upload failed.",
                    "error"
                );
            }

            // Clear the file input so the same file can be re-picked
            studentFile.value = "";

        })
        .catch(function (error) {

            showMessage("Upload error: " + error, "error");

            studentFile.value = "";
        });
}


// ============================================
// ===== START ATTENDANCE =====================
// ============================================

// Reset the current session to a clean state. Called whenever a new
// attendance session begins so old/stale rolls can never leak into a
// fresh session (a separate attendance history is never touched).
function resetSessionState() {

    // A fresh attendance run starts: new unique session identity so the
    // save lands in its own session row (never overwriting a previous
    // legitimate session saved in the same minute).
    sessionUuid = newSessionUuid();

    // Clean live session values
    presentRollNumbers = [];
    sessionSaved = false;
    lastSavedRolls = [];
    sessionOriginalFilename = "";

    // Reset the visible roll list
    if (rollNumberList) {
        rollNumberList.innerHTML = "";
    }

    if (presentCount) {
        presentCount.textContent = "0";
    }

    if (emptyMessage) {
        emptyMessage.style.display = "block";
    }

    // Reset summary counters
    if (presentLiveCount) {
        presentLiveCount.textContent = "0";
    }

    if (absentLiveCount) {
        absentLiveCount.textContent = "0";
    }

    // Reset the absent list
    if (absentList) {
        absentList.innerHTML = "";
    }

    if (absentMessage) {
        absentMessage.style.display = "block";
    }

    // Reset the detected-text placeholder.
    const detectedNode =
        document.getElementById("detectedText");
    if (detectedNode) {
        detectedNode.textContent =
            "Waiting to hear roll numbers...";
    }

    updateAbsentList();
    updateSaveButton();
}

startButton.addEventListener(
    "click",
    async function () {

        // Don't start twice
        if (attendanceRunning) {
            return;
        }

        // A new attendance session begins => start from a clean state
        // (present rolls and the on-screen summary).
        resetSessionState();

        // Ask for the microphone
        try {

            mediaStream =
                await navigator.mediaDevices
                    .getUserMedia({ audio: true });

        } catch (error) {

            alert(
                "Microphone access is required " +
                "for voice attendance."
            );

            status.innerHTML =
                "<span></span> Microphone Permission Denied";

            voiceMessage.textContent =
                "Please allow microphone access.";

            detectedText.textContent =
                "Microphone permission denied.";

            return;
        }

        setupAnalyser();

        attendanceRunning = true;


        startButton.disabled = true;
        stopButton.disabled = false;


        status.innerHTML =
            "<span></span> Listening";


        voiceMessage.textContent =
            "Listening. Say your roll number.";


        detectedText.textContent =
            "🎤 Listening...";


        // Start recording the FIRST student
        startCycle();
    }
);


// ============================================
// ===== STOP ATTENDANCE ======================
// ============================================

stopButton.addEventListener(
    "click",
    function () {

        attendanceRunning = false;

        stopRecorder();
        stopMedia();


        startButton.disabled = false;
        stopButton.disabled = true;


        status.innerHTML =
            "<span></span> Stopped";


        voiceMessage.textContent =
            "Attendance session stopped.";


        detectedText.textContent =
            "Attendance stopped.";
    }
);


// ============================================
// ===== SET UP AUDIO ANALYSER ================
// ============================================

function setupAnalyser() {

    try {

        audioContext =
            new (window.AudioContext ||
                 window.webkitAudioContext)();

        const source =
            audioContext.createMediaStreamSource(
                mediaStream
            );

        analyser =
            audioContext.createAnalyser();

        analyser.fftSize = 2048;

        source.connect(analyser);

        analyserData =
            new Uint8Array(
                analyser.fftSize
            );

    } catch (error) {

        console.log(
            "Analyser setup failed:",
            error
        );

        audioContext = null;
        analyser = null;
    }
}


// ============================================
// ===== START ONE RECORDING CYCLE ============
// ============================================

function startCycle() {

    if (!attendanceRunning) {
        return;
    }

    // Reset cycle state
    mediaChunks = [];
    voiceHeard = false;
    silenceSince = null;
    cycleStartedAt = performance.now();

    status.innerHTML =
        "<span></span> Listening";

    voiceMessage.textContent =
        "Listening for one student...";

    detectedText.textContent =
        "🎤 Listening...";


    // Create a fresh recorder for this clip
    recorder = new MediaRecorder(mediaStream);

    recorder.ondataavailable = function (event) {

        if (event.data && event.data.size > 0) {

            mediaChunks.push(event.data);
        }
    };

    recorder.onstop = function () {

        sendClip();
    };

    recorder.start();

    // Watch the microphone level to know when
    // the student has finished speaking.
    if (analyser) {

        watchLevel();
    } else {

        // Without an analyser, just cut after a fixed time.
        setTimeout(function () {

            if (
                attendanceRunning &&
                recorder &&
                recorder.state === "recording"
            ) {

                recorder.stop();
            }

        }, MAX_CLIP_MS);
    }
}


// ============================================
// ===== WATCH MICROPHONE LEVEL ===============
// ============================================

function watchLevel() {

    if (!attendanceRunning || !recorder) {
        return;
    }

    if (recorder.state !== "recording") {
        return;
    }

    // Measure the current audio level
    analyser.getByteTimeDomainData(
        analyserData
    );

    let peak = 0;

    for (let i = 0; i < analyserData.length; i++) {

        const value =
            (analyserData[i] - 128) / 128;

        const abs =
            value < 0 ? -value : value;

        if (abs > peak) {
            peak = abs;
        }
    }

    const now = performance.now();
    const elapsed = now - cycleStartedAt;

    // Is someone speaking?
    if (peak > SPEECH_THRESHOLD) {

        voiceHeard = true;
        silenceSince = null;

    } else if (voiceHeard && silenceSince === null) {

        // They stopped speaking; start the silence timer
        silenceSince = now;
    }

    // Cut the clip once a short silence is heard,
    // or if it has been going on too long.
    const silenceTooLong =
        silenceSince !== null &&
        (now - silenceSince) >= SILENCE_MS;

    const clipTooLong =
        elapsed >= MAX_CLIP_MS;

    if (silenceTooLong || clipTooLong) {

        if (recorder.state === "recording") {

            recorder.stop();
        }

        return;
    }

    // Keep watching
    requestAnimationFrame(watchLevel);
}


// ============================================
// ===== STOP CURRENT RECORDER ================
// ============================================

function stopRecorder() {

    if (
        recorder &&
        recorder.state !== "inactive"
    ) {

        try {

            recorder.stop();

        } catch (error) {

            console.log(
                "Recorder already stopped:",
                error
            );
        }
    }
}


// ============================================
// ===== STOP MEDIA STREAM ====================
// ============================================

function stopMedia() {

    if (mediaStream) {

        mediaStream.getTracks().forEach(
            function (track) {
                track.stop();
            }
        );

        mediaStream = null;
    }

    if (audioContext && audioContext.state !== "closed") {

        try {

            audioContext.close();

        } catch (error) { /* ignore */ }

        audioContext = null;
    }

    analyser = null;
}


// ============================================
// ===== SEND AUDIO CLIP TO VOSK ==============
// ============================================

function sendClip() {

    if (mediaChunks.length === 0) {

        // Nothing recorded; keep listening
        restartCycle();

        return;
    }

    const blob = new Blob(
        mediaChunks,
        { type: recorder.mimeType || "audio/webm" }
    );


    const formData = new FormData();

    formData.append("audio", blob, "voice.webm");


    status.innerHTML =
        "<span></span> Recognizing";

    voiceMessage.textContent =
        "Recognizing roll number...";


    fetch("/transcribe", {
        method: "POST",
        body: formData
    })
        .then(function (response) {

            return response.json();

        })
        .then(function (data) {

            if (!attendanceRunning) {
                return;
            }

            let rollNumber = null;

            // Prefer the roll number extracted by the server
            if (
                data.success &&
                typeof data.roll_number === "number"
            ) {

                rollNumber = data.roll_number;
            }

            // Fall back to local parsing of the returned text
            if (rollNumber === null && data.text) {

                rollNumber =
                    getRollNumber(data.text);
            }

            const heardText = data.text || "";

            console.log("Heard:", heardText, "Roll:", rollNumber);


            if (rollNumber !== null) {

                detectedText.textContent =
                    "Heard: " + heardText;

                addRollNumber(rollNumber);

            } else {

                detectedText.textContent =
                    "Could not recognize roll number: " +
                    (heardText || "no speech detected");
            }

            // Automatically listen for the next student
            restartCycle();

        })
        .catch(function (error) {

            console.log("Transcription error:", error);

            if (!attendanceRunning) {
                return;
            }

            detectedText.textContent =
                "Server error. Listening again...";

            restartCycle();
        });
}


// ============================================
// ===== RESTART CYCLE (AUTO LOOP) ============
// ============================================

function restartCycle() {

    if (!attendanceRunning) {

        stopRecorder();
        return;
    }

    // Short pause so the next recording does not
    // pick up the previous answer's sound.
    setTimeout(function () {

        if (!attendanceRunning) {
            return;
        }

        startCycle();

    }, 400);
}


// =================================================
// ===== CONVERT SPOKEN TEXT TO ROLL NUMBER =========
// =================================================

function getRollNumber(text) {

    // Clean text
    text = text
        .toLowerCase()
        .trim()
        .replace(/-/g, " ")
        .replace(/[.,!?]/g, "")
        .replace(/\s+/g, " ");


    // Remove common extra words
    text = text
        .replace(/\broll number\b/g, "")
        .replace(/\bmy\b/g, "")
        .replace(/\bi am\b/g, "")
        .replace(/\bi\b/g, "")
        .replace(/\bam\b/g, "")
        .replace(/\bim\b/g, "")
        .replace(/\broll\b/g, "")
        .replace(/\bnumber\b/g, "")
        .trim();


    // ============================================
    // DIRECT DIGIT
    // ============================================

    // Examples:
    // "1"   -> 1
    // "5"   -> 5
    // "23"  -> 23
    // "100" -> 100

    if (/^\d{1,3}$/.test(text)) {

        const number =
            parseInt(text, 10);


        if (
            number >= 1 &&
            number <= 100
        ) {

            return number;
        }
    }


    // ============================================
    // BASIC NUMBERS 1–19
    // ============================================

    const basicNumbers = {

        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,

        "ten": 10,
        "eleven": 11,
        "twelve": 12,
        "thirteen": 13,
        "fourteen": 14,
        "fifteen": 15,
        "sixteen": 16,
        "seventeen": 17,
        "eighteen": 18,
        "nineteen": 19
    };


    // EXACT basic number
    if (
        Object.prototype.hasOwnProperty.call(
            basicNumbers,
            text
        )
    ) {

        return basicNumbers[text];
    }


    // ============================================
    // TENS
    // ============================================

    const tens = {

        "twenty": 20,
        "thirty": 30,
        "forty": 40,
        "fifty": 50,
        "sixty": 60,
        "seventy": 70,
        "eighty": 80,
        "ninety": 90
    };


    if (
        Object.prototype.hasOwnProperty.call(
            tens,
            text
        )
    ) {

        return tens[text];
    }


    // ============================================
    // 100
    // ============================================

    if (
        text === "one hundred" ||
        text === "100"
    ) {

        return 100;
    }


    // ============================================
    // 21–99  ("twenty three" -> 23)
    // ============================================

    const words =
        text.split(" ");


    if (words.length === 2) {

        const first =
            words[0];

        const second =
            words[1];


        if (
            Object.prototype.hasOwnProperty.call(
                tens,
                first
            ) &&
            Object.prototype.hasOwnProperty.call(
                basicNumbers,
                second
            )
        ) {

            const secondNumber =
                basicNumbers[second];


            if (
                secondNumber >= 1 &&
                secondNumber <= 9
            ) {

                return (
                    tens[first] +
                    secondNumber
                );
            }
        }
    }


    // ============================================
    // IMPORTANT:
    // DO NOT COMBINE RANDOM DIGITS
    // ============================================

    // We intentionally DON'T do something like:
    //
    // "two three" -> 23
    //
    // because that caused your previous problem.


    // ============================================
    // FIND DIRECT DIGIT IN TEXT
    // ============================================

    const digitMatch =
        text.match(/\b\d{1,3}\b/);


    if (digitMatch) {

        const number =
            parseInt(
                digitMatch[0],
                10
            );


        if (
            number >= 1 &&
            number <= 100
        ) {

            return number;
        }
    }


    return null;
}


// =================================================
// ===== ADD ROLL NUMBER ============================
// =================================================

function addRollNumber(rollNumber) {

    // Prevent duplicates
    if (
        presentRollNumbers.includes(
            rollNumber
        )
    ) {

        const dupStudent =
            studentMap[rollNumber];

        detectedText.textContent =
            "Roll No. " +
            rollNumber +
            (dupStudent ? " (" + dupStudent.name + ") " : " ") +
            "is already marked Present.";

        return;
    }


    // Validate the roll number is a positive integer (1-1000).
    if (!Number.isInteger(rollNumber) || rollNumber < 1) {

        detectedText.textContent =
            "Invalid roll number.";

        return;
    }

    // Class-strength mode: only rolls within 1..classStrength are valid.
    if (
        attendanceMode === "class_strength" &&
        classStrength > 0 &&
        rollNumber > classStrength
    ) {

        detectedText.textContent =
            "Roll No. " +
            rollNumber +
            " is out of range. Class strength is " +
            classStrength +
            ".";

        return;
    }

    // Check against the uploaded student list (file-upload mode only).
    // In class-strength mode the strength, not the uploaded list,
    // defines which rolls are valid.
    const student =
        studentMap[rollNumber];


    if (
        attendanceMode !== "class_strength" &&
        studentList.length > 0 &&
        !student
    ) {

        // Roll number not found in the uploaded list
        detectedText.textContent =
            "Roll number not found in uploaded student list.";

        return;
    }


    // Save roll number
    presentRollNumbers.push(
        rollNumber
    );


    // Sort:
    // 1, 2, 3, 10, 20...
    presentRollNumbers.sort(
        function (a, b) {

            return a - b;

        }
    );


    // Update count
    presentCount.textContent =
        presentRollNumbers.length;


    // Hide empty message
    if (emptyMessage) {

        emptyMessage.style.display =
            "none";
    }


    // Mark session as no longer clean (needs save)
    sessionSaved = false;

    updateLiveSummary();
    updateAbsentList();
    updateSaveButton();


    // Show detected roll + name + status
    if (student) {

        detectedText.textContent =
            "✓ Roll No. " +
            rollNumber +
            " — " +
            student.name +
            " marked Present.";

    } else {

        detectedText.textContent =
            "✓ Roll No. " +
            rollNumber +
            " marked Present.";
    }


    // Update screen
    displayRollNumbers();
}


// =================================================
// ===== DISPLAY ROLL NUMBERS =======================
// =================================================

function displayRollNumbers() {

    rollNumberList.innerHTML = "";


    presentRollNumbers.forEach(
        function (rollNumber) {

            const rollItem =
                document.createElement("div");


            rollItem.className =
                "roll-item";


            const student =
                studentMap[rollNumber];


            rollItem.innerHTML =
                "Roll No. " +
                rollNumber +
                (student ? "<strong> " + escapeHtml(student.name) + "</strong>" : "") +
                "<small>Present</small>";


            rollNumberList.appendChild(
                rollItem
            );
        }
    );
}


// =================================================
// ===== LIVE SUMMARY ==============================
// =================================================

function updateLiveSummary() {

    // Total is always derived from the CURRENT mode:
    //   - file_upload   -> the uploaded list length
    //   - class_strength -> the current class strength value
    if (totalCount) {

        if (attendanceMode === "class_strength" && classStrength > 0) {

            totalCount.textContent = classStrength;

        } else if (attendanceMode === "file_upload" &&
                   studentList.length > 0) {

            totalCount.textContent = studentList.length;

        } else {

            totalCount.textContent = "0";
        }
    }

    if (presentLiveCount) {

        presentLiveCount.textContent =
            presentRollNumbers.length;
    }

    if (absentLiveCount) {

        const absent = getAbsentRolls();

        absentLiveCount.textContent =
            absent.length;
    }
}


function getAbsentRolls() {

    // Class-strength mode: absent = 1..classStrength minus present
    if (attendanceMode === "class_strength" && classStrength > 0) {

        const presentSet = new Set(presentRollNumbers);

        const absent = [];

        for (let r = 1; r <= classStrength; r++) {

            if (!presentSet.has(r)) {

                absent.push({ roll: r, name: "" });
            }
        }

        return absent;
    }

    // Students in the uploaded list who have not been detected
    if (studentList.length === 0) {

        return [];
    }

    return studentList.filter(
        function (s) {

            return !presentRollNumbers.includes(s.roll);
        }
    );
}


// =================================================
// ===== ABSENT LIST ===============================
// =================================================

function updateAbsentList() {

    if (!absentList || !absentMessage) {
        return;
    }

    const absent = getAbsentRolls();

    absentList.innerHTML = "";

    if (absent.length === 0) {

        absentMessage.style.display = "block";

        return;

    }

    absentMessage.style.display = "none";

    absent.forEach(function (student) {

        const item = document.createElement("div");

        item.className = "absent-item";

        item.innerHTML =
            "Roll No. " +
            student.roll +
            "<small>" +
            escapeHtml(student.name) +
            "</small>";

        absentList.appendChild(item);
    });
}


function escapeHtml(text) {

    const div = document.createElement("div");

    div.textContent = String(text || "");

    return div.innerHTML;
}


// =================================================
// ===== SAVE BUTTON STATE =========================
// =================================================

function updateSaveButton() {

    if (!saveButton) {
        return;
    }

    if (attendanceMode === "class_strength" &&
        (!classStrength || classStrength <= 0)) {

        // Class-strength mode cannot save until a valid strength is set.
        saveButton.disabled = true;

        return;
    }

    saveButton.disabled =
        presentRollNumbers.length === 0;
}


// =================================================
// ===== SAVE ATTENDANCE ===========================
// =================================================

function saveAttendance() {

    const subject =
        document.getElementById("subject").value.trim() || "General";

    const lectureType =
        document.getElementById("lectureType").value;

    const date =
        (attendanceDate && attendanceDate.value) || currentDateStr();

    const time =
        new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit"
        });

    const present = presentRollNumbers;

    // Class-strength mode requires a valid (positive) class strength.
    // Without it, the absent set cannot be computed, so block the save.
    if (attendanceMode === "class_strength" &&
        (!classStrength || classStrength <= 0)) {

        showMessage(
            "Set a valid class strength (1-100) in class-strength mode.",
            "error"
        );

        return;
    }

    // File-upload mode uses the file uploaded for THIS session as the
    // source of truth. Without it there is no student list to mark
    // absent, so block the save (never reuse a stale/global list).
    if (attendanceMode === "file_upload" && studentList.length === 0) {

        showMessage(
            "Upload a student list for this session before saving.",
            "error"
        );

        return;
    }

    const absent = getAbsentRolls().map(function (s) {
        return s.roll;
    });

    if (present.length === 0) {

        alert("No attendance recorded yet.");

        return;
    }

    const payload = {
        date: date,
        time: time,
        subject: subject,
        lecture_type: lectureType,
        attendance_mode: attendanceMode,
        class_strength: (attendanceMode === "class_strength"
                          ? classStrength : null),
        session_uuid: sessionUuid,
        present: present,
        absent: absent,
        students: (attendanceMode === "file_upload"
                   ? studentList
                   : []),
        original_filename: sessionOriginalFilename
    };

    fetch("/attendance/save", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
    })
        .then(function (res) {
            return res.json();
        })
        .then(function (data) {

            if (!data.success) {

                showMessage(
                    data.error || "Could not save attendance.",
                    "error"
                );

                return;
            }

            sessionSaved = true;

            if (!attendanceMessage) {
                return;
            }

            // Render the success message with a download link for the
            // generated attendance-marked result file.
            attendanceMessage.style.display = "block";
            attendanceMessage.className =
                "message-banner success";

            let html =
                "Attendance saved for " + date +
                " (" + present.length + " present, " +
                absent.length + " absent).";

            if (data.download_url && data.filename) {

                html +=
                    "<br><a href=\"" + data.download_url +
                    "\" class=\"download-link\" download>" +
                    "Download attendance file (" +
                    (data.format || "xlsx").toUpperCase() +
                    ")</a>";
            }

            attendanceMessage.innerHTML = html;

        })
        .catch(function (error) {

            showMessage("Save error: " + error, "error");
        });
}


// =================================================
// ===== EXPORT CSV =================================
// =================================================

if (exportButton) {

    exportButton.addEventListener(
        "click",
        function () {

            if (
                presentRollNumbers.length === 0
            ) {

                alert(
                    "No attendance recorded yet."
                );

                return;
            }


            let csv =
                "Roll Number,Attendance\n";


            // Class-strength mode: export all rolls 1..classStrength,
            // marking Present / Absent for the whole class.
            if (
                attendanceMode === "class_strength" &&
                classStrength > 0
            ) {

                const presentSet =
                    new Set(presentRollNumbers);

                for (
                    let r = 1;
                    r <= classStrength;
                    r++
                ) {

                    csv +=
                        r +
                        "," +
                        (presentSet.has(r)
                            ? "Present"
                            : "Absent") +
                        "\n";
                }

            } else {

                // File-upload mode: export every student in the active
                // list, marking Present / Absent (not just the present).
                const presentSet =
                    new Set(presentRollNumbers);

                const rollList =
                    studentList.length > 0
                        ? studentList.map(function (s) {
                            return s.roll;
                        })
                        : presentRollNumbers.slice();

                const ordered = Array.from(
                    new Set(rollList)
                ).sort(function (a, b) {
                    return a - b;
                });

                if (ordered.length === 0) {

                    ordered.push.apply(
                        ordered,
                        presentRollNumbers
                    );
                }

                ordered.forEach(function (rollNumber) {

                    csv +=
                        rollNumber +
                        "," +
                        (presentSet.has(rollNumber)
                            ? "Present"
                            : "Absent") +
                        "\n";
                });
            }


            const blob =
                new Blob(
                    [csv],
                    {
                        type: "text/csv"
                    }
                );


            const url =
                URL.createObjectURL(
                    blob
                );


            const link =
                document.createElement("a");


            link.href = url;


            link.download =
                "attendance.csv";


            link.click();


            URL.revokeObjectURL(url);
        }
    );
}


// =================================================
// ===== SAVE BUTTON ================================
// =================================================

if (saveButton) {

    saveButton.addEventListener(
        "click",
        saveAttendance
    );
}


// =================================================
// ===== INIT =======================================
// =================================================

// Pre-fill the date field with today
if (attendanceDate) {

    attendanceDate.value = currentDateStr();
}

// A fresh attendance session always starts clean. It must NOT auto-load
// /api/students (that would re-activate the previous session's uploaded
// list as the current source). The list becomes available only when the
// user uploads a file for THIS session.
studentList = [];
studentMap = {};

resetSessionState();

if (studentCountInfo) {

    studentCountInfo.textContent = "No student list uploaded yet.";
}

if (totalCount) {

    totalCount.textContent = "0";
}

updateAbsentList();


// =================================================
// ===== ATTENDANCE MODE: FILE vs CLASS STRENGTH ===
// =================================================
//
// These additions are purely additive and do NOT touch the frozen
// Vosk recording / roll-detection logic above.
// (attendanceMode and classStrength are declared at the top of the file with
// the other session state so they
// are available before the INIT block runs.)

const modeBtnFile = document.getElementById("modeFile");
const modeBtnClass = document.getElementById("modeClass");
const classStrengthCard = document.getElementById("classStrengthCard");
const classStrengthInput = document.getElementById("classStrength");
const strengthHint = document.getElementById("strengthHint");
const uploadCard = document.querySelector(".upload-card");

function setAttendanceMode(mode) {

    attendanceMode = mode;

    if (modeBtnFile && modeBtnClass) {

        modeBtnFile.classList.toggle("active", mode === "file_upload");
        modeBtnClass.classList.toggle("active", mode === "class_strength");
    }

    if (classStrengthCard) {

        classStrengthCard.style.display =
            (mode === "class_strength") ? "" : "none";
    }

    if (uploadCard) {

        uploadCard.style.display =
            (mode === "file_upload") ? "" : "none";
    }

    updateLiveSummary();
    updateAbsentList();
}


// ---- mode buttons ----
if (modeBtnFile) {

    modeBtnFile.addEventListener("click", function () {
        setAttendanceMode("file_upload");
    });
}

if (modeBtnClass) {

    modeBtnClass.addEventListener("click", function () {
        setAttendanceMode("class_strength");
    });
}


// ---- class strength quick chips ----
document.querySelectorAll(".strength-chip").forEach(function (chip) {

    chip.addEventListener("click", function () {

        if (classStrengthInput) {

            classStrengthInput.value = chip.getAttribute("data-strength");
            classStrength = parseInt(chip.getAttribute("data-strength"), 10) || 0;
        }

        updateStrengthHint();
        updateLiveSummary();
        updateAbsentList();
        updateSaveButton();
    });
});


// ---- custom class strength ----
if (classStrengthInput) {

    classStrengthInput.addEventListener("input", function () {

        classStrength = parseInt(classStrengthInput.value, 10) || 0;

        updateStrengthHint();
        updateLiveSummary();
        updateAbsentList();
        updateSaveButton();
    });
}


function updateStrengthHint() {

    if (!strengthHint) {
        return;
    }

    if (classStrength <= 0) {

        strengthHint.textContent =
            "Set the class strength to begin. Voice attendance still works.";

    } else {

        strengthHint.textContent =
            "Class strength " + classStrength +
            ". Present: " + presentRollNumbers.length +
            ", Absent: " + getAbsentRolls().length + ".";
    }
}


// Initial save button state. This runs AFTER attendanceMode /
// classStrength are declared so the class-strength branch of
// updateSaveButton() can read them without a ReferenceError.
updateSaveButton();

// Explicit initial attendance controls state: not running, Start
// enabled and clickable, Stop disabled. This guarantees a clean page
// load and must NOT disable Start permanently (Stop re-enables it).
attendanceRunning = false;
if (startButton) {
    startButton.disabled = false;
}
if (stopButton) {
    stopButton.disabled = true;
}



