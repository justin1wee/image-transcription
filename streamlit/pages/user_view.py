import streamlit as st
import pandas as pd
import boto3
import datetime
from botocore.exceptions import ClientError

# S3 setup
s3 = boto3.client("s3")
PROCESSED_BUCKET = "processed-images-ds4300-project"

# Function to get all processed .txt files
def list_processed_files():
    response = s3.list_objects_v2(Bucket=PROCESSED_BUCKET)
    files = response.get("Contents", [])
    return [f["Key"] for f in files]

# Function to get extracted text
def get_text(key):
    try:
        response = s3.get_object(Bucket=PROCESSED_BUCKET, Key=key)
        return response["Body"].read().decode("utf-8")
    except:
        return None


def get_image_url(image_key):
    return f"https://{PROCESSED_BUCKET}.s3.amazonaws.com/{image_key}"

# Function to generate S3 image URL 
# def get_image_url(image_key, expiration=3600):
#     try:
#         url = s3.generate_presigned_url(
#             "get_object",
#             Params={"Bucket": PROCESSED_BUCKET, "Key": image_key},
#             ExpiresIn=expiration  
#         )
#         return url
#     except ClientError as e:
#         st.error(f"Error generating pre-signed URL: {e}")
#         return None

# Build data
data = []
for file in list_processed_files():
    if file.endswith("_text.txt"):
        base_name = file.replace("_text.txt", "")
        text = get_text(file)
        image_key = None

        # Try different image extensions
        for ext in [".jpg", ".jpeg", ".png"]:
            try:
                s3.head_object(Bucket=PROCESSED_BUCKET, Key=base_name + ext)
                image_key = base_name + ext
                break
            except ClientError:
                continue

        # Add to data
        if image_key:
            data.append({
                "Filename": image_key,
                "Upload Time": datetime.datetime.now(),  # Replace with real timestamp if you track it
                "Extracted Text": text,
                "Word Count": len(text.split()),
                "Image URL": get_image_url(image_key)
            })

# Create DataFrame
df = pd.DataFrame(data)
df["Upload Time"] = pd.to_datetime(df["Upload Time"])

# Streamlit Layout
st.set_page_config(page_title="📝 OCR Analytics Dashboard", layout="wide")
st.title("📊 Handwriting Recognition Dashboard")

st.subheader("📁 Uploaded Files Summary")
st.dataframe(df[["Filename", "Upload Time", "Extracted Text"]])

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
