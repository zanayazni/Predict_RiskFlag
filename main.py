# Import necessary libraries
import joblib
import pymysql
import uvicorn
import numpy as np
import bcrypt
import mlflow
import ollama
import re
from pydantic import BaseModel
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import JSONResponse
from pyngrok import ngrok
import pandas as pd
from fastapi.middleware.cors import CORSMiddleware

# Create MySQL connection
conn = pymysql.connect(
    host="localhost",      # Host XAMPP
    user="root",           # Username MySQL (default XAMPP)
    password="",           # Password MySQL (default XAMPP kosong)
    database="fastapi_db"  # Nama database yang dibuat di phpMyAdmin
)
cursor = conn.cursor()

# Setup ngrok, load token from .env
NGROK_TOKEN = "2tsvr0e52TVnMuzMSKuFm5OUJ8C_6fzhGmrPvG7fVofSXLhiW"
ngrok.set_auth_token(NGROK_TOKEN)

# Create table for logging request data
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(255) NOT NULL UNIQUE,
        password VARCHAR(255) NOT NULL
    )
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS predictions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT,
        income INT,
        age INT,
        experience INT,
        married_single VARCHAR(50),
        house_ownership VARCHAR(50),
        car_ownership VARCHAR(50),
        profession VARCHAR(255),
        city VARCHAR(255),
        state VARCHAR(255),
        current_job_yrs INT,
        current_house_yrs INT,
        risk_flag INT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
""")
conn.commit()

# Create a FastAPI instance
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://*.streamlit.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
security = HTTPBasic()

# Load model and preprocessing tools
model = joblib.load("model.pkl")
label_encoders = joblib.load("label_encoders.pkl")

# Create Pydantic model for input data
class InputData(BaseModel):
    Income: int
    Age: int
    Experience: int
    Married_Single: str
    House_Ownership: str
    Car_Ownership: str
    Profession: str
    CITY: str
    STATE: str
    CURRENT_JOB_YRS: int
    CURRENT_HOUSE_YRS: int

class FinancialProfile(BaseModel):
    profile_text: str

def extract_user_profile(user_input):
    """
    Mengekstrak informasi dari input pengguna menjadi dictionary user_profile.

    Args:
        user_input (str): Input user dalam bentuk kalimat.

    Returns:
        dict: Profil user yang telah diekstrak.
    """
    usia = re.search(r'(\d{2})\s*tahun', user_input)
    pendapatan = re.search(r'(\d+)\s*(?:juta|jt|ribu|rb)?', user_input, re.IGNORECASE)
    riwayat_kredit = re.search(r'\b(baik|buruk|sedang)\b', user_input, re.IGNORECASE)

    user_profile = {
        "usia": int(usia.group(1)) if usia else None,
        "pendapatan": int(pendapatan.group(1)) * 1_000_000 if pendapatan else None,  # Konversi ke juta
        "riwayat_kredit": riwayat_kredit.group(1).capitalize() if riwayat_kredit else "Tidak diketahui",
    }

    return user_profile

def generate_recommendation(user_profile):
    """
    Menghasilkan rekomendasi produk keuangan berdasarkan profil pengguna.

    Args:
        user_profile (dict): Dictionary berisi informasi user.

    Returns:
        str: Rekomendasi produk keuangan.
    """
    prompt = f"""
     Berikan rekomendasi produk keuangan spesifik untuk pengguna dengan detail berikut:
    - Usia: {user_profile['usia']} tahun
    - Pendapatan: {user_profile['pendapatan']} per tahun
    - Riwayat kredit: {user_profile['riwayat_kredit']}
    
    Rekomendasi harus:
    1. Langsung ke poin utama tanpa kalimat pengantar
    2. Spesifik dengan nama produk dan lembaga keuangan
    3. Sertakan alasan singkat untuk setiap rekomendasi
    4. Format dalam poin-poin
    """

    try:
        response = ollama.chat(model="mistral", messages=[{"role": "user", "content": prompt}])
        recommendation = response["message"]["content"]
        unwanted_phrases = [
            "Bagi pengguna dengan usia",
            "berbagai produk keuangan dapat menjadi pilihan yang tepat",
            "produk keuangan yang cocok"
        ]
        
        for phrase in unwanted_phrases:
            recommendation = recommendation.replace(phrase, "")
            
        return recommendation.strip()
    except Exception as e:
        recommendation = f"Error generating recommendation: {e}"

    return recommendation

def log_recommendation(user_profile):
    """
    Mencatat profil user dan rekomendasi ke dalam MLflow.

    Args:
        user_profile (dict): Dictionary profil user.
    """
    with mlflow.start_run():
        mlflow.log_params(user_profile)
        recommendation = generate_recommendation(user_profile)
        mlflow.log_text(recommendation, "recommendation.txt")
        return recommendation


# Hashing password
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

# functions for encoding
def safe_transform(label_encoder, value):
    return label_encoder.transform([value])[0] if value in label_encoder.classes_ else 0

def target_encode(value, encoding_dict):
    return encoding_dict.get(value, 0.5)



class UserRegistration(BaseModel):
    username: str
    password: str

@app.post("/register")
def register_user(user: UserRegistration):
    cursor.execute("SELECT username FROM users WHERE username = %s", (user.username,))
    existing_user = cursor.fetchone()
    if existing_user:
        return JSONResponse(content={"message": "Username already exists"}, status_code=400)
    
    hashed_password = hash_password(user.password)
    cursor.execute("""
        INSERT INTO users (username, password) 
        VALUES (%s, %s)
    """, (user.username, hashed_password))
    conn.commit()
    
    return JSONResponse(content={"message": "User registered successfully"})



# Authentication function
def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    cursor.execute("SELECT username, password FROM users WHERE username = %s", (credentials.username,))
    user = cursor.fetchone()
    if user and verify_password(credentials.password, user[1]):
        return credentials.username
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Basic"},
    )


# Endpoint untuk login
@app.post("/login")
def login(username: str = Depends(get_current_user)):
    # Ambil informasi pengguna dari database
    cursor.execute("SELECT id, username FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_id, username = user
    
    return JSONResponse(content={
        "message": "Login successful",
        "user_id": user_id,
        "username": username
    })

# Main router endpoint
@app.get("/")  # Root endpoint
async def main():
    return JSONResponse(content={"message": "Web Apps for Machine Learning Model"})

# Create router to predict the output
@app.post("/predict")
async def predict(data: InputData, username: str = Depends(get_current_user)):
    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user_id = user[0]

    # Hitung global mean dari target_col (risk_flag)
    cursor.execute("SELECT AVG(risk_flag) FROM predictions")
    global_mean = cursor.fetchone()[0] or 0.5  # Default 0.5 jika tidak ada data

    # Hitung mean target untuk setiap kolom kategorikal
    target_encodings = {}
    categorical_columns = ['profession', 'city', 'state']
    for col in categorical_columns:
        cursor.execute(f"SELECT {col}, AVG(risk_flag) FROM predictions GROUP BY {col}")
        mean_target = {row[0]: row[1] for row in cursor.fetchall()}
        target_encodings[col] = mean_target

    # Fungsi untuk melakukan target encoding
    def target_encode(value, encoding_dict, global_mean):
        return encoding_dict.get(value, global_mean)

    # Hitung age_group dari Age
    age_group = pd.cut([data.Age], bins=[0, 25, 40, 60, np.inf], labels=['0', '1', '2', '3'])[0]

    # Hitung experience_age_ratio
    experience_age_ratio = data.Experience / data.Age if data.Age != 0 else 0

    # Preprocess input data untuk prediksi
    input_data = [
        data.Income, data.Age, data.Experience,
        safe_transform(label_encoders["married/single"], data.Married_Single),
        safe_transform(label_encoders["house_ownership"], data.House_Ownership),
        safe_transform(label_encoders["car_ownership"], data.Car_Ownership),
        target_encode(data.Profession, target_encodings["profession"], global_mean),  # Target Encoding untuk Profession
        target_encode(data.CITY, target_encodings["city"], global_mean),              # Target Encoding untuk City
        target_encode(data.STATE, target_encodings["state"], global_mean),            # Target Encoding untuk State
        data.CURRENT_JOB_YRS, data.CURRENT_HOUSE_YRS 
    ]

    input_data = input_data + [experience_age_ratio, int(age_group)]
    # Ubah input data ke bentuk 2D (1, 14)
    input_data = np.array(input_data).reshape(1, -1)

    # Predict
    prediction = model.predict(input_data)[0]

    # Simpan data mentah ke tabel predictions
    cursor.execute("""
        INSERT INTO predictions (
            user_id, income, age, experience, married_single, 
            house_ownership, car_ownership, profession, city, state, 
            current_job_yrs, current_house_yrs, risk_flag
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        user_id, data.Income, data.Age, data.Experience, data.Married_Single,
        data.House_Ownership, data.Car_Ownership, data.Profession, data.CITY,
        data.STATE, data.CURRENT_JOB_YRS, data.CURRENT_HOUSE_YRS, int(prediction))
    )
    conn.commit()
    
    return JSONResponse(content={"Risk_Flag": int(prediction)})
# Create router to fetch logs
@app.get("/log")
async def log(username: str = Depends(get_current_user)):
    # Ambil user_id dari tabel users
    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user_id = user[0]

    # Ambil log prediksi dari tabel predictions
    cursor.execute("""
        SELECT 
            income, age, experience, married_single, 
            house_ownership, car_ownership, profession, 
            city, state, current_job_yrs, current_house_yrs, risk_flag
        FROM predictions
        WHERE user_id = %s
    """, (user_id,))
    logs = cursor.fetchall()
    
    # Format hasil query
    result = []
    for log in logs:
        result.append({
            "income": log[0],
            "age": log[1],
            "experience": log[2],
            "married_single": log[3],
            "house_ownership": log[4],
            "car_ownership": log[5],
            "profession": log[6],
            "city": log[7],
            "state": log[8],
            "current_job_yrs": log[9],
            "current_house_yrs": log[10],
            "risk_flag": log[11]
        })
    
    return JSONResponse(content=result)

@app.post("/financial-recommendation")
async def get_financial_recommendation(profile: FinancialProfile, username: str = Depends(get_current_user)):
    try:
        user_profile = extract_user_profile(profile.profile_text)
        recommendation = log_recommendation(user_profile)
        
        return JSONResponse(content={
            "profile": user_profile,
            "recommendation": recommendation
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing request: {str(e)}")

# Run the app
if __name__ == "__main__":
    public_url = ngrok.connect(addr="8000", proto="http", bind_tls=True)
    print(f"Public URL: {public_url}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
