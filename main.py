# Import necessary libraries
import joblib
import pymysql
import uvicorn
import numpy as np
import bcrypt
from pydantic import BaseModel
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import JSONResponse
from pyngrok import ngrok
import pandas as pd

# Create MySQL connection
conn = pymysql.connect(
    host="localhost",      # Host XAMPP
    user="root",           # Username MySQL (default XAMPP)
    password="",           # Password MySQL (default XAMPP kosong)
    database="fastapi_db"  # Nama database yang dibuat di phpMyAdmin
)
cursor = conn.cursor()

# Setup ngrok, load token from .env
NGROK_TOKEN = "2qbm2tb2N5V976kazTBFrXp6nTH_5ogBZLoLfAB7Cronw98QM"
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

# Run the app
if __name__ == "__main__":
    public_url = ngrok.connect(addr="8000", proto="http", bind_tls=True)
    print(f"Public URL: {public_url}")
    uvicorn.run(app, host="0.0.0.0", port=8000)