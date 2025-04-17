import streamlit as st
import pandas as pd
from collections import Counter
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime


# --- 1. Fake data (you'll replace this with real DB query later)
data = [
    {
        "Filename": "note1.jpg",
        "Upload Time": "2025-04-15 12:03:45",
        "Extracted Text": "Don't forget the milk and eggs from the store.",
        "Word Count": 10,
        "Image URL": "https://media.istockphoto.com/id/543347592/vector/why-god-why-emoticon.jpg"
    },
    {
        "Filename": "meeting.png",
        "Upload Time": "2025-04-15 13:12:11",
        "Extracted Text": "Team sync today at 2PM. Bring updates!",
        "Word Count": 9,
        "Image URL": "https://cdn.pixabay.com/photo/2020/02/07/12/54/emoji-4827091_640.png"
    },
    {
        "Filename": "recipe.jpg",
        "Upload Time": "2025-04-16 09:44:03",
        "Extracted Text": "Mix sugar and flour. Bake at 350 for 20 minutes.",
        "Word Count": 11,
        "Image URL": "https://i.pinimg.com/736x/6c/17/d2/6c17d2311183a7b053b9e99597d7da75.jpg"
    }
]

# --- 2. Create a DataFrame
df = pd.DataFrame(data)
df["Upload Time"] = pd.to_datetime(df["Upload Time"])

# --- 3. Dashboard layout
st.set_page_config(page_title="📝 OCR Analytics Dashboard", layout="wide")
st.title("📊 Handwriting Recognition Dashboard")

st.subheader("📁 Uploaded Files Summary")
st.dataframe(df[["Filename", "Upload Time", "Extracted Text"]])

# --- 6. Keyword search
st.subheader("🔍 Search Image Name Or Transcription")

search_type = st.radio("Search in:", ["Extracted Text", "Filename"], horizontal=True)
search_term = st.text_input("Enter search term")

if search_term:
    mask = df[search_type].str.contains(search_term, case=False, na=False)
    matched = df[mask]
    st.write(f"🔎 Found {len(matched)} result(s) in {search_type.lower()}:")
    
    for index, row in matched.iterrows():
        st.markdown(f"### 🖼️ {row['Filename']}")
        st.image(row["Image URL"], width=300)
        st.markdown(f"**Uploaded at:** {row['Upload Time']}")
        st.markdown("**Extracted Text:**")
        st.code(row["Extracted Text"], language="text")
        st.divider()

