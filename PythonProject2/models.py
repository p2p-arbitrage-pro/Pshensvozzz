from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)
    is_moderator = db.Column(db.Boolean, default=False)
    email_verified = db.Column(db.Boolean, default=False)
    email_verification_code = db.Column(db.String(12))
    email_verification_expires_at = db.Column(db.DateTime)
    email_verification_sent_at = db.Column(db.DateTime)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('submissions', lazy=True))
    batch_id = db.Column(db.String(32), index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    file_name = db.Column(db.String(255))
    file_path = db.Column(db.String(255))
    video_name = db.Column(db.String(255))
    video_path = db.Column(db.String(255))
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Submission {self.id} {self.status}>'


class CalendarEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(200))
    stage = db.Column(db.String(200))
    date = db.Column(db.Date)
    format = db.Column(db.String(100))
    link = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reminder_for_date = db.Column(db.Date)
    reminder_sent_at = db.Column(db.DateTime)

    def __repr__(self):
        return f'<CalendarEvent {self.id} {self.name}>'
