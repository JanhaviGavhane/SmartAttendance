
// ===== STUDENTS PAGE =====


// ===== ELEMENTS =====

const searchBox = document.getElementById("studentSearch");
const studentTable = document.getElementById("studentTable");
const emptyList = document.getElementById("emptyList");
const messageBox = document.getElementById("studentMessage");

const totalStudents = document.getElementById("totalStudents");
const presentToday = document.getElementById("presentToday");
const absentToday = document.getElementById("absentToday");

const studentUpload = document.getElementById("studentUpload");
const uploadFileName = document.getElementById("uploadFileName");
const uploadOptions = document.getElementById("uploadOptions");

const uploadMerge = document.getElementById("uploadMerge");
const uploadReplace = document.getElementById("uploadReplace");
const uploadCancel = document.getElementById("uploadCancel");

let currentFile = null;
let allStudents = [];


// ===== HELPERS =====

function showMessage(text, type) {

    messageBox.style.display = "block";

    messageBox.className = "message-banner " + (type || "");

    messageBox.textContent = text;
}

function clearMessage() {

    messageBox.style.display = "none";

    messageBox.textContent = "";
}

function currentDateStr() {

    const now = new Date();

    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, "0");
    const d = String(now.getDate()).padStart(2, "0");

    return y + "-" + m + "-" + d;
}


// ===== RENDER TABLE =====

function renderStudents(students) {

    studentTable.innerHTML = "";

    if (!students || students.length === 0) {

        emptyList.style.display = "block";

        return;

    }

    emptyList.style.display = "none";

    students.forEach(function (student) {

        const row = document.createElement("tr");

        const rollCell = document.createElement("td");
        rollCell.textContent = student.roll;

        const nameCell = document.createElement("td");
        nameCell.textContent = student.name;

        const actionCell = document.createElement("td");

        const deleteBtn = document.createElement("button");
        deleteBtn.className = "delete-student";
        deleteBtn.title = "Delete student";
        deleteBtn.innerHTML = '<i class="bi bi-trash"></i>';

        deleteBtn.addEventListener(
            "click",
            function () {

                deleteStudent(student.roll);
            }
        );

        actionCell.appendChild(deleteBtn);

        row.appendChild(rollCell);
        row.appendChild(nameCell);
        row.appendChild(actionCell);

        studentTable.appendChild(row);
    });
}


// ===== LOAD STUDENTS =====

function loadStudents() {

    fetch("/api/students")
        .then(function (res) {
            return res.json();
        })
        .then(function (data) {

            allStudents = data.students || [];

            allStudents.sort(function (a, b) {
                return a.roll - b.roll;
            });

            totalStudents.textContent = allStudents.length;

            renderStudents(allStudents);

            searchBox.value = "";

        })
        .catch(function (error) {

            console.log("Load students error:", error);
        });
}


// ===== LOAD TODAY'S COUNTS =====

function loadTodayCounts() {

    const today = currentDateStr();

    fetch("/api/reports")
        .then(function (res) {
            return res.json();
        })
        .then(function (data) {

            const records = (data.records || []).filter(
                function (r) {
                    return r.date === today;
                }
            );

            const present = records.filter(
                function (r) {
                    return r.status === "Present";
                }
            ).length;

            const absent = records.filter(
                function (r) {
                    return r.status === "Absent";
                }
            ).length;

            presentToday.textContent = present;
            absentToday.textContent = absent;

        })
        .catch(function (error) {

            console.log("Load today counts error:", error);
        });
}


// ===== SEARCH =====

searchBox.addEventListener(
    "input",
    function () {

        const searchText =
            searchBox.value.toLowerCase().trim();

        if (searchText === "") {

            renderStudents(allStudents);

            return;
        }

        const filtered = allStudents.filter(
            function (student) {

                return (
                    String(student.roll).indexOf(searchText) !== -1 ||
                    student.name.toLowerCase()
                        .indexOf(searchText) !== -1
                );
            }
        );

        renderStudents(filtered);
    }
);


// ===== FILE SELECTED =====

studentUpload.addEventListener(
    "change",
    function () {

        if (studentUpload.files.length === 0) {

            currentFile = null;
            uploadOptions.style.display = "none";

            return;
        }

        currentFile = studentUpload.files[0];

        uploadFileName.textContent = currentFile.name;

        uploadOptions.style.display = "block";
    }
);


uploadCancel.addEventListener(
    "click",
    function () {

        currentFile = null;

        studentUpload.value = "";

        uploadOptions.style.display = "none";

        clearMessage();
    }
);


// ===== UPLOAD (MERGE or REPLACE) =====

function uploadFile(mode) {

    if (!currentFile) {

        return;
    }

    const formData = new FormData();

    formData.append("file", currentFile);
    formData.append("mode", mode);

    fetch("/students/upload", {
        method: "POST",
        body: formData
    })
        .then(function (res) {
            return res.json();
        })
        .then(function (data) {

            if (!data.success) {

                showMessage(
                    data.error || "Upload failed.",
                    "error"
                );

                return;
            }

            let text = data.message;

            if (data.duplicates && data.duplicates.length > 0) {

                text += " Skipped " + data.duplicates.length +
                    " duplicate roll number(s).";
            }

            if (data.errors && data.errors.length > 0) {

                text += " Warnings: " +
                    data.errors.slice(0, 3).join(" | ");
            }

            showMessage(text, "success");

            currentFile = null;
            studentUpload.value = "";
            uploadOptions.style.display = "none";

            loadStudents();
            loadTodayCounts();

        })
        .catch(function (error) {

            showMessage("Upload error: " + error, "error");
        });
}

uploadMerge.addEventListener("click", function () {

    uploadFile("merge");
});

uploadReplace.addEventListener("click", function () {

    uploadFile("replace");
});


// ===== DELETE =====

function deleteStudent(roll) {

    if (!confirm("Delete roll number " + roll + "?")) {

        return;
    }

    const formData = new FormData();

    formData.append("roll", roll);

    fetch("/students/delete", {
        method: "POST",
        body: formData
    })
        .then(function (res) {
            return res.json();
        })
        .then(function (data) {

            if (data.success) {

                showMessage("Student removed.", "success");

            } else {

                showMessage(
                    data.error || "Could not delete student.",
                    "error"
                );
            }

            loadStudents();

        })
        .catch(function (error) {

            showMessage("Delete error: " + error, "error");
        });
}


loadStudents();
loadTodayCounts();
