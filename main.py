import os
import sqlite3
import uuid
from fastapi import FastAPI, HTTPException, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

# --- إعداد التطبيق ---
app = FastAPI()

# تفعيل CORS للسماح بالاتصال من المتصفح
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- إعداد قاعدة البيانات ---
DB_NAME = "royal_platform.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # جدول الطلاب
    c.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            grade TEXT,
            school_name TEXT,
            avatar_url TEXT,
            xp INTEGER DEFAULT 0
        )
    ''')
    # جدول النتائج
    c.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            student_name TEXT,
            lesson TEXT,
            score INTEGER,
            total INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # جدول الامتحانات المجدولة
    c.execute('''
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            exam_type TEXT,
            exam_date TEXT,
            exam_time TEXT,
            target_lesson TEXT,
            duration INTEGER,
            num_questions INTEGER,
            points_per_q INTEGER,
            target_q_type TEXT
        )
    ''')
    conn.commit()
    conn.close()

# تشغيل قاعدة البيانات عند البدء
init_db()

# --- ربط الملفات الثابتة (الصور والتنسيقات) ---
# تأكد أن لديك مجلد اسمه static ومجلد اسمه uploads
os.makedirs("static", exist_ok=True)
os.makedirs("uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# --- مسارات الصفحات (HTML) ---
@app.get("/")
async def read_index():
    return FileResponse("index.html")

@app.get("/student.html")
async def read_student():
    return FileResponse("student.html")

@app.get("/admin.html")
async def read_admin():
    try:
        return FileResponse("admin.html")
    except:
        return "Admin page not found"

@app.get("/parent.html")
async def read_parent():
    return FileResponse("parent.html")

# --- مسارات API (تسجيل الدخول والطلاب) ---

@app.post("/api/student/register")
async def register_student(
    full_name: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    grade: str = Form(...),
    school_name: str = Form(""),
    avatar_url: str = Form("")
):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute(
            "INSERT INTO students (full_name, username, password, grade, school_name, avatar_url, xp) VALUES (?, ?, ?, ?, ?, ?, 0)",
            (full_name, username, password, grade, school_name, avatar_url)
        )
        conn.commit()
        return {"status": "success", "message": "تم التسجيل بنجاح"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="اسم المستخدم موجود مسبقاً")
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/student/login")
async def login_student(username: str = Form(...), password: str = Form(...)):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    user = c.execute("SELECT * FROM students WHERE username = ? AND password = ?", (username, password)).fetchone()
    conn.close()
    
    if user:
        return {"status": "success", "user": dict(user)}
    else:
        raise HTTPException(status_code=401, detail="بيانات غير صحيحة")

@app.post("/api/student/update")
async def update_student(
    student_id: int = Form(...),
    full_name: str = Form(...),
    school_name: str = Form(...),
    avatar_url: str = Form(...)
):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE students SET full_name=?, school_name=?, avatar_url=? WHERE id=?", 
              (full_name, school_name, avatar_url, student_id))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.get("/api/leaderboard")
async def get_leaderboard():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    # تجميع النقاط من جدول النتائج + الـ XP الأساسي
    rows = conn.execute("SELECT full_name as student_name, xp as total_points FROM students ORDER BY xp DESC LIMIT 10").fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.post("/api/student/results")
async def save_result(
    student_id: int = Form(...),
    score: int = Form(...),
    lesson: str = Form(...),
    total: int = Form(...)
):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # تحديث نقاط الطالب
    c.execute("UPDATE students SET xp = xp + ? WHERE id = ?", (score * 10, student_id))
    # حفظ النتيجة
    c.execute("INSERT INTO results (student_id, lesson, score, total) VALUES (?, ?, ?, ?)", 
              (student_id, lesson, score, total))
    conn.commit()
    conn.close()
    return {"status": "success"}

# --- تشغيل السيرفر ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
