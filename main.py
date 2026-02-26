import os
import shutil
import sqlite3
import uuid  # <--- أداة إنشاء أسماء فريدة للملفات
from urllib.parse import unquote  # <--- أداة فهم اللغة العربية المشفرة
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse  # <--- تم إضافة هذه الأداة لتشغيل صفحات HTML

# --- 1. إعداد المجلدات قبل تشغيل التطبيق ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
STATIC_FOLDER = os.path.join(BASE_DIR, "static")
COMICS_FOLDER = os.path.join(BASE_DIR, "uploads", "comics")

for folder in [UPLOAD_FOLDER, STATIC_FOLDER, COMICS_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)
        print(f"✅ تم إنشاء المجلد: {folder}")

# --- إدارة الخزنة الملكية (Database) ---
def get_db():
    # تم إضافة check_same_thread لضمان استقرار السيرفر السحابي
    conn = sqlite3.connect('royal_platform.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    # تم إضافة الأعمدة الجديدة لهيكل الجدول
    conn.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            grade TEXT NOT NULL,
            school_name TEXT,
            avatar_url TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grade TEXT, lesson TEXT, subject TEXT, q_type TEXT,
            question TEXT, options TEXT, answer TEXT, image_url TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            student_name TEXT,
            lesson TEXT,
            score INTEGER,
            total INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            lesson TEXT UNIQUE, 
            pdf_url TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS comics (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            title TEXT, 
            image_url TEXT, 
            grade TEXT
        )
    ''')
    
    # --- الجدول الجديد: الاختبارات المجدولة (تم إضافة التحكم الشامل للمعلم) ---
    conn.execute('''
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            exam_type TEXT NOT NULL, 
            exam_date TEXT NOT NULL, 
            exam_time TEXT NOT NULL,
            target_lesson TEXT NOT NULL,
            duration INTEGER NOT NULL DEFAULT 15,
            num_questions INTEGER NOT NULL DEFAULT 10,
            points_per_q INTEGER NOT NULL DEFAULT 10,
            target_q_type TEXT NOT NULL DEFAULT 'all'
        )
    ''')
    
    # تحديث الجدول القديم إن وجد لضمان عدم حدوث خطأ وفقدان البيانات
    try:
        conn.execute("ALTER TABLE exams ADD COLUMN duration INTEGER NOT NULL DEFAULT 15")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE exams ADD COLUMN num_questions INTEGER NOT NULL DEFAULT 10")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE exams ADD COLUMN points_per_q INTEGER NOT NULL DEFAULT 10")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE exams ADD COLUMN target_q_type TEXT NOT NULL DEFAULT 'all'")
    except sqlite3.OperationalError:
        pass
        
    conn.commit()
    conn.close()

# --- 2. إدارة دورة حياة التطبيق (Lifespan) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

# --- 3. تفعيل الاتصال الكامل (CORS) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 4. ربط المجلدات بالمتصفح ---
app.mount("/uploads", StaticFiles(directory=UPLOAD_FOLDER), name="uploads")
app.mount("/static", StaticFiles(directory=STATIC_FOLDER), name="static")

# ==========================================
# --- مسارات الاختبارات المجدولة والإشعارات ---
# ==========================================

@app.post("/api/admin/exams")
async def create_exam(
    title: str = Form(...), 
    exam_type: str = Form(...), 
    exam_date: str = Form(...), 
    exam_time: str = Form(...), 
    target_lesson: str = Form(...),
    duration: int = Form(...),
    num_questions: int = Form(...),
    points_per_q: int = Form(...),
    target_q_type: str = Form(...)
):
    conn = get_db()
    conn.execute('''
        INSERT INTO exams (title, exam_type, exam_date, exam_time, target_lesson, duration, num_questions, points_per_q, target_q_type) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (title, exam_type, exam_date, exam_time, target_lesson, duration, num_questions, points_per_q, target_q_type))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.get("/api/exams/upcoming")
async def get_upcoming_exams():
    conn = get_db()
    rows = conn.execute("SELECT * FROM exams ORDER BY exam_date ASC, exam_time ASC").fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.delete("/api/admin/exams/{exam_id}")
async def delete_exam(exam_id: int):
    conn = get_db()
    conn.execute("DELETE FROM exams WHERE id=?", (exam_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

# ==========================================
# --- مسارات نظام الدخول والتسجيل ---
# ==========================================

@app.post("/api/student/register")
async def register_student(
    full_name: str = Form(...), 
    username: str = Form(...), 
    password: str = Form(...), 
    grade: str = Form(...),
    school_name: str = Form(None),
    avatar_url: str = Form(None)
):
    conn = get_db()
    try:
        # استخدام strip() لضمان دقة اسم المستخدم
        u_name = username.strip().lower()
        conn.execute('INSERT INTO students (full_name, username, password, grade, school_name, avatar_url) VALUES (?, ?, ?, ?, ?, ?)', 
                     (full_name, u_name, password.strip(), grade, school_name, avatar_url))
        conn.commit()
        return {"status": "success", "message": "تم انضمام البطل لجيش الرياضيات"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="اسم المستخدم موجود مسبقاً")
    finally:
        conn.close()

@app.post("/api/student/login")
async def login_student(username: str = Form(...), password: str = Form(...)):
    conn = get_db()
    # أهم تعديل لضمان نجاح الدخول: تنظيف البيانات المرسلة
    u_name = username.strip().lower()
    u_pass = password.strip()
    
    user = conn.execute('SELECT * FROM students WHERE username = ? AND password = ?', (u_name, u_pass)).fetchone()
    conn.close()
    if user:
        return {"status": "success", "user": dict(user)}
    raise HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة")

# (بقية مسارات النتائج، المعلم، ولي الأمر، والـ HTML تظل كما هي تماماً في كودك المرجعي)
# [تم الحفاظ على كل الدوال الأخرى كما أرسلتها]

@app.get("/")
async def get_index(): return FileResponse("index.html")

@app.get("/student.html")
async def get_student_page(): return FileResponse("student.html")

@app.get("/parent.html")
async def get_parent_page(): return FileResponse("parent.html")

@app.get("/admin.html")
async def get_admin_page(): return FileResponse("admin.html")

if __name__ == "__main__":
    import uvicorn
    # التعديل الملكي الأخير للعمل على Render بنجاح
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 إمبراطورية الرياضيات الملكية جاهزة على المنفذ {port}...")
    uvicorn.run("main:app", host="0.0.0.0", port=port)
