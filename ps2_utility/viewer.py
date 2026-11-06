import os
import base64
import tempfile
import webbrowser
from tkinter import messagebox

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

    cov_file = next((f for f in matching_files if "COV" in f and "COV2" not in f), None)
    cov2_file = next((f for f in matching_files if "COV2" in f), None)
    lab_file = next((f for f in matching_files if "LAB" in f), None)
    ico_file = next((f for f in matching_files if "ICO" in f), None)

    if not cov_file:
        messagebox.showwarning("Missing Art", "No Front Cover (COV) found to build the 3D Box.")
        return

    b64_front = get_b64(cov_file)
    b64_back = get_b64(cov2_file)
    b64_spine = get_b64(lab_file)
    b64_disc = get_b64(ico_file)

    gallery_html = ""
    for file in sorted(matching_files):
        if file in [cov_file, cov2_file, lab_file]:
            continue
        b64_img = get_b64(file)
        gallery_html += f"""
        <div class="gallery-item">
            <img src="{b64_img}" alt="{file}">
            <h4>{file}</h4>
        </div>
        """

    if not gallery_html:
        gallery_html = "<h4 style='text-align:center; color:#777; margin-top:50px;'>No additional flat art found.</h4>"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>3D Gallery: {game_name} ({raw_id})</title>
        <style>
            body {{ display: flex; margin: 0; background-color: #1e1e1e; color: #eee; font-family: sans-serif; overflow: hidden; height: 100vh; }}
            #viewer-container {{ flex: 1; position: relative; }}
            #gallery-panel {{ width: 350px; background: #252526; border-left: 1px solid #333; overflow-y: auto; padding: 20px; box-sizing: border-box; }}
            .gallery-item {{ margin-bottom: 25px; text-align: center; }}
            .gallery-item img {{ max-width: 100%; border-radius: 4px; box-shadow: 0 4px 8px rgba(0,0,0,0.5); }}
            .gallery-item h4 {{ margin: 10px 0 0 0; font-size: 13px; color: #aaa; word-wrap: break-word; }}
            ::-webkit-scrollbar {{ width: 8px; }}
            ::-webkit-scrollbar-thumb {{ background: #555; border-radius: 4px; }}
        </style>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
    </head>
    <body>
        <div id="viewer-container"></div>
        <div id="gallery-panel">
            <h3 style="text-align:center; margin-top:0; color:#fff;">Raw 2D Assets</h3>
            <hr style="border:0; border-top:1px solid #444; margin-bottom:20px;">
            {gallery_html}
        </div>
        <script>
            const container = document.getElementById('viewer-container');
            const scene = new THREE.Scene();
            const camera = new THREE.PerspectiveCamera(40, container.clientWidth / container.clientHeight, 0.1, 1000);
            scene.add(camera); 
            const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
            renderer.setSize(container.clientWidth, container.clientHeight);
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
        
    webbrowser.open(f"file:///{temp_html}")