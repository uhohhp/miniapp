const API_URL = "/api";
const WEBAPP_TOKEN = "secret_token_123"; // В реальном проде берите из мета-тега или конфига

// Инициализация Telegram WebApp
const tg = window.Telegram.WebApp;
tg.expand();

// Определяем user_id. Если открыто не в ТГ — используем заглушку для тестов
const userId = tg.initDataUnsafe?.user?.id || 8164957125; 

// Элементы UI
const views = {
    courses: document.getElementById('courses-list'),
    topics: document.getElementById('topics-list')
};

// Запуск
document.addEventListener('DOMContentLoaded', () => {
    loadCourses();
});

async function loadCourses() {
    try {
        const res = await fetch(`${API_URL}/courses`);
        const courses = await res.json();
        const container = document.getElementById('courses-container');
        container.innerHTML = '';
        
        courses.forEach(course => {
            const el = document.createElement('div');
            el.className = 'card';
            el.innerHTML = `<h3>${course.title}</h3>`;
            el.onclick = () => loadTopics(course.id, course.title);
            container.appendChild(el);
        });
        showView('courses');
    } catch (e) {
        showNotification('Ошибка загрузки курсов', true);
    }
}

async function loadTopics(courseId, courseTitle) {
    document.getElementById('current-course-title').innerText = courseTitle;
    const container = document.getElementById('topics-container');
    container.innerHTML = 'Загрузка...';
    showView('topics');

    try {
        const res = await fetch(`${API_URL}/topics/${courseId}`);
        const topics = await res.json();
        container.innerHTML = '';

        if (topics.length === 0) {
            container.innerHTML = '<p>Нет тем в этом курсе</p>';
            return;
        }

        topics.forEach(topic => {
            const el = document.createElement('div');
            el.className = 'topic-item';
            
            let filesHtml = '';
            topic.files.forEach(file => {
                filesHtml += `<button class="file-btn" onclick="requestFile('${file.file_id}')">
                    Скачать ${file.name}
                </button>`;
            });

            el.innerHTML = `
                <h3>${topic.title}</h3>
                <div class="files-container">${filesHtml || 'Нет файлов'}</div>
            `;
            container.appendChild(el);
        });
    } catch (e) {
        container.innerHTML = 'Ошибка загрузки тем';
    }
}

async function requestFile(fileId) {
    if (!tg.initDataUnsafe?.user?.id) {
        // Если тестируем в браузере
        console.log("Тестовый режим: запрос файла", fileId);
    }

    try {
        const res = await fetch(`${API_URL}/request_file`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                telegram_id: userId,
                file_id: fileId,
                webapp_token: WEBAPP_TOKEN
            })
        });

        const data = await res.json();
        if (res.ok) {
            showNotification("✅ Файл отправлен в чат!");
            tg.HapticFeedback.notificationOccurred('success');
        } else {
            showNotification("❌ Ошибка: " + data.detail, true);
        }
    } catch (e) {
        showNotification("❌ Ошибка сети", true);
    }
}

function showView(viewName) {
    Object.values(views).forEach(v => v.classList.add('hidden'));
    views[viewName].classList.remove('hidden');
}

function showCourses() {
    showView('courses');
}

function filterTopics() {
    const query = document.getElementById('search').value.toLowerCase();
    const items = document.querySelectorAll('.topic-item');
    items.forEach(item => {
        const text = item.querySelector('h3').innerText.toLowerCase();
        item.style.display = text.includes(query) ? 'block' : 'none';
    });
}

function showNotification(msg, isError = false) {
    const el = document.getElementById('notification');
    el.innerText = msg;
    el.style.background = isError ? '#ff4444' : 'rgba(0,0,0,0.8)';
    el.classList.remove('hidden');
    setTimeout(() => el.classList.add('hidden'), 3000);
}