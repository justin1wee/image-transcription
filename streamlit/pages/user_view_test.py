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

# Tab 2: RDS Database
with tab2:
    st.header("Data from RDS Database")
    
    if st.button("Test RDS Connection and Show Data"):
        conn = get_rds_connection()
        if conn:
            st.success("Successfully connected to RDS!")
            
            # Add debug information
            try:
                with conn.cursor() as cursor:
                    # Show tables
                    cursor.execute("SHOW TABLES")
                    tables = cursor.fetchall()
                    st.write("Tables in database:", [table['Tables_in_ds4300_project'] for table in tables])
                    
                    # Show table structure
                    cursor.execute("DESCRIBE extracted_text_results")
                    columns = cursor.fetchall()
                    st.write("Table structure:", columns)
                    
                    # Try a simple query to count records
                    cursor.execute("SELECT COUNT(*) as count FROM extracted_text_results")
                    count = cursor.fetchone()
                    st.write(f"Total records in table: {count['count']}")
                    
                    # Get all data with basic error handling
                    try:
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
                            LIMIT 100
                        """)
                        results = cursor.fetchall()
                        st.write(f"Retrieved {len(results)} records from the database")
                        
                        # Insert some mock data if no results found
                        if not results:
                            st.warning("No data found in the database. Adding some mock data...")
                            # Insert mock data
                            cursor.execute("""
                            INSERT INTO extracted_text_results 
                            (image_filename, text_content, word_count, char_count) 
                            VALUES 
                            ('mock-image-1.jpg', 'This is some mock text for testing.', 8, 36),
                            ('mock-image-2.jpg', 'Another mock entry with different content.', 6, 38),
                            ('mock-image-3.jpg', 'Testing the RDS display in Streamlit app.', 7, 40)
                            """)
                            conn.commit()
                            st.success("Mock data added successfully!")
                            
                            # Query again to get the mock data
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
                                LIMIT 100
                            """)
                            results = cursor.fetchall()
                            st.write(f"Retrieved {len(results)} records after adding mock data")
                    except Exception as query_error:
                        st.error(f"Error querying data: {str(query_error)}")
                        results = []
                        
            except Exception as db_error:
                st.error(f"Error working with database: {str(db_error)}")
                results = []
            
            conn.close()
        else:
            st.error("Could not connect to RDS database.")
            results = []
            
        # Process and display results if we have any
        if 'results' in locals() and results:
            # Create DataFrame
            df_rds = pd.DataFrame(results)
            
            # Display metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Documents", f"{len(df_rds)}")
            with col2:
                st.metric("Average Words", f"{df_rds['word_count'].mean():.1f}")
            with col3:
                st.metric("Total Words", f"{df_rds['word_count'].sum()}")
            
            # Display columns
            display_cols = ["image_filename", "upload_timestamp", "word_count", "char_count"]
            st.dataframe(df_rds[display_cols])
            
            # Display sample text content
            st.subheader("Sample Text Content")
            for index, row in df_rds.head(3).iterrows():
                st.markdown(f"### 📄 {row['image_filename']}")
                st.markdown(f"**Uploaded at:** {row['upload_timestamp']}")
                st.markdown(f"**Word Count:** {row['word_count']} words")
                st.markdown("**Extracted Text:**")
                st.code(row["text_content"], language="text")
                st.divider()
        else:
            st.info("No data to display. Click the button above to test the connection and add mock data.")
    
    # Get data from RDS (regular functionality)
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
            # For mock data, don't check for S3 images
            if "mock" in image_key:
                image_exists = True
        
        if image_exists:
            # For mock images, create a placeholder URL
            if "mock" in image_key:
                image_url = "https://via.placeholder.com/300x200?text=Mock+Image"
            else:
                image_url = get_image_url(image_key)
                
            data_rds.append({
                "Filename": image_key,
                "Upload Time": result['upload_timestamp'],
                "Extracted Text": result['text_content'],
                "Word Count": result['word_count'],
                "Character Count": result['char_count'],
                "Image URL": image_url
            })
    
    # Create DataFrame
    df_rds = pd.DataFrame(data_rds)
    if not df_rds.empty:
        df_rds["Upload Time"] = pd.to_datetime(df_rds["Upload Time"])
        df_rds = df_rds.sort_values("Upload Time", ascending=False)

    # Display data
    if df_rds.empty:
        st.info("No data found in RDS. Click the 'Test RDS Connection and Show Data' button above to add mock data.")
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
                if "mock" not in row['Filename']:
                    st.image(row["Image URL"], width=300)
                else:
                    st.info("Mock image (placeholder)")
                st.markdown(f"**Uploaded at:** {row['Upload Time']}")
                st.markdown(f"**Word Count:** {row['Word Count']} words")
                st.markdown("**Extracted Text:**")
                st.code(row["Extracted Text"], language="text")
                st.divider()