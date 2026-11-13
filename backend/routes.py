import os
import uuid
from datetime import datetime
from functools import wraps

from flask import (
    Blueprint,
    request,
    jsonify,
    session,
    current_app,
    send_file
)

from werkzeug.utils import secure_filename

from .database import db
from .models import (
    Note,
    Test,
    TestQuestion,
    TestAttempt,
    Batch,
    BatchEnrollment,
    Student,
    ParentStudentLink,
    Attendance
)

from .auth import (
    admin_required,
    student_required,
    parent_required
)

from datetime import datetime, date

# ==========================================
# BLUEPRINTS
# ==========================================

notes_bp = Blueprint(
    "notes",
    __name__,
    url_prefix="/api/notes"
)

tests_bp = Blueprint(
    "tests",
    __name__,
    url_prefix="/api/tests"
)

batches_bp = Blueprint(
    "batches",
    __name__,
    url_prefix="/api/batches"
)

# ==========================================
# ==========================================
# COMMON HELPERS
# ==========================================
  
ALLOWED_CLASSES= [
    "5th", "6th", "7th",
    "8th", "9th", "10th"
]


def get_student_id():
    return session.get("student_id")


def normalize_class(value):

    value = str(value or "").strip().lower()

    mapping = {
        "class 5": "5th",
        "class 6": "6th",
        "class 7": "7th",
        "class 8": "8th",
        "class 9": "9th",
        "class 10": "10th",

        "class-5": "5th",
        "class-6": "6th",
        "class-7": "7th",
        "class-8": "8th",
        "class-9": "9th",
        "class-10": "10th",

        "5": "5th",
        "6": "6th",
        "7": "7th",
        "8": "8th",
        "9": "9th",
        "10": "10th"
    }

    return mapping.get(value, value)

def update_total_marks(test):

    test.total_marks = sum(
        question.marks
        for question in test.questions
    )


def get_upload_folder():

    folder = os.path.join(
        current_app.static_folder,
        "documents"
    )

    os.makedirs(folder, exist_ok=True)

    return folder
# ==========================================
# MEETING LINK VALIDATION
# ==========================================

from urllib.parse import urlparse


def validate_meeting_link(value):

    value = str(value or "").strip()

    if not value:
        return ""

    try:
        parsed = urlparse(value)

        if (
            parsed.scheme != "https"
            or not parsed.netloc
        ):
            return None

        return value

    except Exception:
        return None

def save_pdf(file):

    if not file or not file.filename:
        return None, None

    original_name = secure_filename(file.filename)

    if not original_name.lower().endswith(".pdf"):
        raise ValueError("Only PDF files are allowed")

    unique_name = (
        uuid.uuid4().hex
        + "_"
        + original_name
    )

    folder = get_upload_folder()

    file_path = os.path.join(
        folder,
        unique_name
    )

    file.save(file_path)

    relative_path = os.path.join(
        "static",
        "documents",
        unique_name
    ).replace("\\", "/")

    return unique_name, relative_path


def delete_note_file(note):

    if not note.file_path:
        return

    filename = os.path.basename(note.file_path)

    folder = os.path.realpath(get_upload_folder())

    file_path = os.path.realpath(
        os.path.join(folder, filename)
    )

    if (
        os.path.commonpath([folder, file_path]) == folder
        and os.path.isfile(file_path)
    ):
        os.remove(file_path)


def get_note_file_path(note):

    if not note.file_path:
        return None

    filename = os.path.basename(note.file_path)

    folder = os.path.realpath(get_upload_folder())

    path = os.path.realpath(
        os.path.join(folder, filename)
    )

    if os.path.commonpath([folder, path]) != folder:
        return None

    if not os.path.isfile(path):
        return None

    return path

# ==========================================
# NOTES SYSTEM
# ==========================================

# ------------------------------------------
# STUDENT: GET PUBLISHED NOTES
# ------------------------------------------

@notes_bp.route("", methods=["GET"])
@student_required
def get_notes():

    query = Note.query.filter_by(
        is_published=True,
        board="PSEB"
    )

    class_name = request.args.get("class_name")
    subject = request.args.get("subject")
    chapter = request.args.get("chapter")

    if class_name:
        query = query.filter_by(
            class_name=normalize_class(class_name)
        )

    if subject:
        query = query.filter_by(subject=subject)

    if chapter:
        query = query.filter_by(chapter=chapter)

    notes = query.order_by(
        Note.created_at.desc()
    ).all()

    return jsonify({
        "success": True,
        "total_notes": len(notes),
        "notes": [
            note.to_dict()
            for note in notes
        ]
    })


# ------------------------------------------
# ADMIN: GET ALL NOTES
# ------------------------------------------

@notes_bp.route("/admin", methods=["GET"])
@admin_required
def get_all_notes():

    notes = Note.query.order_by(
        Note.created_at.desc()
    ).all()

    return jsonify({
        "success": True,
        "total_notes": len(notes),
        "notes": [
            note.to_dict()
            for note in notes
        ]
    })


# ------------------------------------------
# ADMIN: UPLOAD NOTE
# ------------------------------------------

@notes_bp.route("", methods=["POST"])
@admin_required
def upload_note():

    data = request.form

    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    board = data.get("board", "PSEB").strip().upper()
    class_name = normalize_class(data.get("class_name"))
    subject = data.get("subject", "").strip()
    chapter = data.get("chapter", "").strip()

    file = request.files.get("file")

    if not all([
        title,
        class_name,
        subject,
        chapter,
        file
    ]):
        return jsonify({
            "success": False,
            "message": "All required fields and PDF file are required"
        }), 400

    if board != "PSEB":
        return jsonify({
            "success": False,
            "message": "Only PSEB board is supported"
        }), 400

    if class_name not in ALLOWED_CLASSES:
        return jsonify({
            "success": False,
            "message": "Invalid class"
        }), 400

    if len(title) > 200:
        return jsonify({
            "success": False,
            "message": "Title is too long"
        }), 400

    try:

        file_name, file_path = save_pdf(file)

        note = Note(
            title=title,
            description=description,
            board="PSEB",
            class_name=class_name,
            subject=subject,
            chapter=chapter,
            file_name=file_name,
            file_path=file_path,
            is_published=False
        )

        db.session.add(note)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Note uploaded successfully",
            "note": note.to_dict()
        }), 201

    except ValueError as error:

        return jsonify({
            "success": False,
            "message": str(error)
        }), 400

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "Note upload failed"
        )

        return jsonify({
            "success": False,
            "message": "Unable to upload note"
        }), 500


# ------------------------------------------
# ADMIN: UPDATE NOTE
# ------------------------------------------

@notes_bp.route("/<int:note_id>", methods=["PUT"])
@admin_required
def update_note(note_id):

    note = Note.query.get_or_404(note_id)

    data = (
        request.form
        if request.form
        else request.get_json(silent=True) or {}
    )

    fields = [
        "title",
        "description",
        "class_name",
        "subject",
        "chapter"
    ]

    for field in fields:

        if field not in data:
            continue

        value = str(data[field]).strip()

        if field == "class_name":
            value = normalize_class(value)

        if field in ["title", "subject", "chapter"] and not value:
            return jsonify({
                "success": False,
                "message": f"{field} cannot be empty"
            }), 400

        if field == "class_name" and value not in ALLOWED_CLASSES:
            return jsonify({
                "success": False,
                "message": "Invalid class"
            }), 400

        setattr(note, field, value)

    new_file = request.files.get("file")

    try:

        if new_file and new_file.filename:

            new_name, new_path = save_pdf(new_file)

            delete_note_file(note)

            note.file_name = new_name
            note.file_path = new_path

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Note updated successfully",
            "note": note.to_dict()
        })

    except ValueError as error:

        return jsonify({
            "success": False,
            "message": str(error)
        }), 400

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "Note update failed"
        )

        return jsonify({
            "success": False,
            "message": "Unable to update note"
        }), 500


# ------------------------------------------
# ADMIN: PUBLISH / UNPUBLISH NOTE
# ------------------------------------------

@notes_bp.route("/<int:note_id>/publish", methods=["PATCH"])
@admin_required
def toggle_note_publish(note_id):

    note = Note.query.get_or_404(note_id)

    data = request.get_json(silent=True) or {}

    published = data.get("is_published")

    if not isinstance(published, bool):

        return jsonify({
            "success": False,
            "message": "Invalid publish status"
        }), 400

    note.is_published = published

    try:

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Note status updated",
            "is_published": note.is_published
        })

    except Exception:

        db.session.rollback()

        return jsonify({
            "success": False,
            "message": "Unable to update note status"
        }), 500


# ------------------------------------------
# ADMIN: DELETE NOTE
# ------------------------------------------

@notes_bp.route("/<int:note_id>", methods=["DELETE"])
@admin_required
def delete_note(note_id):

    note = Note.query.get_or_404(note_id)

    try:

        delete_note_file(note)

        db.session.delete(note)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Note deleted successfully"
        })

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "Note deletion failed"
        )

        return jsonify({
            "success": False,
            "message": "Unable to delete note"
        }), 500


# ------------------------------------------
# STUDENT: PREVIEW / DOWNLOAD NOTE
# ------------------------------------------

@notes_bp.route("/<int:note_id>/file", methods=["GET"])
@student_required
def get_note_file(note_id):

    note = Note.query.filter_by(
        id=note_id,
        is_published=True
    ).first_or_404()

    path = get_note_file_path(note)

    if not path:
        return jsonify({
            "success": False,
            "message": "PDF file not found"
        }), 404

    return send_file(
        path,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=note.file_name
    )


# ==========================================
# ONLINE TEST SYSTEM
# ==========================================

# ------------------------------------------
# STUDENT: GET PUBLISHED TESTS
# ------------------------------------------

@tests_bp.route("", methods=["GET"])
@student_required
def get_published_tests():

    query = Test.query.filter_by(
        is_published=True,
        board="PSEB"
    )

    class_name = request.args.get("class_name")
    subject = request.args.get("subject")

    if class_name:
        query = query.filter_by(
            class_name=normalize_class(class_name)
        )

    if subject:
        query = query.filter_by(subject=subject)

    tests = query.order_by(
        Test.created_at.desc()
    ).all()

    return jsonify({
        "success": True,
        "total_tests": len(tests),
        "tests": [
            test.to_dict(include_questions=False)
            for test in tests
        ]
    })



# ------------------------------------------
# STUDENT: GET SINGLE TEST
# ------------------------------------------

@tests_bp.route("/<int:test_id>", methods=["GET"])
@student_required
def get_test(test_id):

    test = Test.query.filter_by(
        id=test_id,
        is_published=True,
        board="PSEB"
    ).first_or_404()

    # Questions without correct answers
    questions = [
        q.to_dict(include_answer=False)
        for q in test.questions
    ]

    # Include questions inside test as well
    test_data = test.to_dict(include_questions=False)
    test_data["questions"] = questions

    return jsonify({
        "success": True,
        "test": test_data,
        "questions": questions
    })


# ------------------------------------------
# ADMIN: GET ALL TESTS
# ------------------------------------------

@tests_bp.route("/admin", methods=["GET"])
@admin_required
def get_all_tests():

    tests = Test.query.order_by(
        Test.created_at.desc()
    ).all()

    return jsonify({
        "success": True,
        "tests": [
            test.to_dict()
            for test in tests
        ]
    })


# ------------------------------------------
# ADMIN: CREATE TEST
# ------------------------------------------

@tests_bp.route("", methods=["POST"])
@admin_required
def create_test():

    data = request.get_json(silent=True) or {}

    required = [
        "title",
        "board",
        "class_name",
        "subject"
    ]

    for field in required:

        if not str(data.get(field, "")).strip():

            return jsonify({
                "success": False,
                "message": f"{field} is required"
            }), 400

    class_name = normalize_class(data["class_name"])


    if class_name not in ALLOWED_CLASSES:

        return jsonify({
            "success": False,
            "message": "Invalid class"
        }), 400

    if data["board"].strip().upper() != "PSEB":

        return jsonify({
            "success": False,
            "message": "Only PSEB board is supported"
        }), 400

    try:

        duration = int(
            data.get("duration_minutes", 30)
        )

        if not 1 <= duration <= 300:
            raise ValueError()

    except (ValueError, TypeError):

        return jsonify({
            "success": False,
            "message": "Invalid duration"
        }), 400

    test = Test(
        title=data["title"].strip(),
        description=str(data.get("description", "")).strip(),
        board="PSEB",
        class_name=class_name,
        subject=data["subject"].strip(),
        duration_minutes=duration,
        total_marks=0,
        is_published=False
    )

    try:

        db.session.add(test)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Test created successfully",
            "test": test.to_dict()
        }), 201

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "Test creation failed"
        )

        return jsonify({
            "success": False,
            "message": "Unable to create test"
        }), 500


# ------------------------------------------
# ADMIN: UPDATE TEST
# ------------------------------------------

@tests_bp.route("/<int:test_id>", methods=["PUT"])
@admin_required
def update_test(test_id):

    test = Test.query.get_or_404(test_id)

    data = request.get_json(silent=True) or {}

    for field in [
        "title",
        "description",
        "class_name",
        "subject"
    ]:

        if field not in data:
            continue

        value = str(data[field]).strip()

        if field != "description" and not value:

            return jsonify({
                "success": False,
                "message": f"{field} cannot be empty"
            }), 400

        if field == "class_name":

            value = normalize_class(value)

            if value not in ALLOWED_CLASSES:

                return jsonify({
                    "success": False,
                    "message": "Invalid class"
                }), 400

        setattr(test, field, value)

    if "duration_minutes" in data:

        try:

            duration = int(data["duration_minutes"])

            if not 1 <= duration <= 300:
                raise ValueError()

            test.duration_minutes = duration

        except (ValueError, TypeError):

            return jsonify({
                "success": False,
                "message": "Invalid duration"
            }), 400

    try:

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Test updated successfully"
        })

    except Exception:

        db.session.rollback()

        return jsonify({
            "success": False,
            "message": "Unable to update test"
        }), 500


# ------------------------------------------
# ADMIN: ADD QUESTION
# ------------------------------------------

@tests_bp.route("/<int:test_id>/questions", methods=["POST"])
@admin_required
def add_test_question(test_id):

    test = Test.query.get_or_404(test_id)

    data = request.get_json(silent=True) or {}

    text = str(
        data.get("question_text", "")
    ).strip()

    qtype = data.get("question_type", "mcq")

    if not text or qtype not in ["mcq", "subjective"]:

        return jsonify({
            "success": False,
            "message": "Invalid question"
        }), 400

    try:

        marks = int(data.get("marks", 1))

        if not 1 <= marks <= 100:
            raise ValueError()

    except (ValueError, TypeError):

        return jsonify({
            "success": False,
            "message": "Invalid marks"
        }), 400

    options = None
    answer = None

    if qtype == "mcq":

        options = data.get("options")
        answer = data.get("correct_answer")

        if (
            not isinstance(options, list)
            or not 2 <= len(options) <= 6
            or not all(
                isinstance(x, str) and x.strip()
                for x in options
            )
            or not isinstance(answer, str)
            or answer not in options
        ):

            return jsonify({
                "success": False,
                "message": "Invalid MCQ options or correct answer"
            }), 400

    question = TestQuestion(
        test_id=test.id,
        question_text=text,
        question_type=qtype,
        options=options,
        correct_answer=answer,
        marks=marks
    )

    try:

        db.session.add(question)
        db.session.flush()

        update_total_marks(test)

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Question added successfully",
            "question": question.to_dict(include_answer=True)
        }), 201

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "Question creation failed"
        )

        return jsonify({
            "success": False,
            "message": "Unable to add question"
        }), 500


# ------------------------------------------
# ADMIN: UPDATE QUESTION
# ------------------------------------------

@tests_bp.route("/questions/<int:question_id>", methods=["PUT"])
@admin_required
def update_test_question(question_id):

    question = TestQuestion.query.get_or_404(
        question_id
    )

    data = request.get_json(silent=True) or {}

    if "question_text" in data:

        text = str(data["question_text"]).strip()

        if not text:

            return jsonify({
                "success": False,
                "message": "Question cannot be empty"
            }), 400

        question.question_text = text

    if "marks" in data:

        try:

            marks = int(data["marks"])

            if not 1 <= marks <= 100:
                raise ValueError()

            question.marks = marks

        except (ValueError, TypeError):

            return jsonify({
                "success": False,
                "message": "Invalid marks"
            }), 400

    if "options" in data:

        options = data["options"]

        if (
            question.question_type != "mcq"
            or not isinstance(options, list)
            or not 2 <= len(options) <= 6
            or not all(
                isinstance(x, str) and x.strip()
                for x in options
            )
        ):

            return jsonify({
                "success": False,
                "message": "Invalid options"
            }), 400

        question.options = options

    if "correct_answer" in data:

        if (
            question.question_type != "mcq"
            or data["correct_answer"] not in (question.options or [])
        ):

            return jsonify({
                "success": False,
                "message": "Invalid correct answer"
            }), 400

        question.correct_answer = data["correct_answer"]

    try:

        update_total_marks(question.test)

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Question updated successfully"
        })

    except Exception:

        db.session.rollback()

        return jsonify({
            "success": False,
            "message": "Unable to update question"
        }), 500


# ------------------------------------------
# ADMIN: DELETE QUESTION
# ------------------------------------------

@tests_bp.route("/questions/<int:question_id>", methods=["DELETE"])
@admin_required
def delete_test_question(question_id):

    question = TestQuestion.query.get_or_404(
        question_id
    )

    test = question.test

    try:

        db.session.delete(question)
        db.session.flush()

        update_total_marks(test)

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Question deleted successfully"
        })

    except Exception:

        db.session.rollback()

        return jsonify({
            "success": False,
            "message": "Unable to delete question"
        }), 500


# ------------------------------------------
# ADMIN: PUBLISH / UNPUBLISH TEST
# ------------------------------------------

@tests_bp.route("/<int:test_id>/publish", methods=["PATCH"])
@admin_required
def toggle_test_publish(test_id):

    test = Test.query.get_or_404(test_id)

    data = request.get_json(silent=True) or {}

    published = data.get("is_published")

    if not isinstance(published, bool):

        return jsonify({
            "success": False,
            "message": "Invalid publish status"
        }), 400

    if published and not test.questions:

        return jsonify({
            "success": False,
            "message": "Add questions before publishing"
        }), 400

    update_total_marks(test)

    test.is_published = published

    try:

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Test status updated"
        })

    except Exception:

        db.session.rollback()

        return jsonify({
            "success": False,
            "message": "Unable to update test status"
        }), 500


# ------------------------------------------
# ADMIN: DELETE TEST
# ------------------------------------------

@tests_bp.route("/<int:test_id>", methods=["DELETE"])
@admin_required
def delete_test(test_id):

    test = Test.query.get_or_404(test_id)

    try:

        db.session.delete(test)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Test deleted successfully"
        })

    except Exception:

        db.session.rollback()

        return jsonify({
            "success": False,
            "message": "Unable to delete test"
        }), 500


# ==========================================
# STUDENT TEST ATTEMPTS
# ==========================================

# ------------------------------------------
# STUDENT: START TEST
# ------------------------------------------

@tests_bp.route("/<int:test_id>/start", methods=["POST"])
@student_required
def start_test(test_id):

    student_id = get_student_id()

    test = Test.query.filter_by(
        id=test_id,
        is_published=True,
        board="PSEB"
    ).first()

    if not test:

        return jsonify({
            "success": False,
            "message": "Test not available"
        }), 404

    attempt = TestAttempt.query.filter_by(
        test_id=test.id,
        student_id=student_id,
        status="in_progress"
    ).first()

    if not attempt:

        attempt = TestAttempt(
            test_id=test.id,
            student_id=student_id,
            answers={},
            total_questions=len(test.questions),
            total_marks=test.total_marks,
            status="in_progress"
        )

        db.session.add(attempt)

        try:
            db.session.commit()

        except Exception:

            db.session.rollback()

            return jsonify({
                "success": False,
                "message": "Unable to start test"
            }), 500

    elapsed = (
        datetime.utcnow() - attempt.started_at
    ).total_seconds()

    remaining = max(
        0,
        test.duration_minutes * 60 - int(elapsed)
    )

    return jsonify({
        "success": True,
        "attempt_id": attempt.id,
        "remaining_seconds": remaining,
        "test": test.to_dict(include_questions=False),
        "questions": [
            q.to_dict(include_answer=False)
            for q in test.questions
        ],
        "saved_answers": attempt.answers or {}
    })


# ------------------------------------------
# STUDENT: SAVE ANSWERS
# ------------------------------------------

@tests_bp.route(
    "/attempts/<int:attempt_id>/answers",
    methods=["PATCH"]
)
@student_required
def save_test_answers(attempt_id):

    attempt = TestAttempt.query.filter_by(
        id=attempt_id,
        student_id=get_student_id(),
        status="in_progress"
    ).first()

    if not attempt:

        return jsonify({
            "success": False,
            "message": "Active attempt not found"
        }), 404

    test = Test.query.get_or_404(
        attempt.test_id
    )

    elapsed = (
        datetime.utcnow() - attempt.started_at
    ).total_seconds()

    if elapsed >= test.duration_minutes * 60:

        return jsonify({
            "success": False,
            "message": "Test time expired. Submit your test."
        }), 400

    data = request.get_json(silent=True) or {}

    answers = data.get("answers")

    if not isinstance(answers, dict):

        return jsonify({
            "success": False,
            "message": "Invalid answers"
        }), 400

    valid_questions = {
        str(q.id): q
        for q in test.questions
    }

    current_answers = dict(
        attempt.answers or {}
    )

    for question_id, answer in answers.items():

        question = valid_questions.get(
            str(question_id)
        )

        if not question:
            continue

        # Empty answer removes previously saved answer.
        if answer is None or answer == "":

            current_answers.pop(
                str(question.id),
                None
            )

            continue

        if not isinstance(answer, str):
            continue

        answer = answer.strip()

        if not answer:
            current_answers.pop(
                str(question.id),
                None
            )
            continue

        if question.question_type == "mcq":

            if answer not in (question.options or []):
                continue

        current_answers[str(question.id)] = answer

    attempt.answers = current_answers

    try:

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Answers saved successfully"
        })

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "Answer saving failed"
        )

        return jsonify({
            "success": False,
            "message": "Unable to save answers"
        }), 500


# ------------------------------------------
# STUDENT: SUBMIT TEST
# ------------------------------------------

@tests_bp.route(
    "/attempts/<int:attempt_id>/submit",
    methods=["POST"]
)
@student_required
def submit_test(attempt_id):

    attempt = TestAttempt.query.filter_by(
        id=attempt_id,
        student_id=get_student_id(),
        status="in_progress"
    ).first()

    if not attempt:

        return jsonify({
            "success": False,
            "message": "Active attempt not found"
        }), 404

    test = Test.query.get_or_404(
        attempt.test_id
    )

    elapsed = (
        datetime.utcnow() - attempt.started_at
    ).total_seconds()

    time_expired = (
        elapsed >= test.duration_minutes * 60
    )

    answers = attempt.answers or {}

    total_questions = len(test.questions)
    attempted = 0
    correct = 0
    wrong = 0
    obtained_marks = 0
    total_marks = 0

    for question in test.questions:

        total_marks += question.marks

        answer = answers.get(
            str(question.id)
        )

        if not answer:
            continue

        attempted += 1

        # Objective questions are automatically checked.
        if question.question_type == "mcq":

            if answer == question.correct_answer:

                correct += 1
                obtained_marks += question.marks

            else:
                wrong += 1

        # Subjective answers are saved for manual evaluation.

    unattempted = (
        total_questions - attempted
    )

    percentage = (
        obtained_marks / total_marks * 100
        if total_marks else 0
    )

    attempt.total_questions = total_questions
    attempt.attempted_questions = attempted
    attempt.correct_answers = correct
    attempt.wrong_answers = wrong
    attempt.unattempted_questions = unattempted
    attempt.total_marks = total_marks
    attempt.obtained_marks = obtained_marks
    attempt.percentage = round(percentage, 2)
    attempt.status = "submitted"
    attempt.submitted_at = datetime.utcnow()

    try:

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Test submitted successfully",
            "result": {
                "attempt_id": attempt.id,
                "total_questions": total_questions,
                "attempted_questions": attempted,
                "correct_answers": correct,
                "wrong_answers": wrong,
                "unattempted_questions": unattempted,
                "total_marks": total_marks,
                "obtained_marks": obtained_marks,
                "percentage": attempt.percentage,
                "status": attempt.status,
                "time_expired": time_expired
            }
        })

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "Test submission failed"
        )

        return jsonify({
            "success": False,
            "message": "Unable to submit test"
        }), 500


# ------------------------------------------
# STUDENT: TEST HISTORY
# ------------------------------------------

@tests_bp.route("/my-attempts", methods=["GET"])
@student_required
def get_my_attempts():

    attempts = TestAttempt.query.filter_by(
        student_id=get_student_id(),
        status="submitted"
    ).order_by(
        TestAttempt.submitted_at.desc()
    ).all()

    results = []

    for attempt in attempts:

        test = db.session.get(
            Test,
            attempt.test_id
        )

        if not test:
            continue

        results.append({
            "attempt_id": attempt.id,
            "test_id": test.id,
            "test_title": test.title,
            "subject": test.subject,
            "class_name": test.class_name,

            "total_questions": attempt.total_questions,
            "attempted_questions": attempt.attempted_questions,
            "correct_answers": attempt.correct_answers,
            "wrong_answers": attempt.wrong_answers,
            "unattempted_questions": attempt.unattempted_questions,

            "total_marks": attempt.total_marks,
            "obtained_marks": attempt.obtained_marks,
            "percentage": attempt.percentage,

            "submitted_at": (
                attempt.submitted_at.isoformat()
                if attempt.submitted_at else None
            )
        })

    return jsonify({
        "success": True,
        "total_attempts": len(results),
        "attempts": results
    })
# ------------------------------------------
# STUDENT: SINGLE TEST RESULT
# ------------------------------------------

@tests_bp.route(
    "/my-attempts/<int:attempt_id>",
    methods=["GET"]
)
@student_required
def get_single_attempt(attempt_id):

    attempt = TestAttempt.query.filter_by(
        id=attempt_id,
        student_id=get_student_id(),
        status="submitted"
    ).first()

    if not attempt:

        return jsonify({
            "success": False,
            "message": "Result not found"
        }), 404

    test = Test.query.get_or_404(
        attempt.test_id
    )

    return jsonify({
        "success": True,
        "result": {
            "attempt_id": attempt.id,
            "test_title": test.title,
            "subject": test.subject,
            "class_name": test.class_name,
            "total_questions": attempt.total_questions,
            "attempted_questions": attempt.attempted_questions,
            "correct_answers": attempt.correct_answers,
            "wrong_answers": attempt.wrong_answers,
            "unattempted_questions": attempt.unattempted_questions,
            "total_marks": attempt.total_marks,
            "obtained_marks": attempt.obtained_marks,
            "percentage": attempt.percentage,
            "submitted_at": (
                attempt.submitted_at.isoformat()
                if attempt.submitted_at else None
            )
        }
    })
# ==========================================
# ONLINE BATCH MANAGEMENT
# ==========================================

# ADMIN: GET ALL BATCHES

@notes_bp.route("/unused", methods=["GET"])
def unused_route():
    return jsonify({"success": False}), 404

@batches_bp.route("/admin", methods=["GET"])
@admin_required
def get_all_batches():

    batches = Batch.query.order_by(
        Batch.created_at.desc()
    ).all()

    return jsonify({
        "success": True,
        "batches": [
            batch.to_dict() for batch in batches
        ]
    })


# ADMIN: CREATE BATCH

@batches_bp.route("", methods=["POST"])
@admin_required
def create_batch():

    data = request.get_json(silent=True) or {}

    required = [
        "title",
        "class_name",
        "subject"
    ]

    for field in required:
        if not str(data.get(field, "")).strip():
            return jsonify({
                "success": False,
                "message": f"{field} is required."
            }), 400

    class_name = normalize_class(data["class_name"])
    meeting_link = validate_meeting_link(
        data.get("meeting_link", "")
    )

    if meeting_link is None:
        return jsonify({
            "success": False,
            "message": "Please enter a valid HTTPS meeting link."
        }), 400
    if class_name not in ALLOWED_CLASSES:
        return jsonify({
            "success": False,
            "message": "Invalid class."
        }), 400

    try:
        fees = float(data.get("fees", 0))
        capacity = int(data.get("capacity", 50))

        if fees < 0 or not 1 <= capacity <= 500:
            raise ValueError()

    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Invalid fees or capacity."
        }), 400

    batch = Batch(
        title=data["title"].strip(),
        description=str(data.get("description", "")).strip(),
        board="PSEB",
        class_name=class_name,
        subject=data["subject"].strip(),
        teacher_name=str(data.get("teacher_name", "")).strip(),
        fees=fees,
        schedule=str(data.get("schedule", "")).strip(),
        meeting_link=meeting_link,
        capacity=capacity,
        is_published=False
    )

    try:
        db.session.add(batch)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Batch created successfully.",
            "batch": batch.to_dict()
        }), 201

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Batch creation failed")

        return jsonify({
            "success": False,
            "message": "Unable to create batch."
        }), 500
   # ==========================================
# PARENT: CHILD PROGRESS API
# ==========================================

@tests_bp.route(
    "/parent-progress/<int:student_id>",
    methods=["GET"]
)
@parent_required
def get_parent_child_progress(student_id):

    parent_id = session.get("parent_id")

    # Verify parent-student relationship
    link = ParentStudentLink.query.filter_by(
        parent_id=parent_id,
        student_id=student_id
    ).first()

    if not link:
        return jsonify({
            "success": False,
            "message": "You are not authorized to view this student."
        }), 403

    # Get student
    student = Student.query.filter_by(
        id=student_id,
        is_active=True
    ).first()

    if not student:
        return jsonify({
            "success": False,
            "message": "Student not found."
        }), 404

    # ======================================
    # TEST PERFORMANCE
    # ======================================

    attempts = TestAttempt.query.filter_by(
        student_id=student_id,
        status="submitted"
    ).order_by(
        TestAttempt.submitted_at.desc()
    ).all()

    subject_data = {}
    valid_attempts = []

    total_percentage = 0
    best_percentage = 0

    for attempt in attempts:

        test = db.session.get(
            Test,
            attempt.test_id
        )

        if not test:
            continue

        valid_attempts.append((attempt, test))

        subject = test.subject

        if subject not in subject_data:

            subject_data[subject] = {
                "tests": 0,
                "total_percentage": 0,
                "best_percentage": 0
            }

        percentage = float(
            attempt.percentage or 0
        )

        subject_data[subject]["tests"] += 1

        subject_data[subject]["total_percentage"] += percentage

        subject_data[subject]["best_percentage"] = max(
            subject_data[subject]["best_percentage"],
            percentage
        )

        total_percentage += percentage

        best_percentage = max(
            best_percentage,
            percentage
        )

    total_tests = len(valid_attempts)

    average = (
        round(total_percentage / total_tests, 2)
        if total_tests else None
    )

    # Prepare subjects
    subjects = []

    for name, data in subject_data.items():

        subjects.append({
            "subject": name,
            "tests_completed": data["tests"],

            "average_percentage": round(
                data["total_percentage"] / data["tests"],
                2
            ),

            "best_percentage": round(
                data["best_percentage"],
                2
            )
        })

    # ======================================
    # ATTENDANCE SUMMARY
    # ======================================

    attendance_records = Attendance.query.filter_by(
        student_id=student_id
    ).order_by(
        Attendance.attendance_date.desc()
    ).all()

    attendance_summary = {

        "total": len(attendance_records),

        "present": sum(
            1 for record in attendance_records
            if record.status == "present"
        ),

        "absent": sum(
            1 for record in attendance_records
            if record.status == "absent"
        ),

        "leave": sum(
            1 for record in attendance_records
            if record.status == "leave"
        )
    }

    # Attendance history
    attendance_history = [

        {
            "date": record.attendance_date.isoformat(),
            "status": record.status,
            "remarks": record.remarks,
            "batch_id": record.batch_id
        }

        for record in attendance_records
    ]

    # ======================================
    # RECENT TESTS
    # ======================================

    recent_tests = []

    for attempt, test in valid_attempts[:10]:

        recent_tests.append({

            "test_title": test.title,

            "subject": test.subject,

            "obtained_marks": attempt.obtained_marks,

            "total_marks": attempt.total_marks,

            "percentage": attempt.percentage,

            "submitted_at": (
                attempt.submitted_at.isoformat()
                if attempt.submitted_at else None
            )
        })

    # ======================================
    # FINAL RESPONSE
    # ======================================

    return jsonify({

        "success": True,

        "student": {

            "id": student.id,
            "name": student.name,
            "class_name": student.class_name,
            "board": student.board,
            "profile_photo": student.profile_photo
        },

        "summary": {

            "tests_completed": total_tests,

            "active_subjects": len(subjects),

            "average_percentage": average,

            "best_percentage": (
                round(best_percentage, 2)
                if total_tests else None
            )
        },

        "subjects": subjects,

        "attendance_summary": attendance_summary,

        "attendance_history": attendance_history,

        "recent_tests": recent_tests

    })
# ==========================================
# ATTENDANCE MANAGEMENT SYSTEM
# ==========================================

# ADMIN: GET BATCH STUDENTS FOR ATTENDANCE

@batches_bp.route("/<int:batch_id>/attendance/students", methods=["GET"])
@admin_required
def get_batch_attendance_students(batch_id):

    batch = Batch.query.get_or_404(batch_id)

    enrollments = BatchEnrollment.query.filter_by(
        batch_id=batch_id
    ).all()

    students = []

    attendance_date = request.args.get("date")

    try:
        selected_date = (
            date.fromisoformat(attendance_date)
            if attendance_date
            else date.today()
        )
    except ValueError:
        return jsonify({
            "success": False,
            "message": "Invalid date format. Use YYYY-MM-DD."
        }), 400

    for enrollment in enrollments:

        student = db.session.get(
            Student,
            enrollment.student_id
        )

        if not student:
            continue

        record = Attendance.query.filter_by(
            student_id=student.id,
            batch_id=batch_id,
            attendance_date=selected_date
        ).first()

        students.append({
            "student_id": student.id,
            "name": student.name,
            "enrollment_status": enrollment.status,
            "attendance_status": record.status if record else None
        })

    return jsonify({
        "success": True,
        "batch": batch.to_dict(),
        "date": selected_date.isoformat(),
        "students": students
    })


# ADMIN: MARK / UPDATE ATTENDANCE

@batches_bp.route("/<int:batch_id>/attendance", methods=["POST"])
@admin_required
def mark_batch_attendance(batch_id):

    batch = Batch.query.get_or_404(batch_id)

    data = request.get_json(silent=True) or {}

    records = data.get("records")

    if not isinstance(records, list) or not records:
        return jsonify({
            "success": False,
            "message": "Attendance records are required."
        }), 400

    try:
        selected_date = date.fromisoformat(
            data.get("date", date.today().isoformat())
        )
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Invalid attendance date."
        }), 400

    allowed_statuses = ["present", "absent", "leave"]

    try:

        for item in records:

            if not isinstance(item, dict):
                raise ValueError("Invalid attendance record.")

            student_id = item.get("student_id")
            status = str(item.get("status", "")).lower().strip()

            if not isinstance(student_id, int):
                raise ValueError("Invalid student ID.")

            if status not in allowed_statuses:
                raise ValueError("Invalid attendance status.")

            enrollment = BatchEnrollment.query.filter_by(
                batch_id=batch_id,
                student_id=student_id
            ).first()

            if not enrollment:
                raise ValueError(
                    f"Student {student_id} is not enrolled in this batch."
                )

            student = db.session.get(Student, student_id)

            if not student or not student.is_active:
                raise ValueError(
                    f"Student {student_id} is not active."
                )

            attendance = Attendance.query.filter_by(
                student_id=student_id,
                batch_id=batch_id,
                attendance_date=selected_date
            ).first()

            if not attendance:

                attendance = Attendance(
                    student_id=student_id,
                    batch_id=batch_id,
                    attendance_date=selected_date
                )

                db.session.add(attendance)

            attendance.status = status
            attendance.remarks = str(
                item.get("remarks", "")
            ).strip()[:255]

            attendance.marked_by = "admin"

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Attendance saved successfully."
        })

    except ValueError as error:

        db.session.rollback()

        return jsonify({
            "success": False,
            "message": str(error)
        }), 400

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "Attendance marking failed"
        )

        return jsonify({
            "success": False,
            "message": "Unable to save attendance."
        }), 500


# ADMIN: GET BATCH ATTENDANCE HISTORY

@batches_bp.route("/<int:batch_id>/attendance", methods=["GET"])
@admin_required
def get_batch_attendance(batch_id):

    Batch.query.get_or_404(batch_id)

    selected_date = request.args.get("date")

    query = Attendance.query.filter_by(
        batch_id=batch_id
    )

    if selected_date:

        try:
            parsed_date = date.fromisoformat(selected_date)
        except ValueError:
            return jsonify({
                "success": False,
                "message": "Invalid date format."
            }), 400

        query = query.filter_by(
            attendance_date=parsed_date
        )

    records = query.order_by(
        Attendance.attendance_date.desc()
    ).all()

    return jsonify({
        "success": True,
        "total_records": len(records),
        "attendance": [
            record.to_dict()
            for record in records
        ]
    })
# ==========================================
# STUDENT: ONLINE BATCH SYSTEM
# ==========================================

# STUDENT: GET AVAILABLE BATCHES

@batches_bp.route("/student", methods=["GET"])
@student_required
def get_student_batches():

    student = db.session.get(Student, get_student_id())

    if not student or not student.is_active:
        return jsonify({
            "success": False,
            "message": "Student not found."
        }), 404

    batches = Batch.query.filter_by(
        is_published=True,
        board=student.board,
        class_name=normalize_class(student.class_name)
    ).order_by(
        Batch.created_at.desc()
    ).all()

    results = []

    for batch in batches:

        enrollment = BatchEnrollment.query.filter_by(
            batch_id=batch.id,
            student_id=student.id
        ).first()

        batch_data = batch.to_dict()

        batch_data["enrollment_status"] = (
            enrollment.status if enrollment else None
        )

        results.append(batch_data)

    return jsonify({
        "success": True,
        "total_batches": len(results),
        "batches": results
    })


# STUDENT: REQUEST TO JOIN BATCH

@batches_bp.route("/<int:batch_id>/join", methods=["POST"])
@student_required
def join_student_batch(batch_id):

    student = db.session.get(Student, get_student_id())

    if not student or not student.is_active:
        return jsonify({
            "success": False,
            "message": "Student not found."
        }), 404

    batch = Batch.query.filter_by(
        id=batch_id,
        is_published=True
    ).first()

    if not batch:
        return jsonify({
            "success": False,
            "message": "Batch is not available."
        }), 404

    if (
        batch.board != student.board
        or normalize_class(batch.class_name)
        != normalize_class(student.class_name)
    ):
        return jsonify({
            "success": False,
            "message": "This batch is not available for your class."
        }), 403

    existing = BatchEnrollment.query.filter_by(
        batch_id=batch.id,
        student_id=student.id
    ).first()

    if existing:

        return jsonify({
            "success": True,
            "message": (
                "Your request is already pending."
                if existing.status == "pending"
                else f"Your enrollment status is {existing.status}."
            ),
            "status": existing.status
        })

    enrollment_count = BatchEnrollment.query.filter_by(
        batch_id=batch.id
    ).count()

    if enrollment_count >= batch.capacity:

        return jsonify({
            "success": False,
            "message": "This batch is currently full."
        }), 400

    enrollment = BatchEnrollment(
        batch_id=batch.id,
        student_id=student.id,
        status="pending"
    )

    try:

        db.session.add(enrollment)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Batch join request sent successfully!",
            "status": "pending"
        }), 201

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "Student batch enrollment failed"
        )

        return jsonify({
            "success": False,
            "message": "Unable to send join request."
        }), 500
    # ==========================================
# ADMIN: UPDATE BATCH
# ==========================================

@batches_bp.route("/<int:batch_id>", methods=["PUT"])
@admin_required
def update_batch(batch_id):

    batch = db.session.get(Batch, batch_id)

    if not batch:
        return jsonify({
            "success": False,
            "message": "Batch not found."
        }), 404

    data = request.get_json(silent=True) or {}
    meeting_link = validate_meeting_link(
        data.get("meeting_link", batch.meeting_link or "")
    )

    if meeting_link is None:
        return jsonify({
            "success": False,
            "message": "Please enter a valid HTTPS meeting link."
        }), 400
    title = str(data.get("title", "")).strip()
    class_name = normalize_class(data.get("class_name", ""))
    subject = str(data.get("subject", "")).strip()

    if not title or not subject:
        return jsonify({
            "success": False,
            "message": "Title and subject are required."
        }), 400

    if class_name not in [
        "5th", "6th", "7th", "8th", "9th", "10th"
    ]:
        return jsonify({
            "success": False,
            "message": "Invalid class."
        }), 400

    try:
        fees = float(data.get("fees", batch.fees))
        capacity = int(data.get("capacity", batch.capacity))
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Invalid fee or capacity."
        }), 400

    if fees < 0 or capacity < 1 or capacity > 500:
        return jsonify({
            "success": False,
            "message": "Invalid fee or capacity."
        }), 400

    batch.title = title
    batch.board = "PSEB"
    batch.class_name = class_name
    batch.subject = subject
    batch.fees = fees
    batch.capacity = capacity
    batch.schedule = str(data.get("schedule", "")).strip()
    batch.meeting_link = meeting_link
    batch.teacher_name = str(data.get("teacher_name", "")).strip()
    batch.description = str(data.get("description", "")).strip()

    try:
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Batch updated successfully!"
        })

    except Exception:
        db.session.rollback()

        return jsonify({
            "success": False,
            "message": "Unable to update batch."
        }), 500


# ==========================================
# ADMIN: PUBLISH / UNPUBLISH BATCH
# ==========================================

@batches_bp.route("/<int:batch_id>/publish", methods=["PATCH"])
@admin_required
def publish_batch(batch_id):

    batch = db.session.get(Batch, batch_id)

    if not batch:
        return jsonify({
            "success": False,
            "message": "Batch not found."
        }), 404

    data = request.get_json(silent=True) or {}

    if not isinstance(data.get("is_published"), bool):
        return jsonify({
            "success": False,
            "message": "Invalid publish status."
        }), 400

    batch.is_published = data["is_published"]

    try:
        db.session.commit()

        return jsonify({
            "success": True,
            "message": (
                "Batch published successfully!"
                if batch.is_published
                else "Batch unpublished successfully!"
            )
        })

    except Exception:
        db.session.rollback()

        return jsonify({
            "success": False,
            "message": "Unable to update batch status."
        }), 500


# ==========================================
# ADMIN: DELETE BATCH
# ==========================================

@batches_bp.route("/<int:batch_id>", methods=["DELETE"])
@admin_required
def delete_batch(batch_id):

    batch = db.session.get(Batch, batch_id)

    if not batch:
        return jsonify({
            "success": False,
            "message": "Batch not found."
        }), 404

    # Do not delete batches with existing records.
    enrollment = BatchEnrollment.query.filter_by(
        batch_id=batch.id
    ).first()

    attendance = Attendance.query.filter_by(
        batch_id=batch.id
    ).first()

    if enrollment or attendance:
        return jsonify({
            "success": False,
            "message": (
                "This batch has enrollment or attendance records. "
                "Unpublish it instead of deleting."
            )
        }), 400

    try:
        db.session.delete(batch)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Batch deleted successfully!"
        })

    except Exception:
        db.session.rollback()

        return jsonify({
            "success": False,
            "message": "Unable to delete batch."
        }), 500
    # ==========================================
# ADMIN: BATCH ENROLLMENT MANAGEMENT
# ==========================================

@batches_bp.route("/admin/enrollments", methods=["GET"])
@admin_required
def get_batch_enrollments():

    enrollments = BatchEnrollment.query.order_by(
        BatchEnrollment.created_at.desc()
    ).all()

    results = []

    for enrollment in enrollments:

        student = db.session.get(Student, enrollment.student_id)
        batch = db.session.get(Batch, enrollment.batch_id)

        if not student or not batch:
            continue

        results.append({
            "id": enrollment.id,
            "student_id": student.id,
            "student_name": student.name,
            "student_email": student.email,
            "student_class": student.class_name,
            "batch_id": batch.id,
            "batch_title": batch.title,
            "subject": batch.subject,
            "status": enrollment.status,
            "created_at": (
                enrollment.created_at.isoformat()
                if enrollment.created_at else None
            )
        })

    return jsonify({
        "success": True,
        "total": len(results),
        "enrollments": results
    })


# ==========================================
# ADMIN: APPROVE / REJECT REQUEST
# ==========================================

@batches_bp.route(
    "/admin/enrollments/<int:enrollment_id>/status",
    methods=["PATCH"]
)
@admin_required
def update_enrollment_status(enrollment_id):

    enrollment = db.session.get(
        BatchEnrollment, enrollment_id
    )

    if not enrollment:
        return jsonify({
            "success": False,
            "message": "Enrollment request not found."
        }), 404

    data = request.get_json(silent=True) or {}
    status = str(data.get("status", "")).strip().lower()

    if status not in ["approved", "rejected"]:
        return jsonify({
            "success": False,
            "message": "Invalid enrollment status."
        }), 400

    if status == "approved":

        batch = db.session.get(Batch, enrollment.batch_id)
        student = db.session.get(Student, enrollment.student_id)

        if not batch or not student or not student.is_active:
            return jsonify({
                "success": False,
                "message": "Batch or active student not found."
            }), 404

        if not batch.is_published:
            return jsonify({
                "success": False,
                "message": "Cannot approve an unpublished batch."
            }), 400

        approved_count = BatchEnrollment.query.filter_by(
            batch_id=batch.id,
            status="approved"
        ).filter(
            BatchEnrollment.id != enrollment.id
        ).count()

        if approved_count >= batch.capacity:
            return jsonify({
                "success": False,
                "message": "Batch capacity is full."
            }), 400

    try:
        enrollment.status = status
        db.session.commit()

        return jsonify({
            "success": True,
            "message": (
                "Student enrollment approved successfully!"
                if status == "approved"
                else "Student enrollment rejected."
            ),
            "status": status
        })

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Enrollment status update failed"
        )

        return jsonify({
            "success": False,
            "message": "Unable to update enrollment."
        }), 500
    # ==========================================
# STUDENT: MY APPROVED BATCHES
# ==========================================

@batches_bp.route("/student/my-batches", methods=["GET"])
@student_required
def get_my_batches():

    student = db.session.get(Student, get_student_id())

    if not student or not student.is_active:
        return jsonify({
            "success": False,
            "message": "Student not found."
        }), 404

    enrollments = BatchEnrollment.query.filter_by(
        student_id=student.id,
        status="approved"
    ).order_by(
        BatchEnrollment.created_at.desc()
    ).all()

    results = []

    for enrollment in enrollments:

        batch = db.session.get(Batch, enrollment.batch_id)

        if not batch:
            continue

        results.append({
            "enrollment_id": enrollment.id,
            "batch_id": batch.id,
            "title": batch.title,
            "description": batch.description,
            "board": batch.board,
            "class_name": batch.class_name,
            "subject": batch.subject,
            "teacher_name": batch.teacher_name,
            "fees": batch.fees,
            "schedule": batch.schedule,
            "meeting_link": batch.meeting_link,
            "start_date": (
                batch.start_date.isoformat()
                if batch.start_date else None
            ),
            "end_date": (
                batch.end_date.isoformat()
                if batch.end_date else None
            ),
            "enrollment_status": enrollment.status
        })

    return jsonify({
        "success": True,
        "total_batches": len(results),
        "batches": results
    })