import streamlit as st
from PIL import Image

# Optional: display a logo or sample image
# image = Image.open("logo.png")
# st.image(image, width=150)

st.set_page_config(page_title="📄 Project Home", layout="centered")

st.title("🧠 Text Recognition Pipeline")
st.markdown("#### DS 4300 — Spring 2025")

st.markdown("---")

st.markdown("""
This web app demonstrates an **AWS-powered ETL pipeline** for recognizing extracting text from handwritten or printed images.

### 📦 Pipeline Overview
- **Image Upload** → User uploads image files (e.g., handwritten notes) via Streamlit to an S3 bucket.
- **Preprocessing** → AWS Lambda extracts text using OCR (i.e., Amazon Textract).
- **Storage** → Images and extracted text are saved in S3.
- **Analysis Dashboard** → This Streamlit app lets users:
    - Search files by text or filename
    - View OCR results

### 🔧 AWS Services Used
- **Amazon S3**: Storage for images and extracted text files
- **AWS Lambda**: Serverless OCR extraction and processing
- **Amazon EC2**: Hosts this Streamlit web app
- **Amazon RDS**: For structured data storage if needed
- **Amzon Textract**: Used for OCR

### 📂 App Pages
Use the sidebar to navigate:
- **streamlit**: Add a new image to the pipeline
- **user_view**: Search, view, and analyze extracted text

---

April 2025  
""")
