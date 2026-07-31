from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import json

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Bot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    token = db.Column(db.String(255), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity = db.Column(db.DateTime)
    total_messages_sent = db.Column(db.Integer, default=0)
    total_users_collected = db.Column(db.Integer, default=0)
    
    groups = db.relationship('Group', backref='bot', lazy=True)
    statistics = db.relationship('Statistics', backref='bot', lazy=True)
    
    def __repr__(self):
        return f'<Bot {self.name or self.token[:10]}>'

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(200))
    bot_id = db.Column(db.Integer, db.ForeignKey('bot.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    member_count = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<Group {self.group_id}>'

class UserCollect(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), nullable=False)
    username = db.Column(db.String(100))
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))
    collected_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_message_at = db.Column(db.DateTime)
    messages_received = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<User {self.user_id}>'

class Statistics(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bot_id = db.Column(db.Integer, db.ForeignKey('bot.id'))
    date = db.Column(db.Date, default=datetime.utcnow().date)
    messages_sent = db.Column(db.Integer, default=0)
    messages_failed = db.Column(db.Integer, default=0)
    users_contacted = db.Column(db.Integer, default=0)
    active_users = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<Stats {self.date}>'

class MessageLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bot_id = db.Column(db.Integer, db.ForeignKey('bot.id'))
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))
    user_id = db.Column(db.String(50))
    message_text = db.Column(db.Text)
    status = db.Column(db.String(20))  # sent, failed, pending
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    error_message = db.Column(db.Text)
    
    def __repr__(self):
        return f'<MessageLog {self.id}>'

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bot_id = db.Column(db.Integer, db.ForeignKey('bot.id'))
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))
    schedule_type = db.Column(db.String(20))  # hourly, daily, weekly
    interval = db.Column(db.Integer)  # 1-24 hours
    max_messages = db.Column(db.Integer, default=10)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_run = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<Schedule {self.id}>'