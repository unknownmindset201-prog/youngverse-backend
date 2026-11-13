
from datetime import datetime

from flask import Blueprint, request, jsonify, session

from .database import db
from .models import (
    Notification,
    NotificationRecipient,
    Student,
    Parent,
    Batch,
    BatchEnrollment
)

from .auth import (
    admin_required,
    student_required,
    parent_required
)


notifications_bp = Blueprint(
    "notifications",
    __name__,
    url_prefix="/api/notifications"
)


# ==========================================
# HELPERS
# ==========================================

ALLOWED_CATEGORIES = [
    "announcement",
    "study_material",
    "test",
    "payment_reminder",
    "batch",
    "result",
    "important_notice"
]


def get_current_recipient():

    role = session.get("role")

    if role == "student":
        return "student", session.get("student_id")

    if role == "parent":
        return "parent", session.get("parent_id")

    return None, None


def notification_to_dict(recipient):

    notification = recipient.notification

    return {
        "id": recipient.id,
        "notification_id": notification.id,
        "title": notification.title,
        "message": notification.message,
        "category": notification.category,
        "is_read": recipient.is_read,
        "created_at": (
            notification.created_at.isoformat()
            if notification.created_at else None
        ),
        "read_at": (
            recipient.read_at.isoformat()
            if recipient.read_at else None
        )
    }


# ==========================================
# ADMIN: SEND NOTIFICATION
# ==========================================

@notifications_bp.route("/admin", methods=["POST"])
@admin_required
def send_notification():

    data = request.get_json(silent=True) or {}

    title = str(data.get("title", "")).strip()
    message = str(data.get("message", "")).strip()

    category = data.get("category", "announcement")
    target_type = data.get("target_type", "all")

    if not title or not message:
        return jsonify({
            "success": False,
            "message": "Title and message are required."
        }), 400

    if len(title) > 200 or len(message) > 10000:
        return jsonify({
            "success": False,
            "message": "Title or message is too long."
        }), 400

    if category not in ALLOWED_CATEGORIES:
        return jsonify({
            "success": False,
            "message": "Invalid notification category."
        }), 400

    allowed_targets = [
        "all",
        "students",
        "parents",
        "student",
        "parent",
        "class",
        "batch"
    ]

    if target_type not in allowed_targets:
        return jsonify({
            "success": False,
            "message": "Invalid target type."
        }), 400

    recipients = []

    # ALL STUDENTS + PARENTS
    if target_type == "all":

        students = Student.query.filter_by(
            is_active=True
        ).all()

        parents = Parent.query.filter_by(
            is_active=True
        ).all()

        recipients.extend(
            [("student", s.id) for s in students]
        )

        recipients.extend(
            [("parent", p.id) for p in parents]
        )

    # ALL STUDENTS
    elif target_type == "students":

        students = Student.query.filter_by(
            is_active=True
        ).all()

        recipients.extend(
            [("student", s.id) for s in students]
        )

    # ALL PARENTS
    elif target_type == "parents":

        parents = Parent.query.filter_by(
            is_active=True
        ).all()

        recipients.extend(
            [("parent", p.id) for p in parents]
        )

    # SPECIFIC STUDENT
    elif target_type == "student":

        try:
            student_id = int(data.get("recipient_id"))
        except (TypeError, ValueError):
            return jsonify({
                "success": False,
                "message": "Valid student ID required."
            }), 400

        student = Student.query.filter_by(
            id=student_id,
            is_active=True
        ).first()

        if student:
            recipients.append(("student", student.id))

    # SPECIFIC PARENT
    elif target_type == "parent":

        try:
            parent_id = int(data.get("recipient_id"))
        except (TypeError, ValueError):
            return jsonify({
                "success": False,
                "message": "Valid parent ID required."
            }), 400

        parent = Parent.query.filter_by(
            id=parent_id,
            is_active=True
        ).first()

        if parent:
            recipients.append(("parent", parent.id))

    # SPECIFIC CLASS
    elif target_type == "class":

        class_name = str(
            data.get("class_name", "")
        ).strip().lower()

        if not class_name:
            return jsonify({
                "success": False,
                "message": "Class name is required."
            }), 400

        students = Student.query.filter(
            Student.is_active.is_(True),
            db.func.lower(Student.class_name) == class_name
        ).all()

        recipients.extend(
            [("student", s.id) for s in students]
        )

    # SPECIFIC BATCH
    elif target_type == "batch":

        try:
            batch_id = int(data.get("batch_id"))
        except (TypeError, ValueError):
            return jsonify({
                "success": False,
                "message": "Valid batch ID required."
            }), 400

        batch = db.session.get(Batch, batch_id)

        if not batch:
            return jsonify({
                "success": False,
                "message": "Batch not found."
            }), 404

        enrollments = BatchEnrollment.query.filter_by(
            batch_id=batch_id
        ).all()

        for enrollment in enrollments:

            student = db.session.get(
                Student,
                enrollment.student_id
            )

            if student and student.is_active:
                recipients.append(("student", student.id))

    # Remove duplicate recipients
    recipients = list(set(recipients))

    if not recipients:
        return jsonify({
            "success": False,
            "message": "No active recipients found."
        }), 404

    try:

        notification = Notification(
            title=title,
            message=message,
            category=category,
            target_type=target_type,
            created_by="admin"
        )

        db.session.add(notification)
        db.session.flush()

        for role, recipient_id in recipients:

            recipient = NotificationRecipient(
                notification_id=notification.id,
                recipient_role=role,
                recipient_id=recipient_id
            )

            db.session.add(recipient)

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Notification sent successfully.",
            "notification_id": notification.id,
            "recipient_count": len(recipients)
        }), 201

    except Exception:

        db.session.rollback()

        return jsonify({
            "success": False,
            "message": "Unable to send notification."
        }), 500


# ==========================================
# ADMIN: NOTIFICATION HISTORY
# ==========================================

@notifications_bp.route("/admin", methods=["GET"])
@admin_required
def get_admin_notifications():

    notifications = Notification.query.order_by(
        Notification.created_at.desc()
    ).limit(100).all()

    result = []

    for notification in notifications:

        result.append({
            "id": notification.id,
            "title": notification.title,
            "message": notification.message,
            "category": notification.category,
            "target_type": notification.target_type,
            "recipient_count": len(notification.recipients),
            "created_at": (
                notification.created_at.isoformat()
                if notification.created_at else None
            )
        })

    return jsonify({
        "success": True,
        "notifications": result
    })


# ==========================================
# STUDENT + PARENT: GET NOTIFICATIONS
# ==========================================

@notifications_bp.route("", methods=["GET"])
def get_notifications():

    role, recipient_id = get_current_recipient()

    if not role or not recipient_id:
        return jsonify({
            "success": False,
            "message": "Login required."
        }), 403

    if role == "student":
        user = Student.query.filter_by(
            id=recipient_id,
            is_active=True
        ).first()

    elif role == "parent":
        user = Parent.query.filter_by(
            id=recipient_id,
            is_active=True
        ).first()

    else:
        user = None

    if not user:
        session.clear()

        return jsonify({
            "success": False,
            "message": "Account inactive or not found."
        }), 403

    notifications = NotificationRecipient.query.filter_by(
        recipient_role=role,
        recipient_id=recipient_id,
        is_deleted=False
    ).order_by(
        NotificationRecipient.created_at.desc()
    ).limit(100).all()

    return jsonify({
        "success": True,
        "notifications": [
            notification_to_dict(n)
            for n in notifications
        ]
    })
# ==========================================
# UNREAD COUNT
# ==========================================

@notifications_bp.route("/unread-count", methods=["GET"])
def unread_count():

    role, recipient_id = get_current_recipient()

    if not role or not recipient_id:
        return jsonify({
            "success": False,
            "message": "Login required."
        }), 403

    if role == "student":

        if not Student.query.filter_by(
            id=recipient_id,
            is_active=True
        ).first():
            return jsonify({"success": False}), 403

    elif role == "parent":

        if not Parent.query.filter_by(
            id=recipient_id,
            is_active=True
        ).first():
            return jsonify({"success": False}), 403

    count = NotificationRecipient.query.filter_by(
        recipient_role=role,
        recipient_id=recipient_id,
        is_read=False,
        is_deleted=False
    ).count()

    return jsonify({
        "success": True,
        "unread_count": count
    })


# ==========================================
# MARK SINGLE NOTIFICATION AS READ
# ==========================================

@notifications_bp.route("/<int:recipient_notification_id>/read",
                        methods=["PATCH"])
def mark_notification_read(recipient_notification_id):

    role, recipient_id = get_current_recipient()

    if not role or not recipient_id:
        return jsonify({
            "success": False,
            "message": "Login required."
        }), 403

    recipient = NotificationRecipient.query.filter_by(
        id=recipient_notification_id,
        recipient_role=role,
        recipient_id=recipient_id,
        is_deleted=False
    ).first()

    if not recipient:
        return jsonify({
            "success": False,
            "message": "Notification not found."
        }), 404

    recipient.is_read = True
    recipient.read_at = datetime.utcnow()

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Notification marked as read."
    })


# ==========================================
# MARK ALL AS READ
# ==========================================

@notifications_bp.route("/read-all", methods=["POST"])
def mark_all_read():

    role, recipient_id = get_current_recipient()

    if not role or not recipient_id:
        return jsonify({
            "success": False,
            "message": "Login required."
        }), 403

    NotificationRecipient.query.filter_by(
        recipient_role=role,
        recipient_id=recipient_id,
        is_read=False,
        is_deleted=False
    ).update({
        "is_read": True,
        "read_at": datetime.utcnow()
    })

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "All notifications marked as read."
    })


# ==========================================
# DELETE / HIDE NOTIFICATION
# ==========================================

@notifications_bp.route("/<int:recipient_notification_id>",
                        methods=["DELETE"])
def delete_notification(recipient_notification_id):

    role, recipient_id = get_current_recipient()

    if not role or not recipient_id:
        return jsonify({
            "success": False,
            "message": "Login required."
        }), 403

    recipient = NotificationRecipient.query.filter_by(
        id=recipient_notification_id,
        recipient_role=role,
        recipient_id=recipient_id,
        is_deleted=False
    ).first()

    if not recipient:
        return jsonify({
            "success": False,
            "message": "Notification not found."
        }), 404

    recipient.is_deleted = True
    recipient.deleted_at = datetime.utcnow()

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Notification deleted."
    })
