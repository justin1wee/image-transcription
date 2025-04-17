import streamlit as st
import boto3
from botocore.exceptions import ClientError

# Initialize S3 client (IAM role credentials are automatically used on EC2)
s3 = boto3.client("s3")

# Set your bucket name (placeholder for now)
BUCKET_NAME = "raw-images-ds4300-project"  # ← Replace this once your bucket exists

# Streamlit UI
st.title("📤 Upload Image to S3")

uploaded_file = st.file_uploader("Choose an image file...", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    file_name = uploaded_file.name

    try:
        # Upload the file to S3
        s3.upload_fileobj(uploaded_file, BUCKET_NAME, file_name)
        st.success(f"✅ Uploaded `{file_name}` to S3 bucket `{BUCKET_NAME}`")

    except ClientError as e:
        st.error(f"❌ Upload failed: {e}")
    except Exception as e:
        st.error(f"❌ Unexpected error: {e}")
