import os
import time
import subprocess

edge_path = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if not os.path.exists(edge_path):
    edge_path = r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'

# Write a tiny HTML wrapper with a 2-second delay to capture the mid-animation frame
for name in ['banner-swarm', 'banner-goldfish']:
    svg_abs = os.path.abspath(f'assets/{name}.svg')
    html_content = f'''<!DOCTYPE html>
<html>
<head>
  <style>
    body {{ margin: 0; padding: 0; background: #000; overflow: hidden; }}
    img {{ width: 1200px; height: 630px; display: block; }}
  </style>
</head>
<body>
  <img src="file:///{svg_abs}" />
</body>
</html>'''
    html_path = os.path.abspath(f'assets/{name}-test.html')
    png_path = os.path.abspath(f'assets/{name}-preview.png')

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    cmd = [
        edge_path,
        '--headless',
        '--disable-gpu',
        '--run-all-compositor-stages-before-draw',
        '--virtual-time-budget=2500',
        f'--screenshot={png_path}',
        '--window-size=1200,630',
        f'file:///{html_path}'
    ]
    subprocess.run(cmd, check=True)
    print(f"Captured mid-animation preview for {name} -> {png_path}")

print("Previews updated successfully.")
