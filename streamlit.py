import streamlit as st
import requests
from openai import OpenAI
import os
from dotenv import load_dotenv
import pandas as pd

# # Load API key dari file .env
# load_dotenv()

# # Set API key
# api_key = os.getenv("OPENAI_API_KEY")
# client = OpenAI(api_key=api_key)
# URL backend FastAPI (localhost)
BACKEND_URL = "https://e1ca-36-69-142-24.ngrok-free.app"

# Fungsi untuk mendaftarkan pengguna baru
def register_user(username, password):
    try:
        response = requests.post(
            f"{BACKEND_URL}/register",
            json={"username": username, "password": password},
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()  # Raise exception untuk status code 4xx/5xx
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return {"message": "Failed to register user"}

def login_user(username, password):
    try:
        response = requests.post(
            f"{BACKEND_URL}/login",
            auth=(username, password)
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return {"message": "Failed to login"}

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

# Fungsi untuk berinteraksi dengan ChatGPT
# def chat_with_gpt(prompt):
#     try:
#         response = client.chat.completions.create(
#             model="gpt-3.5-turbo",
#             messages=[
#                 {"role": "system", "content": "Anda adalah asisten yang membantu memberikan rekomendasi terkait risiko kredit dan keuangan."},
#                 {"role": "user", "content": prompt}
#             ]
#         )
#         return response.choices[0].message.content
#     except Exception as e:
#         return f"Error: {str(e)}"

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
st.title("Aplikasi Prediksi Risiko Kredit dan Chat dengan AI")

# Sidebar untuk menu
menu = st.sidebar.selectbox("Menu", ["Register", "Login", "Predict", "Logs", "Chat with AI"])

def register_user(username, password):
    response = requests.post(f"{BACKEND_URL}/register", json={"username": username, "password": password})
    return response.json()

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
            print(response)
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

# elif menu == "Chat with AI":
#     st.header("Chat dengan AI")
    
#     # Input chat dari pengguna
#     user_input = st.text_input("Anda: ", placeholder="Tulis pesan Anda di sini...")
    
#     if st.button("Kirim"):
#         if user_input:
#             # Kirim pesan ke ChatGPT
#             response = chat_with_gpt(user_input)
#             st.text_area("AI:", value=response, height=200, disabled=True)
#         else:
#             st.warning("Silakan masukkan pesan terlebih dahulu.")
