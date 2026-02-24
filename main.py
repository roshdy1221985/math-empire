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
    conn = sqlite3.connect('royal_platform.db')
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
# --- مسارات الاختبارات المجدولة والإشعارات (محدثة) ---
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
        conn.execute('INSERT INTO students (full_name, username, password, grade, school_name, avatar_url) VALUES (?, ?, ?, ?, ?, ?)', 
                     (full_name, username, password, grade, school_name, avatar_url))
        conn.commit()
        return {"status": "success", "message": "تم انضمام البطل لجيش الرياضيات"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="اسم المستخدم موجود مسبقاً")
    finally:
        conn.close()

@app.post("/api/student/login")
async def login_student(username: str = Form(...), password: str = Form(...)):
    conn = get_db()
    user = conn.execute('SELECT * FROM students WHERE username = ? AND password = ?', (username, password)).fetchone()
    conn.close()
    if user:
        return {"status": "success", "user": dict(user)}
    raise HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة")

@app.post("/api/student/update")
async def update_student(
    student_id: int = Form(...),
    full_name: str = Form(...),
    school_name: str = Form(None),
    avatar_url: str = Form(None)
):
    conn = get_db()
    conn.execute(
        'UPDATE students SET full_name=?, school_name=?, avatar_url=? WHERE id=?',
        (full_name, school_name, avatar_url, student_id)
    )
    conn.commit()
    conn.close()
    return {"status": "success"}

# ==========================================
# --- مسارات الطلاب (النتائج والملفات) ---
# ==========================================

@app.post("/api/student/results")
async def save_result(student_id: int = Form(...), student_name: str = Form(...), lesson: str = Form(...), score: int = Form(...), total: int = Form(...)):
    conn = get_db()
    conn.execute('INSERT INTO results (student_id, student_name, lesson, score, total) VALUES (?, ?, ?, ?, ?)', 
                 (student_id, student_name, lesson, score, total))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.get("/api/leaderboard")
async def get_leaderboard():
    conn = get_db()
    query = '''
        SELECT student_name, (SUM(score) * 100) as total_points 
        FROM results 
        GROUP BY student_name 
        ORDER BY total_points DESC 
        LIMIT 10
    '''
    rows = conn.execute(query).fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.get("/api/student/summaries/{lesson:path}")
async def get_student_summary(lesson: str):
    lesson_decoded = unquote(lesson) 
    conn = get_db()
    row = conn.execute("SELECT pdf_url FROM summaries WHERE lesson = ?", (lesson_decoded,)).fetchone()
    conn.close()
    if row:
        return {"pdf_url": row["pdf_url"]}
    return {"pdf_url": None}

# ==========================================
# --- مسار بوابة ولي الأمر (Parent Portal) ---
# ==========================================

@app.get("/api/parent/search/{name:path}")
async def parent_search(name: str):
    name_decoded = unquote(name)
    conn = get_db()
    student = conn.execute("SELECT id, full_name, grade, school_name FROM students WHERE full_name LIKE ?", (f"%{name_decoded}%",)).fetchone()
    if not student:
        conn.close()
        return {"found": False}
    
    results = conn.execute("SELECT lesson, score, total, timestamp FROM results WHERE student_id = ? ORDER BY timestamp DESC", (student["id"],)).fetchall()
    total_points_row = conn.execute("SELECT SUM(score) * 100 FROM results WHERE student_id = ?", (student["id"],)).fetchone()
    total_points = total_points_row[0] if total_points_row[0] else 0
    
    conn.close()
    return {
        "found": True,
        "student": dict(student),
        "total_xp": total_points,
        "history": [dict(r) for r in results]
    }

# ==========================================
# --- مسارات المعلم (Admin) ---
# ==========================================

@app.get("/api/admin/stats")
async def get_student_stats():
    conn = get_db()
    query = '''
        SELECT s.full_name, s.grade, COUNT(r.id) as tests_count, AVG(r.score) as avg_score, MAX(r.timestamp) as last_activity
        FROM students s
        LEFT JOIN results r ON s.id = r.student_id
        GROUP BY s.id
    '''
    rows = conn.execute(query).fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.post("/api/admin/summaries")
async def upload_summary(lesson: str = Form(...), pdf: UploadFile = File(...)):
    conn = get_db()
    old_row = conn.execute("SELECT pdf_url FROM summaries WHERE lesson=?", (lesson,)).fetchone()
    if old_row and old_row["pdf_url"]:
        old_file_path = os.path.join(BASE_DIR, old_row["pdf_url"])
        if os.path.exists(old_file_path):
            try: os.remove(old_file_path)
            except: pass

    ext = os.path.splitext(pdf.filename)[1]
    safe_name = f"summary_{uuid.uuid4().hex}{ext}"
    pdf_path = f"uploads/{safe_name}"
    
    with open(os.path.join(BASE_DIR, pdf_path), "wb") as buffer:
        shutil.copyfileobj(pdf.file, buffer)
        
    conn.execute('INSERT OR REPLACE INTO summaries (lesson, pdf_url) VALUES (?, ?)', (lesson, pdf_path))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.get("/api/admin/summaries_list")
async def get_all_summaries():
    conn = get_db()
    rows = conn.execute("SELECT lesson, pdf_url FROM summaries").fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.delete("/api/admin/summaries/{lesson_name:path}")
async def delete_summary(lesson_name: str):
    lesson_decoded = unquote(lesson_name)
    conn = get_db()
    row = conn.execute("SELECT pdf_url FROM summaries WHERE lesson=?", (lesson_decoded,)).fetchone()
    if row and row["pdf_url"]:
        file_path = os.path.join(BASE_DIR, row["pdf_url"])
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass
            
    conn.execute("DELETE FROM summaries WHERE lesson=?", (lesson_decoded,))
    conn.commit()
    conn.close()
    return {"message": "Deleted successfully"}

@app.post("/api/admin/questions")
async def add_question(
    grade: str = Form(...), 
    lesson: str = Form(...), 
    subject: str = Form(...), 
    q_type: str = Form(...), 
    question: str = Form(...), 
    options: str = Form(""), 
    answer: str = Form(...), 
    image: UploadFile = File(None)
):
    img_path = ""
    if image:
        ext = os.path.splitext(image.filename)[1]
        safe_img_name = f"img_{uuid.uuid4().hex}{ext}"
        img_path = f"uploads/{safe_img_name}"
        with open(os.path.join(BASE_DIR, img_path), "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
            
    conn = get_db()
    conn.execute('INSERT INTO questions (grade, lesson, subject, q_type, question, options, answer, image_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', 
                 (grade, lesson, subject, q_type, question, options, answer, img_path))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.put("/api/admin/questions/{q_id}")
async def edit_question(
    q_id: int,
    grade: str = Form(...), 
    lesson: str = Form(...), 
    subject: str = Form(...), 
    q_type: str = Form(...), 
    question: str = Form(...), 
    options: str = Form(""), 
    answer: str = Form(...), 
    image: UploadFile = File(None)
):
    conn = get_db()
    if image:
        ext = os.path.splitext(image.filename)[1]
        safe_img_name = f"img_{uuid.uuid4().hex}{ext}"
        img_path = f"uploads/{safe_img_name}"
        with open(os.path.join(BASE_DIR, img_path), "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        conn.execute('UPDATE questions SET grade=?, lesson=?, subject=?, q_type=?, question=?, options=?, answer=?, image_url=? WHERE id=?', 
                     (grade, lesson, subject, q_type, question, options, answer, img_path, q_id))
    else:
        conn.execute('UPDATE questions SET grade=?, lesson=?, subject=?, q_type=?, question=?, options=?, answer=? WHERE id=?', 
                     (grade, lesson, subject, q_type, question, options, answer, q_id))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.delete("/api/admin/questions/{q_id}")
async def delete_question(q_id: int):
    conn = get_db()
    conn.execute("DELETE FROM questions WHERE id=?", (q_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.get("/api/admin/results")
async def get_results():
    conn = get_db()
    rows = conn.execute("SELECT * FROM results ORDER BY timestamp DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.get("/api/admin/questions")
async def get_questions():
    conn = get_db()
    rows = conn.execute("SELECT * FROM questions ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ==========================================
# --- مسارات واجهات المنصة (HTML) ---
# ==========================================

@app.get("/")
async def get_index():
    # تأكد أن ملف الصفحة الرئيسية الذي به الـ 3 بوابات اسمه index.html
    return FileResponse("index.html")

@app.get("/student.html")
async def get_student_page():
    return FileResponse("student.html")

@app.get("/parent.html")
async def get_parent_page():
    return FileResponse("parent.html")

@app.get("/admin.html")
async def get_admin_page():
    return FileResponse("admin.html")


if __name__ == "__main__":
    import uvicorn
    print("🚀 إمبراطورية الرياضيات الملكية جاهزة لاستقبال بيانات الأبطال والامتحانات المجدولة...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)