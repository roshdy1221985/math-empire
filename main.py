import os
import shutil
import sqlite3
import uuid 
from urllib.parse import unquote 
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

# --- 1. إعداد المجلدات ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
STATIC_FOLDER = os.path.join(BASE_DIR, "static")
COMICS_FOLDER = os.path.join(BASE_DIR, "uploads", "comics")

for folder in [UPLOAD_FOLDER, STATIC_FOLDER, COMICS_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# --- إدارة الخزنة الملكية (Database) ---
def get_db():
    # نستخدم check_same_thread=False للعمل بسلاسة على السيرفر
    conn = sqlite3.connect('royal_platform.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    # إنشاء الجداول (كما هي في كودك المرجعي)
    conn.execute('''CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT, username TEXT UNIQUE, 
        password TEXT, grade TEXT, school_name TEXT, avatar_url TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, grade TEXT, lesson TEXT, subject TEXT, 
        q_type TEXT, question TEXT, options TEXT, answer TEXT, image_url TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, student_name TEXT,
        lesson TEXT, score INTEGER, total INTEGER, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS summaries (id INTEGER PRIMARY KEY AUTOINCREMENT, lesson TEXT UNIQUE, pdf_url TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS comics (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, image_url TEXT, grade TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS exams (
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, exam_type TEXT, exam_date TEXT, 
        exam_time TEXT, target_lesson TEXT, duration INTEGER DEFAULT 15, 
        num_questions INTEGER DEFAULT 10, points_per_q INTEGER DEFAULT 10, target_q_type TEXT DEFAULT 'all')''')
    conn.commit()
    conn.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=UPLOAD_FOLDER), name="uploads")
app.mount("/static", StaticFiles(directory=STATIC_FOLDER), name="static")

# ==========================================
# --- نظام الدخول والتسجيل (الإصلاح الجوهري هنا) ---
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
        # تنظيف البيانات من المسافات الزائدة
        u_name = username.strip()
        conn.execute('INSERT INTO students (full_name, username, password, grade, school_name, avatar_url) VALUES (?, ?, ?, ?, ?, ?)', 
                     (full_name, u_name, password.strip(), grade, school_name, avatar_url))
        conn.commit()
        return {"status": "success", "message": "تم انضمام البطل لجيش الرياضيات"}
    except sqlite3.IntegrityError:
        return JSONResponse(status_code=400, content={"status": "error", "message": "اسم المستخدم موجود مسبقاً"})
    finally:
        conn.close()

@app.post("/api/student/login")
async def login_student(username: str = Form(...), password: str = Form(...)):
    conn = get_db()
    # تنظيف البيانات لضمان التطابق
    u_name = username.strip()
    u_pass = password.strip()
    
    user = conn.execute('SELECT * FROM students WHERE username = ? AND password = ?', (u_name, u_pass)).fetchone()
    conn.close()
    
    if user:
        # تحويل الصف إلى قاموس ليرسله للمتصفح
        user_data = dict(user)
        return {"status": "success", "user": user_data}
    
    # نرسل 401 إذا لم يجد المستخدم
    raise HTTPException(status_code=401, detail="اسم المستخدم أو كلمة المرور غير صحيحة")

# ==========================================
# --- المسارات الأخرى (بقية كودك المرجعي) ---
# ==========================================

@app.get("/")
async def get_index(): return FileResponse("index.html")

@app.get("/student.html")
async def get_student_page(): return FileResponse("student.html")

@app.get("/parent.html")
async def get_parent_page(): return FileResponse("parent.html")

@app.get("/admin.html")
async def get_admin_page(): return FileResponse("admin.html")

# (ملاحظة: أضف بقية مسارات النتائج والامتحانات من كودك الأصلي هنا)

if __name__ == "__main__":
    import uvicorn
    # في Render نستخدم المنفذ من نظام التشغيل
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
