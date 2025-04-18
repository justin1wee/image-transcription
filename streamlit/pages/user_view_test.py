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