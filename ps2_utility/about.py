import tkinter as tk
from tkinter import ttk

def open_about_dialog(parent_window, is_dark_mode=True):
    about_win = tk.Toplevel(parent_window)
    about_win.title("About - PS2 ISO Manager")
    about_win.geometry("520x480")
    about_win.minsize(480, 400)
    about_win.transient(parent_window)
    about_win.grab_set()

    bg_color = "#2d2d2d" if is_dark_mode else "#f0f0f0"
    fg_color = "#ffffff" if is_dark_mode else "#000000"
    card_bg = "#1e1e1e" if is_dark_mode else "#ffffff"
    accent_color = "#4ebaff" if is_dark_mode else "#0055ff"

    about_win.configure(bg=bg_color)

    main_frame = ttk.Frame(about_win, padding=20)
    main_frame.pack(fill='both', expand=True)

    # Title & Version
    title_lbl = tk.Label(main_frame, text="PS2 ISO Batch Management Suite Pro", font=("Arial", 14, "bold"), bg=bg_color, fg=fg_color)
    title_lbl.pack(anchor='center', pady=(0, 2))

    ver_lbl = tk.Label(main_frame, text="Version 1.0.0 (Open Source)", font=("Arial", 9, "italic"), bg=bg_color, fg="#888888")
    ver_lbl.pack(anchor='center', pady=(0, 15))

    # Description Text Frame / Canvas for scrolling attributions
    text_frame = tk.Frame(main_frame, bg=card_bg, highlightbackground="#444" if is_dark_mode else "#ccc", highlightthickness=1)
    text_frame.pack(fill='both', expand=True, pady=(0, 15))

    text_widget = tk.Text(text_frame, wrap='word', bg=card_bg, fg=fg_color, bd=0, highlightthickness=0, font=("Arial", 9))
    scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text_widget.yview)
    text_widget.configure(yscrollcommand=scrollbar.set)

    text_widget.pack(side='left', fill='both', expand=True, padx=10, pady=10)
    scrollbar.pack(side='right', fill='y')

    # Attributions Content
    content = """
    A high-performance desktop utility designed to manage, convert, compress, rename, and organize PlayStation 2 game libraries for Open PS2 Loader (OPL).

    ────────────────────────────────────────
    PROGRAM ATTRIBUTIONS & CREDITS
    ────────────────────────────────────────

    • Open PS2 Loader (OPL)
      The gold standard software loader and community platform for the PlayStation 2.

    • Luden02 OPL Art Database
      Provides the structured static Game ID artwork repositories used for automated cover, disc, and background scraping.

    • xlenore ps2-covers
      Foundational cover art mapping schemas and community layouts.

    • MAME Development Team (chdman)
      Industry-standard lossless CHD compression codecs and command-line management tools.

    • ZSO Compression Tool (ziso)
      Fast, efficient OPL-compatible ISO compression format and binaries.

    • bchunk utility
      Reliable BIN/CUE track conversion mapping for multi-track optical disc rips.

    • Three.js & OrbitControls
      Powers the hardware-accelerated 3D WebGL game case and rotating optical disc preview system.

    ────────────────────────────────────────
    LICENSE & REPOSITORY
    ────────────────────────────────────────
    Open-source software distributed under the MIT License. Contributions, issues, and feature requests are welcome on GitHub under ZonalRipper.
    """

    text_widget.insert("1.0", content.strip())
    text_widget.config(state='disabled') # Make text read-only

    # Close Button
    btn_close = ttk.Button(main_frame, text="Close", command=about_win.destroy)
    btn_close.pack(anchor='center', ipadx=10)