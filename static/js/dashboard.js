// تحديث الإحصائيات تلقائياً
function refreshStats() {
    fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
            // تحديث الأرقام
            document.getElementById('total-bots').textContent = data.total_bots;
            document.getElementById('total-groups').textContent = data.total_groups;
            document.getElementById('total-users').textContent = data.total_users;
            document.getElementById('total-messages').textContent = data.total_messages;
        })
        .catch(error => console.error('Error:', error));
}

// تحديث كل 30 ثانية
setInterval(refreshStats, 30000);

// إدارة البوتات
document.querySelectorAll('.toggle-bot').forEach(button => {
    button.addEventListener('click', function() {
        const botId = this.dataset.botId;
        fetch(`/api/bot/${botId}/toggle`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                location.reload();
            }
        })
        .catch(error => console.error('Error:', error));
    });
});

// إرسال رسالة مخصصة
document.querySelector('#send-message-form')?.addEventListener('submit', function(e) {
    e.preventDefault();
    
    const botId = document.getElementById('bot-select').value;
    const userId = document.getElementById('user-id').value;
    const message = document.getElementById('message-text').value;
    
    fetch('/api/send-message', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            bot_id: botId,
            user_id: userId,
            message: message
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('✅ تم إرسال الرسالة بنجاح!');
            document.getElementById('message-text').value = '';
        } else {
            alert('❌ فشل إرسال الرسالة');
        }
    })
    .catch(error => {
        alert('❌ خطأ في الاتصال');
        console.error(error);
    });
});

// تصدير الإحصائيات
function exportStats() {
    window.location.href = '/api/export-stats';
}

// إظهار/إخفاء التفاصيل
function toggleDetails(elementId) {
    const element = document.getElementById(elementId);
    if (element.style.display === 'none') {
        element.style.display = 'block';
    } else {
        element.style.display = 'none';
    }
}