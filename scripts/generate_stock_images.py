"""Generate stock destination images using Gemini and upload to GCS."""

import os
from google import genai
from google.cloud import storage

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "bikram-java")
BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "us-travel-planner-media-bikram")

STOCK_IMAGES = {
    "zion_national_park": "A stunning professional photograph of Zion National Park Utah, showing the towering red sandstone canyon walls with the Virgin River below, golden hour light, dramatic landscape",
    "scenic_byway_12": "A professional photograph of Utah Scenic Byway 12, showing the winding road across The Hogback ridge with dramatic red rock canyon views on both sides, clear blue sky",
    "grand_canyon": "A professional photograph of the Grand Canyon South Rim at sunrise, showing the vast layered red and orange canyon stretching to the horizon with the Colorado River far below",
    "bryce_canyon": "A professional photograph of Bryce Canyon National Park Utah, showing the iconic orange and red hoodoo spires rising from the canyon floor under a deep blue sky",
    "salt_lake_city": "A professional photograph of Salt Lake City Utah skyline with the Wasatch Mountains covered in snow in the background, clear day, modern city view",
}


def generate_and_upload():
    client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(BUCKET_NAME)

    for slug, prompt in STOCK_IMAGES.items():
        print(f"Generating {slug}...")
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=f"Generate a vivid professional travel photo: {prompt}",
        )

        image_bytes = None
        for candidate in response.candidates or []:
            for part in candidate.content.parts or []:
                if part.inline_data and part.inline_data.data:
                    image_bytes = part.inline_data.data
                    break
            if image_bytes:
                break

        if not image_bytes:
            print(f"  WARNING: no image returned for {slug}")
            continue

        gcs_path = f"stock/{slug}.jpg"
        blob = bucket.blob(gcs_path)
        blob.upload_from_string(image_bytes, content_type="image/jpeg")
        url = f"https://storage.googleapis.com/{BUCKET_NAME}/{gcs_path}"
        print(f"  Uploaded: {url}")


if __name__ == "__main__":
    generate_and_upload()
