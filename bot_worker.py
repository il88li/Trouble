import threading
import time
import logging
from datetime import datetime
import requests
from database import db, Bot, Group, UserCollect, MessageLog

logger = logging.getLogger(__name__)

class BotWorker:
    """مشغل البوت في خلفية"""
    
    def __init__(self, bot_id, token):
        self.bot_id = bot_id
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.running = False
        self.thread = None
        self.last_update_id = 0
        self.users = {}
    
    def start(self):
        """بدء تشغيل البوت"""
        if self.thread and self.thread.is_alive():
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info(f"✅ بدء تشغيل البوت {self.bot_id}")
    
    def stop(self):
        """إيقاف البوت"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info(f"⏹️ إيقاف البوت {self.bot_id}")
    
    def _run(self):
        """الحلقة الرئيسية للبوت"""
        while self.running:
            try:
                # جلب التحديثات
                updates = self._get_updates()
                
                for update in updates:
                    self._process_update(update)
                
                # تحديث الإحصائيات
                self._update_stats()
                
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"خطأ في البوت {self.bot_id}: {e}")
                time.sleep(10)
    
    def _get_updates(self):
        """جلب التحديثات من تيليجرام"""
        try:
            params = {
                'offset': self.last_update_id + 1,
                'limit': 100,
                'timeout': 10
            }
            response = requests.post(f"{self.base_url}/getUpdates", data=params, timeout=30)
            data = response.json()
            
            if data.get('ok'):
                return data.get('result', [])
            return []
            
        except Exception as e:
            logger.error(f"خطأ في جلب التحديثات: {e}")
            return []
    
    def _process_update(self, update):
        """معالجة تحديث واحد"""
        try:
            if 'message' in update:
                message = update['message']
                self.last_update_id = update['update_id']
                
                # استخراج معلومات المستخدم
                user = message.get('from', {})
                chat = message.get('chat', {})
                
                # حفظ المستخدم
                self._save_user(user, chat)
                
        except Exception as e:
            logger.error(f"خطأ في معالجة التحديث: {e}")
    
    def _save_user(self, user, chat):
        """حفظ المستخدم في قاعدة البيانات"""
        try:
            user_id = str(user.get('id'))
            
            # جلب المجموعة
            group = Group.query.filter_by(group_id=str(chat.get('id'))).first()
            if not group:
                return
            
            # حفظ المستخدم
            existing = UserCollect.query.filter_by(
                user_id=user_id,
                group_id=group.id
            ).first()
            
            if not existing:
                new_user = UserCollect(
                    user_id=user_id,
                    username=user.get('username'),
                    first_name=user.get('first_name'),
                    last_name=user.get('last_name'),
                    group_id=group.id,
                    collected_at=datetime.utcnow()
                )
                db.session.add(new_user)
                db.session.commit()
                logger.info(f"📥 مستخدم جديد: {user_id}")
            
        except Exception as e:
            logger.error(f"خطأ في حفظ المستخدم: {e}")
    
    def _update_stats(self):
        """تحديث الإحصائيات"""
        try:
            # تحديث عدد المستخدمين
            bot = Bot.query.get(self.bot_id)
            if bot:
                groups = Group.query.filter_by(bot_id=self.bot_id).all()
                total_users = 0
                for group in groups:
                    count = UserCollect.query.filter_by(group_id=group.id).count()
                    total_users += count
                
                bot.total_users_collected = total_users
                db.session.commit()
                
        except Exception as e:
            logger.error(f"خطأ في تحديث الإحصائيات: {e}")
    
    def send_message(self, user_id, message):
        """إرسال رسالة"""
        try:
            params = {
                'chat_id': user_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(f"{self.base_url}/sendMessage", data=params, timeout=30)
            data = response.json()
            
            success = data.get('ok', False)
            
            # تسجيل الرسالة
            log = MessageLog(
                bot_id=self.bot_id,
                user_id=str(user_id),
                message_text=message,
                status='sent' if success else 'failed',
                sent_at=datetime.utcnow()
            )
            db.session.add(log)
            db.session.commit()
            
            return success
            
        except Exception as e:
            logger.error(f"خطأ في إرسال الرسالة: {e}")
            return False