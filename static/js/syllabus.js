
// ===== SYLLABUS TRACKER =====


// ===== ELEMENTS =====

const messageBox = document.getElementById("syllabusMessage");
const subjectContainer = document.getElementById("subjectContainer");

const subjectName = document.getElementById("subjectName");
const addSubjectButton = document.getElementById("addSubjectButton");

const totalTopics = document.getElementById("totalTopics");
const completedTopics = document.getElementById("completedTopics");
const pendingTopics = document.getElementById("pendingTopics");
const progressPercent = document.getElementById("progressPercent");
const progressPercentBig = document.getElementById("progressPercentBig");
const progressFill = document.getElementById("progressFill");


// ===== HELPERS =====

function showMessage(text, type) {

    messageBox.style.display = "block";
    messageBox.className = "message-banner " + (type || "");
    messageBox.textContent = text;
}

function escapeHtml(text) {

    const div = document.createElement("div");
    div.textContent = String(text || "");
    return div.innerHTML;
}

function updateSummary(summary) {

    totalTopics.textContent = summary.total;
    completedTopics.textContent = summary.completed;
    pendingTopics.textContent = summary.pending;
    progressPercent.textContent = summary.percentage + "%";
    progressPercentBig.textContent = summary.percentage + "%";
    progressFill.style.width = summary.percentage + "%";
}


// ===== ADD SUBJECT =====

addSubjectButton.addEventListener(
    "click",
    function () {

        const name = subjectName.value.trim();

        if (name === "") {

            showMessage("Enter a subject name.", "error");
            return;
        }

        const formData = new FormData();
        formData.append("name", name);

        fetch("/syllabus/subject", {
            method: "POST",
            body: formData
        })
            .then(function (res) {
                return res.json();
            })
            .then(function (data) {

                if (!data.success) {

                    showMessage(data.error || "Could not add subject.", "error");
                    return;
                }

                showMessage("Subject added.", "success");
                subjectName.value = "";
                render(data.syllabus, data.summary);

            })
            .catch(function (error) {

                showMessage("Error: " + error, "error");
            });
    }
);


// ===== ADD UNIT =====

function addUnit(subjectId, inputEl) {

    const name = inputEl.value.trim();

    if (name === "") {

        showMessage("Enter a unit name.", "error");
        return;
    }

    const formData = new FormData();
    formData.append("subject_id", subjectId);
    formData.append("name", name);

    fetch("/syllabus/unit", {
        method: "POST",
        body: formData
    })
        .then(function (res) {
            return res.json();
        })
        .then(function (data) {

            if (!data.success) {

                showMessage(data.error || "Could not add unit.", "error");
                return;
            }

            showMessage("Unit added.", "success");
            loadSyllabus();

        })
        .catch(function (error) {

            showMessage("Error: " + error, "error");
        });
}


// ===== ADD TOPIC =====

function addTopic(subjectId, unitId, inputEl) {

    const title = inputEl.value.trim();

    if (title === "") {

        showMessage("Enter a topic title.", "error");
        return;
    }

    const formData = new FormData();
    formData.append("subject_id", subjectId);
    formData.append("unit_id", unitId);
    formData.append("title", title);

    fetch("/syllabus/topic", {
        method: "POST",
        body: formData
    })
        .then(function (res) {
            return res.json();
        })
        .then(function (data) {

            if (!data.success) {

                showMessage(data.error || "Could not add topic.", "error");
                return;
            }

            showMessage("Topic added.", "success");
            loadSyllabus();

        })
        .catch(function (error) {

            showMessage("Error: " + error, "error");
        });
}


// ===== TOGGLE TOPIC =====

function toggleTopic(subjectId, unitId, topicId) {

    const formData = new FormData();
    formData.append("subject_id", subjectId);
    formData.append("unit_id", unitId);
    formData.append("topic_id", topicId);

    fetch("/syllabus/topic/toggle", {
        method: "POST",
        body: formData
    })
        .then(function (res) {
            return res.json();
        })
        .then(function (data) {

            if (!data.success) {

                showMessage(data.error || "Could not update topic.", "error");
                return;
            }

            render(data.syllabus, data.summary);

        })
        .catch(function (error) {

            showMessage("Error: " + error, "error");
        });
}


// ===== SAVE NOTES =====

function saveNotes(subjectId, unitId, topicId, inputEl) {

    const formData = new FormData();
    formData.append("subject_id", subjectId);
    formData.append("unit_id", unitId);
    formData.append("topic_id", topicId);
    formData.append("notes", inputEl.value);

    fetch("/syllabus/topic/notes", {
        method: "POST",
        body: formData
    })
        .then(function (res) {
            return res.json();
        })
        .then(function (data) {

            if (!data.success) {

                showMessage(data.error || "Could not save notes.", "error");
            }

        })
        .catch(function (error) {

            showMessage("Error: " + error, "error");
        });
}


// ===== DELETE SUBJECT =====

function deleteSubject(subjectId, name) {

    if (!confirm('Delete subject "' + name + '" and all its topics?')) {
        return;
    }

    fetch("/syllabus/subject?subject_id=" + subjectId, {
        method: "DELETE"
    })
        .then(function (res) {
            return res.json();
        })
        .then(function (data) {

            if (!data.success) {

                showMessage(data.error || "Could not delete subject.", "error");
                return;
            }

            showMessage("Subject deleted.", "success");
            render(data.syllabus, data.summary);

        })
        .catch(function (error) {

            showMessage("Error: " + error, "error");
        });
}


// ===== RENDER =====

function render(syllabus, summary) {

    updateSummary(summary);

    subjectContainer.innerHTML = "";

    const subjects = syllabus.subjects || [];

    if (subjects.length === 0) {

        const empty = document.createElement("p");
        empty.className = "empty-subjects";
        empty.textContent = "No subjects yet. Add a subject above.";
        subjectContainer.appendChild(empty);

        return;
    }

    subjects.forEach(function (subject) {

        const card = document.createElement("div");
        card.className = "subject-card";

        // ---- Subject header ----
        const header = document.createElement("div");
        header.className = "subject-header";

        const title = document.createElement("h2");
        title.textContent = subject.name;

        const del = document.createElement("button");
        del.className = "delete-subject";
        del.title = "Delete subject";
        del.innerHTML = '<i class="bi bi-trash"></i>';

        del.addEventListener("click", function () {

            deleteSubject(subject.id, subject.name);
        });

        header.appendChild(title);
        header.appendChild(del);

        card.appendChild(header);

        // ---- Add unit form ----
        const unitRow = document.createElement("div");
        unitRow.className = "add-unit-row";

        const unitInput = document.createElement("input");
        unitInput.type = "text";
        unitInput.placeholder = "New unit name";

        const unitBtn = document.createElement("button");
        unitBtn.className = "add-btn";
        unitBtn.textContent = "Add Unit";

        unitBtn.addEventListener("click", function () {

            addUnit(subject.id, unitInput);
        });

        unitInput.addEventListener("keydown", function (e) {

            if (e.key === "Enter") {
                addUnit(subject.id, unitInput);
            }
        });

        unitRow.appendChild(unitInput);
        unitRow.appendChild(unitBtn);

        card.appendChild(unitRow);

        // ---- Units ----
        (subject.units || []).forEach(function (unit) {

            card.appendChild(buildUnit(subject, unit));
        });

        subjectContainer.appendChild(card);
    });
}


function buildUnit(subject, unit) {

    const block = document.createElement("div");
    block.className = "unit-block";

    const heading = document.createElement("p");
    heading.className = "unit-heading";
    heading.textContent = "Unit: " + unit.name;
    block.appendChild(heading);

    // Add topic form
    const topicRow = document.createElement("div");
    topicRow.className = "add-topic-row";

    const topicInput = document.createElement("input");
    topicInput.type = "text";
    topicInput.placeholder = "New topic title";

    const topicBtn = document.createElement("button");
    topicBtn.className = "add-btn";
    topicBtn.textContent = "Add Topic";

    topicBtn.addEventListener("click", function () {

        addTopic(subject.id, unit.id, topicInput);
    });

    topicInput.addEventListener("keydown", function (e) {

        if (e.key === "Enter") {
            addTopic(subject.id, unit.id, topicInput);
        }
    });

    topicRow.appendChild(topicInput);
    topicRow.appendChild(topicBtn);

    block.appendChild(topicRow);

    // Topics
    (unit.topics || []).forEach(function (topic) {

        block.appendChild(buildTopic(subject, unit, topic));
    });

    // Empty unit hint
    if ((unit.topics || []).length === 0) {

        const hint = document.createElement("p");
        hint.style.color = "#999";
        hint.style.fontSize = "12px";
        hint.textContent = "No topics in this unit yet.";
        block.appendChild(hint);
    }

    return block;
}


function buildTopic(subject, unit, topic) {

    const item = document.createElement("div");
    item.className = "topic-item";

    if (topic.completed) {
        item.classList.add("completed-topic");
    }

    // Toggle check
    const check = document.createElement("button");
    check.className = "topic-check";
    check.innerHTML = topic.completed
        ? '<i class="bi bi-check"></i>'
        : '<i class="bi bi-circle"></i>';

    check.addEventListener("click", function () {

        toggleTopic(subject.id, unit.id, topic.id);
    });

    item.appendChild(check);

    // Info
    const info = document.createElement("div");
    info.className = "topic-info";

    const title = document.createElement("h3");
    title.textContent = topic.title;
    info.appendChild(title);

    const detail = document.createElement("p");
    detail.textContent =
        (topic.completed ? "Completed on " + (topic.completed_date || "-") : "Pending") +
        (topic.notes ? " · " + topic.notes : "");
    info.appendChild(detail);

    item.appendChild(info);

    // Notes
    const notes = document.createElement("input");
    notes.className = "topic-notes";
    notes.type = "text";
    notes.placeholder = "Notes";
    notes.value = topic.notes || "";

    notes.addEventListener("change", function () {

        saveNotes(subject.id, unit.id, topic.id, notes);
    });

    item.appendChild(notes);

    // Status
    const status = document.createElement("span");
    status.className = "topic-status " + (topic.completed ? "completed" : "pending");
    status.textContent = topic.completed ? "Completed" : "Pending";
    item.appendChild(status);

    return item;
}


// ===== LOAD =====

function loadSyllabus() {

    fetch("/api/syllabus")
        .then(function (res) {
            return res.json();
        })
        .then(function (data) {

            render(data.syllabus, data.summary);

        })
        .catch(function (error) {

            showMessage("Could not load syllabus: " + error, "error");
        });
}


// ===== INIT =====

loadSyllabus();
