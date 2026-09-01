
// ===== CALENDAR PAGE =====


// ===== GET ELEMENTS =====

const calendarGrid = document.getElementById("calendarGrid");
const monthTitle = document.getElementById("monthTitle");
const previousMonth = document.getElementById("previousMonth");
const nextMonth = document.getElementById("nextMonth");
const todayButton = document.getElementById("todayButton");

const recentSessionsList = document.getElementById("recentSessionsList");
const sessionDetail = document.getElementById("sessionDetail");
const closeDetail = document.getElementById("closeDetail");
const detailTitle = document.getElementById("detailTitle");
const detailBody = document.getElementById("detailBody");


// ===== DATA =====

let sessionByDate = {};
let dateWise = [];


// ===== CURRENT DATE =====

let currentDate = new Date();


// ===== MONTH NAMES =====

const monthNames = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December"
];


// ===== HELPERS =====

function fmtKey(year, month, day) {

    return year + "-" +
        String(month + 1).padStart(2, "0") + "-" +
        String(day).padStart(2, "0");
}

function displayDate(iso) {

    if (!iso) {

        return "-";
    }

    const parts = iso.split("-");

    if (parts.length < 3) {

        return iso;
    }

    const monthNamesMap = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
    ];

    const y = parts[0];
    const m = parseInt(parts[1], 10) - 1;
    const d = parseInt(parts[2], 10);

    return d + " " + monthNamesMap[m] + " " + y;
}


// ===== RENDER RECENT SESSIONS =====

function renderRecentSessions(sessions) {

    recentSessionsList.innerHTML = "";

    if (!sessions || sessions.length === 0) {

        const empty = document.createElement("p");
        empty.className = "empty-sessions";
        empty.textContent = "No attendance sessions recorded yet.";
        recentSessionsList.appendChild(empty);

        return;
    }

    // Show up to 6 most recent
    sessions.slice(0, 6).forEach(function (s) {

        const item = document.createElement("div");
        item.className = "session-item";

        const icon = document.createElement("div");
        icon.className = "session-icon";
        icon.innerHTML = '<i class="bi bi-calendar-check"></i>';
        item.appendChild(icon);

        const info = document.createElement("div");
        info.className = "session-info";

        const h3 = document.createElement("h3");
        h3.textContent = s.subject || "General";
        info.appendChild(h3);

        const p = document.createElement("p");
        p.textContent = displayDate(s.date) +
            " · " + (s.lecture_type || "") +
            " · " + (s.time || "");
        info.appendChild(p);

        item.appendChild(info);

        const value = document.createElement("span");
        value.textContent = s.percentage + "% Present";
        item.appendChild(value);

        recentSessionsList.appendChild(item);
    });
}


// ===== CREATE CALENDAR =====

function createCalendar() {

    calendarGrid.innerHTML = "";

    const year =
        currentDate.getFullYear();

    const month =
        currentDate.getMonth();


    // ===== SHOW MONTH =====

    monthTitle.textContent =
        monthNames[month] + " " + year;


    // ===== FIND FIRST DAY =====

    const firstDay =
        new Date(
            year,
            month,
            1
        ).getDay();


    // ===== FIND TOTAL DAYS =====

    const totalDays =
        new Date(
            year,
            month + 1,
            0
        ).getDate();


    // ===== EMPTY DAYS =====

    for (
        let i = 0;
        i < firstDay;
        i++
    ) {

        const emptyDay =
            document.createElement("div");

        emptyDay.className =
            "calendar-day other-month";

        calendarGrid.appendChild(
            emptyDay
        );

    }


    // ===== CREATE DAYS =====

    for (
        let day = 1;
        day <= totalDays;
        day++
    ) {

        const dayBox =
            document.createElement("div");

        dayBox.className =
            "calendar-day";


        // ===== DAY NUMBER =====

        const number =
            document.createElement("div");

        number.className =
            "day-number";

        number.textContent =
            day;


        dayBox.appendChild(number);


        // ===== HIGHLIGHT TODAY =====

        const today =
            new Date();

        if (
            day === today.getDate() &&
            month === today.getMonth() &&
            year === today.getFullYear()
        ) {

            dayBox.classList.add(
                "current-day"
            );

        }


        // ===== SESSION MARKER =====

        const key =
            fmtKey(year, month, day);

        const sessionsForDay =
            sessionByDate[key] || [];

        if (sessionsForDay.length > 0) {

            dayBox.classList.add(
                "has-session"
            );

            const dot =
                document.createElement("span");

            dot.className =
                "session-dot";

            dot.textContent =
                sessionsForDay[0].subject || "Class";

            dayBox.appendChild(dot);
        }


        // ===== CLICK DATE =====

        dayBox.addEventListener(
            "click",
            function () {

                showDayDetail(key, day);
            }
        );


        calendarGrid.appendChild(
            dayBox
        );

    }

}


// ===== SHOW DETAIL FOR A DATE =====

function showDayDetail(key, day) {

    const sessions =
        sessionByDate[key] || [];

    closeDetailIfOpen();

    detailTitle.textContent =
        "Sessions on " + displayDate(key);

    detailBody.innerHTML = "";

    if (sessions.length === 0) {

        const p = document.createElement("p");
        p.style.color = "#999";
        p.textContent = "No attendance recorded on this date.";
        detailBody.appendChild(p);

    } else {

        sessions.forEach(function (s) {

            const box = document.createElement("div");
            box.className = "detail-session";

            const strong = document.createElement("strong");
            strong.textContent =
                (s.subject || "General") +
                " (" + (s.lecture_type || "") + ") · " + (s.time || "");
            box.appendChild(strong);

            const span = document.createElement("span");
            span.textContent =
                s.present + " present, " +
                s.absent + " absent (" + s.percentage + "%)";
            box.appendChild(span);

            detailBody.appendChild(box);
        });
    }

    sessionDetail.style.display = "block";
}


function closeDetailIfOpen() {

    sessionDetail.style.display = "none";
}

closeDetail.addEventListener(
    "click",
    closeDetailIfOpen
);


// ===== PREVIOUS MONTH =====

previousMonth.addEventListener(
    "click",
    function () {

        currentDate.setMonth(
            currentDate.getMonth() - 1
        );

        createCalendar();

    }
);


// ===== NEXT MONTH =====

nextMonth.addEventListener(
    "click",
    function () {

        currentDate.setMonth(
            currentDate.getMonth() + 1
        );

        createCalendar();

    }
);


// ===== TODAY BUTTON =====

todayButton.addEventListener(
    "click",
    function () {

        currentDate =
            new Date();

        createCalendar();

    }
);


// ===== LOAD DATA =====

function loadCalendarData() {

    fetch("/api/calendar")
        .then(function (res) {
            return res.json();
        })
        .then(function (data) {

            sessionByDate = {};
            dateWise = data.date_wise || [];

            (data.sessions || []).forEach(function (s) {

                const key = s.date;

                if (!sessionByDate[key]) {

                    sessionByDate[key] = [];
                }

                sessionByDate[key].push(s);
            });

            renderRecentSessions(data.sessions || []);

            createCalendar();

        })
        .catch(function (error) {

            console.log("Calendar data error:", error);

            createCalendar();
        });
}


// ===== INIT =====

loadCalendarData();
