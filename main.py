import customtkinter as ctk
from tkinter import filedialog, messagebox, Canvas, colorchooser
import os
import pdf_tools
from PIL import Image, ImageTk, ImageDraw, ImageFont
import threading

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class InteractivePDFViewer(ctk.CTkScrollableFrame):
    """Visor interactivo de PDF con capacidad de edición directa"""
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.current_pdf = None
        self.zoom_level = 1.0
        self.zoom_mode = 'fit_width'  # 'fixed' or 'fit_width'
        self.pages_data = []  # Lista de {canvas, image, page_num, width, height}
        self.interaction_mode = 'view'  # 'view', 'add_text', 'add_image', 'select_pages'
        self.on_click_callback = None
        self.selected_pages = set()
        self.resize_timer = None
        self.last_width = 0
        
        # Vincular evento de resize para modo responsivo
        self.bind("<Configure>", self._on_container_resize)
        
        # Info panel
        self.info_frame = ctk.CTkFrame(self)
        self.info_frame.pack(fill="x", padx=5, pady=5)
        
        self.info_label = ctk.CTkLabel(self.info_frame, text="Ningún PDF cargado", 
                                       font=("Arial", 11))
        self.info_label.pack(pady=5)
        
    def load_pdf(self, file_path):
        """Carga y muestra las páginas del PDF de forma incremental"""
        self.clear()
        self.current_pdf = file_path
        self.loading_active = True
        
        # Mostrar mensaje de carga inicial
        self.loading_label = ctk.CTkLabel(self, text="Iniciando carga de PDF...", 
                                         font=("Arial", 14))
        self.loading_label.pack(pady=20)
        
        def load_incremental():
            try:
                # Obtener número de páginas
                total_pages = pdf_tools.get_pdf_page_count(file_path)
                self.after(0, lambda: self.loading_label.configure(text=f"Cargando {total_pages} páginas..."))
                
                for i in range(1, total_pages + 1):
                    if not self.loading_active:
                        break
                        
                    # Cargar una sola página a la vez
                    # Factor de conversión: 150 DPI / 72 DPI (estándar PDF) = 2.0833
                    img = pdf_tools.pdf_page_to_image(file_path, i, dpi=int(150 * self.zoom_level))
                    
                    if img:
                        # Mostrar página en la UI
                        self.after(0, lambda p=img, n=i: self._add_page_to_ui(p, n, total_pages))
                
                # Al finalizar, remover label de carga
                self.after(0, self._finalize_loading)
                
            except Exception as e:
                self.after(0, lambda: self._show_error(str(e)))
        
        if self.zoom_mode == 'fit_width':
            self.update_idletasks()
            available_width = self.winfo_width()
            if available_width <= 1:
                available_width = self.master.winfo_width() - 40
            
            # Obtener ancho real del PDF en puntos
            try:
                pdf_w, _ = pdf_tools.get_pdf_page_size(file_path, 1)
            except:
                pdf_w = 612.0
            
            # Pixel width at 150 DPI = points * 150 / 72
            base_pixel_width = pdf_w * 150 / 72
            
            if available_width > 100:
                self.zoom_level = (available_width - 50) / base_pixel_width
            else:
                self.zoom_level = 1.0
            self.last_width = available_width

        self.load_thread = threading.Thread(target=load_incremental, daemon=True)
        self.load_thread.start()

    def _on_container_resize(self, event):
        """Maneja el redimensionamiento del contenedor"""
        if self.zoom_mode == 'fit_width' and self.current_pdf:
            new_width = event.width
            if abs(new_width - self.last_width) < 10:
                return
            
            self.last_width = new_width
            
            # Debounce para recarga (renderizado de alta calidad)
            if self.resize_timer:
                self.after_cancel(self.resize_timer)
            self.resize_timer = self.after(400, self._apply_fit_width)

    def _apply_fit_width(self):
        """Calcula el zoom final y recarga si es necesario"""
        if not self.current_pdf or self.zoom_mode != 'fit_width':
            return
            
        available_width = self.winfo_width() - 50
        if available_width < 100: return

        # Obtener ancho real del PDF
        try:
            pdf_w, _ = pdf_tools.get_pdf_page_size(self.current_pdf, 1)
        except:
            pdf_w = 612.0
            
        base_pixel_width = pdf_w * 150 / 72
        new_zoom = available_width / base_pixel_width
        
        # Si el zoom cambia significativamente, recargamos para calidad
        if abs(new_zoom - self.zoom_level) > 0.05:
            self.set_zoom(new_zoom, mode='fit_width')
    
    def _add_page_to_ui(self, img, page_num, total_pages):
        """Agrega una sola página a la interfaz de forma dinámica"""
        if page_num == 1:
            if hasattr(self, 'loading_label') and self.loading_label.winfo_exists():
                self.loading_label.destroy()
        
        self.info_label.configure(
            text=f"PDF: {os.path.basename(self.current_pdf)} | {total_pages} páginas | Modo: {self.interaction_mode}"
        )
        
        # Frame para cada página
        page_frame = ctk.CTkFrame(self)
        page_frame.pack(pady=10, padx=5, fill="x")
        
        # Label de número de página
        page_label = ctk.CTkLabel(page_frame, text=f"Página {page_num}", 
                                 font=("Arial", 12, "bold"))
        page_label.pack(pady=(5, 2))
        
        # Label para coordenadas
        coord_label = ctk.CTkLabel(page_frame, text="", font=("Arial", 9))
        coord_label.pack(pady=(0, 5))
        
        # Canvas para la imagen (interactivo)
        canvas = Canvas(page_frame, width=img.width, height=img.height, 
                      highlightthickness=0, bg='white')
        canvas.pack(pady=5)
        
        # Convertir PIL Image a PhotoImage
        photo = ImageTk.PhotoImage(img)
        canvas.create_image(0, 0, anchor='nw', image=photo)
        canvas.image = photo  # Mantener referencia
        
        # Guardar datos de la página
        page_data = {
            'canvas': canvas,
            'image': img,
            'photo': photo,
            'page_num': page_num,
            'width': img.width,
            'height': img.height,
            'coord_label': coord_label,
            'pdf_width': 612,  # Ancho estándar carta
            'pdf_height': 792
        }
        self.pages_data.append(page_data)
        
        # Ordenar por número de página si es necesario (Threading podría desordenarlas, 
        # aunque aquí las cargamos secuencialmente en el hilo)
        
        # Eventos de mouse
        canvas.bind('<Button-1>', lambda e, pd=page_data: self._on_canvas_click(e, pd))
        canvas.bind('<Motion>', lambda e, pd=page_data: self._on_canvas_motion(e, pd))
        
        # Si hay páginas seleccionadas, marcarlas
        if page_num in self.selected_pages:
            self._draw_selection_overlay(canvas, img.width, img.height)

    def _finalize_loading(self):
        """Limpieza al finalizar la carga"""
        if hasattr(self, 'loading_label') and self.loading_label.winfo_exists():
            self.loading_label.destroy()
        self.loading_active = False
    
    def _on_canvas_click(self, event, page_data):
        """Maneja clics en el canvas"""
        # Convertir coordenadas de imagen a coordenadas PDF
        pdf_x, pdf_y = self._image_to_pdf_coords(event.x, event.y, page_data)
        
        # Llamar al callback si existe
        if self.on_click_callback:
            self.on_click_callback(page_data['page_num'], pdf_x, pdf_y, event.x, event.y)
    
    def _on_canvas_motion(self, event, page_data):
        """Muestra coordenadas al mover el mouse"""
        pdf_x, pdf_y = self._image_to_pdf_coords(event.x, event.y, page_data)
        page_data['coord_label'].configure(
            text=f"Cursor: X={int(pdf_x)}, Y={int(pdf_y)} (PDF) | X={event.x}, Y={event.y} (Imagen)"
        )
    
    def _image_to_pdf_coords(self, img_x, img_y, page_data):
        """Convierte coordenadas de imagen a coordenadas PDF"""
        # Calcular escala
        scale_x = page_data['pdf_width'] / page_data['width']
        scale_y = page_data['pdf_height'] / page_data['height']
        
        # Convertir X (igual dirección)
        pdf_x = img_x * scale_x
        
        # Convertir Y (invertir porque PDF usa origen en esquina inferior izquierda)
        pdf_y = page_data['pdf_height'] - (img_y * scale_y)
        
        return pdf_x, pdf_y
    
    def draw_text_overlay(self, page_num, x, y, text, font_size=12):
        """Dibuja un overlay de texto en la posición especificada"""
        if page_num <= len(self.pages_data):
            page_data = self.pages_data[page_num - 1]
            canvas = page_data['canvas']
            
            # Convertir coordenadas PDF a imagen
            img_x, img_y = self._pdf_to_image_coords(x, y, page_data)
            
            # Dibujar cruz en la posición
            size = 10
            canvas.create_line(img_x - size, img_y, img_x + size, img_y, 
                             fill='red', width=2, tags='overlay')
            canvas.create_line(img_x, img_y - size, img_x, img_y + size, 
                             fill='red', width=2, tags='overlay')
            
            # Dibujar el texto
            canvas.create_text(img_x, img_y, text=text, anchor='nw', 
                             fill='blue', font=('Arial', font_size), tags='overlay')
    
    def draw_image_overlay(self, page_num, x, y, width, height):
        """Dibuja un rectángulo mostrando dónde se colocará la imagen"""
        if page_num <= len(self.pages_data):
            page_data = self.pages_data[page_num - 1]
            canvas = page_data['canvas']
            
            # Convertir coordenadas PDF a imagen
            img_x, img_y = self._pdf_to_image_coords(x, y, page_data)
            
            # Convertir dimensiones
            scale_x = page_data['width'] / page_data['pdf_width']
            scale_y = page_data['height'] / page_data['pdf_height']
            img_w = width * scale_x
            img_h = height * scale_y
            
            # Dibujar rectángulo
            canvas.create_rectangle(img_x, img_y, img_x + img_w, img_y - img_h,
                                  outline='green', width=2, dash=(5, 5), tags='overlay')
    
    def _pdf_to_image_coords(self, pdf_x, pdf_y, page_data):
        """Convierte coordenadas PDF a coordenadas de imagen"""
        scale_x = page_data['width'] / page_data['pdf_width']
        scale_y = page_data['height'] / page_data['pdf_height']
        
        img_x = pdf_x * scale_x
        img_y = (page_data['pdf_height'] - pdf_y) * scale_y
        
        return img_x, img_y
    
    def clear_overlays(self):
        """Limpia todos los overlays"""
        for page_data in self.pages_data:
            page_data['canvas'].delete('overlay')
    
    def toggle_page_selection(self, page_num):
        """Marca/desmarca una página para eliminación"""
        if page_num in self.selected_pages:
            self.selected_pages.remove(page_num)
        else:
            self.selected_pages.add(page_num)
        
        # Redibujar
        if page_num <= len(self.pages_data):
            page_data = self.pages_data[page_num - 1]
            canvas = page_data['canvas']
            canvas.delete('selection')
            
            if page_num in self.selected_pages:
                self._draw_selection_overlay(canvas, page_data['width'], page_data['height'])
    
    def _draw_selection_overlay(self, canvas, width, height):
        """Dibuja overlay de selección"""
        canvas.create_rectangle(0, 0, width, height, 
                              fill='red', stipple='gray50', tags='selection')
        canvas.create_text(width//2, height//2, text="ELIMINAR", 
                         fill='white', font=('Arial', 24, 'bold'), tags='selection')
    
    def _show_error(self, error_msg):
        """Muestra un mensaje de error"""
        self.clear()
        error_label = ctk.CTkLabel(self, text=f"Error al cargar PDF:\n{error_msg}", 
                                   font=("Arial", 12), text_color="red")
        error_label.pack(pady=20)
    
    def clear(self):
        """Limpia el visor y detiene cargas activas"""
        self.loading_active = False
        for widget in self.winfo_children():
            if widget != self.info_frame:
                widget.destroy()
        self.pages_data = []
        self.selected_pages = set()
    
    def set_zoom(self, zoom, mode='fixed'):
        """Ajusta el nivel de zoom y recarga el PDF"""
        self.zoom_level = zoom
        self.zoom_mode = mode
        if self.current_pdf:
            self.load_pdf(self.current_pdf)
    
    def set_interaction_mode(self, mode):
        """Cambia el modo de interacción"""
        self.interaction_mode = mode
        if self.current_pdf:
            self.info_label.configure(
                text=f"PDF: {os.path.basename(self.current_pdf)} | {len(self.pages_data)} páginas | Modo: {mode}"
            )


class PDFEditorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Editor PDF Interactivo para Linux Mint")
        self.geometry("1600x900")

        # Layout de grid - dos columnas
        self.grid_columnconfigure(0, weight=1)  # Panel izquierdo (controles) - Más estrecho
        self.grid_columnconfigure(1, weight=4)  # Panel derecho (visor) - Más ancho
        self.grid_rowconfigure(0, weight=1)

        # Panel izquierdo - Pestañas de controles
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, padx=(20, 10), pady=20, sticky="nsew")

        # Panel derecho - Visor de PDF
        self.viewer_frame = ctk.CTkFrame(self)
        self.viewer_frame.grid(row=0, column=1, padx=(5, 10), pady=10, sticky="nsew")
        self.viewer_frame.grid_rowconfigure(2, weight=1)
        self.viewer_frame.grid_columnconfigure(0, weight=1)
        
        # Título del visor
        viewer_title = ctk.CTkLabel(self.viewer_frame, text="Editor Interactivo de PDF", 
                                    font=("Arial", 16, "bold"))
        viewer_title.grid(row=0, column=0, pady=10, sticky="ew")
        
        # Controles de zoom
        zoom_frame = ctk.CTkFrame(self.viewer_frame)
        zoom_frame.grid(row=1, column=0, pady=(0, 10), sticky="ew", padx=10)
        
        ctk.CTkLabel(zoom_frame, text="Zoom:").pack(side="left", padx=5)
        
        zoom_25 = ctk.CTkButton(zoom_frame, text="25%", width=50,
                                 command=lambda: self.set_viewer_zoom(0.25))
        zoom_25.pack(side="left", padx=2)

        zoom_50 = ctk.CTkButton(zoom_frame, text="50%", width=50, 
                                command=lambda: self.set_viewer_zoom(0.5))
        zoom_50.pack(side="left", padx=2)
        
        zoom_75 = ctk.CTkButton(zoom_frame, text="75%", width=50,
                                command=lambda: self.set_viewer_zoom(0.75))
        zoom_75.pack(side="left", padx=2)
        
        zoom_100 = ctk.CTkButton(zoom_frame, text="100%", width=55,
                                 command=lambda: self.set_viewer_zoom(1.0))
        zoom_100.pack(side="left", padx=2)
        
        zoom_150 = ctk.CTkButton(zoom_frame, text="150%", width=55,
                                 command=lambda: self.set_viewer_zoom(1.5))
        zoom_150.pack(side="left", padx=2)

        zoom_fit = ctk.CTkButton(zoom_frame, text="Ajustar", width=70, fg_color="purple",
                                 command=lambda: self.set_viewer_zoom(1.0, mode='fit_width'))
        zoom_fit.pack(side="left", padx=10)
        
        # Visor de PDF interactivo - Sin ancho fijo para permitir expansión máxima
        self.pdf_viewer = InteractivePDFViewer(self.viewer_frame)
        self.pdf_viewer.grid(row=2, column=0, sticky="nsew", padx=5, pady=(0, 5))

        # Crear pestañas
        self.tab_merge = self.tabview.add("Unir PDFs")
        self.tab_split = self.tabview.add("Dividir PDF")
        self.tab_rotate = self.tabview.add("Rotar PDF")
        self.tab_extract = self.tabview.add("Extraer Texto")
        self.tab_add_text = self.tabview.add("Agregar Texto")
        self.tab_add_image = self.tabview.add("Agregar Imagen")
        self.tab_delete_pages = self.tabview.add("Eliminar Páginas")
        self.tab_reorder = self.tabview.add("Reordenar Páginas")

        # Variables para cambios pendientes
        self.pending_texts = []
        self.pending_images = []

        self.setup_merge_tab()
        self.setup_split_tab()
        self.setup_rotate_tab()
        self.setup_extract_tab()
        self.setup_add_text_tab()
        self.setup_add_image_tab()
        self.setup_delete_pages_tab()
        self.setup_reorder_tab()
    
    def set_viewer_zoom(self, zoom, mode='fixed'):
        """Ajusta el zoom del visor"""
        self.pdf_viewer.set_zoom(zoom, mode=mode)
    
    def load_pdf_in_viewer(self, file_path):
        """Carga un PDF en el visor"""
        if file_path and os.path.exists(file_path):
            self.pdf_viewer.load_pdf(file_path)

    def setup_merge_tab(self):
        # Variables
        self.merge_files = []

        # UI Elements
        self.merge_frame = ctk.CTkFrame(self.tab_merge)
        self.merge_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        btn_add = ctk.CTkButton(self.merge_frame, text="Agregar Archivos", command=self.add_files_merge)
        btn_add.pack(pady=10)

        self.listbox_merge = ctk.CTkTextbox(self.merge_frame, height=200)
        self.listbox_merge.pack(fill="x", padx=10, pady=5)
        self.listbox_merge.configure(state="disabled")

        btn_merge = ctk.CTkButton(self.merge_frame, text="Unir y Guardar", command=self.process_merge, fg_color="green")
        btn_merge.pack(pady=20)

    def setup_split_tab(self):
        self.split_file = None
        
        self.split_frame = ctk.CTkFrame(self.tab_split)
        self.split_frame.pack(fill="both", expand=True, padx=10, pady=10)

        btn_select = ctk.CTkButton(self.split_frame, text="Seleccionar PDF", command=self.select_file_split)
        btn_select.pack(pady=10)

        self.lbl_split_file = ctk.CTkLabel(self.split_frame, text="Ningún archivo seleccionado")
        self.lbl_split_file.pack(pady=5)

        btn_split = ctk.CTkButton(self.split_frame, text="Dividir PDF", command=self.process_split, fg_color="green")
        btn_split.pack(pady=20)

    def setup_rotate_tab(self):
        self.rotate_file = None
        
        self.rotate_frame = ctk.CTkFrame(self.tab_rotate)
        self.rotate_frame.pack(fill="both", expand=True, padx=10, pady=10)

        btn_select = ctk.CTkButton(self.rotate_frame, text="Seleccionar PDF", command=self.select_file_rotate)
        btn_select.pack(pady=10)

        self.lbl_rotate_file = ctk.CTkLabel(self.rotate_frame, text="Ningún archivo seleccionado")
        self.lbl_rotate_file.pack(pady=5)

        self.rotate_var = ctk.StringVar(value="90")
        radio_90 = ctk.CTkRadioButton(self.rotate_frame, text="90° Horario", variable=self.rotate_var, value="90")
        radio_90.pack(pady=5)
        radio_180 = ctk.CTkRadioButton(self.rotate_frame, text="180°", variable=self.rotate_var, value="180")
        radio_180.pack(pady=5)
        radio_270 = ctk.CTkRadioButton(self.rotate_frame, text="270° Horario (90° Antihorario)", variable=self.rotate_var, value="270")
        radio_270.pack(pady=5)

        btn_rotate = ctk.CTkButton(self.rotate_frame, text="Rotar y Guardar", command=self.process_rotate, fg_color="green")
        btn_rotate.pack(pady=20)

    def setup_extract_tab(self):
        self.extract_file = None

        self.extract_frame = ctk.CTkFrame(self.tab_extract)
        self.extract_frame.pack(fill="both", expand=True, padx=10, pady=10)

        btn_select = ctk.CTkButton(self.extract_frame, text="Seleccionar PDF", command=self.select_file_extract)
        btn_select.pack(pady=10)

        self.lbl_extract_file = ctk.CTkLabel(self.extract_frame, text="Ningún archivo seleccionado")
        self.lbl_extract_file.pack(pady=5)

        btn_extract = ctk.CTkButton(self.extract_frame, text="Extraer Texto", command=self.process_extract, fg_color="green")
        btn_extract.pack(pady=10)

        self.textbox_extract = ctk.CTkTextbox(self.extract_frame, height=200)
        self.textbox_extract.pack(fill="both", expand=True, padx=10, pady=5)
        self.textbox_extract.configure(state="disabled")

        btn_save_text = ctk.CTkButton(self.extract_frame, text="Guardar Texto en Archivo", command=self.save_extracted_text)
        btn_save_text.pack(pady=10)

    def setup_add_text_tab(self):
        self.add_text_file = None
        
        self.add_text_frame = ctk.CTkFrame(self.tab_add_text)
        self.add_text_frame.pack(fill="both", expand=True, padx=10, pady=10)

        btn_select = ctk.CTkButton(self.add_text_frame, text="Seleccionar PDF", command=self.select_file_add_text)
        btn_select.pack(pady=10)

        self.lbl_add_text_file = ctk.CTkLabel(self.add_text_frame, text="Ningún archivo seleccionado")
        self.lbl_add_text_file.pack(pady=5)

        # Instrucciones
        ctk.CTkLabel(self.add_text_frame, text="👆 Haz clic en el PDF para colocar el texto", 
                    font=("Arial", 12, "bold"), text_color="blue").pack(pady=10)

        # Campo de texto
        ctk.CTkLabel(self.add_text_frame, text="Texto a agregar:").pack(pady=5)
        self.entry_text = ctk.CTkEntry(self.add_text_frame, width=400)
        self.entry_text.pack(pady=5)

        # Tamaño de fuente
        ctk.CTkLabel(self.add_text_frame, text="Tamaño de fuente:").pack(pady=5)
        self.entry_font_size = ctk.CTkEntry(self.add_text_frame, width=100)
        self.entry_font_size.insert(0, "12")
        self.entry_font_size.pack(pady=5)

        # Selector de color visual
        ctk.CTkLabel(self.add_text_frame, text="Color del texto:").pack(pady=(10, 5))
        
        # Frame para la paleta de colores
        color_palette_frame = ctk.CTkFrame(self.add_text_frame)
        color_palette_frame.pack(pady=5)
        
        # Colores predefinidos
        self.predefined_colors = [
            ("Negro", "#000000", (0, 0, 0)),
            ("Rojo", "#FF0000", (255, 0, 0)),
            ("Azul", "#0000FF", (0, 0, 255)),
            ("Verde", "#00FF00", (0, 255, 0)),
            ("Amarillo", "#FFFF00", (255, 255, 0)),
            ("Naranja", "#FF8800", (255, 136, 0)),
            ("Morado", "#8800FF", (136, 0, 255)),
            ("Blanco", "#FFFFFF", (255, 255, 255)),
        ]
        
        # Variable para el color seleccionado
        self.selected_text_color = (0, 0, 0)  # Negro por defecto
        self.selected_color_hex = "#000000"
        
        # Crear botones de color
        row = 0
        col = 0
        for name, hex_color, rgb in self.predefined_colors:
            color_btn = ctk.CTkButton(
                color_palette_frame,
                text="",
                width=40,
                height=40,
                fg_color=hex_color,
                hover_color=hex_color,
                border_width=2,
                border_color="gray",
                command=lambda c=rgb, h=hex_color: self.select_text_color(c, h)
            )
            color_btn.grid(row=row, column=col, padx=3, pady=3)
            col += 1
            if col > 3:  # 4 colores por fila
                col = 0
                row += 1
        
        # Botón para color personalizado
        custom_color_btn = ctk.CTkButton(
            color_palette_frame,
            text="🎨",
            width=40,
            height=40,
            command=self.choose_custom_text_color
        )
        custom_color_btn.grid(row=row, column=col, padx=3, pady=3)
        
        # Label para mostrar el color seleccionado
        self.selected_color_display = ctk.CTkLabel(
            self.add_text_frame,
            text=f"Color seleccionado: Negro",
            fg_color=self.selected_color_hex,
            corner_radius=5,
            width=200,
            height=30
        )
        self.selected_color_display.pack(pady=5)

        # Lista de textos pendientes
        ctk.CTkLabel(self.add_text_frame, text="Textos pendientes:").pack(pady=(10, 5))
        self.pending_texts_list = ctk.CTkTextbox(self.add_text_frame, height=100)
        self.pending_texts_list.pack(fill="x", padx=10, pady=5)
        self.pending_texts_list.configure(state="disabled")

        # Botones
        btn_frame = ctk.CTkFrame(self.add_text_frame)
        btn_frame.pack(pady=10)
        
        btn_clear = ctk.CTkButton(btn_frame, text="Limpiar Todo", command=self.clear_pending_texts, fg_color="orange")
        btn_clear.pack(side="left", padx=5)
        
        btn_apply = ctk.CTkButton(btn_frame, text="Aplicar y Guardar", command=self.apply_texts, fg_color="green")
        btn_apply.pack(side="left", padx=5)

        # Configurar callback de clic
        self.pdf_viewer.on_click_callback = self.on_pdf_click_add_text

    def setup_add_image_tab(self):
        self.add_image_file = None
        self.image_to_add = None
        
        self.add_image_frame = ctk.CTkFrame(self.tab_add_image)
        self.add_image_frame.pack(fill="both", expand=True, padx=10, pady=10)

        btn_select_pdf = ctk.CTkButton(self.add_image_frame, text="Seleccionar PDF", command=self.select_file_add_image)
        btn_select_pdf.pack(pady=10)

        self.lbl_add_image_file = ctk.CTkLabel(self.add_image_frame, text="Ningún PDF seleccionado")
        self.lbl_add_image_file.pack(pady=5)

        btn_select_img = ctk.CTkButton(self.add_image_frame, text="Seleccionar Imagen", command=self.select_image_to_add)
        btn_select_img.pack(pady=10)

        self.lbl_image_to_add = ctk.CTkLabel(self.add_image_frame, text="Ninguna imagen seleccionada")
        self.lbl_image_to_add.pack(pady=5)

        # Instrucciones
        ctk.CTkLabel(self.add_image_frame, text="👆 Haz clic en el PDF para colocar la imagen", 
                    font=("Arial", 12, "bold"), text_color="blue").pack(pady=10)

        # Dimensiones
        dim_frame = ctk.CTkFrame(self.add_image_frame)
        dim_frame.pack(pady=10)
        
        ctk.CTkLabel(dim_frame, text="Ancho:").grid(row=0, column=0, padx=5)
        self.entry_width_image = ctk.CTkEntry(dim_frame, width=80)
        self.entry_width_image.insert(0, "200")
        self.entry_width_image.grid(row=0, column=1, padx=5)
        
        ctk.CTkLabel(dim_frame, text="Alto:").grid(row=0, column=2, padx=5)
        self.entry_height_image = ctk.CTkEntry(dim_frame, width=80)
        self.entry_height_image.insert(0, "200")
        self.entry_height_image.grid(row=0, column=3, padx=5)

        # Lista de imágenes pendientes
        ctk.CTkLabel(self.add_image_frame, text="Imágenes pendientes:").pack(pady=(10, 5))
        self.pending_images_list = ctk.CTkTextbox(self.add_image_frame, height=100)
        self.pending_images_list.pack(fill="x", padx=10, pady=5)
        self.pending_images_list.configure(state="disabled")

        # Botones
        btn_frame = ctk.CTkFrame(self.add_image_frame)
        btn_frame.pack(pady=10)
        
        btn_clear = ctk.CTkButton(btn_frame, text="Limpiar Todo", command=self.clear_pending_images, fg_color="orange")
        btn_clear.pack(side="left", padx=5)
        
        btn_apply = ctk.CTkButton(btn_frame, text="Aplicar y Guardar", command=self.apply_images, fg_color="green")
        btn_apply.pack(side="left", padx=5)

    def setup_delete_pages_tab(self):
        self.delete_pages_file = None
        
        self.delete_pages_frame = ctk.CTkFrame(self.tab_delete_pages)
        self.delete_pages_frame.pack(fill="both", expand=True, padx=10, pady=10)

        btn_select = ctk.CTkButton(self.delete_pages_frame, text="Seleccionar PDF", command=self.select_file_delete_pages)
        btn_select.pack(pady=10)

        self.lbl_delete_pages_file = ctk.CTkLabel(self.delete_pages_frame, text="Ningún archivo seleccionado")
        self.lbl_delete_pages_file.pack(pady=5)

        self.lbl_total_pages_delete = ctk.CTkLabel(self.delete_pages_frame, text="")
        self.lbl_total_pages_delete.pack(pady=5)

        # Instrucciones
        ctk.CTkLabel(self.delete_pages_frame, text="👆 Haz clic en las páginas para marcar/desmarcar", 
                    font=("Arial", 12, "bold"), text_color="blue").pack(pady=10)

        btn_delete = ctk.CTkButton(self.delete_pages_frame, text="Eliminar Páginas Marcadas y Guardar", 
                                   command=self.process_delete_pages, fg_color="red")
        btn_delete.pack(pady=20)

    def setup_reorder_tab(self):
        self.reorder_file = None
        
        self.reorder_frame = ctk.CTkFrame(self.tab_reorder)
        self.reorder_frame.pack(fill="both", expand=True, padx=10, pady=10)

        btn_select = ctk.CTkButton(self.reorder_frame, text="Seleccionar PDF", command=self.select_file_reorder)
        btn_select.pack(pady=10)

        self.lbl_reorder_file = ctk.CTkLabel(self.reorder_frame, text="Ningún archivo seleccionado")
        self.lbl_reorder_file.pack(pady=5)

        self.lbl_total_pages_reorder = ctk.CTkLabel(self.reorder_frame, text="")
        self.lbl_total_pages_reorder.pack(pady=5)

        ctk.CTkLabel(self.reorder_frame, text="Nuevo orden de páginas (ej: 3,1,2,4):").pack(pady=5)
        self.entry_new_order = ctk.CTkEntry(self.reorder_frame, width=300)
        self.entry_new_order.pack(pady=5)

        btn_reorder = ctk.CTkButton(self.reorder_frame, text="Reordenar y Guardar", command=self.process_reorder, fg_color="green")
        btn_reorder.pack(pady=20)


    # --- Logic Operations ---

    def add_files_merge(self):
        files = filedialog.askopenfilenames(filetypes=[("PDF files", "*.pdf")])
        if files:
            self.merge_files.extend(files)
            self.update_merge_list()

    def update_merge_list(self):
        self.listbox_merge.configure(state="normal")
        self.listbox_merge.delete("0.0", "end")
        for f in self.merge_files:
            self.listbox_merge.insert("end", f"{os.path.basename(f)}\n")
        self.listbox_merge.configure(state="disabled")

    def process_merge(self):
        if not self.merge_files:
            messagebox.showwarning("Aviso", "Selecciona archivos primero.")
            return
        
        output = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
        if output:
            try:
                pdf_tools.merge_pdfs(self.merge_files, output)
                messagebox.showinfo("Éxito", "Archivos unidos correctamente.")
                self.merge_files = []
                self.update_merge_list()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def select_file_split(self):
        f = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if f:
            self.split_file = f
            self.lbl_split_file.configure(text=os.path.basename(f))
            self.load_pdf_in_viewer(f)

    def process_split(self):
        if not self.split_file:
            messagebox.showwarning("Aviso", "Selecciona un archivo primero.")
            return

        output_dir = filedialog.askdirectory()
        if output_dir:
            try:
                pdf_tools.split_pdf(self.split_file, output_dir)
                messagebox.showinfo("Éxito", f"PDF dividido en {output_dir}")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def select_file_rotate(self):
        f = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if f:
            self.rotate_file = f
            self.lbl_rotate_file.configure(text=os.path.basename(f))
            self.load_pdf_in_viewer(f)

    def process_rotate(self):
        if not self.rotate_file:
            messagebox.showwarning("Aviso", "Selecciona un archivo primero.")
            return
        
        output = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
        if output:
            try:
                degrees = int(self.rotate_var.get())
                pdf_tools.rotate_pdf(self.rotate_file, degrees, output)
                messagebox.showinfo("Éxito", "PDF rotado correctamente.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def select_file_extract(self):
        f = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if f:
            self.extract_file = f
            self.lbl_extract_file.configure(text=os.path.basename(f))
            self.load_pdf_in_viewer(f)

    def process_extract(self):
        if not self.extract_file:
            messagebox.showwarning("Aviso", "Selecciona un archivo primero.")
            return
        
        try:
            text = pdf_tools.extract_text(self.extract_file)
            self.textbox_extract.configure(state="normal")
            self.textbox_extract.delete("0.0", "end")
            self.textbox_extract.insert("0.0", text)
            self.textbox_extract.configure(state="disabled")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def save_extracted_text(self):
        text = self.textbox_extract.get("0.0", "end")
        if not text.strip():
            messagebox.showwarning("Aviso", "No hay texto para guardar.")
            return

        output = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt")])
        if output:
            try:
                with open(output, "w", encoding="utf-8") as f:
                    f.write(text)
                messagebox.showinfo("Éxito", "Texto guardado correctamente.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    # --- Interactive Editing Operations ---

    def select_file_add_text(self):
        f = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if f:
            self.add_text_file = f
            self.lbl_add_text_file.configure(text=os.path.basename(f))
            self.load_pdf_in_viewer(f)
            self.pdf_viewer.set_interaction_mode('add_text')
    
    def select_text_color(self, rgb, hex_color):
        """Selecciona un color de la paleta predefinida"""
        self.selected_text_color = rgb
        self.selected_color_hex = hex_color
        
        # Encontrar el nombre del color
        color_name = "Personalizado"
        for name, h, r in self.predefined_colors:
            if h == hex_color:
                color_name = name
                break
        
        # Actualizar el display
        # Determinar color del texto (blanco para colores oscuros, negro para claros)
        text_color = "white" if sum(rgb) < 400 else "black"
        self.selected_color_display.configure(
            text=f"Color seleccionado: {color_name}",
            fg_color=hex_color,
            text_color=text_color
        )
    
    def choose_custom_text_color(self):
        """Abre el selector de color personalizado"""
        color = colorchooser.askcolor(title="Seleccionar color")
        if color[0]:  # color[0] es RGB, color[1] es hex
            rgb = tuple(int(c) for c in color[0])
            hex_color = color[1]
            self.select_text_color(rgb, hex_color)

    def on_pdf_click_add_text(self, page_num, pdf_x, pdf_y, img_x, img_y):
        """Callback cuando se hace clic en el PDF para agregar texto"""
        text = self.entry_text.get()
        if not text:
            messagebox.showwarning("Aviso", "Ingresa el texto primero.")
            return
        
        try:
            font_size = int(self.entry_font_size.get())
            
            # Usar el color seleccionado visualmente
            r, g, b = self.selected_text_color
            
            # Agregar a la lista de pendientes
            self.pending_texts.append({
                'page': page_num,
                'text': text,
                'x': pdf_x,
                'y': pdf_y,
                'font_size': font_size,
                'color': (r, g, b)
            })
            
            # Dibujar overlay
            self.pdf_viewer.draw_text_overlay(page_num, pdf_x, pdf_y, text, font_size)
            
            # Actualizar lista
            self.update_pending_texts_list()
            
        except ValueError:
            messagebox.showerror("Error", "Verifica que el tamaño de fuente sea correcto.")

    def update_pending_texts_list(self):
        """Actualiza la lista de textos pendientes"""
        self.pending_texts_list.configure(state="normal")
        self.pending_texts_list.delete("0.0", "end")
        for i, item in enumerate(self.pending_texts):
            color_info = f"RGB{item['color']}"
            self.pending_texts_list.insert("end", 
                f"{i+1}. Pág {item['page']}: \"{item['text']}\" en ({int(item['x'])}, {int(item['y'])}) - {color_info}\n")
        self.pending_texts_list.configure(state="disabled")

    def clear_pending_texts(self):
        """Limpia todos los textos pendientes"""
        self.pending_texts = []
        self.update_pending_texts_list()
        self.pdf_viewer.clear_overlays()

    def apply_texts(self):
        """Aplica todos los textos pendientes al PDF"""
        if not self.add_text_file:
            messagebox.showwarning("Aviso", "Selecciona un archivo PDF primero.")
            return
        
        if not self.pending_texts:
            messagebox.showwarning("Aviso", "No hay textos para aplicar.")
            return
        
        output = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
        if output:
            try:
                # Aplicar cada texto
                current_file = self.add_text_file
                for i, item in enumerate(self.pending_texts):
                    if i == len(self.pending_texts) - 1:
                        # Último texto, guardar en output
                        pdf_tools.add_text_to_pdf(current_file, output, item['text'], 
                                                 item['page'], item['x'], item['y'], 
                                                 item['font_size'], item['color'])
                    else:
                        # Textos intermedios, guardar en temporal
                        temp_file = f"/tmp/temp_pdf_{i}.pdf"
                        pdf_tools.add_text_to_pdf(current_file, temp_file, item['text'], 
                                                 item['page'], item['x'], item['y'], 
                                                 item['font_size'], item['color'])
                        current_file = temp_file
                
                messagebox.showinfo("Éxito", f"{len(self.pending_texts)} texto(s) agregado(s) correctamente.")
                self.clear_pending_texts()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def select_file_add_image(self):
        f = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if f:
            self.add_image_file = f
            self.lbl_add_image_file.configure(text=os.path.basename(f))
            self.load_pdf_in_viewer(f)
            self.pdf_viewer.set_interaction_mode('add_image')
            # Configurar callback
            self.pdf_viewer.on_click_callback = self.on_pdf_click_add_image

    def select_image_to_add(self):
        f = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp")])
        if f:
            self.image_to_add = f
            self.lbl_image_to_add.configure(text=os.path.basename(f))

    def on_pdf_click_add_image(self, page_num, pdf_x, pdf_y, img_x, img_y):
        """Callback cuando se hace clic en el PDF para agregar imagen"""
        if not self.image_to_add:
            messagebox.showwarning("Aviso", "Selecciona una imagen primero.")
            return
        
        try:
            width = float(self.entry_width_image.get())
            height = float(self.entry_height_image.get())
            
            # Agregar a la lista de pendientes
            self.pending_images.append({
                'page': page_num,
                'path': self.image_to_add,
                'x': pdf_x,
                'y': pdf_y,
                'width': width,
                'height': height
            })
            
            # Dibujar overlay
            self.pdf_viewer.draw_image_overlay(page_num, pdf_x, pdf_y, width, height)
            
            # Actualizar lista
            self.update_pending_images_list()
            
        except ValueError:
            messagebox.showerror("Error", "Verifica que los valores numéricos sean correctos.")

    def update_pending_images_list(self):
        """Actualiza la lista de imágenes pendientes"""
        self.pending_images_list.configure(state="normal")
        self.pending_images_list.delete("0.0", "end")
        for i, item in enumerate(self.pending_images):
            self.pending_images_list.insert("end", 
                f"{i+1}. Pág {item['page']}: {os.path.basename(item['path'])} en ({int(item['x'])}, {int(item['y'])})\n")
        self.pending_images_list.configure(state="disabled")

    def clear_pending_images(self):
        """Limpia todas las imágenes pendientes"""
        self.pending_images = []
        self.update_pending_images_list()
        self.pdf_viewer.clear_overlays()

    def apply_images(self):
        """Aplica todas las imágenes pendientes al PDF"""
        if not self.add_image_file:
            messagebox.showwarning("Aviso", "Selecciona un archivo PDF primero.")
            return
        
        if not self.pending_images:
            messagebox.showwarning("Aviso", "No hay imágenes para aplicar.")
            return
        
        output = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
        if output:
            try:
                # Aplicar cada imagen
                current_file = self.add_image_file
                for i, item in enumerate(self.pending_images):
                    if i == len(self.pending_images) - 1:
                        # Última imagen, guardar en output
                        pdf_tools.add_image_to_pdf(current_file, output, item['path'], 
                                                  item['page'], item['x'], item['y'], 
                                                  item['width'], item['height'])
                    else:
                        # Imágenes intermedias, guardar en temporal
                        temp_file = f"/tmp/temp_pdf_img_{i}.pdf"
                        pdf_tools.add_image_to_pdf(current_file, temp_file, item['path'], 
                                                  item['page'], item['x'], item['y'], 
                                                  item['width'], item['height'])
                        current_file = temp_file
                
                messagebox.showinfo("Éxito", f"{len(self.pending_images)} imagen(es) agregada(s) correctamente.")
                self.clear_pending_images()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def select_file_delete_pages(self):
        f = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if f:
            self.delete_pages_file = f
            self.lbl_delete_pages_file.configure(text=os.path.basename(f))
            self.load_pdf_in_viewer(f)
            self.pdf_viewer.set_interaction_mode('select_pages')
            # Configurar callback
            self.pdf_viewer.on_click_callback = self.on_pdf_click_delete_page
            # Mostrar número total de páginas
            try:
                from pypdf import PdfReader
                reader = PdfReader(f)
                total = len(reader.pages)
                self.lbl_total_pages_delete.configure(text=f"Total de páginas: {total}")
            except:
                pass

    def on_pdf_click_delete_page(self, page_num, pdf_x, pdf_y, img_x, img_y):
        """Callback cuando se hace clic en una página para marcar/desmarcar"""
        self.pdf_viewer.toggle_page_selection(page_num)

    def process_delete_pages(self):
        if not self.delete_pages_file:
            messagebox.showwarning("Aviso", "Selecciona un archivo PDF primero.")
            return
        
        if not self.pdf_viewer.selected_pages:
            messagebox.showwarning("Aviso", "No has marcado páginas para eliminar.")
            return
        
        pages_to_delete = list(self.pdf_viewer.selected_pages)
        
        output = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
        if output:
            try:
                pdf_tools.delete_pages(self.delete_pages_file, output, pages_to_delete)
                messagebox.showinfo("Éxito", f"{len(pages_to_delete)} página(s) eliminada(s) correctamente.")
                self.pdf_viewer.selected_pages.clear()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def select_file_reorder(self):
        f = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if f:
            self.reorder_file = f
            self.lbl_reorder_file.configure(text=os.path.basename(f))
            self.load_pdf_in_viewer(f)
            # Mostrar número total de páginas
            try:
                from pypdf import PdfReader
                reader = PdfReader(f)
                total = len(reader.pages)
                self.lbl_total_pages_reorder.configure(text=f"Total de páginas: {total}")
            except:
                pass

    def process_reorder(self):
        if not self.reorder_file:
            messagebox.showwarning("Aviso", "Selecciona un archivo PDF primero.")
            return
        
        order_str = self.entry_new_order.get()
        if not order_str:
            messagebox.showwarning("Aviso", "Ingresa el nuevo orden de páginas.")
            return
        
        try:
            # Parsear la entrada (ej: "3,1,2,4" -> [3,1,2,4])
            new_order = [int(x.strip()) for x in order_str.split(',')]
            
            output = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
            if output:
                pdf_tools.reorder_pages(self.reorder_file, output, new_order)
                messagebox.showinfo("Éxito", "Páginas reordenadas correctamente.")
        except ValueError:
            messagebox.showerror("Error", "Formato inválido. Usa formato como: 3,1,2,4")
        except Exception as e:
            messagebox.showerror("Error", str(e))


if __name__ == "__main__":
    app = PDFEditorApp()
    app.mainloop()
