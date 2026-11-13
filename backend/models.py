
from datetime import datetime
from .database import db


# =====================================
# NOTES MODEL
# =====================================

class Note(db.Model):

    __tablename__ = "notes"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    board = db.Column(db.String(50), nullable=False)
    class_name = db.Column(db.String(20), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    chapter = db.Column(db.String(150), nullable=False)

    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)

    is_published = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "board": self.board,
            "class_name": self.class_name,
            "subject": self.subject,
            "chapter": self.chapter,
            "file_name": self.file_name,
            "file_path": self.file_path,
            "is_published": self.is_published,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


# =====================================
# TEST MODEL
# =====================================

class Test(db.Model):

    __tablename__ = "tests"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    board = db.Column(db.String(50), nullable=False, default="PSEB")
    class_name = db.Column(db.String(20), nullable=False)
    subject = db.Column(db.String(100), nullable=False)

    duration_minutes = db.Column(db.Integer, nullable=False, default=30)

    total_marks = db.Column(db.Integer, nullable=False, default=0)

    is_published = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    questions = db.relationship(
        "TestQuestion",
        backref="test",
        cascade="all, delete-orphan",
        order_by="TestQuestion.id"
    )

    attempts = db.relationship(
        "TestAttempt",
        backref="test",
        cascade="all, delete-orphan"
    )

    def calculate_total_marks(self):
        self.total_marks = sum(
            question.marks for question in self.questions
        )
        return self.total_marks

    def to_dict(self, include_questions=True):

        data = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "board": self.board,
            "class_name": self.class_name,
            "subject": self.subject,
            "duration_minutes": self.duration_minutes,
            "total_marks": self.total_marks,
            "is_published": self.is_published,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

        if include_questions:
            data["questions"] = [
                question.to_dict()
                for question in self.questions
            ]

        return data


# =====================================
# TEST QUESTIONS MODEL
# =====================================

class TestQuestion(db.Model):

    __tablename__ = "test_questions"

    id = db.Column(db.Integer, primary_key=True)

    test_id = db.Column(
        db.Integer,
        db.ForeignKey("tests.id"),
        nullable=False
    )

    question_text = db.Column(db.Text, nullable=False)

    question_type = db.Column(
        db.String(20),
        nullable=False,
        default="mcq"
    )

    options = db.Column(db.JSON, nullable=True)

    correct_answer = db.Column(db.Text, nullable=True)

    marks = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self, include_answer=False):

        data = {
            "id": self.id,
            "test_id": self.test_id,
            "question_text": self.question_text,
            "question_type": self.question_type,
            "options": self.options,
            "marks": self.marks
        }

        if include_answer:
            data["correct_answer"] = self.correct_answer

        return data


# =====================================
# STUDENT TEST ATTEMPT MODEL
# =====================================

class TestAttempt(db.Model):

    __tablename__ = "test_attempts"

    id = db.Column(db.Integer, primary_key=True)

    test_id = db.Column(
        db.Integer,
        db.ForeignKey("tests.id"),
        nullable=False
    )

    student_id = db.Column(
        db.Integer,
        nullable=False
    )

    answers = db.Column(db.JSON, nullable=False, default=dict)

    total_questions = db.Column(db.Integer, default=0, nullable=False)

    attempted_questions = db.Column(db.Integer, default=0, nullable=False)

    correct_answers = db.Column(db.Integer, default=0, nullable=False)

    wrong_answers = db.Column(db.Integer, default=0, nullable=False)

    unattempted_questions = db.Column(db.Integer, default=0, nullable=False)

    total_marks = db.Column(db.Integer, default=0, nullable=False)

    obtained_marks = db.Column(db.Integer, default=0, nullable=False)

    percentage = db.Column(db.Float, default=0.0, nullable=False)

    status = db.Column(db.String(20), default="in_progress", nullable=False)

    started_at = db.Column(db.DateTime, default=datetime.utcnow)

    submitted_at = db.Column(db.DateTime, nullable=True)
    # =====================================
# STUDENT MODEL
# =====================================

class Student(db.Model):

    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(120), nullable=False)

    email = db.Column(
        db.String(150),
        unique=True,
        nullable=False,
        index=True
    )

    password_hash = db.Column(db.String(255), nullable=False)
    profile_photo = db.Column(db.String(500), nullable=True)
    board = db.Column(
        db.String(50),
        nullable=False,
        default="PSEB"
    )

    class_name = db.Column(
        db.String(20),
        nullable=False
    )

    is_active = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    def to_dict(self):

        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "profile_photo": self.profile_photo,
            "board": self.board,
            "class_name": self.class_name,
            "is_active": self.is_active,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at else None
            )
        }
    parent_link_code = db.Column(
    db.String(32),
    unique=True,
    nullable=True
)
    # =====================================
# ONLINE BATCH MODEL
# =====================================

class Batch(db.Model):

    __tablename__ = "batches"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(200), nullable=False)

    description = db.Column(db.Text)

    board = db.Column(
        db.String(50),
        nullable=False,
        default="PSEB"
    )

    class_name = db.Column(db.String(20), nullable=False)

    subject = db.Column(db.String(100), nullable=False)

    teacher_name = db.Column(db.String(120))

    fees = db.Column(db.Float, default=0.0, nullable=False)

    schedule = db.Column(db.String(255))

    start_date = db.Column(db.Date, nullable=True)

    end_date = db.Column(db.Date, nullable=True)

    capacity = db.Column(db.Integer, default=50)

    meeting_link = db.Column(db.String(500), nullable=True)

    is_published = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    enrollments = db.relationship(
        "BatchEnrollment",
        backref="batch",
        cascade="all, delete-orphan"
    )

    def to_dict(self):

        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "board": self.board,
            "class_name": self.class_name,
            "subject": self.subject,
            "teacher_name": self.teacher_name,
            "fees": self.fees,
            "schedule": self.schedule,
            "start_date": (
                self.start_date.isoformat()
                if self.start_date else None
            ),
            "end_date": (
                self.end_date.isoformat()
                if self.end_date else None
            ),
            "capacity": self.capacity,
            "is_published": self.is_published,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at else None
            )
        }


# =====================================
# BATCH ENROLLMENT MODEL
# =====================================

class BatchEnrollment(db.Model):

    __tablename__ = "batch_enrollments"

    id = db.Column(db.Integer, primary_key=True)

    batch_id = db.Column(
        db.Integer,
        db.ForeignKey("batches.id"),
        nullable=False
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id"),
        nullable=False
    )

    status = db.Column(
        db.String(20),
        default="pending",
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    student = db.relationship("Student")

    def to_dict(self):

        return {
            "id": self.id,
            "batch_id": self.batch_id,
            "student_id": self.student_id,
            "student_name": self.student.name if self.student else None,
            "status": self.status,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at else None
            )
        }
    # =====================================
# PARENT MODEL
# =====================================

class Parent(db.Model):

    __tablename__ = "parents"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(120), nullable=False)

    email = db.Column(
        db.String(150),
        unique=True,
        nullable=False,
        index=True
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    phone = db.Column(db.String(20), nullable=True)

    is_active = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    def to_dict(self):

        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "is_active": self.is_active,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at else None
            )
        }
    # =====================================
# PARENT - STUDENT CONNECTION MODEL
# =====================================

class ParentStudentLink(db.Model):

    __tablename__ = "parent_student_links"

    id = db.Column(db.Integer, primary_key=True)

    parent_id = db.Column(
        db.Integer,
        db.ForeignKey("parents.id"),
        nullable=False
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    parent = db.relationship("Parent", backref="children")

    student = db.relationship("Student")

    __table_args__ = (
        db.UniqueConstraint(
            "parent_id",
            "student_id",
            name="unique_parent_student"
        ),
    )
    # =====================================
# STUDENT ATTENDANCE MODEL
# =====================================

class Attendance(db.Model):

    __tablename__ = "attendance"

    id = db.Column(db.Integer, primary_key=True)

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id"),
        nullable=False
    )

    batch_id = db.Column(
        db.Integer,
        db.ForeignKey("batches.id"),
        nullable=False
    )

    attendance_date = db.Column(
        db.Date,
        nullable=False,
        default=datetime.utcnow().date
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="present"
    )

    remarks = db.Column(db.String(255), nullable=True)

    marked_by = db.Column(db.String(120), nullable=True)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    student = db.relationship("Student")

    batch = db.relationship("Batch")

    __table_args__ = (
        db.UniqueConstraint(
            "student_id",
            "batch_id",
            "attendance_date",
            name="unique_student_batch_attendance"
        ),
    )

    def to_dict(self):

        return {
            "id": self.id,
            "student_id": self.student_id,
            "student_name": self.student.name if self.student else None,
            "batch_id": self.batch_id,
            "batch_name": self.batch.title if self.batch else None,
            "attendance_date": (
                self.attendance_date.isoformat()
                if self.attendance_date else None
            ),
            "status": self.status,
            "remarks": self.remarks,
            "marked_by": self.marked_by,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at else None
            )
        }


# NOTIFICATION SYSTEM
# =====================================

class Notification(db.Model):

    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(
        db.String(200),
        nullable=False
    )

    message = db.Column(
        db.Text,
        nullable=False
    )

    category = db.Column(
        db.String(50),
        nullable=False,
        default="announcement"
    )

    target_type = db.Column(
        db.String(50),
        nullable=False,
        default="all"
    )

    created_by = db.Column(
        db.String(100),
        nullable=False,
        default="admin"
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    recipients = db.relationship(
        "NotificationRecipient",
        backref="notification",
        cascade="all, delete-orphan"
    )


class NotificationRecipient(db.Model):

    __tablename__ = "notification_recipients"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    notification_id = db.Column(
        db.Integer,
        db.ForeignKey("notifications.id"),
        nullable=False
    )

    recipient_role = db.Column(
        db.String(20),
        nullable=False
    )

    recipient_id = db.Column(
        db.Integer,
        nullable=False
    )

    is_read = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    read_at = db.Column(
        db.DateTime,
        nullable=True
    )

    is_deleted = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    deleted_at = db.Column(
        db.DateTime,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    __table_args__ = (
        db.UniqueConstraint(
            "notification_id",
            "recipient_role",
            "recipient_id",
            name="unique_notification_recipient"
        ),
    )
