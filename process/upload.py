import os
import boto3
from PIL import Image
from io import BytesIO
import exifread
from pymongo import MongoClient
from bson.objectid import ObjectId

USERID = ""
FARMID = ""

# MongoDB connection setup
client = MongoClient("mongodb://localhost:27017/")  # Replace with your MongoDB connection string
db = client['aerialFarm']  # Replace with your database name
collection = db['farm_drone']  # Replace with your collection name

# AWS S3 configuration
AWS_ACCESS_KEY = 'AKIATSY4E6IQYDYFCKET'
AWS_SECRET_KEY = 'siL48HLjLHNE/ld8+MPLxjh9ikpD5muTD2qW7BxS'
S3_BUCKET = 'aerial-farm'
S3_REGION = 'ap-south-1'  # e.g., us-east-1


def resize_image(image_path):
    img = Image.open(image_path)

    # Calculate new dimensions (half of the original dimensions)
    new_width = img.width // 3
    new_height = img.height // 3

    # Resize image - maintain aspect ratio
    img = img.resize((new_width, new_height), Image.LANCZOS)

    img_byte_arr = BytesIO()

    # Get the file extension and determine the format
    file_extension = os.path.splitext(image_path)[1].lower()
    if file_extension in ['.jpg', '.jpeg']:
        img_format = 'JPEG'
    elif file_extension == '.png':
        img_format = 'PNG'
    elif file_extension == '.gif':
        img_format = 'GIF'
    elif file_extension == '.bmp':
        img_format = 'BMP'
    else:
        raise ValueError(f"Unsupported file extension: {file_extension}")

    img.save(img_byte_arr, format=img_format, quality=100)
    img_byte_arr.seek(0)

    return img_byte_arr


def extract_metadata(image_path):
    with open(image_path, 'rb') as img_file:
        tags = exifread.process_file(img_file, details=False)
        metadata = {
            "Latitude": None,
            "Longitude": None,
        }
        if 'GPS GPSLatitude' in tags and 'GPS GPSLatitudeRef' in tags:
            lat_ref = tags['GPS GPSLatitudeRef'].values
            lat = tags['GPS GPSLatitude'].values
            metadata["Latitude"] = convert_to_degrees(lat) * (-1 if lat_ref != 'N' else 1)
        if 'GPS GPSLongitude' in tags and 'GPS GPSLongitudeRef' in tags:
            lon_ref = tags['GPS GPSLongitudeRef'].values
            lon = tags['GPS GPSLongitude'].values
            metadata["Longitude"] = convert_to_degrees(lon) * (-1 if lon_ref != 'E' else 1)
        return metadata


def convert_to_degrees(value):
    d = float(value[0].num) / float(value[0].den)
    m = float(value[1].num) / float(value[1].den)
    s = float(value[2].num) / float(value[2].den)
    return d + (m / 60.0) + (s / 3600.0)


def upload_to_s3(image_path, s3_client):
    img_byte_arr = resize_image(image_path)
    file_name = os.path.basename(image_path)
    s3_client.upload_fileobj(
        img_byte_arr,
        S3_BUCKET,
        file_name,
        ExtraArgs={'ContentType': 'image/jpeg'}
    )
    s3_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{file_name}"
    return s3_url


def process_folder(folder_path):
    s3_client = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=S3_REGION
    )

    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(('png', 'jpg', 'jpeg')):
                image_path = os.path.join(root, file)
                print(f"Processing {image_path}")

                metadata = extract_metadata(image_path)
                print(f"Metadata for {file}: {metadata}")

                s3_url = upload_to_s3(image_path, s3_client)
                print(f"Uploaded {file} to {s3_url}")

                store_metadata_in_mongo(metadata,s3_url )


def store_metadata_in_mongo(metadata, image_name):

    document = {
        'imageUrl': image_name,
        'userId':USERID,
        'farmId':FARMID,
        'status':"TO BE PROCESSED",
        'location': {
            'type': 'Point',
            'coordinates': [metadata['Longitude'], metadata['Latitude']]
        }
    }

    collection.insert_one(document)


if __name__ == "__main__":
    folder_path = input("Enter the path to the folder containing images: ")
    process_folder(folder_path)
