from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField, BooleanField
from wtforms.validators import DataRequired, Length
from datetime import datetime, timedelta
import os
import json
import logging
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

load_dotenv()

from database import db, User, Bot, Group, UserCollect, Statistics, MessageLog, Schedule
from bot_worker import BotWorker

# تهيئة التطبيق
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///instance/bot_manager.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# تهيئة مدير الجلسات
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'يرجى تسجيل الدخول أولاً'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# نماذج الويب
class LoginForm(FlaskForm):
    username = StringField('اسم المستخدم', validators=[DataRequired()])
    password = PasswordField('كلمة المرور', validators=[DataRequired()])
    submit = SubmitField('تسجيل الدخول')

class BotForm(FlaskForm):
    name = StringField('اسم البوت')
    token = StringField('توكن البوت', validators=[DataRequired()])
    submit = SubmitField('إضافة البوت')

class GroupForm(FlaskForm):
    group_id = StringField('معرف المجموعة', validators=[DataRequired()])
    title = StringField('اسم المجموعة')
    bot_id = IntegerField('معرف البوت', validators=[DataRequired()])
    submit = SubmitField('إضافة المجموعة')

class ScheduleForm(FlaskForm):
    schedule_type = StringField('نوع الجدولة', validators=[DataRequired()])
    interval = IntegerField('الفاصل الزمني (ساعات)', default=1)
    max_messages = IntegerField('الحد الأقصى للرسائل', default=10)
    is_active = BooleanField('نشط', default=True)
    submit = SubmitField('حفظ الجدولة')

# المشغل الخلفي
scheduler = BackgroundScheduler()
bot_workers = {}

def init_scheduler():
    """تهيئة المشغل الخلفي"""
    if not scheduler.running:
        scheduler.start()
        # إضافة مهمة لتحديث الإحصائيات كل 5 دقائق
        scheduler.add_job(
            update_statistics,
            IntervalTrigger(minutes=5),
            id='update_stats',
            replace_existing=True
        )

def update_statistics():
    """تحديث الإحصائيات في الخلفية"""
    with app.app_context():
        for bot in Bot.query.filter_by(is_active=True).all():
            stats = Statistics.query.filter_by(
                bot_id=bot.id,
                date=datetime.utcnow().date()
            ).first()
            
            if not stats:
                stats = Statistics(bot_id=bot.id)
                db.session.add(stats)
            
            # تحديث الإحصائيات من قاعدة البيانات
            stats.messages_sent = MessageLog.query.filter_by(
                bot_id=bot.id,
                status='sent'
            ).count()
            
            stats.messages_failed = MessageLog.query.filter_by(
                bot_id=bot.id,
                status='failed'
            ).count()
            
            stats.users_contacted = UserCollect.query.filter_by(
                group_id=Group.query.filter_by(bot_id=bot.id).first().id if Group.query.filter_by(bot_id=bot.id).first() else 0
            ).count()
            
            db.session.commit()

# المسارات
@app.route('/')
def index():
    """الصفحة الرئيسية"""
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """تسجيل الدخول"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.password == form.password.data:  # في الإنتاج استخدم hashing
            login_user(user)
            flash('تم تسجيل الدخول بنجاح!', 'success')
            return redirect(url_for('dashboard'))
        flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'danger')
    
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    """تسجيل الخروج"""
    logout_user()
    flash('تم تسجيل الخروج بنجاح', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    """لوحة التحكم"""
    # إحصائيات عامة
    total_bots = Bot.query.count()
    total_groups = Group.query.count()
    total_users = UserCollect.query.count()
    total_messages = MessageLog.query.filter_by(status='sent').count()
    
    # آخر النشاطات
    recent_logs = MessageLog.query.order_by(MessageLog.sent_at.desc()).limit(20).all()
    
    # إحصائيات البوتات
    bot_stats = []
    for bot in Bot.query.all():
        bot_stats.append({
            'id': bot.id,
            'name': bot.name or 'غير مسمى',
            'token': bot.token[:20] + '...',
            'is_active': bot.is_active,
            'messages': MessageLog.query.filter_by(bot_id=bot.id, status='sent').count(),
            'users': UserCollect.query.filter_by(
                group_id=Group.query.filter_by(bot_id=bot.id).first().id if Group.query.filter_by(bot_id=bot.id).first() else 0
            ).count()
        })
    
    return render_template('dashboard.html', 
                         total_bots=total_bots,
                         total_groups=total_groups,
                         total_users=total_users,
                         total_messages=total_messages,
                         bot_stats=bot_stats,
                         recent_logs=recent_logs)

@app.route('/bots', methods=['GET', 'POST'])
@login_required
def manage_bots():
    """إدارة البوتات"""
    form = BotForm()
    
    if form.validate_on_submit():
        # التحقق من وجود البوت
        existing_bot = Bot.query.filter_by(token=form.token.data).first()
        if existing_bot:
            flash('هذا البوت موجود بالفعل!', 'warning')
        else:
            bot = Bot(
                name=form.name.data,
                token=form.token.data,
                is_active=True
            )
            db.session.add(bot)
            db.session.commit()
            
            # تشغيل البوت
            try:
                worker = BotWorker(bot.id, form.token.data)
                bot_workers[bot.id] = worker
                worker.start()
            except Exception as e:
                flash(f'خطأ في تشغيل البوت: {str(e)}', 'warning')
            
            flash('تم إضافة البوت بنجاح!', 'success')
            return redirect(url_for('manage_bots'))
    
    bots = Bot.query.all()
    return render_template('groups.html', bots=bots, form=form, section='bots')

@app.route('/groups', methods=['GET', 'POST'])
@login_required
def manage_groups():
    """إدارة المجموعات"""
    form = GroupForm()
    form.bot_id.choices = [(b.id, b.name or b.token[:10]) for b in Bot.query.all()]
    
    if form.validate_on_submit():
        group = Group(
            group_id=form.group_id.data,
            title=form.title.data,
            bot_id=form.bot_id.data,
            is_active=True
        )
        db.session.add(group)
        db.session.commit()
        flash('تم إضافة المجموعة بنجاح!', 'success')
        return redirect(url_for('manage_groups'))
    
    groups = Group.query.all()
    return render_template('groups.html', groups=groups, form=form, section='groups')

@app.route('/statistics')
@login_required
def statistics():
    """صفحة الإحصائيات"""
    # إحصائيات البوتات
    bot_stats = []
    for bot in Bot.query.all():
        daily_stats = Statistics.query.filter_by(bot_id=bot.id).order_by(Statistics.date.desc()).limit(7).all()
        bot_stats.append({
            'bot': bot,
            'daily': daily_stats,
            'total_messages': MessageLog.query.filter_by(bot_id=bot.id, status='sent').count(),
            'total_failed': MessageLog.query.filter_by(bot_id=bot.id, status='failed').count(),
            'total_users': UserCollect.query.filter_by(
                group_id=Group.query.filter_by(bot_id=bot.id).first().id if Group.query.filter_by(bot_id=bot.id).first() else 0
            ).count()
        })
    
    # إحصائيات يومية
    today = datetime.utcnow().date()
    stats_today = Statistics.query.filter_by(date=today).all()
    
    return render_template('statistics.html', 
                         bot_stats=bot_stats,
                         stats_today=stats_today)

@app.route('/api/bot/<int:bot_id>/status')
@login_required
def bot_status_api(bot_id):
    """API لحالة البوت"""
    bot = Bot.query.get_or_404(bot_id)
    
    # تشغيل البوت إذا لم يكن يعمل
    if bot_id not in bot_workers:
        try:
            worker = BotWorker(bot_id, bot.token)
            bot_workers[bot_id] = worker
            worker.start()
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)})
    
    return jsonify({
        'status': 'running',
        'bot_id': bot_id,
        'is_active': bot.is_active,
        'total_messages_sent': bot.total_messages_sent,
        'total_users_collected': bot.total_users_collected,
        'last_activity': bot.last_activity.isoformat() if bot.last_activity else None
    })

@app.route('/api/bot/<int:bot_id>/toggle')
@login_required
def toggle_bot(bot_id):
    """تشغيل/إيقاف البوت"""
    bot = Bot.query.get_or_404(bot_id)
    bot.is_active = not bot.is_active
    db.session.commit()
    
    if bot.is_active and bot_id not in bot_workers:
        # تشغيل البوت
        worker = BotWorker(bot_id, bot.token)
        bot_workers[bot_id] = worker
        worker.start()
    elif not bot.is_active and bot_id in bot_workers:
        # إيقاف البوت
        bot_workers[bot_id].stop()
        del bot_workers[bot_id]
    
    return jsonify({
        'status': 'success',
        'is_active': bot.is_active
    })

@app.route('/api/send-message', methods=['POST'])
@login_required
def send_message_api():
    """إرسال رسالة عبر API"""
    data = request.json
    bot_id = data.get('bot_id')
    user_id = data.get('user_id')
    message = data.get('message')
    
    if not all([bot_id, user_id, message]):
        return jsonify({'error': 'بيانات غير مكتملة'}), 400
    
    bot = Bot.query.get_or_404(bot_id)
    
    # إرسال الرسالة
    if bot_id in bot_workers:
        success = bot_workers[bot_id].send_message(user_id, message)
        return jsonify({'success': success})
    
    return jsonify({'error': 'البوت غير نشط'}), 400

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """إعدادات النظام"""
    if request.method == 'POST':
        # تحديث الإعدادات
        admin_username = request.form.get('admin_username')
        admin_password = request.form.get('admin_password')
        
        if admin_username:
            admin = User.query.filter_by(is_admin=True).first()
            if admin:
                admin.username = admin_username
                if admin_password:
                    admin.password = admin_password  # في الإنتاج استخدم hashing
                db.session.commit()
                flash('تم تحديث الإعدادات بنجاح!', 'success')
    
    admin = User.query.filter_by(is_admin=True).first()
    return render_template('settings.html', admin=admin)

# إنشاء المستخدم المشرف الأول
def create_admin():
    with app.app_context():
        if not User.query.filter_by(is_admin=True).first():
            admin = User(
                username=os.getenv('ADMIN_USERNAME', 'admin'),
                password=os.getenv('ADMIN_PASSWORD', 'admin123'),
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()
            print('✅ تم إنشاء المستخدم المشرف')

# تهيئة التطبيق
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_admin()
        init_scheduler()
    
    # تشغيل التطبيق
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)