import streamlit as st
import requests
import subprocess
import time
from pyngrok import ngrok
import pandas as pd

# Fungsi untuk menjalankan backend otomatis
# def start_backend():
#     process = subprocess.Popen(["python", "main.py"])
#     time.sleep(3)  # Tunggu beberapa detik agar backend siap
#     return process

# # Fungsi untuk menjalankan ngrok
# def start_ngrok():
#     ngrok.set_auth_token("2tsvr0e52TVnMuzMSKuFm5OUJ8C_6fzhGmrPvG7fVofSXLhiW")
#     tunnel = ngrok.connect(8000)  # Sesuaikan dengan port backend
#     return tunnel.public_url

# # Mulai backend
# backend_process = start_backend()

# Mulai ngrok
BACKEND_URL = "https://7a66-180-245-185-32.ngrok-free.app"
# print(f"Backend URL: {BACKEND_URL}")

# Fungsi untuk mendaftarkan pengguna baru
def register_user(username, password):
    response = requests.post(f"{BACKEND_URL}/register", json={"username": username, "password": password})
    return response.json()

# Fungsi untuk login
def login_user(username, password):
    auth = (username, password)
    response = requests.post(f"{BACKEND_URL}/login", auth=auth)
    return response.json()

# Fungsi untuk melakukan prediksi risiko kredit
def predict_risk(data, username, password):
    auth = (username, password)
    response = requests.post(f"{BACKEND_URL}/predict", json=data, auth=auth)
    return response.json()

# Fungsi untuk mengambil log prediksi
def get_logs(username, password):
    auth = (username, password)
    response = requests.get(f"{BACKEND_URL}/log", auth=auth)
    return response.json()

# Fungsi untuk mendapatkan rekomendasi keuangan
def get_financial_recommendation(profile_text, username, password):
    auth = (username, password)
    response = requests.post(
        f"{BACKEND_URL}/financial-recommendation",
        json={"profile_text": profile_text},
        auth=auth
    )
    return response.json()

# Inisialisasi session state
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "username" not in st.session_state:
    st.session_state["username"] = None
if "password" not in st.session_state:
    st.session_state["password"] = None
if "user_id" not in st.session_state:
    st.session_state["user_id"] = None

# Tampilan Streamlit
st.title("Aplikasi Prediksi Risiko Kredit dan Rekomendasi Keuangan")

# Sidebar untuk menu
menu = st.sidebar.selectbox("Menu", ["Register", "Login", "Predict", "Logs", "Financial Recommendation"])

if menu == "Register":
    st.header("Daftar Pengguna Baru")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Register"):
        if username and password:
            response = register_user(username, password)
            if "message" in response:
                st.success(response["message"])
            else:
                st.error("Terjadi kesalahan saat mendaftarkan pengguna.")
        else:
            st.error("Username dan password harus diisi")

elif menu == "Login":
    st.header("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username and password:
            response = login_user(username, password)
            if "message" in response and response["message"] == "Login successful":
                st.success("Login berhasil!")
                st.session_state["logged_in"] = True
                st.session_state["username"] = username
                st.session_state["password"] = password
                st.session_state["user_id"] = response["user_id"]
            else:
                st.error("Login gagal. Periksa username dan password Anda.")
        else:
            st.error("Username dan password harus diisi")

elif menu == "Predict":
    st.header("Prediksi Risiko Kredit")
    if not st.session_state.get("logged_in"):
        st.warning("Silakan login terlebih dahulu.")
    else:
        income = st.number_input("Income", min_value=0)
        age = st.number_input("Age", min_value=0)
        experience = st.number_input("Experience", min_value=0)
        married_single = st.selectbox("Married/Single", ["married", "single"])
        house_ownership = st.selectbox("House Ownership", ["rented", "norent_noown", "owned"])
        car_ownership = st.selectbox("Car Ownership", ["no", "yes"])
        profession = st.text_input("Profession")
        city = st.text_input("City")
        state = st.text_input("State")
        current_job_yrs = st.number_input("Current Job Years", min_value=0)
        current_house_yrs = st.number_input("Current House Years", min_value=0)
        
        if st.button("Predict"):
            data = {
                "Income": income,
                "Age": age,
                "Experience": experience,
                "Married_Single": married_single,
                "House_Ownership": house_ownership,
                "Car_Ownership": car_ownership,
                "Profession": profession,
                "CITY": city,
                "STATE": state,
                "CURRENT_JOB_YRS": current_job_yrs,
                "CURRENT_HOUSE_YRS": current_house_yrs
            }
            response = predict_risk(data, st.session_state["username"], st.session_state["password"])
            if "Risk_Flag" in response:
                st.success(f"Predicted Risk Flag: {response['Risk_Flag']}")
            else:
                st.error(response.get("detail", "Terjadi kesalahan saat melakukan prediksi"))

elif menu == "Logs":
    st.header("Log Prediksi")
    if not st.session_state.get("logged_in"):
        st.warning("Silakan login terlebih dahulu.")
    else:
        if st.button("Get Logs"):
            logs = get_logs(st.session_state["username"], st.session_state["password"])
            if isinstance(logs, list):
                # Konversi data log ke DataFrame pandas
                df = pd.DataFrame(logs)
                
                # Tampilkan tabel dengan st.dataframe (interaktif)
                st.subheader("Tabel Log Prediksi (Interaktif)")
                st.dataframe(df)
            else:
                st.error(logs.get("detail", "Terjadi kesalahan saat mengambil log"))

elif menu == "Financial Recommendation":
    st.header("Rekomendasi Produk Keuangan")
    if not st.session_state.get("logged_in"):
        st.warning("Silakan login terlebih dahulu.")
    else:
        profile_text = st.text_area(
            "Masukkan profil keuangan Anda",
            placeholder="Contoh: Saya 25 tahun, pendapatan 15 juta per bulan, riwayat kredit baik"
        )
        
        if st.button("Dapatkan Rekomendasi"):
            if profile_text:
                with st.spinner("Membuat rekomendasi..."):
                    response = get_financial_recommendation(
                        profile_text,
                        st.session_state["username"],
                        st.session_state["password"]
                    )
                    
                    if "recommendation" in response:
                        # Bersihkan output lagi untuk memastikan
                        recommendation = response["recommendation"]
                        unwanted = "Bagi pengguna dengan usia"
                        
                        if recommendation.startswith(unwanted):
                            recommendation = recommendation[len(unwanted):]
                            recommendation = recommendation.split(".", 1)[-1].strip()
                        
                        st.subheader("Rekomendasi untuk Anda:")
                        st.write(recommendation)
                    else:
                        st.error("Gagal mendapatkan rekomendasi")
            else:
                st.warning("Harap masukkan profil keuangan Anda")
