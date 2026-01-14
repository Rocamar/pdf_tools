import os
from pypdf import PdfWriter, PdfReader

def merge_pdfs(file_list, output_path):
    """
    Une una lista de archivos PDF en uno solo.
    """
    merger = PdfWriter()
    for pdf in file_list:
        merger.append(pdf)
    merger.write(output_path)
    merger.close()

def parse_page_range(range_str, max_pages):
    """
    Convierte una cadena como '1,3,5-8' en una lista de índices (0-indexed).
    """
    if not range_str or not range_str.strip():
        return list(range(max_pages))
    
    pages = set()
    parts = range_str.replace(' ', '').split(',')
    
    for part in parts:
        if '-' in part:
            try:
                start, end = map(int, part.split('-'))
                # Asegurar que esté dentro del rango y sea válido
                start = max(1, min(start, max_pages))
                end = max(1, min(end, max_pages))
                for p in range(min(start, end), max(start, end) + 1):
                    pages.add(p - 1)
            except ValueError:
                continue
        else:
            try:
                p = int(part)
                if 1 <= p <= max_pages:
                    pages.add(p - 1)
            except ValueError:
                continue
                
    return sorted(list(pages))

def split_pdf(file_path, output_dir, pages_to_extract=None):
    """
    Divide un PDF en archivos individuales. 
    pages_to_extract: lista de índices 0-indexed. Si es None, divide todo.
    """
    reader = PdfReader(file_path)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    
    if pages_to_extract is None:
        pages_to_extract = range(len(reader.pages))
    
    generated_files = []
    
    for i in pages_to_extract:
        if i < len(reader.pages):
            writer = PdfWriter()
            writer.add_page(reader.pages[i])
            output_filename = os.path.join(output_dir, f"{base_name}_page_{i+1}.pdf")
            writer.write(output_filename)
            writer.close()
            generated_files.append(output_filename)
        
    return generated_files

def extract_pages_to_one_pdf(input_path, output_path, pages):
    """
    Extrae páginas específicas a un nuevo archivo PDF único.
    pages: lista de índices 0-indexed.
    """
    reader = PdfReader(input_path)
    writer = PdfWriter()
    
    for i in pages:
        if 0 <= i < len(reader.pages):
            writer.add_page(reader.pages[i])
            
    with open(output_path, 'wb') as f:
        writer.write(f)
    writer.close()

def rotate_pdf(file_path, degrees, output_path):
    """
    Rota todas las páginas de un PDF.
    """
    reader = PdfReader(file_path)
    writer = PdfWriter()
    
    for page in reader.pages:
        page.rotate(degrees)
        writer.add_page(page)
        
    writer.write(output_path)
    writer.close()

def extract_text(file_path):
    """
    Extrae el texto de un archivo PDF.
    """
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def add_text_to_pdf(input_path, output_path, text, page_num, x, y, font_size=12, color=(0, 0, 0)):
    """
    Agrega texto a una página específica del PDF.
    page_num: número de página (1-indexed)
    x, y: coordenadas en puntos (0,0 es esquina inferior izquierda)
    color: tupla RGB con valores 0-1
    """
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    import io
    
    # Leer el PDF original
    reader = PdfReader(input_path)
    writer = PdfWriter()
    
    # Normalizar color a valores 0-1
    if all(isinstance(c, int) for c in color):
        color = tuple(c / 255.0 for c in color)
    
    # Crear un PDF temporal con el texto
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    can.setFont("Helvetica", font_size)
    can.setFillColorRGB(*color)
    can.drawString(x, y, text)
    can.save()
    
    # Mover al inicio del buffer
    packet.seek(0)
    overlay_pdf = PdfReader(packet)
    
    # Agregar páginas
    for i, page in enumerate(reader.pages):
        if i == page_num - 1:  # Convertir a 0-indexed
            page.merge_page(overlay_pdf.pages[0])
        writer.add_page(page)
    
    # Guardar el resultado
    with open(output_path, 'wb') as output_file:
        writer.write(output_file)

def add_image_to_pdf(input_path, output_path, image_path, page_num, x, y, width, height):
    """
    Agrega una imagen a una página específica del PDF.
    page_num: número de página (1-indexed)
    x, y: coordenadas en puntos (0,0 es esquina inferior izquierda)
    width, height: dimensiones de la imagen en puntos
    """
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    import io
    
    # Leer el PDF original
    reader = PdfReader(input_path)
    writer = PdfWriter()
    
    # Crear un PDF temporal con la imagen
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    can.drawImage(image_path, x, y, width=width, height=height, preserveAspectRatio=True, mask='auto')
    can.save()
    
    # Mover al inicio del buffer
    packet.seek(0)
    overlay_pdf = PdfReader(packet)
    
    # Agregar páginas
    for i, page in enumerate(reader.pages):
        if i == page_num - 1:  # Convertir a 0-indexed
            page.merge_page(overlay_pdf.pages[0])
        writer.add_page(page)
    
    # Guardar el resultado
    with open(output_path, 'wb') as output_file:
        writer.write(output_file)

def delete_pages(input_path, output_path, pages_to_delete):
    """
    Elimina páginas específicas de un PDF.
    pages_to_delete: lista de números de página (1-indexed) a eliminar
    """
    reader = PdfReader(input_path)
    writer = PdfWriter()
    
    total_pages = len(reader.pages)
    pages_to_delete_set = set(pages_to_delete)
    
    for i in range(total_pages):
        if (i + 1) not in pages_to_delete_set:  # Convertir a 1-indexed para comparar
            writer.add_page(reader.pages[i])
    
    with open(output_path, 'wb') as output_file:
        writer.write(output_file)

def reorder_pages(input_path, output_path, new_order):
    """
    Reordena las páginas de un PDF según una lista de índices.
    new_order: lista de números de página (1-indexed) en el nuevo orden
    Ejemplo: [3, 1, 2] moverá la página 3 al inicio
    """
    reader = PdfReader(input_path)
    writer = PdfWriter()
    
    for page_num in new_order:
        if 1 <= page_num <= len(reader.pages):
            writer.add_page(reader.pages[page_num - 1])  # Convertir a 0-indexed
    
    with open(output_path, 'wb') as output_file:
        writer.write(output_file)

def get_pdf_page_count(file_path):
    """
    Retorna el número total de páginas de un PDF.
    """
    reader = PdfReader(file_path)
    return len(reader.pages)

def get_pdf_page_size(file_path, page_num=1):
    """
    Retorna el tamaño de una página en puntos (width, height).
    """
    reader = PdfReader(file_path)
    if 1 <= page_num <= len(reader.pages):
        page = reader.pages[page_num - 1]
        # pypdf usa mediabox para dimensiones en puntos
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        return width, height
    return 612.0, 792.0

def pdf_page_to_image(file_path, page_num, dpi=150):
    """
    Convierte una página específica del PDF a imagen PIL.
    page_num: número de página (1-indexed)
    dpi: resolución de la imagen (default 150)
    Retorna: imagen PIL
    """
    from pdf2image import convert_from_path
    
    # Convertir solo la página específica
    images = convert_from_path(
        file_path,
        dpi=dpi,
        first_page=page_num,
        last_page=page_num
    )
    
    return images[0] if images else None

def pdf_to_images(file_path, dpi=150, max_pages=None):
    """
    Convierte todas las páginas del PDF a imágenes PIL.
    dpi: resolución de las imágenes (default 150)
    max_pages: número máximo de páginas a convertir (None = todas)
    Retorna: lista de imágenes PIL
    """
    from pdf2image import convert_from_path
    
    last_page = max_pages if max_pages else None
    
    images = convert_from_path(
        file_path,
        dpi=dpi,
        last_page=last_page
    )
    
    return images

def export_pdf_to_images(file_path, output_dir, dpi=150):
    """
    Exporta todas las páginas de un PDF como archivos de imagen individuales.
    """
    from pdf2image import convert_from_path
    import os
    
    images = convert_from_path(file_path, dpi=dpi)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    
    generated_paths = []
    for i, image in enumerate(images):
        output_filename = f"{base_name}_page_{i+1}.png"
        full_path = os.path.join(output_dir, output_filename)
        image.save(full_path, "PNG")
        generated_paths.append(full_path)
        
    return generated_paths

def convert_pdf_to_word(input_path, output_path):
    """
    Convierte un PDF a formato Word (.docx) usando pdf2docx.
    """
    from pdf2docx import Converter
    cv = Converter(input_path)
    cv.convert(output_path, start=0, end=None)
    cv.close()

def convert_pdf_to_excel(input_path, output_path):
    """
    Extrae tablas de un PDF a formato Excel (.xlsx) usando pdfplumber y pandas.
    """
    import pdfplumber
    import pandas as pd
    
    all_tables = []
    with pdfplumber.open(input_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                df = pd.DataFrame(table[1:], columns=table[0])
                all_tables.append(df)
    
    if all_tables:
        # Si la extensión es .ods, intentamos usar LibreOffice después de generar el .xlsx
        # o usamos un motor que soporte .ods si está disponible. Por simplicidad y robustez,
        # generamos .xlsx y luego convertimos si es necesario, o usamos odfpy si estuviera disponible.
        # Aquí usaremos la conversión via CLI de LibreOffice para asegurar compatibilidad total.
        
        is_ods = output_path.lower().endswith('.ods')
        temp_xlsx = output_path if not is_ods else output_path + ".xlsx"
        
        with pd.ExcelWriter(temp_xlsx) as writer:
            for i, df in enumerate(all_tables):
                df.to_excel(writer, sheet_name=f'Tabla_{i+1}', index=False)
        
        if is_ods:
            import subprocess
            try:
                # Convertir xlsx a ods usando LibreOffice
                subprocess.run(['libreoffice', '--headless', '--convert-to', 'ods', temp_xlsx, '--outdir', os.path.dirname(output_path)], check=True)
                if os.path.exists(temp_xlsx):
                    os.remove(temp_xlsx)
            except Exception as e:
                raise RuntimeError(f"Error al convertir a ODS: {str(e)}")
    else:
        raise ValueError("No se encontraron tablas en el PDF.")

def convert_pdf_to_odt(input_path, output_path):
    """
    Convierte un PDF a formato LibreOffice Writer (.odt) usando LibreOffice CLI.
    Nota: LibreOffice no convierte directamente de PDF a ODT de forma perfecta vía CLI,
    a menudo lo abre en Draw. Una mejor alternativa es convertir a docx y luego a odt
    o usar un conversor intermedio.
    """
    import subprocess
    import tempfile
    
    # Primero convertimos a docx (que es más fiel al contenido de texto)
    temp_docx = tempfile.mktemp(suffix=".docx")
    convert_pdf_to_word(input_path, temp_docx)
    
    try:
        # Luego convertimos de docx a odt
        subprocess.run(['libreoffice', '--headless', '--convert-to', 'odt', temp_docx, '--outdir', os.path.dirname(output_path)], check=True)
        # El comando anterior genera un archivo con el mismo nombre base que el input en el outdir
        generated_odt = os.path.join(os.path.dirname(output_path), os.path.basename(temp_docx).replace('.docx', '.odt'))
        if os.path.exists(generated_odt):
            if os.path.exists(output_path): os.remove(output_path)
            os.rename(generated_odt, output_path)
        
        if os.path.exists(temp_docx):
            os.remove(temp_docx)
    except Exception as e:
        if os.path.exists(temp_docx): os.remove(temp_docx)
        raise RuntimeError(f"Error al convertir a ODT: {str(e)}")

def convert_pdf_to_ods(input_path, output_path):
    """
    Convierte un PDF a formato LibreOffice Calc (.ods) extrayendo tablas.
    """
    return convert_pdf_to_excel(input_path, output_path)

def sign_pdf_digitally(input_path, output_path, certificate_path, password):
    """
    Firma digitalmente un PDF usando un certificado .p12 o .pfx y pyHanko.
    """
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import signers
    from pyhanko.sign.fields import SigSeedValueSpec
    
    signer = signers.SimpleSigner.load_pkcs12(
        pfx_file=certificate_path,
        passphrase=password.encode() if password else None
    )
    
    with open(input_path, 'rb') as inf:
        w = IncrementalPdfFileWriter(inf)
        with open(output_path, 'wb') as outf:
            signers.sign_pdf(
                w, signers.PdfSignatureMetadata(field_name='Signature1'),
                signer=signer, output=outf
            )

def add_link_to_pdf(input_path, output_path, page_num, x, y, width, height, url):
    """
    Agrega un enlace (Annotation) a una página específica del PDF.
    """
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import AnnotationBuilder
    
    reader = PdfReader(input_path)
    writer = PdfWriter()
    
    for i, page in enumerate(reader.pages):
        writer.add_page(page)
        if i == page_num - 1:
            # rect: [xLL, yLL, xUR, yUR]
            link_ann = AnnotationBuilder.make_link_annotation(
                rect=[x, y, x + width, y + height],
                url=url
            )
            writer.add_annotation(page_number=i, annotation=link_ann)
            
    with open(output_path, "wb") as f:
        writer.write(f)

def find_text_coordinates(file_path, query):
    """
    Busca todas las coordenadas de un texto en el PDF.
    Retorna una lista de diccionarios con la página y el rectángulo [x, y, w, h].
    """
    from pypdf import PdfReader
    import re
    
    reader = PdfReader(file_path)
    all_matches = []
    
    for page_index, page in enumerate(reader.pages):
        page_num = page_index + 1
        
        def visitor_body(text, cm, tm, font_dict, font_size):
            if not text.strip():
                return
                
            # Buscar el query dentro del texto del chunk (insensible a mayúsculas)
            lower_text = text.lower()
            lower_query = query.lower()
            
            if lower_query in lower_text:
                # El "tm" (Text Matrix) nos da la posición base del chunk [a, b, c, d, e, f]
                # e = tm[4], f = tm[5]
                base_x = tm[4]
                base_y = tm[5]
                
                # Encontrar todas las ocurrencias en este chunk
                for m in re.finditer(re.escape(lower_query), lower_text):
                    start_idx = m.start()
                    
                    # Estimación de desplazamiento horizontal:
                    # El ancho aproximado de los caracteres antes de la coincidencia
                    # Usamos una media de 0.5 * font_size por caracter (esto es una aproximación para fuentes proporcionales)
                    offset_x = start_idx * font_size * 0.5
                    
                    # Ancho de la palabra buscada
                    w = len(query) * font_size * 0.5
                    h = font_size
                    
                    all_matches.append({
                        "page": page_num,
                        "rect": [base_x + offset_x, base_y, w, h]
                    })
        
        page.extract_text(visitor_text=visitor_body)
            
    return all_matches
