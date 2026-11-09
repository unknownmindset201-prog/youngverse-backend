import os
import hmac
import secrets
from functools import wraps

from PIL import Image, UnidentifiedImageError
from flask import Blueprint, request, jsonify, session, current_app
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError

from .database import db
from .models import Student, Parent, ParentStudentLink


auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


# =====================================
# ALLOWED STUDENT CLASSES
# =====================================

ALLOWED_CLASSES = ["5th", "6th", "7th", "8th", "9th", "10th"]


# =====================================
# ADMIN PROTECTION
# =====================================

def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            return jsonify({
                "success": False,
                "message": "Admin login required"
            }), 403
        return func(*args, **kwargs)
    return wrapper


# =====================================
# STUDENT PROTECTION
# =====================================

def student_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if session.get("role") != "student":
            return jsonify({
                "success": False,
                "message": "Student login required"
            }), 403

        student = Student.query.get(session.get("student_id"))
        if not student or not student.is_active:
            session.clear()
            return jsonify({
                "success": False,
                "message": "Student account is inactive"
            }), 403

        return func(*args, **kwargs)
    return wrapper


# =====================================
# PARENT PROTECTION
# =====================================

def parent_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if session.get("role") != "parent":
            return jsonify({
                "success": False,
                "message": "Parent login required."
            }), 403

        parent = Parent.query.get(session.get("parent_id"))
        if not parent or not parent.is_active:
            session.clear()
            return jsonify({
                "success": False,
                "message": "Parent account is inactive."
            }), 403

        return func(*args, **kwargs)
    return wrapper


# =====================================
# ADMIN LOGIN
# =====================================

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")

    admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "")

    if not admin_email or not admin_password:
        return jsonify({
            "success": False,
            "message": "Admin credentials are not configured"
        }), 500

    email_valid = hmac.compare_digest(email, admin_email)
    password_valid = (
        isinstance(password, str)
        and hmac.compare_digest(password, admin_password)
    )

    if not email_valid or not password_valid:
        return jsonify({
            "success": False,
            "message": "Invalid email or password"
        }), 401

    session.clear()
    session["role"] = "admin"
    session.permanent = True

    return jsonify({
        "success": True,
        "message": "Admin login successful",
        "role": "admin",
        "redirect": "/admin/dashboard.html"
    })


# =====================================
# STUDENT REGISTRATION
# =====================================

@auth_bp.route("/student/register", methods=["POST"])
def student_register():
    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")
    board = str(data.get("board", "PSEB")).strip().upper()
    class_name = str(data.get("class_name", "")).strip().lower()

    if not name or not email or not password or not class_name:
        return jsonify({
            "success": False,
            "message": "All fields are required"
        }), 400

    if len(name) > 120:
        return jsonify({
            "success": False,
            "message": "Name is too long"
        }), 400

    if len(email) > 150 or "@" not in email:
        return jsonify({
            "success": False,
            "message": "Enter a valid email address"
        }), 400

    if not isinstance(password, str) or len(password) < 8:
        return jsonify({
            "success": False,
            "message": "Password must be at least 8 characters"
        }), 400

    if board != "PSEB":
        return jsonify({
            "success": False,
            "message": "Only PSEB board is supported"
        }), 400

    if class_name not in ALLOWED_CLASSES:
        return jsonify({
            "success": False,
            "message": "Only Classes 5th to 10th are allowed"
        }), 400

    if Student.query.filter_by(email=email).first():
        return jsonify({
            "success": False,
            "message": "This email is already registered"
        }), 409

    student = Student(
        name=name,
        email=email,
        password_hash=generate_password_hash(password),
        board="PSEB",
        class_name=class_name
    )

    try:
        db.session.add(student)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": "This email is already registered"
        }), 409
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Student registration failed")
        return jsonify({
            "success": False,
            "message": "Registration failed"
        }), 500

    return jsonify({
        "success": True,
        "message": "Registration successful",
        "student": student.to_dict(),
        "redirect": "/student-login.html"
    }), 201


# =====================================
# STUDENT LOGIN
# =====================================

@auth_bp.route("/student/login", methods=["POST"])
def student_login():
    data = request.get_json(silent=True) or {}

    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({
            "success": False,
            "message": "Email and password are required"
        }), 400

    student = Student.query.filter_by(email=email).first()

    if not student or not check_password_hash(student.password_hash, password):
        return jsonify({
            "success": False,
            "message": "Invalid email or password"
        }), 401

    if not student.is_active:
        return jsonify({
            "success": False,
            "message": "Your account is inactive"
        }), 403

    session.clear()
    session["role"] = "student"
    session["student_id"] = student.id
    session.permanent = True

    return jsonify({
        "success": True,
        "message": "Student login successful",
        "role": "student",
        "student": student.to_dict(),
        "redirect": "/students/dashboard.html"
    })


# =====================================
# STUDENT PROFILE
# =====================================

@auth_bp.route("/student/me", methods=["GET"])
@student_required
def student_profile():
    student = Student.query.get(session["student_id"])

    return jsonify({
        "success": True,
        "authenticated": True,
        "role": "student",
        "student": student.to_dict()
    })


# =====================================
# STUDENT PROFILE PHOTO UPLOAD
# =====================================

@auth_bp.route("/student/profile-photo", methods=["POST"])
@student_required
def upload_profile_photo():
    student = Student.query.get(session["student_id"])

    if not student:
        return jsonify({
            "success": False,
            "message": "Student not found."
        }), 404

    if "photo" not in request.files:
        return jsonify({
            "success": False,
            "message": "Please select a photo."
        }), 400

    photo = request.files["photo"]

    if not photo.filename or "." not in photo.filename:
        return jsonify({
            "success": False,
            "message": "Invalid file."
        }), 400

    extension = photo.filename.rsplit(".", 1)[-1].lower()
    expected_formats = {
        "jpg": "JPEG",
        "jpeg": "JPEG",
        "png": "PNG",
        "webp": "WEBP"
    }

    if extension not in expected_formats:
        return jsonify({
            "success": False,
            "message": "Only JPG, PNG and WEBP allowed."
        }), 400

    photo_data = photo.stream.read(5 * 1024 * 1024 + 1)
    if len(photo_data) > 5 * 1024 * 1024:
        return jsonify({
            "success": False,
            "message": "Photo must be smaller than 5 MB."
        }), 413

    photo.stream.seek(0)

    try:
        with Image.open(photo.stream) as image:
            actual_format = image.format
            image.verify()

        if actual_format != expected_formats[extension]:
            return jsonify({
                "success": False,
                "message": "Image format does not match file extension."
            }), 400

    except (UnidentifiedImageError, OSError, ValueError):
        return jsonify({
            "success": False,
            "message": "Invalid image file."
        }), 400

    photo.stream.seek(0)

    upload_folder = os.path.join(
        current_app.static_folder,
        "uploads",
        "profile_photos"
    )
    os.makedirs(upload_folder, exist_ok=True)

    filename = secure_filename(f"student_{student.id}.{extension}")
    photo_path = os.path.join(upload_folder, filename)
    photo.save(photo_path)

    student.profile_photo = f"/static/uploads/profile_photos/{filename}"

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Profile photo update failed")
        return jsonify({
            "success": False,
            "message": "Could not save profile photo."
        }), 500

    return jsonify({
        "success": True,
        "message": "Profile photo uploaded successfully.",
        "profile_photo": student.profile_photo
    }), 200


# =====================================
# STUDENT LOGOUT
# =====================================

@auth_bp.route("/student/logout", methods=["POST"])
def student_logout():
    if session.get("role") == "student":
        session.clear()

    return jsonify({
        "success": True,
        "message": "Student logout successful"
    })


# =====================================
# ADMIN LOGOUT
# =====================================

@auth_bp.route("/logout", methods=["POST"])
def logout():
    if session.get("role") == "admin":
        session.clear()

    return jsonify({
        "success": True,
        "message": "Logout successful"
    })


# =====================================
# CURRENT USER
# =====================================

@auth_bp.route("/me", methods=["GET"])
def current_user():
    role = session.get("role")

    if role == "student":
        student = Student.query.get(session.get("student_id"))
        if student and student.is_active:
            return jsonify({
                "authenticated": True,
                "role": "student",
                "student": student.to_dict()
            })

        session.clear()
        return jsonify({
            "authenticated": False,
            "role": None
        }), 401

    if role == "parent":
        parent = Parent.query.get(session.get("parent_id"))
        if parent and parent.is_active:
            return jsonify({
                "authenticated": True,
                "role": "parent",
                "parent": parent.to_dict()
            })

        session.clear()
        return jsonify({
            "authenticated": False,
            "role": None
        }), 401

    return jsonify({
        "authenticated": role == "admin",
        "role": role
    })


# =====================================
# PARENT REGISTRATION
# =====================================

@auth_bp.route("/parent/register", methods=["POST"])
def parent_register():
    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")
    phone = str(data.get("phone", "")).strip()

    if not name or not email or not password:
        return jsonify({
            "success": False,
            "message": "Name, email and password are required."
        }), 400

    if len(name) > 120 or len(email) > 150:
        return jsonify({
            "success": False,
            "message": "Name or email is too long."
        }), 400

    if "@" not in email or not isinstance(password, str) or len(password) < 8:
        return jsonify({
            "success": False,
            "message": "Enter a valid email and password of at least 8 characters."
        }), 400

    if phone and len(phone) > 20:
        return jsonify({
            "success": False,
            "message": "Phone number is too long."
        }), 400

    if Parent.query.filter_by(email=email).first():
        return jsonify({
            "success": False,
            "message": "This email is already registered."
        }), 409

    parent = Parent(
        name=name,
        email=email,
        password_hash=generate_password_hash(password),
        phone=phone or None
    )

    try:
        db.session.add(parent)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Parent registration successful.",
            "parent": parent.to_dict()
        }), 201

    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": "This email is already registered."
        }), 409

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Parent registration failed")
        return jsonify({
            "success": False,
            "message": "Registration failed."
        }), 500


# =====================================
# PARENT LOGIN
# =====================================

@auth_bp.route("/parent/login", methods=["POST"])
def parent_login():
    data = request.get_json(silent=True) or {}

    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({
            "success": False,
            "message": "Email and password are required."
        }), 400

    parent = Parent.query.filter_by(email=email).first()

    if not parent or not check_password_hash(parent.password_hash, password):
        return jsonify({
            "success": False,
            "message": "Invalid email or password."
        }), 401

    if not parent.is_active:
        return jsonify({
            "success": False,
            "message": "Parent account is inactive."
        }), 403

    session.clear()
    session["role"] = "parent"
    session["parent_id"] = parent.id
    session.permanent = True

    return jsonify({
        "success": True,
        "message": "Parent login successful.",
        "role": "parent",
        "parent": parent.to_dict(),
        "redirect": "/parent/dashboard.html"
    })


# =====================================
# PARENT PROFILE
# =====================================

@auth_bp.route("/parent/me", methods=["GET"])
@parent_required
def parent_profile():
    parent = Parent.query.get(session["parent_id"])

    return jsonify({
        "success": True,
        "authenticated": True,
        "role": "parent",
        "parent": parent.to_dict()
    })


# =====================================
# STUDENT PARENT LINK CODE
# =====================================

@auth_bp.route("/student/parent-link-code", methods=["GET"])
@student_required
def get_parent_link_code():
    student = Student.query.get(session.get("student_id"))

    if not student or not student.is_active:
        return jsonify({
            "success": False,
            "message": "Student account not found."
        }), 404

    if not student.parent_link_code:
        student.parent_link_code = secrets.token_hex(16)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Parent link code generation failed")
            return jsonify({
                "success": False,
                "message": "Could not generate linking code."
            }), 500

    return jsonify({
        "success": True,
        "link_code": student.parent_link_code,
        "message": "Parent linking code retrieved successfully."
    }), 200


# =====================================
# PARENT - LINK STUDENT
# =====================================

@auth_bp.route("/parent/link-student", methods=["POST"])
@parent_required
def link_student():
    data = request.get_json(silent=True) or {}

    student_id = data.get("student_id")
    link_code = str(data.get("link_code", "")).strip()

    if not student_id or not link_code:
        return jsonify({
            "success": False,
            "message": "Student ID and linking code are required."
        }), 400

    student = Student.query.filter_by(
        id=student_id,
        is_active=True
    ).first()

    if not student or not student.parent_link_code:
        return jsonify({
            "success": False,
            "message": "Invalid student ID or linking code."
        }), 404

    if not hmac.compare_digest(student.parent_link_code, link_code):
        return jsonify({
            "success": False,
            "message": "Invalid student ID or linking code."
        }), 404

    existing_link = ParentStudentLink.query.filter_by(
        parent_id=session["parent_id"],
        student_id=student.id
    ).first()

    if existing_link:
        return jsonify({
            "success": False,
            "message": "This student is already linked."
        }), 409

    new_link = ParentStudentLink(
        parent_id=session["parent_id"],
        student_id=student.id
    )

    try:
        db.session.add(new_link)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Student linked successfully!"
        }), 201

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Parent-student linking failed")
        return jsonify({
            "success": False,
            "message": "Could not link student."
        }), 500


# =====================================
# PARENT - CHILDREN LIST
# =====================================

@auth_bp.route("/parent/children", methods=["GET"])
@parent_required
def get_parent_children():
    links = ParentStudentLink.query.filter_by(
        parent_id=session["parent_id"]
    ).all()

    children = []

    for link in links:
        student = link.student

        if student and student.is_active:
            children.append({
                "id": student.id,
                "name": student.name,
                "class_name": student.class_name,
                "board": student.board,
                "profile_photo": student.profile_photo
            })

    return jsonify({
        "success": True,
        "children": children,
        "total_children": len(children)
    }), 200


# =====================================
# PARENT LOGOUT
# =====================================

@auth_bp.route("/parent/logout", methods=["POST"])
@parent_required
def parent_logout():
    session.clear()

    return jsonify({
        "success": True,
        "message": "Parent logged out successfully."
    }), 200
