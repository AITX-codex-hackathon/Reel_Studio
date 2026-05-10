from PIL import Image

def crop_to_content(input_path, output_path):
    img = Image.open(input_path).convert("RGBA")
    
    # Get bounding box of non-transparent pixels
    bbox = img.getbbox()
    if bbox:
        img_cropped = img.crop(bbox)
        
        # Make it square if we want a nice favicon, padding with transparent pixels
        w, h = img_cropped.size
        size = max(w, h)
        
        new_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        # paste centered
        x = (size - w) // 2
        y = (size - h) // 2
        new_img.paste(img_cropped, (x, y))
        
        new_img.save(output_path, "PNG")
        print(f"Cropped and saved to {output_path}")
    else:
        print("Image is entirely empty/transparent.")

crop_to_content("frontend/public/logo_transparent_fallback.png", "frontend/public/logo_cropped.png")
