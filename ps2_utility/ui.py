import os
import json
import shutil
import subprocess
import threading
import urllib.request
import urllib.error
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

from ps2_utility.core import extract_game_id, format_size, resource_path
from ps2_utility.viewer import open_3d_art_viewer
from ps2_utility.about import open_about_dialog

game_db = {}

from ps2_utility.core import extract_game_id, format_size, resource_path

def update_database_threaded(app_instance):
    global game_db
    db_path = resource_path("PS2.data.json")
    
    if not os.path.exists(db_path):
        app_instance.status_label.config(text="PS2.data.json not found. Titles will default to 'Unknown Title'.")
        return

    try:
        app_instance.status_label.config(text="Parsing local PS2.data.json...")
        loaded_count = 0
        
        with open(db_path, 'r', encoding='utf-8', errors='ignore') as f:
            data = json.load(f)
            
            for raw_id, game_info in data.items():
                game_title = game_info.get("title", "Unknown Title").strip()
                clean_key = raw_id.replace('_', '').replace('-', '').replace('.', '').replace(' ', '').upper()
                
                if clean_key:
                    game_db[clean_key] = game_title
                    loaded_count += 1
                        
        if loaded_count > 0:
            app_instance.status_label.config(text=f"Local database synced! Loaded {loaded_count} game titles. Ready.")
        else:
            raise ValueError("Empty data records.")
            
    except Exception as e:
        print(f"Local database parse failed: {e}")
        app_instance.status_label.config(text="Error reading PS2.data.json. Titles will default to 'Unknown Title'.")

def get_preview_name(file_path, clean_id, raw_id, include_id=True):
    if not clean_id:
        return "GameID Not Found, rename will be skipped"
        
    display_id = raw_id.replace('_', '-')
    clean_name = game_db.get(clean_id, "Unknown Title")
    clean_name = re_sub_safe(clean_name)
    
    _, ext = os.path.splitext(file_path)
    if include_id:
        return f"{clean_name} [{display_id}]{ext.lower()}"
    else:
        return f"{clean_name}{ext.lower()}"

def re_sub_safe(name):
    import re
    return re.sub(r'[\/*?:"<>|]', "", name).strip()

class PSToolkitApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PS2 ISO Manager")
        # --- TOP MENU BAR ---
        menubar = tk.Menu(root)
        
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About PS2-ISO-Manager", command=lambda: open_about_dialog(root, self.is_dark_mode))
        help_menu.add_command(label="GitHub Repository", command=lambda: webbrowser.open("https://github.com/ZonalRipper/PS2-ISO-Manager"))
        menubar.add_cascade(label="Help", menu=help_menu)
        
        self.root.geometry("1000x650")
        self.root.minsize(900, 550)

        # --- SET CUSTOM WINDOW ICON ---
        icon_path = resource_path("app_icon.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception as e:
                print(f"Failed to load window icon: {e}")
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.queued_files = [] 
        self.opl_files = []    
        self.file_cache = {}  
        
        self.is_dark_mode = True  
        self.active_process = None  
        self.cancel_requested = False 
        
        self.include_game_id = tk.BooleanVar(value=True)
        self.make_rename_copy = tk.BooleanVar(value=False)
        self.del_after_compress = tk.BooleanVar(value=False)
        self.del_after_chd = tk.BooleanVar(value=False) 
        self.del_after_convert = tk.BooleanVar(value=False)
        self.del_after_decompress = tk.BooleanVar(value=False)
        
        self.opl_target_dir = tk.StringVar(value="No Directory Selected")
        self.overwrite_art = tk.BooleanVar(value=False)
        
        top_bar = ttk.Frame(root)
        top_bar.pack(fill='x', padx=15, pady=(8, 5))
        
        # Left side: Progress & Status
        progress_frame = ttk.Frame(top_bar)
        progress_frame.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        self.progress = ttk.Progressbar(progress_frame, orient='horizontal', mode='determinate')
        self.progress.pack(fill='x', pady=(0, 2))
        
        self.status_label = ttk.Label(progress_frame, text="Preparing configurations...", font=("Arial", 9, "italic"))
        self.status_label.pack(side='left')
        
        # Right side: Controls (Stop Button, Help, Theme Toggle)
        controls_frame = ttk.Frame(top_bar)
        controls_frame.pack(side='right')

        # Standard tk.Button so we can style the background and text color explicitly (Red Stop Button)
        self.btn_cancel = tk.Button(
            controls_frame, text="🛑 Stop Task", command=self.cancel_process, state='disabled',
            relief="flat", font=("Arial", 9, "bold"), bd=0, padx=10, pady=4, cursor="hand2"
        )
        self.btn_cancel.pack(side='left', padx=(0, 8))

        self.btn_help = ttk.Button(controls_frame, text="Help ▾", command=self.show_help_menu)
        self.btn_help.pack(side='left', padx=(0, 8))

        self.btn_theme = tk.Button(controls_frame, text="", command=self.toggle_theme, relief="flat", font=("Segoe UI Symbol", 13), cursor="hand2", bd=0)
        self.btn_theme.pack(side='left')
        
        header_frame = ttk.LabelFrame(root, text="Queue Management")
        header_frame.pack(fill='x', padx=10, pady=(10, 5))
        
        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        self.btn_add_files = ttk.Button(btn_frame, text="Add Individual Files", command=self.load_files_picker)
        self.btn_add_files.pack(side='left', padx=5)
        
        self.btn_add_folder = ttk.Button(btn_frame, text="Scan Entire Folder Directory", command=self.load_folder_picker)
        self.btn_add_folder.pack(side='left', padx=5)
        
        self.btn_clear_queue = ttk.Button(btn_frame, text="Clear Queue List", command=self.clear_queue)
        self.btn_clear_queue.pack(side='right', padx=5)
        
        self.btn_remove_selected = ttk.Button(btn_frame, text="Remove Selected / Ticked", command=self.remove_selected)
        self.btn_remove_selected.pack(side='right', padx=5)
        
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=5)

        # Bind tab change event to toggle queue button states
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        
        self.columns = ('selected', 'original_name', 'preview_action', 'size_status')
        self.opl_columns = ('selected', 'original_name', 'game_id', 'art_missing', 'art_status', 'action')
        
        tab_bin = ttk.Frame(self.notebook)
        self.notebook.add(tab_bin, text="1: BIN > ISO")
        self.bin_tree = self._build_tree_tab(
            tab_bin, self.columns, 
            [("Delete Original File(s) After Conversion", self.del_after_convert, None)], 
            "Compile BIN/CUE -> ISO", self.execute_batch_bin
        )

        tab_rename = ttk.Frame(self.notebook)
        self.notebook.add(tab_rename, text="2: Rename ISOs & ZSOs")
        self.rename_tree = self._build_tree_tab(
            tab_rename, self.columns,
            [
                ("Include Game ID in New Name", self.include_game_id, self.populate_queue_ui),
                ("Make Renamed File a Copy (Keep Original)", self.make_rename_copy, None)
            ], 
            "Execute Batch Rename", self.execute_batch_rename
        )

        tab_compress = ttk.Frame(self.notebook)
        self.notebook.add(tab_compress, text="3: Compress to ZSO")
        self.compress_tree = self._build_tree_tab(
            tab_compress, self.columns,
            [("Delete Original ISO After Compression", self.del_after_compress, None)], 
            "Compress Target ISOs -> ZSO", self.execute_batch_zso
        )
        
        tab_chd = ttk.Frame(self.notebook)
        self.notebook.add(tab_chd, text="4: Compress to CHD")
        self.chd_tree = self._build_tree_tab(
            tab_chd, self.columns,
            [("Delete Original ISO After Compression", self.del_after_chd, None)], 
            "Compress Target ISOs -> CHD", self.execute_batch_chd
        )
        
        tab_decompress = ttk.Frame(self.notebook)
        self.notebook.add(tab_decompress, text="5: Extract ZSO > ISO")
        self.decompress_tree = self._build_tree_tab(
            tab_decompress, self.columns,
            [("Delete Original ZSO After Extraction", self.del_after_decompress, None)], 
            "Extract ZSO -> ISO", self.execute_batch_decompress
        )
        
        tab_opl = ttk.Frame(self.notebook)
        self.notebook.add(tab_opl, text="6: OPL Drive & Art")
        self.opl_tree = self._build_opl_tab(tab_opl)

        self.apply_theme()
        threading.Thread(target=update_database_threaded, args=(self,), daemon=True).start()

    def on_tab_changed(self, event):
        try:
            current_tab_index = self.notebook.index(self.notebook.select())
            
            # Tab 6 is index 5 (0: BIN>ISO, 1: Rename, 2: ZSO, 3: CHD, 4: Extract, 5: OPL Drive & Art)
            if current_tab_index == 5:
                self.btn_add_files.config(state='disabled')
                self.btn_add_folder.config(state='disabled')
            else:
                # Only re-enable if a background batch task isn't currently running
                if self.progress['value'] == 0:
                    self.btn_add_files.config(state='normal')
                    self.btn_add_folder.config(state='normal')
        except Exception:
            pass

    def on_closing(self):
        if self.active_process and self.active_process.poll() is None:
            if messagebox.askokcancel("Task Running", "A process is currently running in the background.\n\nDo you want to terminate it and exit?"):
                self.cancel_requested = True
                try:
                    self.active_process.kill()
                except Exception as e:
                    print(f"Failed to kill process: {e}")
                self.root.destroy()
                os._exit(0) 
        else:
            self.root.destroy()
            os._exit(0)

    def cancel_process(self):
        self.cancel_requested = True
        self.status_label.config(text="Halting task... wrapping up current operations.")
        self.btn_cancel.config(state='disabled')
        if self.active_process and self.active_process.poll() is None:
            try:
                self.active_process.kill()
            except Exception as e:
                print(f"Failed to kill child process: {e}")

    def _build_tree_tab(self, parent_tab, columns, checkboxes, btn_text, btn_command):
        tree_frame = ttk.Frame(parent_tab)
        tree_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', selectmode='extended')
        tree.heading('selected', text='✔')
        tree.column('selected', width=30, anchor='center', stretch=False)
        tree.heading('original_name', text='Original File')
        tree.column('original_name', width=250, anchor='w')
        
        if 'preview_action' in columns:
            tree.heading('preview_action', text='Preview Action')
            tree.column('preview_action', width=280, anchor='w')
        if 'size_status' in columns:
            tree.heading('size_status', text='File Size')
            tree.column('size_status', width=120, anchor='center')
        
        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        
        tree.bind("<Delete>", self.remove_selected)
        tree.bind("<ButtonRelease-1>", self.handle_tree_click)

        ctrl_frame = ttk.Frame(parent_tab)
        ctrl_frame.pack(side='bottom', fill='x', padx=10, pady=10)
        
        chk_frame = ttk.Frame(ctrl_frame)
        chk_frame.pack(side='left')
        
        for text, var, cmd in checkboxes:
            ttk.Checkbutton(chk_frame, text=text, variable=var, command=cmd).pack(anchor='w', pady=2)
            
        ttk.Button(ctrl_frame, text=btn_text, command=btn_command).pack(side='right', padx=10, anchor='s')
        
        return tree

    def _build_opl_tab(self, parent_tab):
        target_frame = ttk.Frame(parent_tab)
        target_frame.pack(fill='x', padx=5, pady=(10, 5))
        
        ttk.Button(target_frame, text="Select OPL Target Drive/Folder", command=self.select_opl_directory).pack(side='left', padx=5)
        ttk.Label(target_frame, text="Current Target:").pack(side='left', padx=(10, 2))
        ttk.Label(target_frame, textvariable=self.opl_target_dir, font=("Arial", 9, "bold")).pack(side='left')
        
        ttk.Button(target_frame, text="1. Build Folder Structure", command=self.generate_opl_folders).pack(side='right', padx=5)

        tree_frame = ttk.Frame(parent_tab)
        tree_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        tree = ttk.Treeview(tree_frame, columns=self.opl_columns, show='headings', selectmode='extended')
        tree.heading('selected', text='✔')
        tree.column('selected', width=30, anchor='center', stretch=False)
        tree.heading('original_name', text='Detected Drive File')
        tree.column('original_name', width=250, anchor='w')
        tree.heading('game_id', text='Detected Game ID')
        tree.column('game_id', width=130, anchor='center')
        tree.heading('art_missing', text='Art Missing?')
        tree.column('art_missing', width=100, anchor='center')
        tree.heading('art_status', text='Art Scraping Status')
        tree.column('art_status', width=170, anchor='w')
        
        tree.heading('action', text='Gallery')
        tree.column('action', width=70, anchor='center')
        
        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        
        tree.bind("<Delete>", self.remove_selected)
        tree.bind("<ButtonRelease-1>", self.handle_tree_click)
        tree.bind("<Motion>", lambda event: tree.config(cursor="hand2" if tree.identify_column(event.x) == '#6' else ""))

        ctrl_frame = ttk.Frame(parent_tab)
        ctrl_frame.pack(side='bottom', fill='x', padx=10, pady=10)
        
        ttk.Checkbutton(ctrl_frame, text="Overwrite Existing Art (Refresh All)", variable=self.overwrite_art).pack(side='left', padx=5, pady=2)
        ttk.Button(ctrl_frame, text="2. Scrape Missing Art for Target Drive", command=self.execute_art_scraper).pack(side='right', padx=10, anchor='s')
        
        return tree

    def open_art_viewer(self, item):
        values = self.opl_tree.item(item)['values']
        open_3d_art_viewer(self.root, self.opl_target_dir.get(), values, self.is_dark_mode)

    def select_opl_directory(self):
        directory = filedialog.askdirectory(title="Select OPL Root Directory (e.g., USB Drive Root)")
        if directory:
            self.opl_target_dir.set(directory)
            threading.Thread(target=self.scan_opl_drive_bg, args=(directory,), daemon=True).start()

    def generate_opl_folders(self):
        target = self.opl_target_dir.get()
        if target == "No Directory Selected" or not os.path.exists(target):
            messagebox.showwarning("No Target", "Please select a valid OPL target drive or directory first.")
            return
            
        folders = ['DVD', 'CD', 'ART', 'CFG', 'VMC']
        created = 0
        for folder in folders:
            path = os.path.join(target, folder)
            if not os.path.exists(path):
                try:
                    os.makedirs(path)
                    created += 1
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to create {folder}:\n{e}")
                    
        messagebox.showinfo("OPL Structure", f"Successfully created {created} missing OPL directories in:\n{target}")
        threading.Thread(target=self.scan_opl_drive_bg, args=(target,), daemon=True).start()

    def scan_opl_drive_bg(self, target_dir):
        self.root.after(0, self.start_progress, 1, "Scanning OPL Drive...")
        
        dvd_dir = os.path.join(target_dir, "DVD")
        cd_dir = os.path.join(target_dir, "CD")
        art_dir = os.path.join(target_dir, "ART")
        
        try:
            art_files = set(os.listdir(art_dir))
        except Exception:
            art_files = set()
        
        found_files = []
        for scan_dir in [dvd_dir, cd_dir]:
            if os.path.exists(scan_dir):
                for root_dir, _, filenames in os.walk(scan_dir):
                    for f in filenames:
                        if f.lower().endswith(('.iso', '.zso', '.chd')):
                            found_files.append(os.path.join(root_dir, f))
                            
        total = len(found_files)
        if total == 0:
            self.opl_files.clear()
            self.root.after(0, self.populate_opl_tree)
            self.root.after(0, self.stop_progress, "OPL Drive scan complete. No files found.")
            return
            
        self.root.after(0, self.start_progress, total, f"Found {total} files on drive. Parsing IDs...")
        self.opl_files.clear()
        
        for i, file_path in enumerate(found_files):
            if self.cancel_requested:
                break
                
            self.root.after(0, self.update_progress, i + 1, total, f"Parsing Target Drive IDs: {i + 1} / {total}...")
            
            if file_path not in self.file_cache:
                self.cache_file_info(file_path)
                
            cache = self.file_cache.get(file_path, {})
            raw_id = cache.get('raw_id')
            clean_id = cache.get('clean_id')
            
            art_missing = "Yes"
            initial_status = "Pending..."
            
            if raw_id:
                has_cov = any(f.startswith(f"{raw_id}_COV") for f in art_files)
                has_ico = any(f.startswith(f"{raw_id}_ICO") for f in art_files)
                has_bg  = any(f.startswith(f"{raw_id}_BG") for f in art_files)
                has_scr = any(f.startswith(f"{raw_id}_SCR") for f in art_files)
                has_lgo = any(f.startswith(f"{raw_id}_LGO") for f in art_files)
                
                tags = []
                if has_cov: tags.append("COV")
                if has_ico: tags.append("DSC")
                if has_bg:  tags.append("BG")
                if has_scr: tags.append("SCR")
                if has_lgo: tags.append("LGO")
                
                found_count = len(tags)
                if found_count == 5:
                    art_missing = "No"
                elif found_count > 0:
                    art_missing = "Partial"
                else:
                    art_missing = "Yes"
                
                if tags:
                    initial_status = " | ".join(tags)
                else:
                    initial_status = "No Art Found"
                    
            self.opl_files.append({
                'path': file_path,
                'filename': os.path.basename(file_path),
                'raw_id': raw_id if raw_id else "Unknown",
                'clean_id': clean_id,
                'art_missing': art_missing,
                'initial_status': initial_status
            })
            
        if not self.cancel_requested:
            self.root.after(0, self.populate_opl_tree)
            self.root.after(0, self.stop_progress, f"OPL Drive scan complete. Found {total} items.")
        else:
            self.root.after(0, self.stop_progress, "OPL Drive scan halted.")

    def download_art(self, clean_id, raw_id, art_dir, overwrite):
        base_url = f"https://raw.githubusercontent.com/Luden02/psx-ps2-opl-art-database/main/PS2/{raw_id}"
        
        art_types = {
            "COV": "png", "COV2": "png", "ICO": "png",
            "BG_00": "png", "BG_01": "png",
            "LAB" : "png", "LGO" : "png",
            "SCR_00": "png", "SCR_01": "png"
        }
        
        status = []
        downloaded_primary = False
        
        for art_type, ext in art_types.items():
            file_name = f"{raw_id}_{art_type}.{ext}"
            file_url = f"{base_url}/{file_name}"
            local_path = os.path.join(art_dir, file_name)
            
            if not os.path.exists(local_path) or overwrite:
                try:
                    req = urllib.request.Request(file_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=5) as response, open(local_path, 'wb') as out_file:
                        shutil.copyfileobj(response, out_file)
                    
                    if art_type in ["COV", "ICO", "BG_00", "BG_01", "SCR_00", "SCR_01", "LGO"]:
                        clean_type = art_type.split('_')[0]
                        clean_type = "DSC" if clean_type == "ICO" else clean_type
                        if f"{clean_type}: OK" not in status:
                            status.append(f"{clean_type}: OK")
                    downloaded_primary = True
                except urllib.error.HTTPError:
                    if art_type in ["COV", "ICO"]:
                        status.append(f"{art_type}: 404")
                except Exception:
                    if art_type in ["COV", "ICO"]:
                        status.append(f"{art_type}: Error")
            else:
                if art_type in ["COV", "ICO", "BG_00", "BG_01", "SCR_00", "SCR_01", "LGO"]:
                    clean_type = art_type.split('_')[0]
                    clean_type = "DSC" if clean_type == "ICO" else clean_type
                    if f"{clean_type}: Exists" not in status:
                        status.append(f"{clean_type}: Exists")
                downloaded_primary = True

        if not downloaded_primary and not status:
             return "Failed: No Art Found in Repo Folder"
             
        return " | ".join(status)

    def execute_art_scraper(self):
        target = self.opl_target_dir.get()
        if target == "No Directory Selected" or not os.path.exists(target):
            messagebox.showerror("Missing Target", "Please select an OPL target directory first so the software knows where to save the ART.")
            return
            
        art_dir = os.path.join(target, "ART")
        if not os.path.exists(art_dir):
            try:
                os.makedirs(art_dir)
            except Exception as e:
                messagebox.showerror("Folder Error", f"Could not create ART directory:\n{e}")
                return

        children = self.opl_tree.get_children()
        if not children:
            messagebox.showwarning("Queue Empty", "No files found on the OPL drive to scrape.")
            return

        def process():
            total = len(children)
            self.root.after(0, self.start_progress, total, "Connecting to GitHub Art Repositories...")
            success_count = 0
            overwrite_checked = self.overwrite_art.get()
            
            for i, child in enumerate(children):
                if self.cancel_requested:
                    break
                    
                file_path = self.opl_tree.item(child)['tags'][0]
                game_id_val = self.opl_tree.item(child)['values'][2]
                art_missing_val = self.opl_tree.item(child)['values'][3]
                
                self.root.after(0, self.update_progress, i + 1, total, f"Scraping Art {i + 1} of {total}...")
                
                if game_id_val == "Unknown" or not game_id_val:
                    self.root.after(0, lambda c=child: self.opl_tree.set(c, 'art_status', "Skipped (No ID)"))
                    continue
                    
                if art_missing_val == "No" and not overwrite_checked:
                    self.root.after(0, lambda c=child: self.opl_tree.set(c, 'art_status', "Skipped (Art Exists)"))
                    continue
                
                self.root.after(0, lambda c=child: self.opl_tree.set(c, 'art_status', "Downloading..."))
                
                cache = self.file_cache.get(file_path, {})
                clean_id = cache.get('clean_id')
                raw_id = cache.get('raw_id')
                
                if clean_id and raw_id:
                    result = self.download_art(clean_id, raw_id, art_dir, overwrite_checked)
                    if "OK" in result:
                        success_count += 1
                        
                    try:
                        current_art = set(os.listdir(art_dir))
                        c_cov = any(f.startswith(f"{raw_id}_COV") for f in current_art)
                        c_ico = any(f.startswith(f"{raw_id}_ICO") for f in current_art)
                        c_bg  = any(f.startswith(f"{raw_id}_BG") for f in current_art)
                        c_scr = any(f.startswith(f"{raw_id}_SCR") for f in current_art)
                        c_lgo = any(f.startswith(f"{raw_id}_LGO") for f in current_art)
                        
                        found = sum([c_cov, c_ico, c_bg, c_scr, c_lgo])
                        if found == 5:
                            new_missing = "No"
                        elif found > 0:
                            new_missing = "Partial"
                        else:
                            new_missing = "Yes"
                            
                        self.root.after(0, lambda c=child, m=new_missing: self.opl_tree.set(c, 'art_missing', m))
                    except Exception:
                        pass
                        
                    self.root.after(0, lambda c=child, r=result: self.opl_tree.set(c, 'art_status', r))
                else:
                    self.root.after(0, lambda c=child: self.opl_tree.set(c, 'art_status', "Failed (No ID Cached)"))
                    
            if self.cancel_requested:
                self.root.after(0, self.stop_progress, "Scraping Operation Cancelled.")
            else:
                self.root.after(0, self.stop_progress, "Batch Art Scraping Completed.")
                self.root.after(0, lambda: messagebox.showinfo("Scraping Finished", f"Art scraping cycle complete!\nSuccessfully processed art for {success_count} games."))
            
        threading.Thread(target=process, daemon=True).start()

    def show_help_menu(self):
        # Create a popup menu that matches the action coordinates
        help_popup = tk.Menu(self.root, tearoff=0)
        
        # Style the popup menu colors dynamically based on theme
        if self.is_dark_mode:
            help_popup.config(bg="#242832", fg="#f4f4f5", activebackground="#00439c", activeforeground="#ffffff")
        else:
            help_popup.config(bg="#e1e1e1", fg="#000000", activebackground="#0070d1", activeforeground="#ffffff")
            
        help_popup.add_command(label="About PS2-ISO-Manager", command=lambda: open_about_dialog(self.root, self.is_dark_mode))
        help_popup.add_command(label="GitHub Repository", command=lambda: webbrowser.open("https://github.com/ZonalRipper/PS2-ISO-Manager"))
        
        # Get button screen coordinates to pop the menu right below it
        try:
            x = self.btn_help.winfo_rootx()
            y = self.btn_help.winfo_rooty() + self.btn_help.winfo_height()
            help_popup.tk_popup(x, y)
        finally:
            help_popup.grab_release()

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.apply_theme()
    def apply_theme(self):
        style = ttk.Style()
        style.theme_use('clam') 

        if self.is_dark_mode:
            # PlayStation Console Dark Theme Palette
            bg_color = "#121418"       # Deep console chassis dark
            fg_color = "#f4f4f5"       # Crisp PlayStation white text
            tree_bg = "#1a1d23"        # Slightly lighter panel background
            tree_fg = "#f4f4f5"
            select_bg = "#00439c"      # Official PlayStation Blue
            btn_bg = "#242832"         # Controller matte dark grey
            btn_fg = "#ffffff"
            error_color = "#f87171"    # Soft red for errors
            self.btn_cancel.config(bg="#3a1c1c", fg="#f87171", activebackground="#581c1c", activeforeground="#fca5a5")
        else:
            # Clean Light Mode
            bg_color = "#f0f0f0"
            fg_color = "#000000"
            tree_bg = "#ffffff"
            tree_fg = "#000000"
            select_bg = "#0070d1"
            btn_bg = "#e1e1e1"
            btn_fg = "#000000"
            error_color = "red"
            self.btn_cancel.config(bg="#fee2e2", fg="#dc2626", activebackground="#fecaca", activeforeground="#b91c1c")

        self.root.configure(bg=bg_color)
        
        style.configure(".", background=bg_color, foreground=fg_color)
        style.configure("TFrame", background=bg_color)
        style.configure("TLabelframe", background=bg_color, foreground=fg_color)
        style.configure("TLabelframe.Label", background=bg_color, foreground=fg_color)
        style.configure("TLabel", background=bg_color, foreground=fg_color)
        style.configure("TCheckbutton", background=bg_color, foreground=fg_color)
        style.map("TCheckbutton", background=[("active", bg_color)])
        
        style.configure("TButton", background=btn_bg, foreground=btn_fg)
        style.map("TButton", background=[("active", select_bg)])
        
        style.configure("TNotebook", background=bg_color)
        style.configure("TNotebook.Tab", background=btn_bg, foreground=btn_fg)
        style.map("TNotebook.Tab", background=[("selected", bg_color)], foreground=[("selected", fg_color)])
        
        style.configure("Treeview", background=tree_bg, foreground=tree_fg, fieldbackground=tree_bg)
        style.map('Treeview', background=[('selected', select_bg)], foreground=[('selected', '#ffffff')])
        style.configure("Treeview.Heading", background=btn_bg, foreground=btn_fg)
        
        style.configure("Horizontal.TProgressbar", background=select_bg, troughcolor=tree_bg)
        
        if hasattr(self, 'btn_theme'):
            icon = "☀" if self.is_dark_mode else "🌙"
            icon_color = "#FDB813" if self.is_dark_mode else "#00439c"
            self.btn_theme.config(text=icon, bg=bg_color, fg=icon_color, activebackground=bg_color, activeforeground=icon_color)
        
        for tree in [self.bin_tree, self.rename_tree, self.compress_tree, self.chd_tree, self.decompress_tree, self.opl_tree]:
            tree.tag_configure('error', foreground=error_color)
            tree.tag_configure('clickable', foreground="#38bdf8" if self.is_dark_mode else "#0055ff", font=('Arial', 9, 'underline'))
    
    def start_progress(self, total, message):
        self.cancel_requested = False
        self.progress['maximum'] = total
        self.progress['value'] = 0
        self.status_label.config(text=message)
        self.btn_cancel.config(state='normal')
        self.btn_add_files.config(state='disabled')
        self.btn_add_folder.config(state='disabled')
        self.btn_clear_queue.config(state='disabled')
        self.btn_remove_selected.config(state='disabled')

    def update_progress(self, current, total, message=None):
        self.progress['value'] = current
        if message:
            self.status_label.config(text=message)

    def stop_progress(self, message):
        self.progress['value'] = 0
        self.status_label.config(text=message)
        self.btn_cancel.config(state='disabled')
        self.btn_add_files.config(state='normal')
        self.btn_add_folder.config(state='normal')
        self.btn_clear_queue.config(state='normal')
        self.btn_remove_selected.config(state='normal')
        self.populate_queue_ui()

    def handle_tree_click(self, event):
        tree = event.widget
        region = tree.identify_region(event.x, event.y)
        if region == "cell":
            column = tree.identify_column(event.x)
            item = tree.identify_row(event.y)
            if not item:
                return
                
            if column == '#1': 
                current_val = tree.set(item, 'selected')
                new_val = '☑' if current_val == '☐' else '☐'
                tree.set(item, 'selected', new_val)
            elif tree == getattr(self, 'opl_tree', None) and column == '#6':
                self.open_art_viewer(item)

    def clear_queue(self):
        self.queued_files.clear()
        self.opl_files.clear()
        self.populate_queue_ui()
        self.populate_opl_tree()
        
    def remove_selected(self, event=None):
        try:
            current_tab_index = self.notebook.index(self.notebook.select())
            trees = [self.bin_tree, self.rename_tree, self.compress_tree, self.chd_tree, self.decompress_tree, self.opl_tree]
            active_tree = trees[current_tab_index]
        except Exception:
            return

        removed_any = False
        
        for item in active_tree.get_children():
            if active_tree.set(item, 'selected') == '☑':
                file_path = active_tree.item(item)['tags'][0]
                
                if active_tree == self.opl_tree:
                    self.opl_files = [f for f in self.opl_files if f['path'] != file_path]
                    removed_any = True
                elif file_path in self.queued_files:
                    self.queued_files.remove(file_path)
                    removed_any = True
                    
        selected_items = active_tree.selection()
        for item in selected_items:
            file_path = active_tree.item(item)['tags'][0]
            
            if active_tree == self.opl_tree:
                self.opl_files = [f for f in self.opl_files if f['path'] != file_path]
                removed_any = True
            elif file_path in self.queued_files:
                self.queued_files.remove(file_path)
                removed_any = True

        if not removed_any and event is None:
            messagebox.showwarning("No Selection", "Please check the box (☑) next to files or highlight them to remove.")
            return

        if active_tree == self.opl_tree:
            self.populate_opl_tree()
        else:
            self.populate_queue_ui()

    def cache_file_info(self, file_path):
        if not os.path.exists(file_path): return
        filename = os.path.basename(file_path)
        _, ext = os.path.splitext(filename)
        ext = ext.lower()
        
        size_bytes = os.path.getsize(file_path)
        human_size = format_size(size_bytes)
        
        if ext in ['.iso', '.zso', '.chd']:
            clean_id, raw_id = extract_game_id(file_path)
            self.file_cache[file_path] = {'clean_id': clean_id, 'raw_id': raw_id, 'size': human_size}
        else:
            self.file_cache[file_path] = {'size': human_size}

    def process_files_in_background(self, new_files):
        total = len(new_files)
        self.root.after(0, self.start_progress, total, f"Scanning {total} files... Please wait.")
        
        for i, file_path in enumerate(new_files):
            if self.cancel_requested:
                break
            self.cache_file_info(file_path)
            self.root.after(0, self.update_progress, i + 1, total, f"Scanning files: {i + 1} / {total} processed...")
            
        if not self.cancel_requested:
            self.queued_files.extend(new_files)
            self.root.after(0, self.stop_progress, f"Added {total} files to the queue.")
            self.root.after(0, self.populate_queue_ui)
        else:
            self.root.after(0, self.stop_progress, "File scanning halted by user.")
            self.root.after(0, self.populate_queue_ui)

    def populate_queue_ui(self):
        self.queued_files.sort(key=lambda x: os.path.basename(x).lower())
        
        for tree in [self.bin_tree, self.rename_tree, self.compress_tree, self.chd_tree, self.decompress_tree]:
            for item in tree.get_children():
                tree.delete(item)
            
        for file_path in self.queued_files:
            if not os.path.exists(file_path):
                continue
            filename = os.path.basename(file_path)
            _, ext = os.path.splitext(filename)
            ext = ext.lower()
            
            cache = self.file_cache.get(file_path, {})
            human_size = cache.get('size', 'Unknown Size')
            
            if ext in ['.iso', '.zso', '.chd']:
                clean_id = cache.get('clean_id')
                raw_id = cache.get('raw_id')
                preview_rename = get_preview_name(file_path, clean_id, raw_id, self.include_game_id.get())
                row_tags = (file_path, 'error') if "GameID Not Found" in preview_rename else (file_path,)
                
                self.rename_tree.insert('', 'end', values=('☐', filename, preview_rename, human_size), tags=row_tags)
                
            if ext == '.iso':
                preview_zso = filename.replace('.iso', '.zso')
                self.compress_tree.insert('', 'end', values=('☐', filename, preview_zso, human_size), tags=(file_path,))
                
                preview_chd = filename.replace('.iso', '.chd')
                self.chd_tree.insert('', 'end', values=('☐', filename, preview_chd, human_size), tags=(file_path,))
                
            elif ext == '.bin':
                preview = filename.replace('.bin', '_converted.iso')
                self.bin_tree.insert('', 'end', values=('☐', filename, preview, f"BIN: {human_size}"), tags=(file_path,))
                
            elif ext == '.zso':
                preview = filename.replace('.zso', '.iso')
                self.decompress_tree.insert('', 'end', values=('☐', filename, preview, f"ZSO: {human_size}"), tags=(file_path,))

    def populate_opl_tree(self):
        self.opl_files.sort(key=lambda x: x['filename'].lower())
        
        for item in self.opl_tree.get_children():
            self.opl_tree.delete(item)
            
        for f in self.opl_files:
            if f['raw_id'] == "Unknown":
                row_tags = (f['path'], 'error')
            else:
                row_tags = (f['path'], 'clickable') 
                
            self.opl_tree.insert('', 'end', values=('☐', f['filename'], f['raw_id'], f['art_missing'], f.get('initial_status', 'Pending...'), '🔍 View'), tags=row_tags)

    def load_files_picker(self):
        files = filedialog.askopenfilenames(filetypes=[("Archival Images", "*.iso *.bin *.zso *.chd")])
        if files:
            new_files = [f for f in files if f not in self.queued_files]
            if new_files:
                threading.Thread(target=self.process_files_in_background, args=(new_files,), daemon=True).start()

    def load_folder_picker(self):
        directory = filedialog.askdirectory()
        if directory:
            new_files = []
            for root_dir, _, filenames in os.walk(directory):
                for filename in filenames:
                    if filename.lower().endswith(('.iso', '.bin', '.zso', '.chd')):
                        full_path = os.path.join(root_dir, filename)
                        if full_path not in self.queued_files:
                            new_files.append(full_path)
            if new_files:
                threading.Thread(target=self.process_files_in_background, args=(new_files,), daemon=True).start()
            else:
                self.status_label.config(text="No new valid files found in directory.")

    def run_bin_to_iso(self, bin_path, bchunk_exe_path):
        cue_path = bin_path.replace('.bin', '.cue')
        if not os.path.exists(cue_path):
            return False, "Missing .cue metadata index file alongside target bin."
        base_path, _ = os.path.splitext(bin_path)
        output_prefix = base_path + "_converted"
        cmd = [bchunk_exe_path, bin_path, cue_path, output_prefix]
        try:
            self.active_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            stdout, stderr = self.active_process.communicate()
            if self.active_process.returncode == 0:
                return True, "Success"
            else:
                return False, stderr or stdout or "Conversion halted."
        except Exception as e:
            return False, str(e)
        finally:
            self.active_process = None

    def run_iso_to_zso(self, iso_path, ziso_exe_path):
        base_path, _ = os.path.splitext(iso_path)
        output_zso = base_path + ".zso"
        cmd = [ziso_exe_path, "-i", iso_path, "-o", output_zso]
        try:
            self.active_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            stdout, stderr = self.active_process.communicate()
            if self.active_process.returncode == 0 and os.path.exists(output_zso):
                return True, output_zso
            else:
                return False, stderr or stdout or "ZSO Compression failed."
        except Exception as e:
            return False, str(e)
        finally:
            self.active_process = None

    def run_iso_to_chd(self, iso_path, chdman_exe_path):
        base_path, _ = os.path.splitext(iso_path)
        output_chd = base_path + ".chd"
        is_cd_game = "/CD" in iso_path.replace("\\", "/") or os.path.getsize(iso_path) < 700 * 1024 * 1024
        chd_command = "createcd" if is_cd_game else "createdvd"
        
        cmd = [chdman_exe_path, chd_command, "-i", iso_path, "-o", output_chd, "-f"]
        try:
            self.active_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            stdout, _ = self.active_process.communicate()
            
            if self.active_process.returncode == 0 and os.path.exists(output_chd):
                return True, output_chd
            else:
                err_lines = [line.strip() for line in stdout.split('\n') if line.strip()]
                err_msg = err_lines[-1] if err_lines else "CHD Compression failed."
                return False, err_msg
        except Exception as e:
            return False, str(e)
        finally:
            self.active_process = None

    def run_zso_to_iso(self, zso_path, ziso_exe_path):
        base_path, _ = os.path.splitext(zso_path)
        output_iso = base_path + "_restored.iso"
        cmd = [ziso_exe_path, "-i", zso_path, "-o", output_iso]
        try:
            self.active_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            stdout, stderr = self.active_process.communicate()
            if os.path.exists(output_iso):
                return True, output_iso
            else:
                return False, stderr or stdout or "Extraction failed."
        except Exception as e:
            return False, str(e)
        finally:
            self.active_process = None

    def execute_batch_rename(self):
        children = self.rename_tree.get_children()
        if not children: 
            messagebox.showwarning("Queue Empty", "No files queued for renaming.")
            return
            
        def process():
            total = len(children)
            self.root.after(0, self.start_progress, total, "Processing Batch Rename...")
            success_count = 0
            error_log = []
            
            for i, child in enumerate(children):
                if self.cancel_requested:
                    break
                    
                file_path = self.rename_tree.item(child)['tags'][0]
                preview_val = self.rename_tree.item(child)['values'][2]
                
                self.root.after(0, self.update_progress, i + 1, total, f"Renaming file {i + 1} of {total}...")
                
                if "GameID Not Found" in preview_val:
                    continue
                
                directory = os.path.dirname(file_path)
                new_path = os.path.join(directory, preview_val) 
                
                if file_path == new_path:
                    success_count += 1
                    self.root.after(0, lambda c=child: self.rename_tree.set(c, 'preview_action', "Skipped (Same Name)"))
                    continue
                    
                try:
                    if not os.path.exists(new_path): 
                        if self.make_rename_copy.get():
                            shutil.copy2(file_path, new_path)
                        else:
                            os.rename(file_path, new_path) 
                            if file_path in self.queued_files:
                                self.queued_files.remove(file_path)
                                if file_path in self.file_cache:
                                    del self.file_cache[file_path]
                        
                        if new_path not in self.queued_files:
                            self.queued_files.append(new_path)
                            self.cache_file_info(new_path)
                            
                        success_count += 1
                        self.root.after(0, lambda c=child: self.rename_tree.set(c, 'preview_action', "Success!"))
                    else:
                        error_log.append(f"Skipped: {preview_val} (Destination already exists)")
                        self.root.after(0, lambda c=child: self.rename_tree.set(c, 'preview_action', "Error: Destination exists"))
                except Exception as e:
                    err_clean = str(e).replace('\n', ' ').replace('\r', '')
                    error_log.append(f"Failed {os.path.basename(file_path)}: {err_clean}")
                    self.root.after(0, lambda c=child: self.rename_tree.set(c, 'preview_action', "Error: See Log"))
                    
            if self.cancel_requested:
                self.root.after(0, self.stop_progress, "Renaming Operation Cancelled by User.")
            else:
                self.root.after(0, self.stop_progress, "Batch Renaming Operations Completed.")
            
            if error_log:
                self.root.after(0, lambda: messagebox.showerror("OS File Error", "The operating system blocked the following operations:\n\n" + "\n".join(error_log[:10])))
                
            self.root.after(0, lambda: messagebox.showinfo("Processing Finished", f"Batch Renaming cycle ended.\nSuccessfully processed {success_count} files."))
            
        threading.Thread(target=process, daemon=True).start()

    def execute_batch_zso(self):
        exe_path = resource_path("ziso.exe")
        if not os.path.exists(exe_path):
            messagebox.showerror("Utility Missing", "Please drop your 'ziso.exe' binary tool into this program home directory folder path first.")
            return
            
        children = self.compress_tree.get_children()
        if not children:
            messagebox.showwarning("Queue Empty", "No ISO files queued for ZSO compression.")
            return
            
        def process():
            total = len(children)
            self.root.after(0, self.start_progress, total, "Processing ZSO conversion tasks... UI locked for stability.")
            success_count = 0
            
            for i, child in enumerate(children):
                if self.cancel_requested:
                    break
                    
                file_path = self.compress_tree.item(child)['tags'][0]
                orig_size = os.path.getsize(file_path)
                
                self.root.after(0, lambda c=child: self.compress_tree.set(c, 'preview_action', "Compressing item actively..."))
                self.root.after(0, self.update_progress, i + 1, total, f"Compressing file {i + 1} of {total}...")
                
                success, output_or_err = self.run_iso_to_zso(file_path, exe_path)
                
                if success and os.path.exists(output_or_err):
                    success_count += 1
                    comp_size = os.path.getsize(output_or_err)
                    ratio = (comp_size / orig_size) * 100
                    size_str = f"{format_size(orig_size)} -> {format_size(comp_size)} ({ratio:.1f}%)"
                    
                    self.root.after(0, lambda c=child, s=size_str: (
                        self.compress_tree.set(c, 'preview_action', "ZSO Compressed Successfully!"),
                        self.compress_tree.set(c, 'size_status', s)
                    ))
                    
                    if output_or_err not in self.queued_files:
                        self.queued_files.append(output_or_err)
                        self.cache_file_info(output_or_err)
                    
                    if self.del_after_compress.get():
                        try:
                            os.remove(file_path)
                            if file_path in self.queued_files:
                                self.queued_files.remove(file_path)
                                if file_path in self.file_cache:
                                    del self.file_cache[file_path]
                        except OSError as e:
                            print(f"Failed to delete original file {file_path}: {e}")
                else:
                    err_clean = str(output_or_err).replace('\n', ' | ').replace('\r', '')
                    if len(err_clean) > 80: err_clean = err_clean[:77] + "..."
                    self.root.after(0, lambda c=child, e=err_clean: self.compress_tree.set(c, 'preview_action', f"Error: {e}"))
                    
            if self.cancel_requested:
                self.root.after(0, self.stop_progress, "Compression Operation Cancelled by User.")
            else:
                self.root.after(0, self.stop_progress, "Batch Compression Operations Completed.")
                self.root.after(0, lambda: messagebox.showinfo("Batch Core Finished", f"ZSO Compression cycle complete! {success_count} files processed."))
            
        threading.Thread(target=process, daemon=True).start()

    def execute_batch_chd(self):
        exe_path = resource_path("chdman.exe")
        if not os.path.exists(exe_path):
            messagebox.showerror("Utility Missing", "Please drop your 'chdman.exe' binary tool into this program home directory folder path first.")
            return
            
        children = self.chd_tree.get_children()
        if not children:
            messagebox.showwarning("Queue Empty", "No ISO files queued for CHD compression.")
            return
            
        def process():
            total = len(children)
            self.root.after(0, self.start_progress, total, "Processing CHD conversion tasks... UI locked for stability.")
            success_count = 0
            
            for i, child in enumerate(children):
                if self.cancel_requested:
                    break
                    
                file_path = self.chd_tree.item(child)['tags'][0]
                orig_size = os.path.getsize(file_path)
                
                self.root.after(0, lambda c=child: self.chd_tree.set(c, 'preview_action', "Creating CHD actively..."))
                self.root.after(0, self.update_progress, i + 1, total, f"Compressing file {i + 1} of {total}...")
                
                success, output_or_err = self.run_iso_to_chd(file_path, exe_path)
                
                if success and os.path.exists(output_or_err):
                    success_count += 1
                    comp_size = os.path.getsize(output_or_err)
                    ratio = (comp_size / orig_size) * 100
                    size_str = f"{format_size(orig_size)} -> {format_size(comp_size)} ({ratio:.1f}%)"
                    
                    self.root.after(0, lambda c=child, s=size_str: (
                        self.chd_tree.set(c, 'preview_action', "CHD Created Successfully!"),
                        self.chd_tree.set(c, 'size_status', s)
                    ))
                    
                    if output_or_err not in self.queued_files:
                        self.queued_files.append(output_or_err)
                        self.cache_file_info(output_or_err)
                    
                    if self.del_after_chd.get():
                        try:
                            os.remove(file_path)
                            if file_path in self.queued_files:
                                self.queued_files.remove(file_path)
                                if file_path in self.file_cache:
                                    del self.file_cache[file_path]
                        except OSError as e:
                            print(f"Failed to delete original file {file_path}: {e}")
                else:
                    err_clean = str(output_or_err).replace('\n', ' | ').replace('\r', '')
                    if len(err_clean) > 80: err_clean = err_clean[:77] + "..."
                    self.root.after(0, lambda c=child, e=err_clean: self.chd_tree.set(c, 'preview_action', f"Error: {e}"))
                    
            if self.cancel_requested:
                self.root.after(0, self.stop_progress, "Compression Operation Cancelled by User.")
            else:
                self.root.after(0, self.stop_progress, "Batch Compression Operations Completed.")
                self.root.after(0, lambda: messagebox.showinfo("Batch Core Finished", f"CHD Compression cycle complete! {success_count} files processed."))
            
        threading.Thread(target=process, daemon=True).start()

    def execute_batch_decompress(self):
        exe_path = resource_path("ziso.exe")
        if not os.path.exists(exe_path):
            messagebox.showerror("Utility Missing", "Please drop your 'ziso.exe' binary tool into this program home directory folder path first.")
            return
            
        children = self.decompress_tree.get_children()
        if not children:
            messagebox.showwarning("Queue Empty", "No ZSO files queued for extraction.")
            return
            
        def process():
            total = len(children)
            self.root.after(0, self.start_progress, total, "Processing ZSO extraction tasks...")
            success_count = 0
            last_error = "Unknown error."
            
            for i, child in enumerate(children):
                if self.cancel_requested:
                    break
                    
                file_path = self.decompress_tree.item(child)['tags'][0]
                
                self.root.after(0, lambda c=child: self.decompress_tree.set(c, 'preview_action', "Extracting item actively..."))
                self.root.after(0, self.update_progress, i + 1, total, f"Extracting file {i + 1} of {total}...")
                
                success, output_or_err = self.run_zso_to_iso(file_path, exe_path)
                
                if success and os.path.exists(output_or_err):
                    self.root.after(0, lambda c=child: self.decompress_tree.set(c, 'preview_action', "ZSO Extracted Successfully!"))
                    success_count += 1
                    
                    if output_or_err not in self.queued_files:
                        self.queued_files.append(output_or_err)
                        self.cache_file_info(output_or_err)
                        
                    if self.del_after_decompress.get():
                        try:
                            os.remove(file_path)
                            if file_path in self.queued_files:
                                self.queued_files.remove(file_path)
                                if file_path in self.file_cache:
                                    del self.file_cache[file_path]
                        except OSError as e:
                            print(f"Failed to delete original file {file_path}: {e}")
                else:
                    last_error = str(output_or_err).replace('\n', ' ').replace('\r', '')
                    if len(last_error) > 80: last_error = last_error[:77] + "..."
                    self.root.after(0, lambda c=child, e=last_error: self.decompress_tree.set(c, 'preview_action', f"Failed: {e}"))
                    
            if self.cancel_requested:
                self.root.after(0, self.stop_progress, "Extraction Operation Cancelled by User.")
            else:
                self.root.after(0, self.stop_progress, "Batch Extraction Operations Completed.")
                if success_count > 0:
                    self.root.after(0, lambda: messagebox.showinfo("Batch Core Finished", f"Extraction cycle complete! {success_count} files restored."))
                else:
                    self.root.after(0, lambda: messagebox.showwarning("Extraction Failed", f"The queue finished, but no ISOs were generated.\n\nError returned:\n{last_error}"))
            
        threading.Thread(target=process, daemon=True).start()

    def execute_batch_bin(self):
        exe_path = resource_path("bchunk.exe")
        if not os.path.exists(exe_path):
            messagebox.showerror("Utility Missing", "Please drop 'bchunk.exe' inside your home active execution directory pathway framework root.")
            return
            
        children = self.bin_tree.get_children()
        if not children:
            messagebox.showwarning("Queue Empty", "No BIN files queued for conversion.")
            return
            
        def process():
            total = len(children)
            self.root.after(0, self.start_progress, total, "Processing background BIN track conversions...")
            success_count = 0
            
            for i, child in enumerate(children):
                if self.cancel_requested:
                    break
                    
                file_path = self.bin_tree.item(child)['tags'][0]
                
                self.root.after(0, lambda c=child: self.bin_tree.set(c, 'preview_action', "Converting BIN structures..."))
                self.root.after(0, self.update_progress, i + 1, total, f"Converting file {i + 1} of {total}...")
                
                success, log = self.run_bin_to_iso(file_path, exe_path)
                
                if success:
                    success_count += 1
                    self.root.after(0, lambda c=child: self.bin_tree.set(c, 'preview_action', "Converted to full ISO structure."))
                    
                    base_path, _ = os.path.splitext(file_path)
                    expected_iso = base_path + "_converted01.iso"
                    
                    if os.path.exists(expected_iso) and expected_iso not in self.queued_files:
                        self.queued_files.append(expected_iso)
                        self.cache_file_info(expected_iso)

                    if self.del_after_convert.get():
                        try:
                            os.remove(file_path)
                            if file_path in self.queued_files:
                                self.queued_files.remove(file_path)
                                if file_path in self.file_cache:
                                    del self.file_cache[file_path]
                            
                            cue_path = file_path.replace('.bin', '.cue')
                            if os.path.exists(cue_path):
                                os.remove(cue_path)
                        except OSError as e:
                            print(f"Failed to delete original files for {file_path}: {e}")
                else:
                    err_clean = str(log).replace('\n', ' ').replace('\r', '')
                    if len(err_clean) > 80: err_clean = err_clean[:77] + "..."
                    self.root.after(0, lambda c=child, e=err_clean: self.bin_tree.set(c, 'preview_action', f"Failed: {e}"))
                    
            if self.cancel_requested:
                self.root.after(0, self.stop_progress, "BIN Conversion Operation Cancelled by User.")
            else:
                self.root.after(0, self.stop_progress, "BIN batch tracking complete.")
                self.root.after(0, lambda: messagebox.showinfo("Pipeline Complete", f"Batch transformation processing finalized! {success_count} files converted."))
            
        threading.Thread(target=process, daemon=True).start()