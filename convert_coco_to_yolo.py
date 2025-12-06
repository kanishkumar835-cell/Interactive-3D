import json
import os
import sys

def convert_coco_to_yolo(coco_json_path, save_path):
    """
    Converts COCO JSON annotations to YOLO format.
    """
    # Create the save directory if it doesn't exist
    if not os.path.exists(save_path):
        os.makedirs(save_path)

    # Load the COCO JSON file
    try:
        with open(coco_json_path, 'r') as f:
            coco_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: The file '{coco_json_path}' was not found.")
        print("Please make sure the path is correct and the file exists.")
        sys.exit(1)


    # Create mappings for images and categories
    images_info = {img['id']: img for img in coco_data['images']}
    categories = {cat['id']: cat['name'] for cat in coco_data['categories']}
    
    # Use a dictionary to store annotations for each image
    annotations_by_image = {}
    for ann in coco_data['annotations']:
        image_id = ann['image_id']
        if image_id not in annotations_by_image:
            annotations_by_image[image_id] = []
        annotations_by_image[image_id].append(ann)

    # Process each image and its annotations
    image_count = len(images_info)
    for i, (image_id, annotations) in enumerate(annotations_by_image.items()):
        image_info = images_info[image_id]
        image_width = image_info['width']
        image_height = image_info['height']
        
        # Get the base filename and create the corresponding label filename
        base_filename = os.path.basename(image_info['file_name'])
        label_filename = os.path.splitext(base_filename)[0] + '.txt'
        label_filepath = os.path.join(save_path, label_filename)

        with open(label_filepath, 'w') as f:
            for ann in annotations:
                # COCO bbox format: [x_min, y_min, width, height]
                bbox = ann['bbox']
                category_id = ann['category_id']

                # Convert to YOLO format: [class_id, x_center, y_center, width, height] (normalized)
                x_center = (bbox[0] + bbox[2] / 2) / image_width
                y_center = (bbox[1] + bbox[3] / 2) / image_height
                norm_width = bbox[2] / image_width
                norm_height = bbox[3] / image_height
                
                # The category IDs in CubiCasa5k start at 1, but YOLO needs them to start at 0.
                # So we subtract 1 from the category_id.
                yolo_class_id = category_id - 1
                
                f.write(f"{yolo_class_id} {x_center} {y_center} {norm_width} {norm_height}\n")
        
        # Print progress
        print(f"Processing... {i+1}/{image_count}", end='\r')

    print(f"\nConversion complete! YOLO labels saved in: {save_path}")


if __name__ == '__main__':
    # --- YOUR PATH IS CONFIGURED HERE ---
    
    # Path to the unzipped cubicasa5k folder based on your input
    base_cubicasa_path = r'C:\Users\kanis\pytorch_floorplan\cubicasa5k'
    
    # Path to the COCO annotation file
    json_file = os.path.join(base_cubicasa_path, 'coco_annotations.json')
    
    # Directory where you want to save the final .txt label files
    output_labels_dir = os.path.join(base_cubicasa_path, 'labels') 
    
    # --- RUN THE CONVERSION ---
    convert_coco_to_yolo(json_file, output_labels_dir)