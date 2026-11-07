import os
import json
import base64
import tempfile
import subprocess
import webbrowser
from tkinter import messagebox
from ps2_utility.core import resource_path

def open_3d_art_viewer(parent_window, opl_target_dir, item_values, is_dark_mode):
    raw_id = item_values[2]
    game_name = item_values[1]
    
    if raw_id == "Unknown" or not raw_id:
        messagebox.showwarning("No Game ID", "Cannot view art because the Game ID is unknown or unparsed.")
        return
        
    art_dir = os.path.join(opl_target_dir, "ART")
    if not os.path.exists(art_dir):
        messagebox.showwarning("No ART Folder", "The OPL ART folder does not exist yet on the target drive.")
        return
        
    matching_files = [f for f in os.listdir(art_dir) if f.startswith(raw_id)]
    if not matching_files:
        messagebox.showinfo("No Art", f"No downloaded art was found in the ART folder for:\n{raw_id}")
        return

    def get_b64(filename):
        if not filename: return ""
        path = os.path.join(art_dir, filename)
        if not os.path.exists(path): return ""
        with open(path, "rb") as img:
            ext = "png" if filename.lower().endswith('.png') else "jpeg"
            return f"data:image/{ext};base64," + base64.b64encode(img.read()).decode('utf-8')

    # --- PULL METADATA FROM PS2.data.json ---
    db_path = resource_path("PS2.data.json")
    db_info = {}
    if os.path.exists(db_path):
        try:
            with open(db_path, 'r', encoding='utf-8', errors='ignore') as f:
                data = json.load(f)
                clean_key = raw_id.replace('_', '').replace('-', '').replace('.', '').replace(' ', '').upper()
                for db_id, info in data.items():
                    if db_id.replace('_', '').replace('-', '').replace('.', '').upper() == clean_key:
                        db_info = info
                        break
        except Exception as e:
            print(f"Failed to load game info from JSON: {e}")

    publisher = db_info.get("publisher", "Unknown Publisher")
    developer = db_info.get("developer", "Unknown Developer")
    release_date = db_info.get("release_date", db_info.get("date", "Unknown Date"))
    genre = db_info.get("genre", "Unknown Genre")
    
    json_region = db_info.get("region", db_info.get("format", None))

    # --- PARSE REGION FROM GAME ID (Corrected to Index 2) ---
    region_map = {
        'U': 'NTSC-U (North America)', 
        'E': 'PAL (Europe)', 
        'J': 'NTSC-J (Japan)', 
        'P': 'NTSC-J / Japan', 
        'A': 'Asia', 
        'K': 'Korea', 
        'H': 'Hong Kong', 
        'C': 'China'
    }
    
    if json_region:
        region_str = json_region
    else:
        region_str = "Unknown Region"
        if len(raw_id) >= 3:
            reg_char = raw_id[2].upper()
            region_str = region_map.get(reg_char, f"Region Code: {reg_char}")

    cov_file = next((f for f in matching_files if "COV" in f and "COV2" not in f), None)
    cov2_file = next((f for f in matching_files if "COV2" in f), None)
    lab_file = next((f for f in matching_files if "LAB" in f), None)
    ico_file = next((f for f in matching_files if "ICO" in f), None)
    lgo_file = next((f for f in matching_files if "LGO" in f), None)
    bg_file  = next((f for f in matching_files if "BG_00" in f or "BG_01" in f), None)

    if not cov_file:
        messagebox.showwarning("Missing Art", "No Front Cover (COV) found to build the 3D Box.")
        return

    b64_front = get_b64(cov_file)
    b64_back = get_b64(cov2_file)
    b64_spine = get_b64(lab_file)
    b64_disc = get_b64(ico_file)
    b64_lgo = get_b64(lgo_file)
    b64_bg = get_b64(bg_file)

    logo_html = f'<img src="{b64_lgo}" class="game-logo" alt="Logo">' if b64_lgo else ''
    bg_html = f'<div class="bg-backdrop" style="background-image: url(\'{b64_bg}\');"></div>' if b64_bg else ''

    asset_badges = []
    if cov_file: asset_badges.append('<span class="badge active">COV</span>')
    if cov2_file: asset_badges.append('<span class="badge active">COV2</span>')
    if lab_file: asset_badges.append('<span class="badge active">LAB</span>')
    if ico_file: asset_badges.append('<span class="badge active">ICO</span>')
    if b64_lgo: asset_badges.append('<span class="badge active">LGO</span>')
    if b64_bg: asset_badges.append('<span class="badge active">BG</span>')
    badges_html = "".join(asset_badges)

    gallery_html = ""
    for file in sorted(matching_files):
        b64_img = get_b64(file)
        if b64_img:
            gallery_html += f"""
            <div class="gallery-item" onclick="openLightbox('{b64_img}', '{file}')">
                <img src="{b64_img}" alt="{file}">
                <h4>{file}</h4>
            </div>
            """

    if not gallery_html:
        gallery_html = "<h4 style='text-align:center; color:#71717a; margin-top:40px;'>No art found.</h4>"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>3D Viewer & Gallery: {game_name} ({raw_id})</title>
        <style>
            body {{
                display: flex;
                flex-direction: column;
                margin: 0;
                background-color: #0b0d10;
                color: #f4f4f5;
                font-family: sans-serif;
                overflow: hidden;
                height: 100vh;
                width: 100vw;
                position: relative;
            }}
            .bg-backdrop {{
                position: absolute;
                top: -20px;
                left: -20px;
                right: -20px;
                bottom: -20px;
                background-size: cover;
                background-position: center;
                filter: blur(14px) grayscale(70%) brightness(0.3);
                z-index: 0;
                pointer-events: none;
            }}
            .main-workspace {{
                display: flex;
                flex: 1;
                width: 100%;
                overflow: hidden;
                z-index: 1;
            }}
            #viewer-container {{
                flex: 1;
                position: relative;
                height: 100%;
            }}
            #gallery-panel {{
                width: 340px;
                background: rgba(22, 25, 31, 0.90);
                backdrop-filter: blur(10px);
                border-left: 1px solid rgba(255, 255, 255, 0.1);
                display: flex;
                flex-direction: column;
                height: 100%;
                box-sizing: border-box;
                box-shadow: -10px 0 30px rgba(0,0,0,0.5);
            }}
            .panel-header {{
                padding: 15px 20px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                background: rgba(18, 20, 24, 0.6);
                text-align: center;
            }}
            .game-logo {{
                max-width: 100%;
                max-height: 60px;
                object-fit: contain;
                margin-bottom: 8px;
                filter: drop-shadow(0 4px 6px rgba(0,0,0,0.4));
            }}
            .panel-header h3 {{
                margin: 0 0 2px 0;
                font-size: 14px;
                color: #ffffff;
            }}
            .panel-header p {{
                margin: 0 0 10px 0;
                font-size: 11px;
                color: #a1a1aa;
            }}
            .meta-grid {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 6px;
                text-align: left;
                font-size: 11px;
                background: rgba(0,0,0,0.3);
                padding: 8px 10px;
                border-radius: 4px;
                border: 1px solid rgba(255,255,255,0.05);
            }}
            .meta-item span {{
                color: #71717a;
                display: block;
                font-size: 9px;
                text-transform: uppercase;
            }}
            .meta-item strong {{
                color: #e4e4e7;
                font-size: 11px;
            }}
            .scroll-content {{
                flex: 1;
                overflow-y: auto;
                padding: 20px;
                box-sizing: border-box;
            }}
            .gallery-item {{
                margin-bottom: 25px;
                text-align: center;
                background: rgba(18, 20, 24, 0.7);
                padding: 12px;
                border-radius: 6px;
                border: 1px solid rgba(255, 255, 255, 0.05);
                cursor: pointer;
                transition: transform 0.2s, border-color 0.2s;
            }}
            .gallery-item:hover {{
                transform: translateY(-2px);
                border-color: #00439c;
            }}
            .gallery-item img {{
                max-width: 100%;
                max-height: 180px;
                border-radius: 4px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.5);
                object-fit: contain;
            }}
            .gallery-item h4 {{
                margin: 10px 0 0 0;
                font-size: 12px;
                color: #a1a1aa;
                word-wrap: break-word;
            }}
            .lightbox-modal {{
                display: none;
                position: fixed;
                top: 0; left: 0; width: 100vw; height: 100vh;
                background: rgba(11, 13, 16, 0.90);
                backdrop-filter: blur(12px);
                z-index: 9999;
                justify-content: center;
                align-items: center;
                flex-direction: column;
                cursor: pointer;
            }}
            .lightbox-modal img {{
                max-width: 85vw;
                max-height: 80vh;
                object-fit: contain;
                border-radius: 8px;
                box-shadow: 0 15px 40px rgba(0,0,0,0.8);
                border: 1px solid rgba(255,255,255,0.15);
            }}
            .lightbox-caption {{
                margin-top: 15px;
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                letter-spacing: 0.5px;
                background: rgba(0,0,0,0.5);
                padding: 6px 14px;
                border-radius: 4px;
                border: 1px solid rgba(255,255,255,0.1);
            }}
            .close-btn-container {{
                padding: 15px 20px;
                border-top: 1px solid rgba(255, 255, 255, 0.1);
                background: rgba(18, 20, 24, 0.6);
                text-align: center;
            }}
            .close-btn {{
                width: 100%;
                background: #242832;
                color: #f4f4f5;
                border: 1px solid #3d4452;
                padding: 10px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
                cursor: pointer;
                transition: background 0.2s, border-color 0.2s;
            }}
            .close-btn:hover {{
                background: #00439c;
                border-color: #38bdf8;
            }}
            .hud-footer {{
                height: 45px;
                background: rgba(14, 16, 20, 0.95);
                border-top: 1px solid rgba(255, 255, 255, 0.1);
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 0 20px;
                font-size: 12px;
                color: #a1a1aa;
                z-index: 10;
                box-sizing: border-box;
            }}
            .hud-section {{
                display: flex;
                align-items: center;
                gap: 15px;
            }}
            .hud-item strong {{
                color: #ffffff;
            }}
            .badge {{
                background: #00439c;
                color: #ffffff;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
                letter-spacing: 0.5px;
            }}
            ::-webkit-scrollbar {{ width: 8px; }}
            ::-webkit-scrollbar-track {{ background: rgba(0,0,0,0.2); }}
            ::-webkit-scrollbar-thumb {{ background: #2d3139; border-radius: 4px; }}
            ::-webkit-scrollbar-thumb:hover {{ background: #3d4452; }}
        </style>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
    </head>
    <body>
        {bg_html}
        <div class="main-workspace">
            <div id="viewer-container"></div>
            
            <div id="gallery-panel">
                <div class="panel-header">
                    {logo_html}
                    <h3>{game_name}</h3>
                    <p>ID: {raw_id}</p>
                    
                    <div class="meta-grid">
                        <div class="meta-item">
                            <span>Publisher</span>
                            <strong>{publisher}</strong>
                        </div>
                        <div class="meta-item">
                            <span>Released</span>
                            <strong>{release_date}</strong>
                        </div>
                        <div class="meta-item" style="grid-column: span 2;">
                            <span>Genre</span>
                            <strong>{genre}</strong>
                        </div>
                    </div>
                </div>
                
                <div class="scroll-content">
                    {gallery_html}
                </div>
                
                <div class="close-btn-container">
                    <button class="close-btn" onclick="window.close()">✕ Close Viewer Window</button>
                </div>
            </div>
        </div>

        <div class="hud-footer">
            <div class="hud-section">
                <span class="hud-item"><strong>Region:</strong> {region_str}</span>
                <span class="hud-item"><strong>Developer:</strong> {developer}</span>
            </div>
            <div class="hud-section">
                <span class="hud-item"><strong>Assets Loaded:</strong> {badges_html}</span>
            </div>
        </div>

        <!-- Lightbox Modal Overlay -->
        <div id="lightbox" class="lightbox-modal" onclick="closeLightbox()">
            <img id="lightbox-img" src="" alt="Enlarged Art">
            <div id="lightbox-caption" class="lightbox-caption"></div>
        </div>

        <script>
            function openLightbox(src, caption) {{
                document.getElementById('lightbox-img').src = src;
                document.getElementById('lightbox-caption').innerText = caption;
                document.getElementById('lightbox').style.display = 'flex';
            }}
            function closeLightbox() {{
                document.getElementById('lightbox').style.display = 'none';
            }}

            const container = document.getElementById('viewer-container');
            const scene = new THREE.Scene();
            
            const camera = new THREE.PerspectiveCamera(40, container.clientWidth / container.clientHeight, 0.1, 1000);
            scene.add(camera); 
            
            const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
            renderer.setSize(container.clientWidth, container.clientHeight);
            renderer.setPixelRatio(window.devicePixelRatio);
            container.appendChild(renderer.domElement);
            
            const controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.dampingFactor = 0.05;
            controls.minDistance = 2.5; 
            controls.maxDistance = 8.0;
            
            scene.add(new THREE.AmbientLight(0xffffff, 0.7));
            const dirLight = new THREE.DirectionalLight(0xffffff, 0.4);
            dirLight.position.set(5, 5, 5);
            scene.add(dirLight);
            
            const camLight = new THREE.PointLight(0xffffff, 0.4);
            camera.add(camLight);
            
            const caseGeo = new THREE.BoxGeometry(1.35, 1.90, 0.14);
            const loader = new THREE.TextureLoader();
            const blackPlastic = new THREE.MeshStandardMaterial({{ color: 0x111111, roughness: 0.9 }});
            const matFront = new THREE.MeshStandardMaterial({{ map: loader.load('{b64_front}'), roughness: 0.3 }});
            const matBack = '{b64_back}' ? new THREE.MeshStandardMaterial({{ map: loader.load('{b64_back}'), roughness: 0.3 }}) : blackPlastic;
            const matSpine = '{b64_spine}' ? new THREE.MeshStandardMaterial({{ map: loader.load('{b64_spine}'), roughness: 0.3 }}) : blackPlastic;
            const materials = [blackPlastic, matSpine, blackPlastic, blackPlastic, matFront, matBack];
            
            const caseMesh = new THREE.Mesh(caseGeo, materials);
            caseMesh.position.set(-0.8, 0, 0); 
            scene.add(caseMesh);
            
            let discMesh = null;
            if ('{b64_disc}') {{
                const discGeo = new THREE.CylinderGeometry(0.175, 0.175, 0.005, 64);
                const discShinyMat = new THREE.MeshStandardMaterial({{ color: 0xcccccc, metalness: 0.8, roughness: 0.2 }});
                const discTopMat = new THREE.MeshStandardMaterial({{ 
                    map: loader.load('{b64_disc}'), metalness: 0.3, roughness: 0.2, transparent: true, alphaTest: 0.05
                }});
                discMesh = new THREE.Mesh(discGeo, [discShinyMat, discTopMat, discShinyMat]);
                discMesh.rotation.x = Math.PI / 2;
                discMesh.position.set(0.55, 0, -1.8);
                camera.add(discMesh);
            }}
            
            camera.position.set(0, 0.2, 4.0);
            controls.target.set(-0.8, 0, 0); 
            
            function animate() {{
                requestAnimationFrame(animate);
                controls.update();
                if (discMesh) {{ discMesh.rotateY(-0.01); }}
                renderer.render(scene, camera);
            }}
            
            window.addEventListener('resize', () => {{
                camera.aspect = container.clientWidth / container.clientHeight;
                camera.updateProjectionMatrix();
                renderer.setSize(container.clientWidth, container.clientHeight);
            }});
            
            animate();
        </script>
    </body>
    </html>
    """
    
    temp_dir = tempfile.gettempdir()
    temp_html = os.path.join(temp_dir, f"view_{raw_id}.html")
    with open(temp_html, 'w', encoding='utf-8') as f:
        f.write(html_content)
        
    url = f"file:///{temp_html.replace(os.sep, '/')}"
    
    launched = False
    for browser_path in [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    ]:
        if os.path.exists(browser_path):
            try:
                subprocess.Popen([browser_path, f"--app={url}", "--window-size=1150,815"])
                launched = True
                break
            except Exception:
                pass
                
    if not launched:
        webbrowser.open(url)