import streamlit as st
import pandas as pd
import boto3
import datetime
import pymysql
import os
from botocore.exceptions import ClientError

# S3 setup
s3 = boto3.client("s3", region_name="us-east-2")
PROCESSED_BUCKET = "processed-images-ds4300-project"

# RDS Configuration
RDS_HOST = 'ds4300-mysql-project.cdmu6kgsobyy.us-east-2.rds.amazonaws.com'
RDS_PORT = 3306
RDS_USER = 'admin'
RDS_PASSWORD = 'lambda-function-rds'
RDS_DB_NAME = 'ds4300_project'

# Function to connect to RDS
def get_rds_connection():
    try:
        conn = pymysql.connect(
            host=RDS_HOST,
            port=RDS_PORT,
            user=RDS_USER,
            password=RDS_PASSWORD,
            database=RDS_DB_NAME,
            cursorclass=pymysql.cursors.DictCursor
        )
        return conn
    except Exception as e:
        st.error(f"Error connecting to RDS: {e}")
        return None

# Function to get data from RDS
def get_extraction_results_from_rds():
    conn = get_rds_connection()
    results = []
    
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        id, 
                        image_filename, 
                        text_content, 
                        confidence, 
                        word_count, 
                        char_count, 
                        upload_timestamp 
                    FROM extracted_text_results
                    ORDER BY upload_timestamp DESC
                """)
                results = cursor.fetchall()
            conn.close()
        except Exception as e:
            st.error(f"Error fetching data from RDS: {e}")
    
    return results

# Existing S3 functions
def list_processed_files():
    response = s3.list_objects_v2(Bucket=PROCESSED_BUCKET)
    files = response.get("Contents", [])
    return [f["Key"] for f in files]

def get_text(key):
    try:
        response = s3.get_object(Bucket=PROCESSED_BUCKET, Key=key)
        return response["Body"].read().decode("utf-8")
    except:
        return None

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

# Streamlit UI
st.set_page_config(page_title="📝 OCR Analytics Dashboard", layout="wide")
st.title("📊 Handwriting Recognition Dashboard")

# Add data source selection
data_source = st.sidebar.radio("Data Source:", ["S3 Storage", "RDS Database"])

if data_source == "S3 Storage":
    # Original S3-based code
    data = []
    for file in list_processed_files():
        if file.endswith("_text.txt"):
            base_name = file.replace("_text.txt", "")
            text = get_text(file)
            image_key = None
            # Try different image extensions
            for ext in [".jpg", ".jpeg", ".png"]:
                try:
                    s3.head_object(Bucket=PROCESSED_BUCKET, Key=f"images/{base_name + ext}")
                    image_key = f"images/{base_name + ext}"
                    break
                except ClientError:
                    try:
                        # Try without the images/ prefix
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
    if not df.empty:
        df["Upload Time"] = pd.to_datetime(df["Upload Time"])

else:  # RDS Database
    # Get data from RDS
    rds_results = get_extraction_results_from_rds()
    
    # Transform RDS data to match the format
    data = []
    for result in rds_results:
        image_key = result['image_filename']
        
        # Check if the image exists in the processed bucket (in images folder or root)
        image_exists = False
        image_path = ""
        try:
            try:
                s3.head_object(Bucket=PROCESSED_BUCKET, Key=f"images/{image_key}")
                image_path = f"images/{image_key}"
                image_exists = True
            except ClientError:
                s3.head_object(Bucket=PROCESSED_BUCKET, Key=image_key)
                image_path = image_key
                image_exists = True
        except ClientError:
            pass
        
        if image_exists:
            data.append({
                "Filename": image_key,
                "Upload Time": result['upload_timestamp'],
                "Extracted Text": result['text_content'],
                "Word Count": result['word_count'],
                "Char Count": result['char_count'],
                "Confidence": result['confidence'],
                "Image URL": get_image_url(image_path)
            })
    
    # Create DataFrame
    df = pd.DataFrame(data)
    if not df.empty:
        df["Upload Time"] = pd.to_datetime(df["Upload Time"])

# Display data (common for both sources)
if df.empty:
    st.info("No data found. Please upload some images to process.")
else:
    # Show the dashboard
    st.subheader("📁 Uploaded Files Summary")
    
    # Determine columns to display based on source
    if data_source == "RDS Database":
        display_cols = ["Filename", "Upload Time", "Confidence", "Word Count", "Char Count"]
    else:
        display_cols = ["Filename", "Upload Time", "Word Count"]
    
    st.dataframe(df[display_cols])
    
    # Analytics section (only if using RDS)
    if data_source == "RDS Database" and not df.empty:
        st.subheader("📊 OCR Analytics")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Average Confidence", f"{df['Confidence'].mean():.2f}%")
        col2.metric("Average Word Count", f"{df['Word Count'].mean():.1f}")
        col3.metric("Total Images Processed", f"{len(df)}")
        
        # Add a chart
        st.subheader("Confidence by Image")
        chart_data = df[["Filename", "Confidence"]].set_index("Filename")
        st.bar_chart(chart_data)
    
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
            if "Confidence" in row:
                st.markdown(f"**Confidence:** {row['Confidence']:.2f}%")
            
            st.markdown("**Extracted Text:**")
            st.code(row["Extracted Text"], language="text")
            st.divider()