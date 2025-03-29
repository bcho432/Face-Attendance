import os
import json
import atexit
import requests
from flask import Flask, request, render_template, jsonify
from dataclasses import dataclass, asdict
import logging
import os
import shutil


@dataclass
class Person:
    name: str
    checked: int = 0

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API credentials (IMPORTANT: Replace with your actual credentials)
API_KEY = "2fewjHUCav3AAH7CapRbbzH08rVTYM5r"
API_SECRET = "PziGAoFKlZUG2NdAd67tE9blEaBAVtPE"

# Define file to persist check-in data
CHECK_IN_FILE = 'check_in_records.json'

def clear_image_directory(directory='images'):
    """
    Completely clear the specified image directory.
    
    Args:
        directory (str, optional): Path to the image directory. Defaults to 'images'.
    """
    try:
        # Check if directory exists
        if os.path.exists(directory):
            # Remove all files in the directory
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    print(f"Failed to delete {file_path}. Reason: {e}")
        else:
            print(f"Directory {directory} does not exist.")
    except Exception as e:
        print(f"Error clearing image directory: {e}")

# Add this to your existing code, potentially in the __main__ block or as an atexit handler
atexit.register(clear_image_directory)

def clear_check_in_records():
    """Clear all check-in records."""
    try:
        with open(CHECK_IN_FILE, 'w') as f:
            json.dump([], f)
        logger.info("Check-in records cleared.")
    except Exception as e:
        logger.error(f"Error clearing check-in records: {e}")

# Register the cleanup function to run when the program exits
atexit.register(clear_check_in_records)

def load_check_in_records():
    """Load check-in records from a JSON file."""
    try:
        with open(CHECK_IN_FILE, 'r') as f:
            return [Person.from_dict(record) for record in json.load(f)]
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_check_in_records(records):
    """Save check-in records to a JSON file."""
    with open(CHECK_IN_FILE, 'w') as f:
        json.dump([record.to_dict() for record in records], f)

def print_unchecked_people():
    """Print all people who have not been checked in."""
    images_check = load_check_in_records()
    unchecked = [p for p in images_check if p.checked != 1]
    
    if unchecked:
        print("\n--- Unchecked People ---")
        for person in unchecked:
            print(f"{person.name}")
    else:
        print("\nAll people have been checked in!")

# Define the directory containing images
IMAGE_DIRECTORY = "images"

# Make sure the directory exists
os.makedirs(IMAGE_DIRECTORY, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_reference', methods=['POST'])
def upload_reference_image():
    # Get the uploaded files
    if 'image' not in request.files:
        return jsonify({'success': False, 'message': 'No file part'}), 400
    
    image_file = request.files['image']
    
    if image_file.filename == '':
        return jsonify({'success': False, 'message': 'No selected file'}), 400
    
    # Get the student's first and last name from the form
    first_name = request.form.get('first_name', '').lower()
    last_name = request.form.get('last_name', '').lower()
    
    if not first_name or not last_name:
        return jsonify({'success': False, 'message': 'First and last name are required'}), 400
    
    # Load existing records
    images_check = load_check_in_records()
    
    # Create person and add to images_check
    p = Person(name=f"{first_name} {last_name}")
    images_check.append(p)
    
    # Save updated records
    save_check_in_records(images_check)
    
    logger.info(f"Added reference image for {p.name}")
    
    # Generate filename
    filename = f"{first_name}_{last_name}.jpg"
    file_path = os.path.join(IMAGE_DIRECTORY, filename)
    
    # Save the image
    try:
        image_file.save(file_path)
        return jsonify({
            'success': True, 
            'message': f'Reference image for {first_name} {last_name} uploaded successfully!'
        })
    except Exception as e:
        return jsonify({
            'success': False, 
            'message': f'Error uploading image: {str(e)}'
        }), 500

@app.route('/upload', methods=['POST'])
def upload_image():
    # Get the uploaded files
    if 'image' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    image_file = request.files['image']
    
    if image_file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    checked_list = []
    
    # Save the uploaded image
    image1_path = os.path.join(IMAGE_DIRECTORY, 'captured_image.jpg')
    image_file.save(image1_path)
    
    # Get the student's first and last name from the form
    first_name = request.form.get('first_name', '').lower()
    last_name = request.form.get('last_name', '').lower()
    full_name = f"{first_name} {last_name}"
    
    if not first_name or not last_name:
        return jsonify({'error': 'First and last name are required'}), 400
    
    # Load existing records
    images_check = load_check_in_records()
    
    # List all image files in the directory
    image_files = [file for file in os.listdir(IMAGE_DIRECTORY) 
                   if file.lower().endswith(('.jpg', '.jpeg'))]
    
    # Find the matching person in images_check
    matching_person = next((p for p in images_check if p.name.lower() == full_name), None)
    
    # If no matching person found, create a new one
    if not matching_person:
        matching_person = Person(name=full_name)
        images_check.append(matching_person)
    
    for image2_path in image_files:
        # Skip if the file doesn't match the student's name pattern
        if not (first_name + last_name + ".jpg" in image2_path.lower() or
                first_name + "_" + last_name + ".jpg" in image2_path.lower() or
                first_name + last_name + ".jpeg" in image2_path.lower() or
                first_name + "_" + last_name + ".jpeg" in image2_path.lower()):
            continue
        
        image2_full_path = os.path.join(IMAGE_DIRECTORY, image2_path)
        
        # Send the images to the Face++ API for comparison
        try:
            with open(image1_path, 'rb') as image1, open(image2_full_path, 'rb') as image2:
                files = {
                    'image_file1': image1,
                    'image_file2': image2
                }
                
                payload = {
                    'api_key': API_KEY,
                    'api_secret': API_SECRET
                }
                
                response = requests.post(
                    'https://api-us.faceplusplus.com/facepp/v3/compare', 
                    files=files, 
                    data=payload
                )
                
                if response.status_code != 200:
                    logger.error(f"API request failed with status code {response.status_code}")
                    logger.error(response.text)
                    continue
                
                result = response.json()
                
                # Check if faces were detected and compared
                if 'confidence' in result:
                    similarity_score = result['confidence']
                    logger.info(f"Similarity Score: {similarity_score}")
                    
                    # Set a threshold for deciding if it's the same person
                    if similarity_score > 75:
                        checked_list.append(f"✅ {image2_path} is likely the same person. Similarity Score: {similarity_score:.2f}")
                        
                        # Update the matching person's check-in status
                        matching_person.checked = 1
                        logger.info(f"Checked in: {matching_person.name}")
                        
                        # Save the updated records
                        save_check_in_records(images_check)
                        
                        # Exit the loop after successful check-in
                        break
                    else:
                        checked_list.append(f"❌ {image2_path} is likely a different person. Similarity Score: {similarity_score:.2f}")
                else:
                    checked_list.append(f"Could not compare faces for {image2_path}.")
        
        except Exception as e:
            logger.error(f"Error comparing images: {e}")
            checked_list.append(f"Error comparing {image2_path}")
    
    # Print unchecked people after processing
    print_unchecked_people()
    
    # Log the current state of images_check
    logger.info("Current images_check: %s", [p.name for p in images_check])
    
    # Render the results in the HTML
    return render_template('results.html', results=checked_list)

@app.route('/clear_images', methods=['POST'])
def clear_images():
    clear_image_directory()
    return jsonify({'success': True, 'message': 'Images cleared successfully'})

@app.route('/get_check_ins', methods=['GET'])
def get_check_ins():
    """Endpoint to retrieve all check-in records."""
    images_check = load_check_in_records()
    return jsonify([
        {
            'name': p.name, 
            'checked': p.checked
        } for p in images_check
    ])

@app.route('/remove_student', methods=['POST'])
def remove_student():
    """
    Remove a student from check-in records and delete their reference image.
    """
    first_name = request.form.get('first_name', '').lower()
    last_name = request.form.get('last_name', '').lower()
    full_name = f"{first_name} {last_name}"
    
    if not first_name or not last_name:
        return jsonify({'success': False, 'message': 'First and last name are required'}), 400
    
    # Load existing records
    images_check = load_check_in_records()
    
    # Find and remove the student from check-in records
    images_check = [p for p in images_check if p.name.lower() != full_name]
    
    # Save updated records
    save_check_in_records(images_check)
    
    # Remove reference image
    image_filename_patterns = [
        f"{first_name}_{last_name}.jpg",
        f"{first_name}{last_name}.jpg",
        f"{first_name}_{last_name}.jpeg",
        f"{first_name}{last_name}.jpeg"
    ]
    
    image_removed = False
    for filename in image_filename_patterns:
        file_path = os.path.join(IMAGE_DIRECTORY, filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                image_removed = True
                logger.info(f"Removed image for {full_name}")
                break
            except Exception as e:
                logger.error(f"Error removing image {filename}: {e}")
    
    return jsonify({
        'success': True, 
        'message': f'Student {full_name} removed. ' + 
                   ('Image deleted.' if image_removed else 'No image found.')
    })

if __name__ == '__main__':
    clear_check_in_records()
    clear_image_directory()
    app.run(debug=True, host='0.0.0.0', port=5001)