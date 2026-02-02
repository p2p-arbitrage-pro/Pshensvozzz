import calendar as pycalendar
import os
import re
import uuid
from datetime import date

from flask import Flask, render_template, request, redirect, url_for, flash, abort, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sqlalchemy import inspect, text, func
from werkzeug.utils import secure_filename

from config import Config
from models import db, User, Submission
from olympiad_parser import fetch_olympiad_news

app = Flask(__name__)
app.config.from_object(Config)

# Инициализация расширений
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице.'

UPLOAD_ROOT = os.path.join(app.instance_path, "uploads")
FILES_DIR = os.path.join(UPLOAD_ROOT, "files")
VIDEOS_DIR = os.path.join(UPLOAD_ROOT, "videos")
os.makedirs(FILES_DIR, exist_ok=True)
os.makedirs(VIDEOS_DIR, exist_ok=True)

ALLOWED_FILE_EXTS = {"pdf", "doc", "docx", "txt", "zip"}
ALLOWED_VIDEO_EXTS = {"mp4", "webm", "mov"}

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
MONTH_KEYWORDS_RU = {
    "янв": 1,
    "январ": 1,
    "фев": 2,
    "феврал": 2,
    "мар": 3,
    "март": 3,
    "апр": 4,
    "апрел": 4,
    "май": 5,
    "мая": 5,
    "июн": 6,
    "июнь": 6,
    "июня": 6,
    "июл": 7,
    "июль": 7,
    "июля": 7,
    "авг": 8,
    "август": 8,
    "сен": 9,
    "сент": 9,
    "сентябр": 9,
    "окт": 10,
    "октябр": 10,
    "ноя": 11,
    "нояб": 11,
    "ноябр": 11,
    "дек": 12,
    "декабр": 12,
}


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def _parse_event_date(raw_value):
    if not raw_value:
        return None

    text = str(raw_value).strip().lower()
    if not text:
        return None

    text = text.replace("–", "-").replace("—", "-")
    if re.search(r"\b20\d{2}\s*-\s*20\d{2}\b", text):
        return None

    match = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b", text)
    if match:
        day, month, year = match.groups()
        if len(year) == 2:
            year = f"20{year}"
        try:
            return date(int(year), int(month), int(day))
        except ValueError:
            return None

    match = re.search(r"\b(20\d{2})[./-](\d{1,2})[./-](\d{1,2})\b", text)
    if match:
        year, month, day = match.groups()
        try:
            return date(int(year), int(month), int(day))
        except ValueError:
            return None

    match = re.search(r"\b(\d{1,2})\s+([a-zа-яё]+)\s+(\d{4})\b", text)
    if match:
        day, month_word, year = match.groups()
        month_num = None
        for key, value in MONTH_KEYWORDS_RU.items():
            if month_word.startswith(key):
                month_num = value
                break
        if month_num:
            try:
                return date(int(year), int(month_num), int(day))
            except ValueError:
                return None

    return None


def _get_months_to_show(current_date=None):
    if current_date is None:
        current_date = date.today()
    year = current_date.year
    month = current_date.month
    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1
    return [(year, month), (next_year, next_month)]


def _build_calendar_view(items):
    events_by_date = {}
    undated = []
    months_to_show = _get_months_to_show()
    months_set = set(months_to_show)
    for item in items:
        parsed = _parse_event_date(item.get("date"))
        if not parsed:
            undated.append(item)
            continue
        if parsed.month == 2 and parsed.day == 14:
            continue
        if (parsed.year, parsed.month) not in months_set:
            continue
        key = parsed.isoformat()
        events_by_date.setdefault(key, []).append(item)

    months = list(months_to_show)
    calendar_months = []
    cal = pycalendar.Calendar(firstweekday=0)
    for year, month in months:
        weeks = []
        for week in cal.monthdatescalendar(year, month):
            week_cells = []
            for day in week:
                if day.month != month:
                    week_cells.append(None)
                else:
                    key = day.isoformat()
                    week_cells.append(
                        {
                            "day": day.day,
                            "date": key,
                            "events": events_by_date.get(key, []),
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
    original_name = secure_filename(file_storage.filename)
    extension = os.path.splitext(original_name)[1].lower()
    unique_name = f"{uuid.uuid4().hex}{extension}"
    file_path = os.path.join(target_dir, unique_name)
    file_storage.save(file_path)
    relative_path = os.path.relpath(file_path, UPLOAD_ROOT)
    return original_name, relative_path


def _require_admin():
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)


def _delete_upload(relative_path):
    if not relative_path:
        return
    abs_path = os.path.join(UPLOAD_ROOT, relative_path)
    if os.path.isfile(abs_path):
        os.remove(abs_path)


@app.route('/')
def index():
    base_calendar = [
        {
            'name': 'ОММО',
            'subject': 'Математика',
            'stage': 'Заключительный этап',
            'date': '01 фев 2026',
            'format': 'Очно',
            'link': 'https://ommo.ru'
        },
        {
            'name': 'Олимпиада «Росатом»',
            'subject': 'Математика',
            'stage': 'Заключительный этап',
            'date': '08 фев 2026',
            'format': 'Очно',
            'link': 'https://olymp.mephi.ru/rosatom/about'
        },
        {
            'name': 'Физтех-олимпиада',
            'subject': 'Математика',
            'stage': 'Заключительный этап',
            'date': '15 фев 2026',
            'format': 'Очно',
            'link': 'https://olymp-online.mipt.ru/'
        },
        {
            'name': 'Олимпиада «Газпром»',
            'subject': 'Профиль',
            'stage': 'Заключительный этап',
            'date': '22 фев 2026',
            'format': 'Очно',
            'link': ''
        },
        {
            'name': 'Шаг в будущее',
            'subject': 'Математика',
            'stage': 'Заключительный этап',
            'date': '09 мар 2026',
            'format': 'Очно',
            'link': 'https://olymp.bmstu.ru/ru/news/2025/12/25/raspisanie-zaklyuchitelnogo-etapa-olimpiady-shkolnikov-shag-v-buduschee'
        },
        {
            'name': 'МОШ',
            'subject': 'Математика',
            'stage': 'Заключительный этап',
            'date': '15 мар 2026',
            'format': 'Очно',
            'link': 'https://mosolymp.ru'
        },
        {
            'name': 'Олимпиада «Ломоносов»',
            'subject': 'Математика',
            'stage': 'Заключительный этап',
            'date': '29 мар 2026',
            'format': 'Очно',
            'link': 'https://olymp.msu.ru'
        },
    ]

    olympiad_calendar = base_calendar
    olympiad_news = fetch_olympiad_news()
    calendar_months, undated_events = _build_calendar_view(olympiad_calendar)

    return render_template(
        'index.html',
        olympiad_calendar=olympiad_calendar,
        olympiad_news=olympiad_news,
        calendar_months=calendar_months,
        undated_events=undated_events,
        weekday_labels=WEEKDAY_LABELS_RU,
    )


@app.route('/theory')
def theory():
    submissions = Submission.query.filter_by(status='approved').order_by(Submission.created_at.desc()).all()
    return render_template('theory.html', submissions=submissions)


@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        file = request.files.get('file')
        video = request.files.get('video')

        if not title:
            flash('Укажите название темы.', 'error')
            return redirect(url_for('upload'))

        if (not file or not file.filename) and (not video or not video.filename):
            flash('Добавьте файл или видео для отправки на модерацию.', 'error')
            return redirect(url_for('upload'))

        file_name = None
        file_path = None
        if file and file.filename:
            if not _allowed_file(file.filename, ALLOWED_FILE_EXTS):
                flash('Недопустимый формат файла.', 'error')
                return redirect(url_for('upload'))
            file_name, file_path = _save_upload(file, FILES_DIR)

        video_name = None
        video_path = None
        if video and video.filename:
            if not _allowed_file(video.filename, ALLOWED_VIDEO_EXTS):
                flash('Недопустимый формат видео.', 'error')
                return redirect(url_for('upload'))
            video_name, video_path = _save_upload(video, VIDEOS_DIR)

        submission = Submission(
            user_id=current_user.id,
            title=title,
            description=description or None,
            file_name=file_name,
            file_path=file_path,
            video_name=video_name,
            video_path=video_path,
            status='pending',
        )
        db.session.add(submission)
        db.session.commit()
        flash('Материалы отправлены на одобрение администратора.', 'success')
        return redirect(url_for('upload'))

    submissions = Submission.query.filter_by(user_id=current_user.id).order_by(Submission.created_at.desc()).all()
    return render_template('upload.html', submissions=submissions)


@app.route('/admin/submissions')
@login_required
def admin_submissions():
    _require_admin()
    submissions = Submission.query.order_by(Submission.created_at.desc()).all()
    return render_template('admin_submissions.html', submissions=submissions)


@app.post('/admin/submissions/<int:submission_id>/approve')
@login_required
def approve_submission(submission_id):
    _require_admin()
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
def download_submission_file(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    if submission.status != 'approved' and (not current_user.is_authenticated or not current_user.is_admin):
        abort(403)
    if not submission.file_path:
        abort(404)
    rel_dir = os.path.dirname(submission.file_path)
    filename = os.path.basename(submission.file_path)
    directory = os.path.join(UPLOAD_ROOT, rel_dir)
    return send_from_directory(directory, filename, as_attachment=True)


@app.route('/theory/video/<int:submission_id>')
def stream_submission_video(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    if submission.status != 'approved' and (not current_user.is_authenticated or not current_user.is_admin):
        abort(403)
    if not submission.video_path:
        abort(404)
    rel_dir = os.path.dirname(submission.video_path)
    filename = os.path.basename(submission.video_path)
    directory = os.path.join(UPLOAD_ROOT, rel_dir)
    return send_from_directory(directory, filename, as_attachment=False)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

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
        if User.query.count() == 0:
            user.is_admin = True
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        flash('Регистрация прошла успешно! Теперь вы можете войти.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
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
def dashboard():
    return render_template('dashboard.html', user=current_user)


@app.route('/profile')
@login_required
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
        admin_user = User.query.filter(func.lower(User.username) == 'admin').first()
        if admin_user and not admin_user.is_admin:
            admin_user.is_admin = True
            db.session.commit()
    if 'submission' in inspector.get_table_names():
        submission_columns = [column['name'] for column in inspector.get_columns('submission')]
        if 'title' not in submission_columns:
            db.session.execute(text("ALTER TABLE submission ADD COLUMN title VARCHAR(200) DEFAULT '' NOT NULL"))
        if 'description' not in submission_columns:
            db.session.execute(text('ALTER TABLE submission ADD COLUMN description TEXT'))
        db.session.commit()


if __name__ == '__main__':
    app.run(debug=True)
