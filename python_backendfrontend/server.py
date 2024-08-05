import gradio as gr
from PIL import Image, ImageDraw
import requests
from io import BytesIO
import numpy as np
from pymongo import MongoClient
from bson.objectid import ObjectId

# MongoDB connection setup
client = MongoClient("mongodb://localhost:27017/")  # Replace with your MongoDB connection string
db = client['aerialFarm']  # Replace with your database name
collection = db['farm_drone']  # Replace with your collection name

selected_points = []  # List to hold multiple points
current_object_id = None  # To keep track of the current image's Object ID

def fetch_image_details():
    try:
        # Fetch the next image document from the collection
        if(current_object_id!=None):
            image_document = collection.find_one({"_id": {"$gt": ObjectId(current_object_id)}})
        else:
            image_document = collection.find_one()

        if image_document:
            return (image_document['_id'],
                    image_document['imageUrl'],
                    image_document['annotationId'],
                    image_document['userId'],
                    image_document.get('annotationText', ''))  # Add annotationText field
        else:
            print("No image details found in the database.")
            return None, None, None, None, ''
    except Exception as e:
        print(f"Error fetching image details from MongoDB: {e}")
        return None, None, None, None, ''

def show_image():
    global current_object_id
    current_object_id, url, annotationId, userId, annotationText = fetch_image_details()
    if not url:
        return None, ''  # Return None for the image and an empty string for annotation text

    try:
        response = requests.get(url)
        img = Image.open(BytesIO(response.content))
        return np.array(img), annotationText  # Convert to NumPy array for Gradio
    except Exception as e:
        print(f"Error loading image: {e}")
        return None, ''  # Return None for the image and an empty string for annotation text

def annotate_image(img, selected_points, radius):
    img = Image.fromarray(img)  # Convert NumPy array back to Pillow image
    annotated_image = img.copy()

    # Draw the markers for all selected points
    draw = ImageDraw.Draw(annotated_image)
    for point in selected_points:
        x = point[0]
        y = point[1]
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline="black", width=2)

    return np.array(annotated_image)  # Convert back to NumPy array for Gradio

def select_image(image, evt: gr.SelectData):
    global selected_points
    selected_points.append((evt.index[0], evt.index[1]))
    return image, selected_points

def load_next_image(annotation_text_value):
    global selected_points, current_object_id
    print("Object ID:", current_object_id)
    print("Selected Points:", selected_points)
    print("Annotation Text:", annotation_text_value)

    # Update the document in MongoDB
    collection.update_one(
        {"_id": ObjectId(current_object_id)},
        {"$set": {
            "selectedPoints": selected_points,
            "annotationText": annotation_text_value
        }}
    )

    selected_points = []  # Reset selected points for new image
    img, annotationText = show_image()
    return img, img, ""  # Return the original image, annotated image, and reset annotation text

def clear_annotations(image):
    global selected_points
    selected_points = []  # Clear the selected points
    return image, image  # Return the original and cleared annotated image

with gr.Blocks() as demo:
    with gr.Row():
        with gr.Column():
            gr.Markdown("## Aerial Farm - Field Sales Person")
            image = gr.Image(value=lambda: show_image()[0], label="Click a point on the Original Image")
            circle_radius = gr.Slider(minimum=0, maximum=50, step=10, value=20, label="Affected Area Radius")
            with gr.Row():
                next_button = gr.Button("Save and Load Next Image")
                clear_button = gr.Button("Clear Annotations")
        with gr.Column():
            annotated_image = gr.Image(label="Annotated Image")
            annotation_text = gr.Textbox(label="Annotation Text", placeholder="Add your annotation here...")

    selected_points_state = gr.State()

    image.select(fn=select_image, inputs=[image], outputs=[image, selected_points_state])
    selected_points_state.change(fn=annotate_image, inputs=[image, selected_points_state, circle_radius], outputs=annotated_image)
    next_button.click(fn=load_next_image, inputs=[annotation_text], outputs=[image, annotated_image, annotation_text])
    clear_button.click(fn=clear_annotations, inputs=[image], outputs=[image, annotated_image])

    demo.launch()
