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
        return content
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
        # Skip non-image files
        if not file.endswith(('.jpg', '.jpeg', '.png')):
            continue
            
        # Check if corresponding text file exists
        base_name = os.path.splitext(file)[0]
        text_file = f"{base_name}_text.txt"
        
        try:
            s3.head_object(Bucket=PROCESSED_BUCKET, Key=text_file)
            text = get_text(text_file)
            
            if text is None:
                continue
                
            # Add to data
            word_count = len(text.split()) if text else 0
            char_count = len(text) if text else 0
            image_size = get_image_size(file)
            
            data_s3.append({
                "Filename": file,
                "Upload Time": get_last_modified(file),
                "Extracted Text": text,
                "Word Count": word_count,
                "Character Count": char_count,
                "Line Count": text.count('\n') + 1 if text else 0,
                "Image Size (KB)": image_size,
                "Image URL": get_image_url(file)
            })
        except ClientError:
            # Text file doesn't exist for this image, skip it
            continue

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

# Tab 2: CSV Data (instead of RDS)
with tab2:
    st.header("Data from CSV")
    
    # Function to load CSV data from S3
    def get_extraction_results_from_csv():
        try:
            # Try to get the CSV file from S3
            csv_key = "extraction_results.csv"
            try:
                response = s3.get_object(Bucket=PROCESSED_BUCKET, Key=csv_key)
                csv_content = response['Body'].read().decode('utf-8')
                
                # Parse CSV
                data = []
                csv_reader = csv.DictReader(io.StringIO(csv_content))
                for row in csv_reader:
                    data.append(row)
                
                return data
            except Exception as e:
                st.error(f"Error retrieving CSV: {e}")
                
                # If no CSV exists, create a mock one for testing
                if st.button("Create Mock CSV Data"):
                    create_mock_csv_data()
                    st.success("Mock CSV data created! Refresh the page to see it.")
                
                return []
        except Exception as e:
            st.error(f"Error: {e}")
            return []
    
    # Function to create mock CSV data
    def create_mock_csv_data():
        try:
            # Create CSV in memory
            csv_buffer = io.StringIO()
            csv_writer = csv.writer(csv_buffer)
            
            # Write header
            csv_writer.writerow(['image_filename', 'text_content', 'word_count', 'char_count', 'upload_timestamp'])
            
            # Write mock data
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            csv_writer.writerow(['mock-image-1.jpg', 'This is some mock text for testing.', '8', '36', current_time])
            csv_writer.writerow(['mock-image-2.jpg', 'Another mock entry with different content.', '6', '38', current_time])
            csv_writer.writerow(['mock-image-3.jpg', 'Testing the CSV display in Streamlit app.', '7', '40', current_time])
            
            # Upload to S3
            s3.put_object(
                Bucket=PROCESSED_BUCKET,
                Key="extraction_results.csv",
                Body=csv_buffer.getvalue()
            )
            return True
        except Exception as e:
            st.error(f"Error creating mock data: {e}")
            return False
    
    # Get data from CSV
    csv_results = get_extraction_results_from_csv()
    
    # Transform CSV data to match the format
    data_csv = []
    for result in csv_results:
        image_key = result['image_filename']
        
        # Check if the image exists in the processed bucket
        image_exists = False
        try:
            s3.head_object(Bucket=PROCESSED_BUCKET, Key=image_key)
            image_exists = True
        except ClientError:
            # For mock data, don't check for S3 images
            if "mock" in image_key:
                image_exists = True
        
        if image_exists:
            # For mock images, create a placeholder URL
            if "mock" in image_key:
                image_url = "https://via.placeholder.com/300x200?text=Mock+Image"
            else:
                image_url = get_image_url(image_key)
                
            data_csv.append({
                "Filename": image_key,
                "Upload Time": result['upload_timestamp'],
                "Extracted Text": result['text_content'],
                "Word Count": int(result['word_count']),
                "Character Count": int(result['char_count']),
                "Image URL": image_url
            })
    
    # Create DataFrame
    df_csv = pd.DataFrame(data_csv)
    if not df_csv.empty:
        df_csv["Upload Time"] = pd.to_datetime(df_csv["Upload Time"])
        df_csv = df_csv.sort_values("Upload Time", ascending=False)

    # Display data
    if df_csv.empty:
        st.info("No data found in CSV. You can create mock data by clicking the button above.")
    else:
        # Show the dashboard
        st.subheader("📁 Extracted Text Summary (CSV)")
        
        # Display metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Documents", f"{len(df_csv)}")
        with col2:
            st.metric("Average Words", f"{df_csv['Word Count'].mean():.1f}")
        with col3:
            st.metric("Total Words", f"{df_csv['Word Count'].sum()}")
        
        # Display columns
        display_cols = ["Filename", "Upload Time", "Word Count", "Character Count"]
        st.dataframe(df_csv[display_cols])
        
        # Search functionality
        st.subheader("🔍 Search Image Name Or Transcription")
        search_type = st.radio("Search in:", ["Extracted Text", "Filename"], horizontal=True, key="csv_search_type")
        search_term = st.text_input("Enter search term", key="csv_search_term")
        
        if search_term:
            mask = df_csv[search_type].str.contains(search_term, case=False, na=False)
            matched = df_csv[mask]
            st.write(f"🔎 Found {len(matched)} result(s) in {search_type.lower()}:")
            
            for index, row in matched.iterrows():
                st.markdown(f"### 🖼️ {row['Filename']}")
                if "mock" not in row['Filename']:
                    st.image(row["Image URL"], width=300)
                else:
                    st.info("Mock image (placeholder)")
                st.markdown(f"**Uploaded at:** {row['Upload Time']}")
                st.markdown(f"**Word Count:** {row['Word Count']} words")
                st.markdown("**Extracted Text:**")
                st.code(row["Extracted Text"], language="text")
                st.divider()