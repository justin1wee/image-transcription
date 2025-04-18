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

# S3 functions
def list_processed_files():
    response = s3.list_objects_v2(Bucket=PROCESSED_BUCKET)
    files = response.get("Contents", [])
    return [f["Key"] for f in files]

def get_text(key):
    try:
        response = s3.get_object(Bucket=PROCESSED_BUCKET, Key=key)
        content = response["Body"].read().decode("utf-8")
        
        # Strip confidence line if it exists
        text = content
        if content.startswith("CONFIDENCE:"):
            text = "\n".join(content.split('\n')[2:])  # Skip the confidence line and the blank line
            
        return text
    except Exception as e:
        st.error(f"Error retrieving text: {e}")
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

# RDS functions
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

# Streamlit UI
st.set_page_config(page_title="📝 OCR Analytics Dashboard", layout="wide")
st.title("📊 Text Recognition Dashboard")

# Create tabs
tab1, tab2 = st.tabs(["S3 Storage", "RDS Database"])

# Tab 1: S3 Storage
with tab1:
    st.header("Data from S3 Storage")
    
    # S3-based code
    data_s3 = []
    for file in list_processed_files():
        if file.endswith("_text.txt"):
            base_name = file.replace("_text.txt", "")
            text = get_text(file)
            
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
                
                data_s3.append({
                    "Filename": image_key,
                    "Upload Time": get_last_modified(image_key),
                    "Extracted Text": text,
                    "Word Count": word_count,
                    "Character Count": char_count,
                    "Line Count": text.count('\n') + 1 if text else 0,
                    "Image Size (KB)": image_size,
                    "Image URL": get_image_url(image_key)
                })

    # Create DataFrame
    df_s3 = pd.DataFrame(data_s3)
    if not df_s3.empty:
        df_s3["Upload Time"] = pd.to_datetime(df_s3["Upload Time"])
        df_s3 = df_s3.sort_values("Upload Time", ascending=False)

    # Display data
    if df_s3.empty:
        st.info("No data found in S3. Please upload some images to process.")
    else:
        # Show the dashboard
        st.subheader("📁 Uploaded Files Summary (S3)")
        
        # Display metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Documents", f"{len(df_s3)}")
        with col2:
            st.metric("Average Words", f"{df_s3['Word Count'].mean():.1f}")
        with col3:
            if "Image Size (KB)" in df_s3.columns and df_s3["Image Size (KB)"].notna().any():
                st.metric("Average File Size", f"{df_s3['Image Size (KB)'].mean():.1f} KB")
        
        # Display columns including Image Size
        display_cols = ["Filename", "Upload Time", "Word Count", "Image Size (KB)"]
        st.dataframe(df_s3[display_cols])
        
        # Search functionality
        st.subheader("🔍 Search Image Name Or Transcription (S3)")
        search_type = st.radio("Search in:", ["Extracted Text", "Filename"], horizontal=True, key="s3_search_type")
        search_term = st.text_input("Enter search term", key="s3_search_term")
        
        if search_term:
            mask = df_s3[search_type].str.contains(search_term, case=False, na=False)
            matched = df_s3[mask]
            st.write(f"🔎 Found {len(matched)} result(s) in {search_type.lower()}:")
            
            for index, row in matched.iterrows():
                st.markdown(f"### 🖼️ {row['Filename']}")
                st.image(row["Image URL"], width=300)
                st.markdown(f"**Uploaded at:** {row['Upload Time']}")
                
                # Display image size if available
                if "Image Size (KB)" in row and pd.notna(row["Image Size (KB)"]):
                    st.markdown(f"**Image Size:** {row['Image Size (KB)']} KB")
                
                st.markdown(f"**Word Count:** {row['Word Count']} words")
                st.markdown("**Extracted Text:**")
                st.code(row["Extracted Text"], language="text")
                st.divider()

# Tab 2: RDS Database
with tab2:
    st.header("Data from RDS Database")
    
    if st.button("Test RDS Connection"):
        conn = get_rds_connection()
        if conn:
            st.success("Successfully connected to RDS!")
            conn.close()
    
    # Get data from RDS
    rds_results = get_extraction_results_from_rds()
    
    # Transform RDS data to match the format
    data_rds = []
    for result in rds_results:
        image_key = result['image_filename']
        
        # Check if the image exists in the processed bucket
        image_exists = False
        try:
            s3.head_object(Bucket=PROCESSED_BUCKET, Key=image_key)
            image_exists = True
        except ClientError:
            pass
        
        if image_exists:
            data_rds.append({
                "Filename": image_key,
                "Upload Time": result['upload_timestamp'],
                "Extracted Text": result['text_content'],
                "Word Count": result['word_count'],
                "Character Count": result['char_count'],
                "Image URL": get_image_url(image_key)
            })
    
    # Create DataFrame
    df_rds = pd.DataFrame(data_rds)
    if not df_rds.empty:
        df_rds["Upload Time"] = pd.to_datetime(df_rds["Upload Time"])
        df_rds = df_rds.sort_values("Upload Time", ascending=False)

    # Display data
    if df_rds.empty:
        st.info("No data found in RDS. Make sure your Lambda function is storing data in RDS.")
    else:
        # Show the dashboard
        st.subheader("📁 Uploaded Files Summary (RDS)")
        
        # Display metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Documents", f"{len(df_rds)}")
        with col2:
            st.metric("Average Words", f"{df_rds['Word Count'].mean():.1f}")
        with col3:
            st.metric("Total Words", f"{df_rds['Word Count'].sum()}")
        
        # Display columns
        display_cols = ["Filename", "Upload Time", "Word Count", "Character Count"]
        st.dataframe(df_rds[display_cols])
        
        # Search functionality
        st.subheader("🔍 Search Image Name Or Transcription (RDS)")
        search_type = st.radio("Search in:", ["Extracted Text", "Filename"], horizontal=True, key="rds_search_type")
        search_term = st.text_input("Enter search term", key="rds_search_term")
        
        if search_term:
            mask = df_rds[search_type].str.contains(search_term, case=False, na=False)
            matched = df_rds[mask]
            st.write(f"🔎 Found {len(matched)} result(s) in {search_type.lower()}:")
            
            for index, row in matched.iterrows():
                st.markdown(f"### 🖼️ {row['Filename']}")
                st.image(row["Image URL"], width=300)
                st.markdown(f"**Uploaded at:** {row['Upload Time']}")
                st.markdown(f"**Word Count:** {row['Word Count']} words")
                st.markdown("**Extracted Text:**")
                st.code(row["Extracted Text"], language="text")
                st.divider()

# Instructions for setting up RDS connection
with tab2:
    if df_rds.empty:
        st.subheader("How to Set Up RDS Integration")
        st.markdown("""
        To set up the RDS integration:
        
        1. **Create an RDS instance** in AWS if you haven't already
        2. **Update the RDS configuration** at the top of this script with your RDS details
        3. **Modify your Lambda function** to store extraction results in RDS:
           - Add RDS connection code
           - Create the required table 
           - Insert extraction results along with metadata
        4. **Ensure security groups** allow connections between Lambda and RDS
        5. **Test the system** by uploading an image to your raw bucket
        """)