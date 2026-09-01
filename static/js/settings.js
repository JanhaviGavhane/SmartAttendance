
// ===== SETTINGS PAGE =====


// ===== SAVE BUTTON =====

const saveButton =
    document.getElementById(
        "saveSettings"
    );


// ===== SAVE SETTINGS =====

saveButton.addEventListener(
    "click",
    function () {

        // ===== GET VALUES =====

        const name =
            document.getElementById(
                "teacherName"
            ).value;

        const email =
            document.getElementById(
                "teacherEmail"
            ).value;


        const voice =
            document.getElementById(
                "voiceAttendance"
            ).checked;


        const duplicate =
            document.getElementById(
                "duplicatePrevention"
            ).checked;


        const notification =
            document.getElementById(
                "lowAttendanceAlert"
            ).checked;


        // ===== TEMPORARY SAVE =====

        console.log("Name:", name);

        console.log("Email:", email);

        console.log(
            "Voice Attendance:",
            voice
        );

        console.log(
            "Duplicate Prevention:",
            duplicate
        );

        console.log(
            "Low Attendance Alert:",
            notification
        );


        // ===== SUCCESS MESSAGE =====

        alert(
            "Settings saved successfully!"
        );

    }
);
