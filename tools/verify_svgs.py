import re
import xml.etree.ElementTree as ET

files = ['assets/banner-swarm.svg', 'assets/banner-goldfish.svg']

for filename in files:
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Well-formedness
    try:
        ET.fromstring(content)
        print(f"[{filename}] XML well-formed: OK")
    except Exception as e:
        print(f"[{filename}] XML ERROR: {e}")
        raise

    # 2. Forbidden tags
    assert '<script' not in content, f"Forbidden <script> tag in {filename}"
    assert 'foreignObject' not in content, f"Forbidden <foreignObject> tag in {filename}"
    print(f"[{filename}] No script or foreignObject: OK")

    # 3. URL check
    urls = re.findall(r'https?://[^\s"\'>]+', content)
    allowed_urls = {'http://www.w3.org/2000/svg', 'http://www.w3.org/1999/xlink'}
    for url in urls:
        assert url in allowed_urls, f"Forbidden external URL {url} in {filename}"
    print(f"[{filename}] External URLs checked (only standard xmlns): OK")

print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")
