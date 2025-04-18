import streamlit as st
import pandas as pd
import boto3
import datetime
import os
from botocore.exceptions import ClientError
import matplotlib.pyplot as plt

# S3 setup
s3 = boto3.client("s3", region_name="us-east-2")
PROCESSED_BUCKET = "processed-images-ds4300-project"

# S3 functions
def list_processed_files():
    response = s3.list_objects_v2(Bucket=PROCESSED_BUCKET)
    files = response.get("Contents", [])
    return [f["Key"] for f in files]

def get_text_with_confidence(key):
    try:
        response = s3.get_object(Bucket=PROCESSED_BUCKET, Key=key)
        content = response["Body"].read().decode("utf-8")
        
        # Extract confidence if available
        confidence = None
        text = content
        if content.startswith("CONFIDENCE:"):
            first_line = content.split('\n')[0]
            confidence = float(first_line.replace("CONFIDENCE:", "").replace("%", "").strip())
            text = "\n".join(content.split('\n')[2:])  # Skip the confidence line and the blank line
            
        return text, confidence
    except Exception as e:
        st.error(f"Error retrieving text: {e}")
        return None, None

def get_image_url(image_key, expiration=3600):
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": PROCESSED_BUCKET, "Key": image_key},
            ExpiresIn=expiration  
        )
        return url
    except ClientError as e:
        st.error(f"Error generating pre-signed URL: {e}")
        return None

def get_image_size(key, bucket=PROCESSED_BUCKET):
    """Get the size of an S3 object in KB"""
    try:
        response = s3.head_object(Bucket=bucket, Key=key)
        size_kb = response['ContentLength'] / 1024
        return round(size_kb, 2)
    except Exception as e:
        st.error(f"Error getting image size: {e}")
        return None

def get_last_modified(key, bucket=PROCESSED_BUCKET):
    """Get the last modified date of an S3 object"""
    try:
        response = s3.head_object(Bucket=bucket, Key=key)
        return response['LastModified']
    except Exception as e:
        return datetime.datetime.now()

# Streamlit UI
st.set_page_config(page_title="📝 OCR Analytics Dashboard", layout="wide")
st.title("📊 Text Recognition Dashboard")

# S3-based code
data = []
for file in list_processed_files():
    if file.endswith("_text.txt"):
        base_name = file.replace("_text.txt", "")
        text, confidence = get_text_with_confidence(file)
        
        if text is None:
            continue
            
        image_key = None
        # Try different image extensions
        for ext in [".jpg", ".jpeg", ".png"]:
            try:
                # Try without the images/ prefix since we're not using folders now
                s3.head_object(Bucket=PROCESSED_BUCKET, Key=base_name + ext)
                image_key = base_name + ext
                break
            except ClientError:
                continue
                
        # Add to data
        if image_key:
            word_count = len(text.split()) if text else 0
            char_count = len(text) if text else 0
            image_size = get_image_size(image_key)
            
            data.append({
                "Filename": image_key,
                "Upload Time": get_last_modified(image_key),
                "Extracted Text": text,
                "Word Count": word_count,
                "Character Count": char_count,
                "Line Count": text.count('\n') + 1 if text else 0,
                "Image Size (KB)": image_size,
                "Confidence": confidence,
                "Image URL": get_image_url(image_key)
            })

# Create DataFrame
df = pd.DataFrame(data)
if not df.empty:
    df["Upload Time"] = pd.to_datetime(df["Upload Time"])
    df = df.sort_values("Upload Time", ascending=False)

# Display data
if df.empty:
    st.info("No data found. Please upload some images to process.")
else:
    # Show the dashboard
    st.subheader("📁 Uploaded Files Summary")
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Documents", f"{len(df)}")
    with col2:
        if "Confidence" in df.columns and df["Confidence"].notna().any():
            st.metric("Average Confidence", f"{df['Confidence'].mean():.2f}%")
    with col3:
        st.metric("Average Words", f"{df['Word Count'].mean():.1f}")
    with col4:
        if "Image Size (KB)" in df.columns and df["Image Size (KB)"].notna().any():
            st.metric("Average File Size", f"{df['Image Size (KB)'].mean():.1f} KB")
    
    # Display columns including Image Size
    display_cols = ["Filename", "Upload Time", "Word Count", "Confidence", "Image Size (KB)"]
    st.dataframe(df[display_cols])
    
    # Visualization section
    if "Confidence" in df.columns and df["Confidence"].notna().any():
        st.subheader("📊 Text Extraction Confidence")
        
        # Display a bar chart
        chart_data = df[["Filename", "Confidence"]].set_index("Filename")
        st.bar_chart(chart_data)
    
    # Word count distribution
    st.subheader("📊 Word Count Distribution")
    fig, ax = plt.figure(figsize=(10, 6)), plt.subplot(111)
    ax.hist(df["Word Count"], bins=10, alpha=0.7)
    ax.set_xlabel("Word Count")
    ax.set_ylabel("Number of Documents")
    st.pyplot(fig)
    
    # Add a chart for image size vs word count
    if "Image Size (KB)" in df.columns and df["Image Size (KB)"].notna().any():
        st.subheader("📊 Image Size vs Word Count")
        fig2, ax2 = plt.figure(figsize=(10, 6)), plt.subplot(111)
        ax2.scatter(df["Image Size (KB)"], df["Word Count"], alpha=0.7)
        ax2.set_xlabel("Image Size (KB)")
        ax2.set_ylabel("Word Count")
        st.pyplot(fig2)
    
    # Search functionality
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
            
            # Display confidence if available
            if "Confidence" in row and pd.notna(row["Confidence"]):
                st.markdown(f"**Confidence:** {row['Confidence']:.2f}%")
            
            # Display image size if available
            if "Image Size (KB)" in row and pd.notna(row["Image Size (KB)"]):
                st.markdown(f"**Image Size:** {row['Image Size (KB)']} KB")
            
            st.markdown(f"**Word Count:** {row['Word Count']} words")
            st.markdown("**Extracted Text:**")
            st.code(row["Extracted Text"], language="text")
            st.divider()