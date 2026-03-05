import calendar as pycalendar
import os
import random
import secrets
import smtplib
import uuid
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, abort, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sqlalchemy import inspect, text, func
from werkzeug.utils import secure_filename

from config import Config
from models import db, User, Submission, CalendarEvent

app = Flask(__name__)
app.config.from_object(Config)

# Инициализация расширений
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице.'

UPLOAD_ROOT = app.config.get("UPLOAD_ROOT") or os.path.join(app.instance_path, "uploads")
FILES_DIR = os.path.join(UPLOAD_ROOT, "files")
VIDEOS_DIR = os.path.join(UPLOAD_ROOT, "videos")
os.makedirs(FILES_DIR, exist_ok=True)
os.makedirs(VIDEOS_DIR, exist_ok=True)

ALLOWED_FILE_EXTS = {"pdf", "doc", "docx", "ppt", "pptx", "odp", "txt", "zip"}
ALLOWED_VIDEO_EXTS = {"mp4", "webm", "mov"}
VERIFICATION_TTL_MIN_SECONDS = 444
VERIFICATION_TTL_MAX_SECONDS = 1488
PASSWORD_RESET_TTL_SECONDS = 900
PASSWORD_RESET_RESEND_SECONDS = 60
REMINDER_DAYS_BEFORE = 3

MONTH_LABELS_RU = [
    "",
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
]
WEEKDAY_LABELS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
DEFAULT_CALENDAR_EVENTS = [
    {
        "name": "ОММО",
        "subject": "Математика",
        "stage": "Заключительный этап",
        "date": date(2026, 2, 1),
        "format": "Очно",
        "link": "https://ommo.ru",
    },
    {
        "name": "Олимпиада «Росатом»",
        "subject": "Математика",
        "stage": "Заключительный этап",
        "date": date(2026, 2, 8),
        "format": "Очно",
        "link": "https://olymp.mephi.ru/rosatom/about",
    },
    {
        "name": "Физтех-олимпиада",
        "subject": "Математика",
        "stage": "Заключительный этап",
        "date": date(2026, 2, 15),
        "format": "Очно",
        "link": "https://olymp-online.mipt.ru/",
    },
    {
        "name": "Олимпиада «Газпром»",
        "subject": "Профиль",
        "stage": "Заключительный этап",
        "date": date(2026, 2, 22),
        "format": "Очно",
        "link": None,
    },
    {
        "name": "Шаг в будущее",
        "subject": "Математика",
        "stage": "Заключительный этап",
        "date": date(2026, 3, 9),
        "format": "Очно",
        "link": "https://olymp.bmstu.ru/ru/news/2025/12/25/raspisanie-zaklyuchitelnogo-etapa-olimpiady-shkolnikov-shag-v-buduschee",
    },
    {
        "name": "МОШ",
        "subject": "Математика",
        "stage": "Заключительный этап",
        "date": date(2026, 3, 15),
        "format": "Очно",
        "link": "https://mosolymp.ru",
    },
    {
        "name": "Олимпиада «Ломоносов»",
        "subject": "Математика",
        "stage": "Заключительный этап",
        "date": date(2026, 3, 29),
        "format": "Очно",
        "link": "https://olymp.msu.ru",
    },
]


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def _get_email_settings():
    host = os.environ.get("SMTP_HOST", "").strip()
    port_raw = os.environ.get("SMTP_PORT", "").strip()
    port = int(port_raw) if port_raw.isdigit() else 0
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "")
    use_tls = os.environ.get("SMTP_USE_TLS", "1").lower() in ("1", "true", "yes")
    use_ssl = os.environ.get("SMTP_USE_SSL", "0").lower() in ("1", "true", "yes")
    sender = os.environ.get("EMAIL_FROM", "").strip() or user
    dry_run = os.environ.get("EMAIL_DRY_RUN", "0").lower() in ("1", "true", "yes")
    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "use_tls": use_tls,
        "use_ssl": use_ssl,
        "sender": sender,
        "dry_run": dry_run,
    }


def _send_email(to_address, subject, body):
    settings = _get_email_settings()
    if settings["dry_run"]:
        app.logger.info("EMAIL_DRY_RUN to=%s subject=%s body=%s", to_address, subject, body)
        return True
    if not settings["host"] or not settings["sender"]:
        app.logger.warning("Email not sent: SMTP not configured.")
        return False

    msg = EmailMessage()
    msg["From"] = settings["sender"]
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        if settings["use_ssl"]:
            port = settings["port"] or 465
            with smtplib.SMTP_SSL(settings["host"], port) as smtp:
                if settings["user"] and settings["password"]:
                    smtp.login(settings["user"], settings["password"])
                smtp.send_message(msg)
        else:
            port = settings["port"] or 587
            with smtplib.SMTP(settings["host"], port) as smtp:
                smtp.ehlo()
                if settings["use_tls"]:
                    smtp.starttls()
                    smtp.ehlo()
                if settings["user"] and settings["password"]:
                    smtp.login(settings["user"], settings["password"])
                smtp.send_message(msg)
        return True
    except Exception as exc:
        app.logger.warning("Email send failed: %s", exc)
        return False


def _is_email_configured():
    settings = _get_email_settings()
    return bool(settings["host"] and settings["sender"])


def _should_show_verification_code():
    return os.environ.get("EMAIL_SHOW_CODE", "0").lower() in ("1", "true", "yes")


def _issue_verification_code(user):
    ttl_seconds = random.randint(VERIFICATION_TTL_MIN_SECONDS, VERIFICATION_TTL_MAX_SECONDS)
    code = f"{secrets.randbelow(1_000_000):06d}"
    user.email_verification_code = code
    user.email_verification_expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
    user.email_verification_sent_at = datetime.utcnow()
    return code, ttl_seconds


def _send_verification_email(user):
    code, ttl_seconds = _issue_verification_code(user)
    db.session.commit()
    subject = "Код подтверждения почты"
    body = (
        "Ваш код подтверждения:\n"
        f"{code}\n\n"
        f"Код действует {ttl_seconds} секунд."
    )
    sent = _send_email(user.email, subject, body)
    if not sent:
        app.logger.warning("Verification code for %s: %s", user.email, code)
    return sent, code, ttl_seconds


def _issue_password_reset_code(user):
    code = f"{secrets.randbelow(1_000_000):06d}"
    user.password_reset_code = code
    user.password_reset_expires_at = datetime.utcnow() + timedelta(seconds=PASSWORD_RESET_TTL_SECONDS)
    user.password_reset_sent_at = datetime.utcnow()
    return code, PASSWORD_RESET_TTL_SECONDS


def _announce_password_reset_code(user, code, ttl_seconds):
    message = f"Код смены пароля для {user.email}: {code} (TTL {ttl_seconds}s)"
    app.logger.warning(message)
    print(message)


def _send_password_reset_code(user):
    code, ttl_seconds = _issue_password_reset_code(user)
    db.session.commit()
    _announce_password_reset_code(user, code, ttl_seconds)
    return code, ttl_seconds


def verified_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if current_user.is_admin:
            return view(*args, **kwargs)
        if not current_user.email_verified:
            flash('Подтвердите почту для доступа к разделу.', 'error')
            return redirect(url_for('verify_email'))
        return view(*args, **kwargs)
    return wrapper


def _build_reminder_body(events, target_date):
    target_label = target_date.strftime("%d.%m.%Y")
    lines = [
        f"Напоминание: олимпиады через {REMINDER_DAYS_BEFORE} дня",
        f"Дата: {target_label}",
        "",
    ]
    for event in events:
        details = [event.name]
        if event.subject:
            details.append(event.subject)
        if event.stage:
            details.append(event.stage)
        line = " — ".join(details)
        lines.append(line)
        extra = []
        if event.format:
            extra.append(f"Формат: {event.format}")
        if event.link:
            extra.append(f"Ссылка: {event.link}")
        if extra:
            lines.append(" | ".join(extra))
        lines.append("")
    return "\n".join(lines).strip()


def _send_olympiad_reminders():
    settings = _get_email_settings()
    if not settings["dry_run"] and (not settings["host"] or not settings["sender"]):
        app.logger.warning("Reminders skipped: SMTP not configured.")
        return 0

    target_date = date.today() + timedelta(days=REMINDER_DAYS_BEFORE)
    events = CalendarEvent.query.filter(CalendarEvent.date == target_date).all()
    if not events:
        return 0

    events_to_send = [event for event in events if event.reminder_for_date != event.date]
    if not events_to_send:
        return 0

    users = User.query.all()
    recipients = [user.email for user in users if user.email]
    if not recipients:
        return 0

    subject = f"Напоминание: олимпиады через {REMINDER_DAYS_BEFORE} дня"
    body = _build_reminder_body(events_to_send, target_date)

    sent_count = 0
    for email in recipients:
        if _send_email(email, subject, body):
            sent_count += 1

    if sent_count > 0 or settings["dry_run"]:
        now = datetime.utcnow()
        for event in events_to_send:
            event.reminder_for_date = event.date
            event.reminder_sent_at = now
        db.session.commit()

    return sent_count


def _run_reminder_job():
    with app.app_context():
        _send_olympiad_reminders()


def _start_reminder_scheduler():
    if os.environ.get("DISABLE_REMINDERS", "0").lower() in ("1", "true", "yes"):
        return None
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except Exception as exc:
        app.logger.warning("APScheduler not available: %s", exc)
        return None
    scheduler = BackgroundScheduler(timezone=os.environ.get("REMINDER_TIMEZONE", "UTC"))
    scheduler.add_job(
        _run_reminder_job,
        "cron",
        hour=int(os.environ.get("REMINDER_HOUR", "9")),
        minute=int(os.environ.get("REMINDER_MINUTE", "0")),
        id="olympiad_reminders",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler


def _parse_form_date(raw_value):
    if not raw_value:
        return None
    try:
        return date.fromisoformat(str(raw_value))
    except ValueError:
        return None


def _format_event_date(event_date):
    if not event_date:
        return "Дата не указана"
    return event_date.strftime("%d.%m.%Y")


def _serialize_event(event):
    return {
        "id": event.id,
        "name": event.name,
        "subject": event.subject or "",
        "stage": event.stage or "",
        "date": event.date,
        "date_label": _format_event_date(event.date),
        "format": event.format or "",
        "link": event.link or "",
    }


def _get_months_to_show(items=None, current_date=None):
    if current_date is None:
        current_date = date.today()
    months = set()
    if items:
        for item in items:
            event_date = item.get("date")
            if event_date:
                months.add((event_date.year, event_date.month))
    year = current_date.year
    month = current_date.month
    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1
    months.add((year, month))
    months.add((next_year, next_month))
    months_list = sorted(months)
    current_key = (year, month)
    if current_key in months_list:
        index = months_list.index(current_key)
        months_list = months_list[index:] + months_list[:index]
    return months_list


def _build_calendar_view(items):
    events_by_date = {}
    undated = []
    for item in items:
        event_date = item.get("date")
        if not event_date:
            undated.append(item)
            continue
        key = event_date.isoformat()
        events_by_date.setdefault(key, []).append(item)

    for event_list in events_by_date.values():
        event_list.sort(key=lambda event: event.get("name") or "")
    undated.sort(key=lambda event: event.get("name") or "")

    months = list(_get_months_to_show(items))
    calendar_months = []
    cal = pycalendar.Calendar(firstweekday=0)
    today = date.today()
    for year, month in months:
        weeks = []
        for week in cal.monthdatescalendar(year, month):
            week_cells = []
            for day in week:
                if day.month != month:
                    week_cells.append(None)
                else:
                    key = day.isoformat()
                    events = events_by_date.get(key, [])
                    status = None
                    if events:
                        delta_days = (day - today).days
                        if delta_days < 0:
                            status = "past"
                        elif delta_days < REMINDER_DAYS_BEFORE:
                            status = "soon"
                        else:
                            status = "future"
                    week_cells.append(
                        {
                            "day": day.day,
                            "date": key,
                            "events": events,
                            "status": status,
                        }
                    )
            weeks.append(week_cells)
        calendar_months.append(
            {
                "month_label": f"{MONTH_LABELS_RU[month]} {year}",
                "weeks": weeks,
            }
        )
    return calendar_months, undated


def _allowed_file(filename, allowed_exts):
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in allowed_exts


def _save_upload(file_storage, target_dir):
    client_name = (file_storage.filename or "").replace("\\", "/")
    original_name = os.path.basename(client_name).strip()
    safe_name = secure_filename(original_name)
    extension = os.path.splitext(safe_name)[1].lower()
    if not extension:
        extension = os.path.splitext(original_name)[1].lower()
    unique_name = f"{uuid.uuid4().hex}{extension}"
    file_path = os.path.join(target_dir, unique_name)
    file_storage.save(file_path)
    relative_path = os.path.relpath(file_path, UPLOAD_ROOT)
    return original_name or unique_name, relative_path


def _require_admin():
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)


def _is_staff(user):
    return bool(user and (user.is_admin or user.is_moderator))


def _require_staff():
    if not current_user.is_authenticated or not _is_staff(current_user):
        abort(403)


def _delete_upload(relative_path):
    if not relative_path:
        return
    abs_path = os.path.join(UPLOAD_ROOT, relative_path)
    if os.path.isfile(abs_path):
        os.remove(abs_path)


def _build_theory_groups(submissions):
    grouped = {}
    order = []
    for submission in submissions:
        key = submission.batch_id or f"single-{submission.id}"
        if key not in grouped:
            grouped[key] = {
                "title": submission.title,
                "description": submission.description,
                "user": submission.user,
                "created_at": submission.created_at,
                "files": [],
                "videos": [],
            }
            order.append(key)
        group = grouped[key]
        if not group["description"] and submission.description:
            group["description"] = submission.description
        if submission.created_at > group["created_at"]:
            group["created_at"] = submission.created_at
        if submission.file_name and submission.file_path:
            group["files"].append(
                {
                    "id": submission.id,
                    "name": submission.file_name,
                }
            )
        if submission.video_name and submission.video_path:
            group["videos"].append(
                {
                    "id": submission.id,
                    "name": submission.video_name,
                }
            )
    return [grouped[key] for key in order]


@app.route('/')
def index():
    events = CalendarEvent.query.order_by(
        CalendarEvent.date.is_(None),
        CalendarEvent.date.asc(),
        CalendarEvent.name.asc(),
    ).all()
    olympiad_calendar = [_serialize_event(event) for event in events]
    calendar_months, undated_events = _build_calendar_view(olympiad_calendar)

    return render_template(
        'index.html',
        calendar_months=calendar_months,
        undated_events=undated_events,
        weekday_labels=WEEKDAY_LABELS_RU,
    )


@app.route('/theory')
@login_required
@verified_required
def theory():
    submissions = Submission.query.filter_by(status='approved').order_by(Submission.created_at.desc()).all()
    theory_groups = _build_theory_groups(submissions)
    return render_template('theory.html', theory_groups=theory_groups)


@app.route('/upload', methods=['GET', 'POST'])
@login_required
@verified_required
def upload():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        files = [item for item in request.files.getlist('files') if item and item.filename]
        videos = [item for item in request.files.getlist('videos') if item and item.filename]

        # Backward compatibility for older form fields.
        if not files:
            legacy_file = request.files.get('file')
            if legacy_file and legacy_file.filename:
                files = [legacy_file]
        if not videos:
            legacy_video = request.files.get('video')
            if legacy_video and legacy_video.filename:
                videos = [legacy_video]

        if not title:
            flash('Укажите название темы.', 'error')
            return redirect(url_for('upload'))

        if not files and not videos:
            flash('Добавьте файл или видео для отправки на модерацию.', 'error')
            return redirect(url_for('upload'))

        for file_item in files:
            if not _allowed_file(file_item.filename, ALLOWED_FILE_EXTS):
                flash('Недопустимый формат файла.', 'error')
                return redirect(url_for('upload'))
        for video_item in videos:
            if not _allowed_file(video_item.filename, ALLOWED_VIDEO_EXTS):
                flash('Недопустимый формат видео.', 'error')
                return redirect(url_for('upload'))

        total_items = len(files) + len(videos)
        batch_id = uuid.uuid4().hex
        if len(files) <= 1 and len(videos) <= 1:
            file_name = None
            file_path = None
            if files:
                file_name, file_path = _save_upload(files[0], FILES_DIR)

            video_name = None
            video_path = None
            if videos:
                video_name, video_path = _save_upload(videos[0], VIDEOS_DIR)

            db.session.add(
                Submission(
                    user_id=current_user.id,
                    batch_id=batch_id,
                    title=title,
                    description=description or None,
                    file_name=file_name,
                    file_path=file_path,
                    video_name=video_name,
                    video_path=video_path,
                    status='pending',
                )
            )
        else:
            for file_item in files:
                file_name, file_path = _save_upload(file_item, FILES_DIR)
                db.session.add(
                    Submission(
                        user_id=current_user.id,
                        batch_id=batch_id,
                        title=title,
                        description=description or None,
                        file_name=file_name,
                        file_path=file_path,
                        status='pending',
                    )
                )
            for video_item in videos:
                video_name, video_path = _save_upload(video_item, VIDEOS_DIR)
                db.session.add(
                    Submission(
                        user_id=current_user.id,
                        batch_id=batch_id,
                        title=title,
                        description=description or None,
                        video_name=video_name,
                        video_path=video_path,
                        status='pending',
                    )
                )
        db.session.commit()
        if total_items > 1:
            flash(f'Материалы отправлены на одобрение: {total_items} шт.', 'success')
        else:
            flash('Материалы отправлены на одобрение администратора.', 'success')
        return redirect(url_for('upload'))

    submissions = Submission.query.filter_by(user_id=current_user.id).order_by(Submission.created_at.desc()).all()
    return render_template('upload.html', submissions=submissions)


@app.route('/admin/submissions')
@login_required
def admin_submissions():
    _require_staff()
    submissions = Submission.query.order_by(Submission.created_at.desc()).all()
    return render_template(
        'admin_submissions.html',
        submissions=submissions,
        can_full_moderation=current_user.is_admin,
    )


@app.route('/admin/calendar', methods=['GET', 'POST'])
@login_required
def admin_calendar():
    _require_admin()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        subject = request.form.get('subject', '').strip()
        stage = request.form.get('stage', '').strip()
        date_raw = request.form.get('date', '').strip()
        event_format = request.form.get('format', '').strip()
        link = request.form.get('link', '').strip()

        if not name:
            flash('Укажите название олимпиады.', 'error')
            return redirect(url_for('admin_calendar'))

        event_date = _parse_form_date(date_raw)
        if date_raw and not event_date:
            flash('Некорректная дата.', 'error')
            return redirect(url_for('admin_calendar'))

        new_event = CalendarEvent(
            name=name,
            subject=subject or None,
            stage=stage or None,
            date=event_date,
            format=event_format or None,
            link=link or None,
        )
        db.session.add(new_event)
        db.session.commit()
        flash('Событие добавлено.', 'success')
        return redirect(url_for('admin_calendar'))

    events = CalendarEvent.query.order_by(
        CalendarEvent.date.is_(None),
        CalendarEvent.date.asc(),
        CalendarEvent.name.asc(),
    ).all()
    return render_template('admin_calendar.html', events=events)


@app.route('/admin/users')
@login_required
def admin_users():
    _require_admin()
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin_users.html', users=users)


@app.post('/admin/users/<int:user_id>/toggle-moderator')
@login_required
def toggle_moderator(user_id):
    _require_admin()
    user = User.query.get_or_404(user_id)
    if user.is_admin:
        flash('Нельзя изменить роль администратора.', 'error')
        return redirect(url_for('admin_users'))
    user.is_moderator = not user.is_moderator
    db.session.commit()
    if user.is_moderator:
        flash(f'Пользователь {user.username} назначен модератором.', 'success')
    else:
        flash(f'Пользователь {user.username} больше не модератор.', 'success')
    return redirect(url_for('admin_users'))


@app.post('/admin/users/<int:user_id>/delete')
@login_required
def delete_user(user_id):
    _require_admin()
    user = User.query.get_or_404(user_id)
    if user.is_admin or user.username.lower() == 'admin':
        flash('Нельзя удалить администратора.', 'error')
        return redirect(url_for('admin_users'))
    if user.id == current_user.id:
        flash('Нельзя удалить свой аккаунт.', 'error')
        return redirect(url_for('admin_users'))

    submissions = Submission.query.filter_by(user_id=user.id).all()
    for submission in submissions:
        _delete_upload(submission.file_path)
        _delete_upload(submission.video_path)
        db.session.delete(submission)
    db.session.delete(user)
    db.session.commit()
    flash('Аккаунт пользователя удалён.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/calendar/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_calendar_event(event_id):
    _require_admin()
    event = CalendarEvent.query.get_or_404(event_id)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        subject = request.form.get('subject', '').strip()
        stage = request.form.get('stage', '').strip()
        date_raw = request.form.get('date', '').strip()
        event_format = request.form.get('format', '').strip()
        link = request.form.get('link', '').strip()

        if not name:
            flash('Укажите название олимпиады.', 'error')
            return redirect(url_for('edit_calendar_event', event_id=event_id))

        event_date = _parse_form_date(date_raw)
        if date_raw and not event_date:
            flash('Некорректная дата.', 'error')
            return redirect(url_for('edit_calendar_event', event_id=event_id))

        event.name = name
        event.subject = subject or None
        event.stage = stage or None
        event.date = event_date
        event.format = event_format or None
        event.link = link or None
        db.session.commit()
        flash('Событие обновлено.', 'success')
        return redirect(url_for('admin_calendar'))

    return render_template('admin_calendar_edit.html', event=event)


@app.post('/admin/calendar/<int:event_id>/delete')
@login_required
def delete_calendar_event(event_id):
    _require_admin()
    event = CalendarEvent.query.get_or_404(event_id)
    db.session.delete(event)
    db.session.commit()
    flash('Событие удалено.', 'success')
    return redirect(url_for('admin_calendar'))


@app.post('/admin/reminders/send')
@login_required
def send_reminders_now():
    _require_admin()
    sent = _send_olympiad_reminders()
    flash(f'Напоминания отправлены: {sent}.', 'success')
    return redirect(url_for('admin_calendar'))


@app.post('/admin/submissions/<int:submission_id>/approve')
@login_required
def approve_submission(submission_id):
    _require_staff()
    submission = Submission.query.get_or_404(submission_id)
    submission.status = 'approved'
    db.session.commit()
    flash('Материал одобрен.', 'success')
    return redirect(url_for('admin_submissions'))


@app.post('/admin/submissions/<int:submission_id>/reject')
@login_required
def reject_submission(submission_id):
    _require_admin()
    submission = Submission.query.get_or_404(submission_id)
    submission.status = 'rejected'
    db.session.commit()
    flash('Материал отклонён.', 'success')
    return redirect(url_for('admin_submissions'))


@app.post('/admin/submissions/<int:submission_id>/delete')
@login_required
def delete_submission(submission_id):
    _require_admin()
    submission = Submission.query.get_or_404(submission_id)
    _delete_upload(submission.file_path)
    _delete_upload(submission.video_path)
    db.session.delete(submission)
    db.session.commit()
    flash('Материал удалён.', 'success')
    return redirect(url_for('admin_submissions'))


@app.route('/theory/file/<int:submission_id>')
@login_required
@verified_required
def download_submission_file(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    if submission.status != 'approved' and (not current_user.is_authenticated or not _is_staff(current_user)):
        abort(403)
    if not submission.file_path:
        abort(404)
    rel_dir = os.path.dirname(submission.file_path)
    filename = os.path.basename(submission.file_path)
    directory = os.path.join(UPLOAD_ROOT, rel_dir)
    return send_from_directory(
        directory,
        filename,
        as_attachment=True,
        download_name=submission.file_name or filename,
    )


@app.route('/theory/video/<int:submission_id>')
@login_required
@verified_required
def stream_submission_video(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    if submission.status != 'approved' and (not current_user.is_authenticated or not _is_staff(current_user)):
        abort(403)
    if not submission.video_path:
        abort(404)
    rel_dir = os.path.dirname(submission.video_path)
    filename = os.path.basename(submission.video_path)
    directory = os.path.join(UPLOAD_ROOT, rel_dir)
    return send_from_directory(directory, filename, as_attachment=False)


@app.route('/verify-email', methods=['GET', 'POST'])
@login_required
def verify_email():
    if current_user.is_admin or current_user.email_verified:
        flash('Почта уже подтверждена.', 'success')
        return redirect(url_for('profile'))

    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        if not code:
            flash('Введите код подтверждения.', 'error')
            return redirect(url_for('verify_email'))

        if not current_user.email_verification_code or not current_user.email_verification_expires_at:
            flash('Код не найден. Запросите новый.', 'error')
            return redirect(url_for('verify_email'))

        if datetime.utcnow() > current_user.email_verification_expires_at:
            flash('Срок действия кода истёк.', 'error')
            return redirect(url_for('verify_email'))

        if code != current_user.email_verification_code:
            flash('Неверный код подтверждения.', 'error')
            return redirect(url_for('verify_email'))

        current_user.email_verified = True
        current_user.email_verification_code = None
        current_user.email_verification_expires_at = None
        current_user.email_verification_sent_at = None
        db.session.commit()
        flash('Почта подтверждена.', 'success')
        return redirect(url_for('profile'))

    return render_template('verify_email.html')


@app.post('/verify-email/resend')
@login_required
def resend_verification_email():
    if current_user.is_admin or current_user.email_verified:
        flash('Почта уже подтверждена.', 'success')
        return redirect(url_for('profile'))

    if current_user.email_verification_sent_at:
        elapsed = datetime.utcnow() - current_user.email_verification_sent_at
        if elapsed < timedelta(seconds=60):
            flash('Подождите минуту перед повторной отправкой.', 'error')
            return redirect(url_for('verify_email'))

    sent, code, _ = _send_verification_email(current_user)
    if sent:
        flash('Код подтверждения отправлен повторно.', 'success')
    else:
        if _is_email_configured():
            flash('Не удалось отправить письмо. Проверьте пароль приложения и 2FA.', 'error')
        else:
            flash('Почта не настроена. Код подтверждения выведен в консоль.', 'error')
        if _should_show_verification_code():
            flash(f'Код: {code}', 'success')
    return redirect(url_for('verify_email'))


@app.route('/password-reset', methods=['GET', 'POST'])
def password_reset_request():
    email_prefill = request.args.get('email', '').strip()
    if current_user.is_authenticated and current_user.email and not email_prefill:
        email_prefill = current_user.email

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if not email:
            flash('Введите email.', 'error')
            return redirect(url_for('password_reset_request'))

        user = User.query.filter(func.lower(User.email) == email.lower()).first()
        if not user:
            flash('Пользователь с таким email не найден.', 'error')
            return redirect(url_for('password_reset_request'))

        if user.password_reset_sent_at:
            elapsed = datetime.utcnow() - user.password_reset_sent_at
            if elapsed < timedelta(seconds=PASSWORD_RESET_RESEND_SECONDS):
                flash('Подождите минуту перед повторной отправкой.', 'error')
                return redirect(url_for('password_reset_request'))

        _send_password_reset_code(user)
        flash('Код для смены пароля выведен в консоль сервера.', 'success')
        return redirect(url_for('password_reset_confirm', email=email))

    return render_template('password_reset_request.html', email_prefill=email_prefill)


@app.route('/password-reset/confirm', methods=['GET', 'POST'])
def password_reset_confirm():
    email_prefill = request.args.get('email', '').strip()

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        code = request.form.get('code', '').strip()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')

        if not email or not code or not password or not password_confirm:
            flash('Заполните все поля.', 'error')
            return redirect(url_for('password_reset_confirm', email=email))

        if password != password_confirm:
            flash('Пароли не совпадают.', 'error')
            return redirect(url_for('password_reset_confirm', email=email))

        user = User.query.filter(func.lower(User.email) == email.lower()).first()
        if not user:
            flash('Пользователь не найден.', 'error')
            return redirect(url_for('password_reset_confirm'))

        if not user.password_reset_code or not user.password_reset_expires_at:
            flash('Код не найден. Запросите новый.', 'error')
            return redirect(url_for('password_reset_request'))

        if datetime.utcnow() > user.password_reset_expires_at:
            user.password_reset_code = None
            user.password_reset_expires_at = None
            user.password_reset_sent_at = None
            db.session.commit()
            flash('Срок действия кода истёк. Запросите новый.', 'error')
            return redirect(url_for('password_reset_request'))

        if code != user.password_reset_code:
            flash('Неверный код.', 'error')
            return redirect(url_for('password_reset_confirm', email=email))

        user.set_password(password)
        user.password_reset_code = None
        user.password_reset_expires_at = None
        user.password_reset_sent_at = None
        db.session.commit()
        flash('Пароль успешно изменён. Войдите снова.', 'success')
        return redirect(url_for('login'))

    return render_template('password_reset_confirm.html', email_prefill=email_prefill)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('profile'))

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        # Проверка существования пользователя
        if User.query.filter(func.lower(User.username) == username.lower()).first():
            flash('Пользователь с таким именем уже существует', 'error')
            return render_template('register.html')

        if User.query.filter_by(email=email).first():
            flash('Пользователь с таким email уже существует', 'error')
            return render_template('register.html')

        # Создание нового пользователя
        user = User(username=username, email=email)
        if username.strip().lower() == 'admin':
            user.is_admin = True
            user.email_verified = True
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        if not user.is_admin:
            sent, code, _ = _send_verification_email(user)
            if sent:
                flash('Код подтверждения отправлен на почту.', 'success')
            else:
                if _is_email_configured():
                    flash('Не удалось отправить письмо. Проверьте пароль приложения и 2FA.', 'error')
                else:
                    flash('Почта не настроена. Код подтверждения выведен в консоль.', 'error')
                if _should_show_verification_code():
                    flash(f'Код: {code}', 'success')

        flash('Регистрация прошла успешно! Теперь вы можете войти.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('profile'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            if not user.email_verified and not user.is_admin:
                return redirect(url_for('verify_email'))
            return redirect(next_page or url_for('profile'))
        flash('Неверное имя пользователя или пароль', 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы успешно вышли из системы', 'success')
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
@verified_required
def dashboard():
    return redirect(url_for('profile'))


@app.route('/profile')
@login_required
@verified_required
def profile():
    return render_template('profile.html', user=current_user)


# Создание таблиц в базе данных
with app.app_context():
    db.create_all()
    inspector = inspect(db.engine)
    if 'user' in inspector.get_table_names():
        columns = [column['name'] for column in inspector.get_columns('user')]
        if 'is_admin' not in columns:
            db.session.execute(text('ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0'))
            db.session.commit()
        if 'is_moderator' not in columns:
            db.session.execute(text('ALTER TABLE user ADD COLUMN is_moderator BOOLEAN DEFAULT 0'))
            db.session.commit()
        if 'email_verified' not in columns:
            db.session.execute(text('ALTER TABLE user ADD COLUMN email_verified BOOLEAN DEFAULT 0'))
            db.session.commit()
        if 'email_verification_code' not in columns:
            db.session.execute(text('ALTER TABLE user ADD COLUMN email_verification_code VARCHAR(12)'))
            db.session.commit()
        if 'email_verification_expires_at' not in columns:
            db.session.execute(text('ALTER TABLE user ADD COLUMN email_verification_expires_at DATETIME'))
            db.session.commit()
        if 'email_verification_sent_at' not in columns:
            db.session.execute(text('ALTER TABLE user ADD COLUMN email_verification_sent_at DATETIME'))
            db.session.commit()
        if 'password_reset_code' not in columns:
            db.session.execute(text('ALTER TABLE user ADD COLUMN password_reset_code VARCHAR(12)'))
            db.session.commit()
        if 'password_reset_expires_at' not in columns:
            db.session.execute(text('ALTER TABLE user ADD COLUMN password_reset_expires_at DATETIME'))
            db.session.commit()
        if 'password_reset_sent_at' not in columns:
            db.session.execute(text('ALTER TABLE user ADD COLUMN password_reset_sent_at DATETIME'))
            db.session.commit()
        db.session.execute(
            text("UPDATE user SET is_admin = CASE WHEN lower(username) = 'admin' THEN 1 ELSE 0 END")
        )
        db.session.execute(
            text("UPDATE user SET is_moderator = CASE WHEN lower(username) = 'admin' THEN 0 ELSE is_moderator END")
        )
        db.session.commit()
        admin_user = User.query.filter(func.lower(User.username) == 'admin').first()
        if admin_user and not admin_user.email_verified:
            admin_user.email_verified = True
            db.session.commit()
    if 'submission' in inspector.get_table_names():
        submission_columns = [column['name'] for column in inspector.get_columns('submission')]
        if 'batch_id' not in submission_columns:
            db.session.execute(text('ALTER TABLE submission ADD COLUMN batch_id VARCHAR(32)'))
        if 'title' not in submission_columns:
            db.session.execute(text("ALTER TABLE submission ADD COLUMN title VARCHAR(200) DEFAULT '' NOT NULL"))
        if 'description' not in submission_columns:
            db.session.execute(text('ALTER TABLE submission ADD COLUMN description TEXT'))
        db.session.commit()
    if 'calendar_event' in inspector.get_table_names():
        event_columns = [column['name'] for column in inspector.get_columns('calendar_event')]
        if 'reminder_for_date' not in event_columns:
            db.session.execute(text('ALTER TABLE calendar_event ADD COLUMN reminder_for_date DATE'))
        if 'reminder_sent_at' not in event_columns:
            db.session.execute(text('ALTER TABLE calendar_event ADD COLUMN reminder_sent_at DATETIME'))
        db.session.commit()
        if CalendarEvent.query.count() == 0:
            for item in DEFAULT_CALENDAR_EVENTS:
                db.session.add(
                    CalendarEvent(
                        name=item["name"],
                        subject=item.get("subject"),
                        stage=item.get("stage"),
                        date=item.get("date"),
                        format=item.get("format"),
                        link=item.get("link"),
                    )
                )
            db.session.commit()


if __name__ == '__main__':
    debug_mode = True
    if debug_mode:
        if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
            _start_reminder_scheduler()
    else:
        _start_reminder_scheduler()
    app.run(debug=debug_mode)
