import sqlite3

# الاتصال بقاعدة البيانات
conn = sqlite3.connect('math_platform.db')
cursor = conn.cursor()

print("جاري تحديث قاعدة البيانات...")

try:
    # محاولة إضافة عمود student_id لجدول النتائج
    cursor.execute("ALTER TABLE results ADD COLUMN student_id INTEGER")
    print("✅ تم إضافة عمود 'student_id' لجدول النتائج.")
except sqlite3.OperationalError:
    print("ℹ️ ملاحظة: عمود 'student_id' موجود بالفعل.")

try:
    # محاولة إضافة عمود school_name لجدول الطلاب
    cursor.execute("ALTER TABLE students ADD COLUMN school_name TEXT")
    print("✅ تم إضافة عمود 'school_name' لجدول الطلاب.")
except sqlite3.OperationalError:
    print("ℹ️ ملاحظة: عمود 'school_name' موجود بالفعل.")

try:
    # محاولة إضافة عمود avatar_url لجدول الطلاب
    cursor.execute("ALTER TABLE students ADD COLUMN avatar_url TEXT")
    print("✅ تم إضافة عمود 'avatar_url' لجدول الطلاب.")
except sqlite3.OperationalError:
    print("ℹ️ ملاحظة: عمود 'avatar_url' موجود بالفعل.")

conn.commit()
conn.close()
print("🚀 تم تحديث هيكل قاعدة البيانات بنجاح!")