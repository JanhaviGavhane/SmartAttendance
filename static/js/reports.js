
// ===== REPORTS PAGE =====


// ===== ELEMENTS =====

const overallPercent = document.getElementById("overallPercent");
const totalPresent = document.getElementById("totalPresent");
const totalAbsent = document.getElementById("totalAbsent");
const totalRecords = document.getElementById("totalRecords");

const studentPerformanceBody = document.getElementById("studentPerformanceBody");
const belowThresholdBody = document.getElementById("belowThresholdBody");
const frequentAbsentBody = document.getElementById("frequentAbsentBody");
const dateWiseBody = document.getElementById("dateWiseBody");
const sessionsBody = document.getElementById("sessionsBody");

const dateFrom = document.getElementById("reportDateFrom");
const dateTo = document.getElementById("reportDateTo");
const subjectSelect = document.getElementById("reportSubject");
const lectureTypeSelect = document.getElementById("reportType");
const studentInput = document.getElementById("reportStudent");

const generateButton = document.getElementById("generateReportButton");
const downloadButton = document.getElementById("downloadReportButton");

let currentData = null;
let currentQuery = "";


// ===== HELPERS =====

function escapeHtml(text) {

    const div = document.createElement("div");
    div.textContent = String(text == null ? "" : text);
    return div.innerHTML;
}

function buildQuery() {

    const params = new URLSearchParams();

    if (dateFrom.value) params.set("date_from", dateFrom.value);
    if (dateTo.value) params.set("date_to", dateTo.value);

    if (subjectSelect.value) {

        params.set("subject", subjectSelect.value);
    }

    if (lectureTypeSelect.value) {

        params.set("lecture_type", lectureTypeSelect.value);
    }

    if (studentInput.value) {

        params.set("roll", studentInput.value);
    }

    return params.toString();
}


// ===== RENDER =====

function render(data) {

    // Summary
    const summary = data.summary || {};

    overallPercent.textContent =
        (summary.percentage || 0) + "%";

    totalPresent.textContent =
        summary.present || 0;

    totalAbsent.textContent =
        summary.absent || 0;

    totalRecords.textContent =
        summary.total || 0;

    // Student performance
    renderTable(
        studentPerformanceBody,
        data.student_attendance || [],
        function (s) {

            const status = s.percentage < 75
                ? '<span class="warning-status">Low</span>'
                : '<span class="warning-status" style="background:#edf8ef;color:#2f6b3a;">OK</span>';

            return "<tr>" +
                "<td>" + s.roll + "</td>" +
                "<td>" + escapeHtml(s.name) + "</td>" +
                "<td>" + s.present + "</td>" +
                "<td>" + s.absent + "</td>" +
                "<td>" + s.percentage + "%</td>" +
                "<td>" + status + "</td>" +
                "</tr>";
        },
        "No attendance records yet."
    );

    // Below 75%
    renderTable(
        belowThresholdBody,
        data.below_threshold || [],
        function (s) {

            return "<tr>" +
                "<td>" + s.roll + "</td>" +
                "<td>" + escapeHtml(s.name) + "</td>" +
                "<td><span class='warning-status'>" +
                s.percentage + "%</span></td>" +
                "</tr>";
        },
        "No students below 75%."
    );

    // Frequently absent
    renderTable(
        frequentAbsentBody,
        data.frequently_absent || [],
        function (s) {

            return "<tr>" +
                "<td>" + s.roll + "</td>" +
                "<td>" + escapeHtml(s.name) + "</td>" +
                "<td>" + s.absent + "</td>" +
                "</tr>";
        },
        "No frequently absent students."
    );

    // Date-wise
    renderTable(
        dateWiseBody,
        data.date_wise || [],
        function (d) {

            return "<tr>" +
                "<td>" + escapeHtml(d.date) + "</td>" +
                "<td>" + d.present + "</td>" +
                "<td>" + d.absent + "</td>" +
                "<td>" + d.percentage + "%</td>" +
                "</tr>";
        },
        "No data."
    );

    // Sessions
    renderTable(
        sessionsBody,
        data.sessions || [],
        function (s) {

            return "<tr>" +
                "<td>" + escapeHtml(s.date) + "</td>" +
                "<td>" + escapeHtml(s.time) + "</td>" +
                "<td>" + escapeHtml(s.subject) + "</td>" +
                "<td>" + escapeHtml(s.lecture_type) + "</td>" +
                "<td>" + s.present + "</td>" +
                "<td>" + s.absent + "</td>" +
                "<td>" + s.percentage + "%</td>" +
                "</tr>";
        },
        "No sessions."
    );

    renderCharts(data);
}


// ===== CHARTS (lightweight inline canvas, no dependencies) =====

const chartPresentAbsent = document.getElementById("chartPresentAbsent");
const chartDateTrend = document.getElementById("chartDateTrend");
const chartStudent = document.getElementById("chartStudent");
const chartFrequentAbsent = document.getElementById("chartFrequentAbsent");

function renderCharts(data) {

    const summary = data.summary || {};

    // 1. Present vs Absent (donut)
    drawDonut(
        chartPresentAbsent,
        [
            { label: "Present", value: summary.present || 0, color: "#6c8b31" },
            { label: "Absent", value: summary.absent || 0, color: "#c05555" }
        ]
    );

    // 2. Attendance % by date (line)
    const dateWise = (data.date_wise || [])
        .slice()
        .sort(function (a, b) {
            return a.date < b.date ? -1 : (a.date > b.date ? 1 : 0);
        });

    drawLine(
        chartDateTrend,
        dateWise.map(function (d) { return d.date; }),
        dateWise.map(function (d) { return d.percentage; }),
        "#d6b82f"
    );

    // 3. Attendance % by student (horizontal bars)
    const studentStats = (data.student_attendance || [])
        .slice()
        .sort(function (a, b) { return a.percentage - b.percentage; })
        .slice(0, 10);

    drawHBars(
        chartStudent,
        studentStats.map(function (s) { return "R" + s.roll; }),
        studentStats.map(function (s) { return s.percentage; })
    );

    // 4. Frequently absent (horizontal bars)
    const frequent = (data.frequently_absent || [])
        .slice()
        .sort(function (a, b) { return b.absent - a.absent; })
        .slice(0, 8);

    drawHBars(
        chartFrequentAbsent,
        frequent.map(function (s) { return "R" + s.roll; }),
        frequent.map(function (s) { return s.absent; }),
        "#c05555"
    );
}


function drawDonut(canvas, slices) {

    clearCanvas(canvas);

    const ctx = canvas.getContext("2d");

    const total = slices.reduce(function (sum, s) {
        return sum + (s.value > 0 ? s.value : 0);
    }, 0);

    if (total === 0) {

        drawEmptyText(ctx, canvas, "No data");

        return;
    }

    const cx = canvas.width / 2;
    const cy = canvas.height / 2;
    const radius = Math.min(cx, cy) - 20;
    const innerR = radius * 0.6;

    let angle = -Math.PI / 2;

    slices.forEach(function (slice) {

        const sweep = (slice.value / total) * Math.PI * 2;

        ctx.beginPath();
        ctx.arc(cx, cy, radius, angle, angle + sweep);
        ctx.arc(cx, cy, innerR, angle + sweep, angle, true);
        ctx.closePath();

        ctx.fillStyle = slice.color;
        ctx.fill();

        angle += sweep;
    });

    ctx.fillStyle = "#333";
    ctx.font = "bold 16px Arial";
    ctx.textAlign = "center";

    ctx.fillText(Math.round(total) + "", cx, cy - 4);

    ctx.font = "11px Arial";
    ctx.fillStyle = "#777";
    ctx.fillText("records", cx, cy + 14);

    // Legend
    let lx = 10;
    const ly = canvas.height - 14;

    ctx.textAlign = "left";

    slices.forEach(function (slice) {

        ctx.fillStyle = slice.color;
        ctx.fillRect(lx, ly - 8, 10, 10);

        ctx.fillStyle = "#555";
        ctx.font = "11px Arial";
        ctx.fillText(
            slice.label + " (" + slice.value + ")",
            lx + 14,
            ly
        );

        lx += 18 + ctx.measureText(
            slice.label + " (" + slice.value + ")"
        ).width;
    });
}


function clearCanvas(canvas) {

    if (!canvas) {
        return;
    }

    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
}


function drawEmptyText(ctx, canvas, text) {

    ctx.fillStyle = "#999";
    ctx.font = "13px Arial";
    ctx.textAlign = "center";
    ctx.fillText(text, canvas.width / 2, canvas.height / 2);
}


function drawLine(canvas, labels, values, color) {

    clearCanvas(canvas);

    const ctx = canvas.getContext("2d");

    if (!values || values.length === 0) {

        drawEmptyText(ctx, canvas, "No data");
        return;
    }

    const padL = 34, padR = 14, padT = 14, padB = 28;
    const w = canvas.width - padL - padR;
    const h = canvas.height - padT - padB;

    const maxV = Math.max.apply(null, values.concat([100]));
    const minV = Math.min.apply(null, values.concat([0]));

    const range = (maxV - minV) || 1;

    const x = function (i) {
        return padL + (values.length === 1 ? w / 2 : (i / (values.length - 1)) * w);
    };

    const y = function (v) {
        return padT + h - ((v - minV) / range) * h;
    };

    // grid lines
    ctx.strokeStyle = "#eee";
    ctx.lineWidth = 1;

    for (let g = 0; g <= 4; g++) {

        const gy = padT + (h / 4) * g;

        ctx.beginPath();
        ctx.moveTo(padL, gy);
        ctx.lineTo(w + padL, gy);
        ctx.stroke();
    }

    // line
    ctx.strokeStyle = color || "#d6b82f";
    ctx.lineWidth = 2;
    ctx.beginPath();

    values.forEach(function (v, i) {

        if (i === 0) ctx.moveTo(x(i), y(v));
        else ctx.lineTo(x(i), y(v));
    });

    ctx.stroke();

    // points
    ctx.fillStyle = color || "#d6b82f";

    values.forEach(function (v, i) {

        ctx.beginPath();
        ctx.arc(x(i), y(v), 3, 0, Math.PI * 2);
        ctx.fill();
    });

    // x labels
    ctx.fillStyle = "#777";
    ctx.font = "10px Arial";
    ctx.textAlign = "center";

    const step = Math.max(1, Math.ceil(values.length / 6));

    values.forEach(function (v, i) {

        if (i % step !== 0 && i !== values.length - 1) return;

        ctx.fillText(String(labels[i]).slice(5), x(i), canvas.height - 10);
    });

    // y labels
    ctx.textAlign = "right";

    for (let g = 0; g <= 4; g++) {

        const gy = padT + (h / 4) * g;
        const gv = Math.round(minV + (range / 4) * g);

        ctx.fillText(gv + "", padL - 6, gy + 3);
    }
}


function drawHBars(canvas, labels, values, color) {

    clearCanvas(canvas);

    const ctx = canvas.getContext("2d");

    if (!values || values.length === 0) {

        drawEmptyText(ctx, canvas, "No data");
        return;
    }

    const padL = 46, padR = 12, padT = 12, padB = 8;
    const w = canvas.width - padL - padR;
    const h = canvas.height - padT - padB;

    const maxV = Math.max.apply(null, values);

    const barH = Math.min(22, (h / values.length) - 6);
    const rowH = h / values.length;

    ctx.textAlign = "right";
    ctx.font = "11px Arial";

    values.forEach(function (v, i) {

        const barW = maxV > 0 ? (v / maxV) * w : 0;
        const y = padT + i * rowH;

        ctx.fillStyle = "#f5ead0";
        ctx.fillRect(padL, y, w, barH);

        ctx.fillStyle = color || "#6c8b31";
        ctx.fillRect(padL, y, barW, barH);

        ctx.fillStyle = "#555";
        ctx.fillText(String(labels[i]), padL - 6, y + barH - 4);

        ctx.textAlign = "left";
        ctx.fillStyle = "#333";
        ctx.fillText(String(v), padL + barW + 6, y + barH - 4);
        ctx.textAlign = "right";
    });
}

function renderTable(body, rows, rowBuilder, emptyText) {

    body.innerHTML = "";

    if (!rows || rows.length === 0) {

        const tr = document.createElement("tr");
        const td = document.createElement("td");
        td.colSpan = 6;
        td.textContent = emptyText;
        td.style.color = "#999";
        td.style.textAlign = "center";
        tr.appendChild(td);
        body.appendChild(tr);

        return;
    }

    rows.forEach(function (row) {

        body.insertAdjacentHTML(
            "beforeend",
            rowBuilder(row)
        );
    });
}


// ===== LOAD FILTER OPTIONS =====

function loadSubjects(data) {

    const current = subjectSelect.value;

    subjectSelect.innerHTML =
        '<option value="">All Subjects</option>';

    (data.subjects || []).forEach(function (s) {

        const option = document.createElement("option");
        option.value = s;
        option.textContent = s;
        subjectSelect.appendChild(option);
    });

    if (current) {

        subjectSelect.value = current;
    }
}


// ===== LOAD =====

function loadReports() {

    currentQuery = buildQuery();

    fetch("/api/reports?" + currentQuery)
        .then(function (res) {
            return res.json();
        })
        .then(function (data) {

            currentData = data;

            loadSubjects(data);

            render(data);

        })
        .catch(function (error) {

            console.log("Reports error:", error);
        });
}


// ===== GENERATE =====

generateButton.addEventListener(
    "click",
    function () {

        loadReports();
    }
);


// ===== DOWNLOAD REPORT (filtered CSV) =====

function downloadCSV() {

    if (!currentData) {

        alert("Generate a report first.");

        return;
    }

    const studentStats =
        currentData.student_attendance || [];

    if (studentStats.length === 0) {

        alert("No data to download.");

        return;
    }

    let csv =
        "Roll Number,Student Name,Present,Absent,Total,Percentage\n";

    studentStats.forEach(function (s) {

        csv += s.roll + "," +
            '"' + String(s.name).replace(/"/g, '""') + '",' +
            s.present + "," +
            s.absent + "," +
            s.total + "," +
            s.percentage + "%\n";
    });

    const blob = new Blob(["\ufeff" + csv], {
        type: "text/csv"
    });

    const url = URL.createObjectURL(blob);

    const link = document.createElement("a");

    link.href = url;

    link.download = "attendance_report.csv";

    link.click();

    URL.revokeObjectURL(url);
}

downloadButton.addEventListener(
    "click",
    downloadCSV
);


// ===== INIT =====

loadReports();
