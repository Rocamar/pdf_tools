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
        self.loading_active = False
        self.load_thread = None
        self.resize_timer = None
        self.last_width = 0
        
        # Vincular evento de resize para modo responsivo
        self.bind("<Configure>", self._on_container_resize)
        
        # Info panel - oculto en el nuevo diseño pro
        self.info_frame = ctk.CTkFrame(self, height=1, fg_color="transparent")
        # self.info_frame.pack(fill="x", padx=5, pady=5)
        
        self.info_label = ctk.CTkLabel(self.info_frame, text="", font=("Arial", 11))
        # self.info_label.pack(pady=5)
        
    def load_pdf(self, file_path):
        """Carga y muestra las páginas del PDF de forma incremental"""
        # Cancelar cualquier carga activa previa
        self.loading_active = False
        if self.load_thread and self.load_thread.is_alive():
            # Esperar un poco a que el hilo actual detecte el flag de parada
            pass
            
        self.clear()
        self.current_pdf = file_path
        self.loading_active = True
        self.pages_data = [] # Reset data
        
        # Mostrar mensaje de carga inicial
        self.loading_label = ctk.CTkLabel(self, text="Cargando PDF...", 
                                         font=("Arial", 16, "bold"))
        self.loading_label.pack(pady=50)
        
        def load_incremental():
            try:
                # Obtener número de páginas
                total_pages = pdf_tools.get_pdf_page_count(file_path)
                
                # Cargar dimensiones de la primera página para el cálculo de zoom inicial
                pdf_w, pdf_h = pdf_tools.get_pdf_page_size(file_path, 1)
                
                for i in range(1, total_pages + 1):
                    if not self.loading_active:
                        return
                        
                    # Cargar una sola página a la vez
                    img = pdf_tools.pdf_page_to_image(file_path, i, dpi=int(144 * self.zoom_level))
                    
                    if img and self.loading_active:
                        # Mostrar página en la UI
                        self.after(0, lambda p=img, n=i, tp=total_pages, pw=pdf_w, ph=pdf_h: 
                                   self._add_page_to_ui(p, n, tp, pw, ph))
                
                # Al finalizar, remover label de carga
                if self.loading_active:
                    self.after(0, self._finalize_loading)
                
            except Exception as e:
                if self.loading_active:
                    self.after(0, lambda msg=str(e): self._show_error(msg))
        
        if self.zoom_mode == 'fit_width':
            self.update_idletasks()
            available_width = self.winfo_width()
            if available_width <= 1:
                # Si aún no tiene ancho definido, usar el del maestro
                parent = self.master
                while parent and parent.winfo_width() <= 1:
                    parent = parent.master
                available_width = parent.winfo_width() - 300 if parent else 800
            
            # Obtener ancho real del PDF en puntos
            try:
                pdf_w, _ = pdf_tools.get_pdf_page_size(file_path, 1)
            except:
                pdf_w = 612.0
            
            # Pixel width at 144 DPI (2x 72)
            base_pixel_width = pdf_w * 2.0
            
            if available_width > 100:
                self.zoom_level = (available_width - 80) / base_pixel_width
            else:
                self.zoom_level = 0.8
            self.last_width = available_width

        self.load_thread = threading.Thread(target=load_incremental, daemon=True)
        self.load_thread.start()

    def _on_container_resize(self, event):
        """Maneja el redimensionamiento del contenedor con debounce"""
        if self.zoom_mode == 'fit_width' and self.current_pdf:
            new_width = event.width
            if abs(new_width - self.last_width) < 20:
                return
            
            self.last_width = new_width
            
            # Debounce para recarga
            if self.resize_timer:
                self.after_cancel(self.resize_timer)
            self.resize_timer = self.after(600, self._apply_fit_width)

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
    
    def _add_page_to_ui(self, img, page_num, total_pages, pdf_w, pdf_h):
        """Agrega una sola página a la interfaz de forma dinámica"""
        if page_num == 1:
            if hasattr(self, 'loading_label') and self.loading_label.winfo_exists():
                self.loading_label.destroy()
        
        # El info_label ya no se actualiza aquí, se hará en el controlador de la App
        
        # Frame para cada página con sombra/borde sutil
        page_frame = ctk.CTkFrame(self, fg_color="white", border_width=1, border_color="#cccccc")
        page_frame.pack(pady=15, padx=20)
        
        # Canvas para la imagen (interactivo)
        canvas = Canvas(page_frame, width=img.width, height=img.height, 
                      highlightthickness=0, bg='white')
        canvas.pack(padx=2, pady=2)
        
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
            'pdf_width': pdf_w,
            'pdf_height': pdf_h
        }
        self.pages_data.append(page_data)
        
        # Ordenar por número de página para evitar desorden por hilos
        self.pages_data.sort(key=lambda x: x['page_num'])
        
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
        """Muestra coordenadas al mover el mouse (opcional)"""
        # pdf_x, pdf_y = self._image_to_pdf_coords(event.x, event.y, page_data)
        pass
    
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

        self.title("Editor PDF Pro - Antigravity")
        self.geometry("1400x900")
        self.configure(fg_color="#f5f5f7")

        # --- Variables de Estado ---
        self.current_pdf_path = None
        # Variables para cambios pendientes
        self.pending_texts = []
        self.pending_images = []

        # El estado de los diálogos se cargará dinámicamente según la herramienta seleccionada

        # --- Layout Principal ---
        # 1. Header (Top Bar)
        self.setup_header()

        # 2. Área Central (Sidebar + Viewer)
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True)

        self.setup_sidebar()
        self.setup_viewer_area()
        
        # Seleccionar tab inicial
        self.switch_tab("Editar")

        # Barra de Herramientas Flotante (opcional, se puede añadir después)
        # self.setup_floating_toolbar()

    def setup_header(self):
        """Crea la barra de navegación superior"""
        self.header = ctk.CTkFrame(self, height=50, corner_radius=0, fg_color="white", border_width=1, border_color="#e0e0e0")
        self.header.pack(fill="x", side="top")
        self.header.pack_propagate(False)

        # Tabs de navegación (lado izquierdo)
        tabs_frame = ctk.CTkFrame(self.header, fg_color="transparent")
        tabs_frame.pack(side="left", padx=20)

        nav_tabs = ["Todas las herramientas", "Editar", "Convertir", "Firma electrónica"]
        self.nav_buttons = {}
        for tab in nav_tabs:
            btn = ctk.CTkButton(tabs_frame, text=tab, font=("Arial", 12), 
                                fg_color="transparent", text_color="#555555", 
                                hover_color="#f0f0f0", width=120, height=50, corner_radius=0,
                                command=lambda t=tab: self.switch_tab(t))
            btn.pack(side="left")
            self.nav_buttons[tab] = btn

        # Herramientas de utilidad (lado derecho)
        utils_frame = ctk.CTkFrame(self.header, fg_color="transparent")
        utils_frame.pack(side="right", padx=20)

        search_entry = ctk.CTkEntry(utils_frame, placeholder_text="Buscar texto o herramientas...", 
                                   width=250, height=30, font=("Arial", 12))
        search_entry.pack(side="left", padx=10)

        # Iconos (Guardar, Compartir, etc)
        btn_save = ctk.CTkButton(utils_frame, text="💾", width=30, height=30, fg_color="transparent", text_color="black", font=("Arial", 16), command=self.save_current_pdf)
        btn_save.pack(side="left", padx=5)
        
        btn_share = ctk.CTkButton(utils_frame, text="🔗", width=30, height=30, fg_color="transparent", text_color="black", font=("Arial", 16))
        btn_share.pack(side="left", padx=5)

    def save_current_pdf(self):
        """Guarda los cambios en el PDF actual"""
        if self.current_pdf_path:
            messagebox.showinfo("Guardar", "Función de guardado rápido seleccionada. Usa 'Aplicar' en las herramientas para guardar versiones específicas.")
        else:
            messagebox.showwarning("Aviso", "No hay ningún PDF abierto.")

    def switch_tab(self, tab_name):
        """Cambia la vista según el tab de navegación superior"""
        # Actualizar estilo de botones
        for name, btn in self.nav_buttons.items():
            if name == tab_name:
                btn.configure(text_color="black", font=("Arial", 12, "bold"), border_width=2, border_color="black")
            else:
                btn.configure(text_color="#555555", font=("Arial", 12), border_width=0)
        
        # Limpiar sidebar y cargar nuevo contenido
        for widget in self.sidebar.winfo_children():
            widget.destroy()
            
        if tab_name == "Todas las herramientas":
            self.setup_all_tools_sidebar()
        elif tab_name == "Editar":
            self.setup_edit_sidebar()
        elif tab_name == "Convertir":
            self.setup_convert_sidebar()
        elif tab_name == "Firma electrónica":
            self.setup_sign_sidebar()

    def setup_header_utils(self, utils_frame):
        # ... (se mantiene igual pero movido si es necesario)
        pass

    def setup_sidebar(self):
        """Crea la estructura básica de la barra lateral"""
        self.sidebar = ctk.CTkScrollableFrame(self.main_container, width=280, corner_radius=0, 
                                             fg_color="white", border_width=0)
        self.sidebar.pack(side="left", fill="y", padx=0, pady=0)
        # Borde separador sutil
        line = ctk.CTkFrame(self.main_container, width=1, fg_color="#e0e0e0")
        line.pack(side="left", fill="y")

    def setup_edit_sidebar(self):
        """Carga las herramientas de edición en la barra lateral"""
        # Header
        sidebar_header = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        sidebar_header.pack(fill="x", padx=15, pady=(15, 20))
        ctk.CTkLabel(sidebar_header, text="Editar", font=("Arial", 18, "bold"), text_color="black").pack(side="left")

        # Grupos
        self.create_sidebar_group("MODIFICAR PAGINA", [
            ("🔄", "Rotar PDF", self.select_tab_rotate),
            ("🗑️", "Eliminar páginas", self.select_tab_delete),
            ("📑", "Organizar páginas", self.select_tab_reorder),
            ("📑", "Dividir PDF", self.select_tab_split)
        ])
        
        self.create_sidebar_group("AGREGAR CONTENIDO", [
            ("T+", "Texto", self.select_tab_add_text),
            ("🖼️", "Imagen", self.select_tab_add_image),
        ])

        self.context_frame = ctk.CTkFrame(self.sidebar, fg_color="#f0f0f0", corner_radius=10)
        self.context_frame.pack(fill="x", padx=15, pady=20)
        self.context_label = ctk.CTkLabel(self.context_frame, text="Selecciona una herramienta", font=("Arial", 12, "italic"))
        self.context_label.pack(pady=20)

    def setup_all_tools_sidebar(self):
        ctk.CTkLabel(self.sidebar, text="Todas las herramientas", font=("Arial", 16, "bold"), text_color="black").pack(pady=20)
        ctk.CTkLabel(self.sidebar, text="Vista general próximamente...", font=("Arial", 12), text_color="gray").pack()

    def setup_convert_sidebar(self):
        ctk.CTkLabel(self.sidebar, text="Convertir", font=("Arial", 16, "bold"), text_color="black").pack(pady=20)
        self.create_sidebar_group("FORMATOS", [
            ("📄", "A Word", None),
            ("📊", "A Excel", None),
            ("🖼️", "A Imagen", None),
        ])

    def setup_sign_sidebar(self):
        ctk.CTkLabel(self.sidebar, text="Firma electrónica", font=("Arial", 16, "bold"), text_color="black").pack(pady=20)
        self.create_sidebar_group("ACCIONES", [
            ("🖋️", "Firmar yo mismo", None),
            ("📧", "Solicitar firmas", None),
        ])

    def create_sidebar_group(self, title, items):
        """Crea un grupo de herramientas en la barra lateral"""
        group_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        group_frame.pack(fill="x", padx=15, pady=(20, 10))
        
        ctk.CTkLabel(group_frame, text=title, font=("Arial", 11, "bold"), text_color="#666666").pack(anchor="w")
        
        for icon, label, command in items:
            btn = ctk.CTkButton(self.sidebar, text=f"  {icon}   {label}", anchor="w",
                                font=("Arial", 13), fg_color="transparent", text_color="black",
                                hover_color="#f0f0f0", height=40, command=command)
            btn.pack(fill="x", padx=10, pady=2)

    def setup_viewer_area(self):
        """Configura el área del visor central"""
        self.viewer_container = ctk.CTkFrame(self.main_container, fg_color="#e5e5e5", corner_radius=0)
        self.viewer_container.pack(side="right", fill="both", expand=True)

        # Barra de herramientas del visor (Flotante o fija)
        self.toolbar_overlay = ctk.CTkFrame(self.viewer_container, width=50, fg_color="white", corner_radius=8, border_width=1, border_color="#cccccc")
        self.toolbar_overlay.place(relx=0.02, rely=0.1)
        
        tools = ["↖️", "💬", "🖋️", "〰️", "T", "📸"]
        for tool in tools:
            btn = ctk.CTkButton(self.toolbar_overlay, text=tool, width=35, height=35, fg_color="transparent", text_color="black", hover_color="#f0f0f0")
            btn.pack(pady=5, padx=5)

        # Controles de zoom (parte inferior o superior)
        self.zoom_ctrls = ctk.CTkFrame(self.viewer_container, fg_color="white", corner_radius=20, border_width=1, border_color="#cccccc")
        self.zoom_ctrls.place(relx=0.5, rely=0.02, anchor="n")
        
        ctk.CTkButton(self.zoom_ctrls, text="-", width=30, height=30, fg_color="transparent", text_color="black", command=lambda: self.adjust_zoom(-0.1)).pack(side="left", padx=5)
        self.zoom_label = ctk.CTkLabel(self.zoom_ctrls, text="100%", font=("Arial", 12, "bold"))
        self.zoom_label.pack(side="left", padx=10)
        ctk.CTkButton(self.zoom_ctrls, text="+", width=30, height=30, fg_color="transparent", text_color="black", command=lambda: self.adjust_zoom(0.1)).pack(side="left", padx=5)

        # El visor de PDF propiamente dicho
        self.pdf_viewer = InteractivePDFViewer(self.viewer_container)
        self.pdf_viewer.pack(fill="both", expand=True, padx=20, pady=(50, 10))

    def adjust_zoom(self, delta):
        self.zoom_level += delta
        self.zoom_level = max(0.1, min(5.0, self.zoom_level))
        self.zoom_label.configure(text=f"{int(self.zoom_level*100)}%")
        self.pdf_viewer.set_zoom(self.zoom_level)

    def show_tool_options(self, tool_name, setup_func):
        """Limpia el panel contextual y carga las opciones de la herramienta"""
        for widget in self.context_frame.winfo_children():
            widget.destroy()
        
        self.context_label = ctk.CTkLabel(self.context_frame, text=tool_name, font=("Arial", 14, "bold"))
        self.context_label.pack(pady=(10, 5))
        
        # Ejecutar función de configuración del panel
        setup_func(self.context_frame)


    # --- Handlers adaptados ---
    def select_tab_rotate(self):
        self.open_pdf_dialog()
        self.show_tool_options("Rotar PDF", self.setup_rotate_context)
    
    def select_tab_delete(self):
        self.open_pdf_dialog()
        self.pdf_viewer.set_interaction_mode('select_pages')
        self.show_tool_options("Eliminar Páginas", self.setup_delete_context)
    
    def select_tab_add_text(self):
        self.open_pdf_dialog()
        self.pdf_viewer.set_interaction_mode('add_text')
        self.show_tool_options("Agregar Texto", self.setup_add_text_context)
        
    def select_tab_add_image(self):
        self.open_pdf_dialog()
        self.pdf_viewer.set_interaction_mode('add_image')
        self.show_tool_options("Agregar Imagen", self.setup_add_image_context)

    def setup_add_text_context(self, parent):
        ctk.CTkLabel(parent, text="Texto a agregar:").pack(pady=5)
        self.entry_text = ctk.CTkEntry(parent, width=220)
        self.entry_text.pack(pady=5)
        
        ctk.CTkLabel(parent, text="Tamaño:").pack(pady=2)
        self.entry_font_size = ctk.CTkEntry(parent, width=60)
        self.entry_font_size.insert(0, "12")
        self.entry_font_size.pack(pady=2)

        # Paleta de colores simplificada
        self.predefined_colors = [
            ("Negro", "#000000", (0, 0, 0)),
            ("Rojo", "#FF0000", (255, 0, 0)),
            ("Azul", "#0000FF", (0, 0, 255)),
            ("Verde", "#00FF00", (0, 255, 0)),
        ]
        self.selected_text_color = (0, 0, 0)
        
        color_frame = ctk.CTkFrame(parent, fg_color="transparent")
        color_frame.pack(pady=5)
        for _, hex_color, rgb in self.predefined_colors:
            ctk.CTkButton(color_frame, text="", width=30, height=30, fg_color=hex_color,
                          command=lambda c=rgb, h=hex_color: self.select_text_color(c, h)).pack(side="left", padx=2)
        
        self.selected_color_display = ctk.CTkLabel(parent, text="Color: Negro", font=("Arial", 10))
        self.selected_color_display.pack()

        # Lista de textos pendientes (mini)
        self.pending_texts_list = ctk.CTkTextbox(parent, height=60, width=220, font=("Arial", 10))
        self.pending_texts_list.pack(pady=5)
        self.pending_texts_list.configure(state="disabled")

        btn_apply = ctk.CTkButton(parent, text="Aplicar y Guardar", command=self.apply_texts, fg_color="#28a745")
        btn_apply.pack(pady=10)
        
        # Vincular callback del visor
        self.pdf_viewer.on_click_callback = self.on_pdf_click_add_text

    def setup_rotate_context(self, parent):
        self.rotate_var = ctk.StringVar(value="90")
        ctk.CTkRadioButton(parent, text="90° Horario", variable=self.rotate_var, value="90").pack(pady=2)
        ctk.CTkRadioButton(parent, text="180°", variable=self.rotate_var, value="180").pack(pady=2)
        ctk.CTkRadioButton(parent, text="270° Horario", variable=self.rotate_var, value="270").pack(pady=2)
        
        btn_rot = ctk.CTkButton(parent, text="Rotar y Guardar", command=self.process_rotate, fg_color="#0066cc")
        btn_rot.pack(pady=15)

    def setup_delete_context(self, parent):
        ctk.CTkLabel(parent, text="Haz clic en las páginas\nen el visor para marcarlas.", font=("Arial", 11)).pack(pady=10)
        btn_del = ctk.CTkButton(parent, text="Eliminar Marcadas", command=self.process_delete_pages, fg_color="#cc0000")
        btn_del.pack(pady=15)

    def setup_add_image_context(self, parent):
        ctk.CTkButton(parent, text="Seleccionar Imagen", command=self.select_image_to_add).pack(pady=10)
        self.lbl_image_to_add = ctk.CTkLabel(parent, text="Sin imagen", font=("Arial", 10))
        self.lbl_image_to_add.pack()

        dim_frame = ctk.CTkFrame(parent, fg_color="transparent")
        dim_frame.pack(pady=5)
        ctk.CTkLabel(dim_frame, text="W:").pack(side="left")
        self.entry_width_image = ctk.CTkEntry(dim_frame, width=50)
        self.entry_width_image.insert(0, "200")
        self.entry_width_image.pack(side="left", padx=2)
        ctk.CTkLabel(dim_frame, text="H:").pack(side="left")
        self.entry_height_image = ctk.CTkEntry(dim_frame, width=50)
        self.entry_height_image.insert(0, "200")
        self.entry_height_image.pack(side="left", padx=2)
        
        self.pending_images_list = ctk.CTkTextbox(parent, height=60, width=220, font=("Arial", 10))
        self.pending_images_list.pack(pady=5)
        self.pending_images_list.configure(state="disabled")

        btn_apply = ctk.CTkButton(parent, text="Aplicar y Guardar", command=self.apply_images, fg_color="#28a745")
        btn_apply.pack(pady=10)
        
        # Vincular callback
        self.pdf_viewer.on_click_callback = self.on_pdf_click_add_image
    
    def select_tab_reorder(self):
        self.open_pdf_dialog()
        self.show_tool_options("Reordenar Páginas", self.setup_reorder_context)

    def select_tab_split(self):
        self.open_pdf_dialog()
        self.show_tool_options("Dividir PDF", self.setup_split_context)

    def select_tab_merge(self):
        self.show_tool_options("Unir PDFs", self.setup_merge_context)

    def setup_reorder_context(self, parent):
        ctk.CTkLabel(parent, text="Nuevo orden (ej: 3,1,2):").pack(pady=5)
        self.entry_new_order = ctk.CTkEntry(parent, width=220)
        self.entry_new_order.pack(pady=5)
        btn_reorder = ctk.CTkButton(parent, text="Reordenar", command=self.process_reorder, fg_color="#0066cc")
        btn_reorder.pack(pady=15)

    def setup_split_context(self, parent):
        ctk.CTkLabel(parent, text="Divide el PDF en páginas\nindividuales.", font=("Arial", 11)).pack(pady=10)
        btn_split = ctk.CTkButton(parent, text="Dividir PDF", command=self.process_split, fg_color="#0066cc")
        btn_split.pack(pady=15)

    def setup_merge_context(self, parent):
        ctk.CTkButton(parent, text="Agregar Archivos", command=self.add_files_merge).pack(pady=10)
        self.listbox_merge = ctk.CTkTextbox(parent, height=100, width=220)
        self.listbox_merge.pack(pady=5)
        self.listbox_merge.configure(state="disabled")
        btn_merge = ctk.CTkButton(parent, text="Unir y Guardar", command=self.process_merge, fg_color="#28a745")
        btn_merge.pack(pady=15)

    def set_viewer_zoom(self, zoom, mode='fixed'):
        """Ajusta el zoom del visor"""
        self.pdf_viewer.set_zoom(zoom, mode=mode)
    
    def load_pdf_in_viewer(self, file_path):
        """Carga un PDF en el visor"""
        if file_path and os.path.exists(file_path):
            self.pdf_viewer.load_pdf(file_path)

    def open_pdf_dialog(self):
        """Abre el selector de archivos y carga el PDF en el visor"""
        f = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if f:
            self.current_pdf_path = f
            # Actualizar todos los flags de archivos antiguos para compatibilidad
            # These are now mostly redundant as tools will use current_pdf_path directly
            # but kept for any potential legacy references in other parts of the code not shown.
            self.add_text_file = f
            self.add_image_file = f
            self.rotate_file = f
            self.split_file = f
            self.delete_pages_file = f
            self.reorder_file = f
            self.extract_file = f
            
            self.pdf_viewer.load_pdf(f)
            self.title(f"Editor PDF Pro - {os.path.basename(f)}")

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

    def process_split(self):
        if not self.current_pdf_path:
            messagebox.showwarning("Aviso", "Abre un PDF primero.")
            return

        output_dir = filedialog.askdirectory()
        if output_dir:
            try:
                pdf_tools.split_pdf(self.current_pdf_path, output_dir)
                messagebox.showinfo("Éxito", f"PDF dividido en {output_dir}")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def process_rotate(self):
        if not self.current_pdf_path:
            messagebox.showwarning("Aviso", "Abre un PDF primero.")
            return
        
        output = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
        if output:
            try:
                degrees = int(self.rotate_var.get())
                pdf_tools.rotate_pdf(self.current_pdf_path, degrees, output)
                messagebox.showinfo("Éxito", "PDF rotado correctamente.")
                self.current_pdf_path = output
                self.pdf_viewer.load_pdf(output)
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def process_extract(self):
        if not self.current_pdf_path:
            messagebox.showwarning("Aviso", "Abre un PDF primero.")
            return
        
        try:
            text = pdf_tools.extract_text(self.current_pdf_path)
            # Mostrar texto en un cuadro emergente o en la sidebar si fuera necesario
            # Por ahora, abrimos un diálogo simple
            from tkinter import scrolledtext
            top = ctk.CTkToplevel(self)
            top.title("Texto Extraído")
            top.geometry("600x400")
            txt = scrolledtext.ScrolledText(top, width=80, height=20)
            txt.pack(fill="both", expand=True)
            txt.insert("1.0", text)
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
        if not self.current_pdf_path:
            messagebox.showwarning("Aviso", "Abre un PDF primero.")
            return
        
        if not self.pending_texts:
            messagebox.showwarning("Aviso", "No hay textos para aplicar.")
            return
        
        output = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
        if output:
            try:
                current_file = self.current_pdf_path
                # Para evitar loops infinitos de archivos temporales manejamos esto con cuidado
                for i, item in enumerate(self.pending_texts):
                    temp_output = output if i == len(self.pending_texts) - 1 else f"/tmp/tp_{i}.pdf"
                    pdf_tools.add_text_to_pdf(current_file, temp_output, item['text'], 
                                             item['page'], item['x'], item['y'], 
                                             item['font_size'], item['color'])
                    current_file = temp_output
                
                messagebox.showinfo("Éxito", f"{len(self.pending_texts)} texto(s) agregado(s).")
                self.clear_pending_texts()
                self.current_pdf_path = output
                self.pdf_viewer.load_pdf(output)
            except Exception as e:
                messagebox.showerror("Error", str(e))

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
        if not self.current_pdf_path:
            messagebox.showwarning("Aviso", "Abre un PDF primero.")
            return
        
        if not self.pending_images:
            messagebox.showwarning("Aviso", "No hay imágenes para aplicar.")
            return
        
        output = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
        if output:
            try:
                current_file = self.current_pdf_path
                for i, item in enumerate(self.pending_images):
                    temp_output = output if i == len(self.pending_images) - 1 else f"/tmp/tp_img_{i}.pdf"
                    pdf_tools.add_image_to_pdf(current_file, temp_output, item['path'], 
                                              item['page'], item['x'], item['y'], 
                                              item['width'], item['height'])
                    current_file = temp_output
                
                messagebox.showinfo("Éxito", f"{len(self.pending_images)} imagen(es) agregadas.")
                self.clear_pending_images()
                self.current_pdf_path = output
                self.pdf_viewer.load_pdf(output)
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def process_delete_pages(self):
        if not self.current_pdf_path:
            messagebox.showwarning("Aviso", "Abre un PDF primero.")
            return
        
        if not self.pdf_viewer.selected_pages:
            messagebox.showwarning("Aviso", "No has marcado páginas para eliminar.")
            return
        
        pages_to_delete = list(self.pdf_viewer.selected_pages)
        
        output = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
        if output:
            try:
                pdf_tools.delete_pages(self.current_pdf_path, output, pages_to_delete)
                messagebox.showinfo("Éxito", f"{len(pages_to_delete)} página(s) eliminada(s).")
                self.pdf_viewer.selected_pages.clear()
                self.current_pdf_path = output
                self.pdf_viewer.load_pdf(output)
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def process_reorder(self):
        if not self.current_pdf_path:
            messagebox.showwarning("Aviso", "Abre un PDF primero.")
            return
        
        order_str = self.entry_new_order.get()
        if not order_str:
            messagebox.showwarning("Aviso", "Ingresa el nuevo orden de páginas.")
            return
        
        try:
            # Parsear la entrada (ej: "3,1,2" -> [3,1,2])
            new_order = [int(x.strip()) for x in order_str.split(',')]
            
            output = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
            if output:
                pdf_tools.reorder_pages(self.current_pdf_path, output, new_order)
                messagebox.showinfo("Éxito", "Páginas reordenadas correctamente.")
                self.current_pdf_path = output
                self.pdf_viewer.load_pdf(output)
        except ValueError:
            messagebox.showerror("Error", "Formato inválido. Usa: 3,1,2")
        except Exception as e:
            messagebox.showerror("Error", str(e))


if __name__ == "__main__":
    app = PDFEditorApp()
    app.mainloop()
