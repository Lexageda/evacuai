# EvacuAI — Cebu Campus Evacuation System

## Quick Start
```bash
cd evacuai
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
python app.py
```
Open: http://127.0.0.1:5000

## Default Admin Login
- Student ID: `ADMIN001`
- Password: `admin123`

## Adding Students (Admin side)
1. Log in as admin
2. Go to Student Management
3. Add individually OR upload CSV

## CSV Format
```
student_id,name,password,role
2024-00001,Juan Dela Cruz,temp123,student
2024-00002,Maria Santos,temp456,student
```

## Files to copy after download
- app.py
- database.py  
- requirements.txt
- templates/ (all .html files)
- static/css/style.css
- static/map.obj + map.mtl (your Tinkercad export)
