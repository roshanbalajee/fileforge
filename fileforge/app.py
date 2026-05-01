import os
import uuid
from flask import Flask, render_template, request, send_file, redirect, url_for, flash
from werkzeug.utils import secure_filename
from PIL import Image
from PyPDF2 import PdfMerger
import time
from pdf2image import convert_from_path
import zipfile
import fitz # PyMuPDF

app = Flask(__name__)
app.secret_key = "fileforge_super_secret_key"

# Configuration
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
ALLOWED_PDF_EXTENSIONS = {'pdf'}
POPPLER_PATH = r"C:\poppler\Library\bin" # Manual path for Poppler

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def cleanup_old_files():
    """Delete files older than 30 minutes in uploads and outputs."""
    now = time.time()
    for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
        if not os.path.exists(folder): continue
        for filename in os.listdir(folder):
            filepath = os.path.join(folder, filename)
            if os.stat(filepath).st_mtime < now - 1800:
                try:
                    os.remove(filepath)
                except:
                    pass

def pdf_to_images_fallback(pdf_path, output_folder, unique_id):
    """Fallback using PyMuPDF if pdf2image (poppler) fails."""
    doc = fitz.open(pdf_path)
    images = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap()
        page_filename = f"page_{i+1}.png"
        output_file = os.path.join(output_folder, f"fallback_{unique_id}_{page_filename}")
        pix.save(output_file)
        images.append((output_file, page_filename))
    doc.close()
    return images

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/compress', methods=['GET', 'POST'])
def image_compress():
    if request.method == 'POST':
        cleanup_old_files()
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        quality_val = request.form.get('quality', 'medium')
        
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename, ALLOWED_IMAGE_EXTENSIONS):
            filename = secure_filename(file.filename)
            unique_id = str(uuid.uuid4())[:8]
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{unique_id}_{filename}")
            file.save(input_path)
            
            # Compression logic
            quality = 50 # Default Medium
            if quality_val == 'low': quality = 80
            elif quality_val == 'high': quality = 20
            
            output_filename = f"compressed_{unique_id}_{filename}"
            output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
            
            try:
                img = Image.open(input_path)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(output_path, optimize=True, quality=quality)
                return render_template('image_compress.html', download_url=output_filename, success=True)
            except Exception as e:
                flash(f'Error processing image: {str(e)}', 'error')
                return redirect(request.url)
        else:
            flash('Invalid file type.', 'error')
            return redirect(request.url)
            
    return render_template('image_compress.html')

@app.route('/merge', methods=['GET', 'POST'])
def pdf_merge():
    if request.method == 'POST':
        cleanup_old_files()
        if 'files' not in request.files:
            flash('No files part', 'error')
            return redirect(request.url)
        
        files = request.files.getlist('files')
        if not files or files[0].filename == '':
            flash('No files selected', 'error')
            return redirect(request.url)
        
        merger = PdfMerger()
        processed_any = False
        
        try:
            for file in files:
                if file and allowed_file(file.filename, ALLOWED_PDF_EXTENSIONS):
                    filename = secure_filename(file.filename)
                    unique_id = str(uuid.uuid4())[:8]
                    path = os.path.join(app.config['UPLOAD_FOLDER'], f"{unique_id}_{filename}")
                    file.save(path)
                    merger.append(path)
                    processed_any = True
            
            if processed_any:
                output_filename = f"merged_{str(uuid.uuid4())[:8]}.pdf"
                output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
                merger.write(output_path)
                merger.close()
                return render_template('pdf_merge.html', download_url=output_filename, success=True)
            else:
                flash('No valid PDF files found.', 'error')
                return redirect(request.url)
        except Exception as e:
            flash(f'Error merging PDFs: {str(e)}', 'error')
            return redirect(request.url)
            
    return render_template('pdf_merge.html')

@app.route('/convert', methods=['GET', 'POST'])
def image_convert():
    if request.method == 'POST':
        cleanup_old_files()
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        target_format = request.form.get('format', 'PNG').upper()
        
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename, ALLOWED_IMAGE_EXTENSIONS):
            filename = secure_filename(file.filename)
            unique_id = str(uuid.uuid4())[:8]
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{unique_id}_{filename}")
            file.save(input_path)
            
            output_filename = f"converted_{unique_id}.{target_format.lower()}"
            output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
            
            try:
                img = Image.open(input_path)
                if target_format in ['JPG', 'JPEG']:
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    img.save(output_path, "JPEG")
                else:
                    img.save(output_path, target_format)
                
                return render_template('image_convert.html', download_url=output_filename, success=True)
            except Exception as e:
                flash(f'Error converting image: {str(e)}', 'error')
                return redirect(request.url)
        else:
            flash('Invalid file type.', 'error')
            return redirect(request.url)
            
    return render_template('image_convert.html')

@app.route('/image-to-pdf', methods=['GET', 'POST'])
def image_to_pdf():
    if request.method == 'POST':
        cleanup_old_files()
        files = request.files.getlist('files')
        if not files or files[0].filename == '':
            flash('No files selected', 'error')
            return redirect(request.url)
        
        images = []
        try:
            for file in files:
                if file and allowed_file(file.filename, ALLOWED_IMAGE_EXTENSIONS):
                    filename = secure_filename(file.filename)
                    path = os.path.join(app.config['UPLOAD_FOLDER'], f"{str(uuid.uuid4())[:8]}_{filename}")
                    file.save(path)
                    img = Image.open(path)
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    images.append(img)
            
            if images:
                output_filename = f"images_to_pdf_{str(uuid.uuid4())[:8]}.pdf"
                output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
                images[0].save(output_path, save_all=True, append_images=images[1:])
                return render_template('image_to_pdf.html', download_url=output_filename, success=True)
            else:
                flash('No valid images uploaded', 'error')
                return redirect(request.url)
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
            return redirect(request.url)
            
    return render_template('image_to_pdf.html')

@app.route('/pdf-to-image', methods=['GET', 'POST'])
def pdf_to_image():
    if request.method == 'POST':
        cleanup_old_files()
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename, ALLOWED_PDF_EXTENSIONS):
            filename = secure_filename(file.filename)
            unique_id = str(uuid.uuid4())[:8]
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{unique_id}_{filename}")
            file.save(input_path)
            
            try:
                # Try pdf2image (poppler) first
                try:
                    if os.path.exists(POPPLER_PATH):
                        pages = convert_from_path(input_path, poppler_path=POPPLER_PATH)
                    else:
                        pages = convert_from_path(input_path)
                    
                    if len(pages) == 1:
                        output_filename = f"pdf_page_{unique_id}.png"
                        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
                        pages[0].save(output_path, 'PNG')
                    else:
                        output_filename = f"pdf_pages_{unique_id}.zip"
                        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
                        with zipfile.ZipFile(output_path, 'w') as zipf:
                            for i, page in enumerate(pages):
                                page_filename = f"page_{i+1}.png"
                                temp_path = os.path.join(app.config['OUTPUT_FOLDER'], f"temp_{unique_id}_{page_filename}")
                                page.save(temp_path, 'PNG')
                                zipf.write(temp_path, page_filename)
                                os.remove(temp_path)
                    
                    return render_template('pdf_to_image.html', download_url=output_filename, success=True)
                
                except Exception:
                    # Fallback to PyMuPDF
                    fallback_images = pdf_to_images_fallback(input_path, app.config['OUTPUT_FOLDER'], unique_id)
                    
                    if len(fallback_images) == 1:
                        # Move fallback file to final output_filename
                        output_filename = f"pdf_page_{unique_id}.png"
                        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
                        os.rename(fallback_images[0][0], output_path)
                    else:
                        output_filename = f"pdf_pages_{unique_id}.zip"
                        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
                        with zipfile.ZipFile(output_path, 'w') as zipf:
                            for temp_file, page_name in fallback_images:
                                zipf.write(temp_file, page_name)
                                os.remove(temp_file)
                    
                    return render_template('pdf_to_image.html', download_url=output_filename, success=True)
                    
            except Exception as e:
                flash(f"Error converting PDF: {str(e)}", "error")
                return redirect(request.url)
        else:
            flash('Invalid file type. Only PDF allowed.', 'error')
            return redirect(request.url)
            
    return render_template('pdf_to_image.html')

@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
    
    # Basic mimetype detection
    ext = filename.rsplit('.', 1)[-1].lower()
    mimetypes = {
        'pdf': 'application/pdf',
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'webp': 'image/webp',
        'zip': 'application/zip'
    }
    mimetype = mimetypes.get(ext, 'application/octet-stream')
    
    return send_file(
        file_path,
        as_attachment=True,
        download_name=filename,
        mimetype=mimetype
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)
