"""OpenRank Leaderboard Web App"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from gpa_scraper import PowerSchoolGPAScraper

DEFAULT_DISTRICT = "Bentonville School District"
DATA_FILE = Path("data/students.json")


@dataclass
class StudentRecord:
    username: str
    password: str
    district: str = DEFAULT_DISTRICT
    name: Optional[str] = None
    gpa: Optional[float] = None
    last_updated: Optional[str] = None

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "StudentRecord":
        return cls(
            username=payload.get("username", ""),
            password=payload.get("password", ""),
            district=payload.get("district", DEFAULT_DISTRICT),
            name=payload.get("name"),
            gpa=payload.get("gpa"),
            last_updated=payload.get("last_updated"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "username": self.username,
            "password": self.password,
            "district": self.district,
            "name": self.name,
            "gpa": self.gpa,
            "last_updated": self.last_updated,
        }


def _ensure_data_file() -> Dict[str, Any]:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        initial_state = {
            "users": [
                {
                    "username": "admin",
                    "password": "admin123",
                    "role": "admin",
                    "name": "OpenRank Admin",
                }
            ],
            "students": [],
        }
        DATA_FILE.write_text(json.dumps(initial_state, indent=2), encoding="utf-8")
        return initial_state

    try:
        with DATA_FILE.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError:
        # Reset the store if it becomes corrupted to keep the app usable.
        initial_state = {
            "users": [
                {
                    "username": "admin",
                    "password": "admin123",
                    "role": "admin",
                    "name": "OpenRank Admin",
                }
            ],
            "students": [],
        }
        DATA_FILE.write_text(json.dumps(initial_state, indent=2), encoding="utf-8")
        return initial_state


def _save_state(state: Dict[str, Any]) -> None:
    DATA_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _load_students(state: Dict[str, Any]) -> List[StudentRecord]:
    students: List[StudentRecord] = []
    for record in state.get("students", []):
        students.append(StudentRecord.from_dict(record))
    return students


def _find_user(state: Dict[str, Any], username: str) -> Optional[Dict[str, Any]]:
    for user in state.get("users", []):
        if user.get("username") == username:
            return user
    return None


def _find_student(students: List[StudentRecord], username: str) -> Optional[StudentRecord]:
    for student in students:
        if student.username == username:
            return student
    return None


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _refresh_student(student: StudentRecord) -> StudentRecord:
    scraper = PowerSchoolGPAScraper(
        username=student.username,
        password=student.password,
        district=student.district or DEFAULT_DISTRICT,
    )
    info = scraper.get_transcript_info()

    if not info:
        gpa_only = scraper.get_gpa()
        if gpa_only is None:
            raise RuntimeError("Unable to refresh GPA for the provided credentials")
        info = {"weighted_cumulative_gpa": gpa_only}

    gpa_value = info.get("weighted_cumulative_gpa")
    if gpa_value is None:
        raise RuntimeError("Weighted cumulative GPA not found")

    student.gpa = float(gpa_value)
    student.name = info.get("student_name") or student.name or student.username
    student.last_updated = _timestamp()
    if not student.district:
        student.district = DEFAULT_DISTRICT
    return student


def _refresh_all_students(students: List[StudentRecord]) -> Dict[str, List[str]]:
    results = {"success": [], "failed": []}
    for student in students:
        try:
            _refresh_student(student)
            results["success"].append(student.username)
        except Exception as exc:  # noqa: BLE001
            results["failed"].append(f"{student.username}: {exc}")
    return results


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "openrank-secret-key")


@app.context_processor
def inject_now() -> Dict[str, Any]:
    return {"now": datetime.now(timezone.utc)}


@app.template_filter("humandate")
def format_human_date(value: Optional[str]) -> str:
    if not value:
        return "Never"
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return value
    return dt.astimezone().strftime("%b %d, %Y %I:%M %p")


@app.route("/")
def home() -> Any:
    if session.get("username"):
        return redirect(url_for("leaderboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login() -> Any:
    state = _ensure_data_file()
    students = _load_students(state)

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        district = request.form.get("district", DEFAULT_DISTRICT).strip() or DEFAULT_DISTRICT
        display_name = request.form.get("display_name", "").strip()

        if not username or not password:
            flash("Please provide both username and password.", "error")
            return render_template(
                "login.html",
                district=district,
            )

        admin = _find_user(state, username)
        if admin:
            if admin.get("password") != password:
                flash("Incorrect password for admin account.", "error")
                return render_template("login.html", district=district)

            session["username"] = admin["username"]
            session["role"] = admin.get("role", "admin")
            flash("Welcome back, administrator!", "success")
            return redirect(url_for("leaderboard"))

        student = _find_student(students, username)
        if student and student.password != password:
            flash("Incorrect password. Please try again.", "error")
            return render_template("login.html", district=student.district)

        student = student or StudentRecord(username=username, password=password, district=district)
        student.password = password
        student.district = district or DEFAULT_DISTRICT
        if display_name:
            student.name = display_name

        try:
            _refresh_student(student)
        except Exception as exc:  # noqa: BLE001
            flash(str(exc), "error")
            return render_template("login.html", district=student.district)

        updated_students: List[StudentRecord] = []
        exists = False
        for record in students:
            if record.username == student.username:
                updated_students.append(student)
                exists = True
            else:
                updated_students.append(record)
        if not exists:
            updated_students.append(student)

        state["students"] = [s.to_dict() for s in updated_students]
        _save_state(state)

        session["username"] = student.username
        session["role"] = "student"
        flash("GPA refreshed and leaderboard updated!", "success")
        return redirect(url_for("leaderboard"))

    return render_template("login.html", district=DEFAULT_DISTRICT)


@app.route("/logout", methods=["POST"])
def logout() -> Any:
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("login"))


@app.route("/leaderboard")
def leaderboard() -> Any:
    if not session.get("username"):
        flash("Please sign in to view the leaderboard.", "warning")
        return redirect(url_for("login"))

    state = _ensure_data_file()
    students = _load_students(state)

    sorted_students = sorted(
        students,
        key=lambda s: (s.gpa is not None, s.gpa if s.gpa is not None else 0.0),
        reverse=True,
    )

    return render_template(
        "leaderboard.html",
        students=sorted_students,
        current_user=session.get("username"),
        role=session.get("role", "student"),
    )


@app.route("/admin/refresh", methods=["POST"])
def admin_refresh() -> Any:
    if session.get("role") != "admin":
        flash("Admin access required.", "error")
        return redirect(url_for("leaderboard"))

    state = _ensure_data_file()
    students = _load_students(state)

    if not students:
        flash("No students to refresh yet.", "info")
        return redirect(url_for("leaderboard"))

    results = _refresh_all_students(students)
    state["students"] = [s.to_dict() for s in students]
    _save_state(state)

    if results["success"]:
        flash(f"Refreshed GPA for: {', '.join(results['success'])}", "success")
    if results["failed"]:
        flash("Unable to refresh: " + "; ".join(results["failed"]), "error")

    return redirect(url_for("leaderboard"))


if __name__ == "__main__":
    app.run(debug=True)
