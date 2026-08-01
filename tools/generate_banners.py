import os
import math
import xml.etree.ElementTree as ET

def create_swarm_svg():
    # 28 outer points around (600, 270)
    outer_points = []
    num_outer = 28
    r_outer = 500
    for i in range(num_outer):
        angle_deg = i * (360 / num_outer)
        rad = math.radians(angle_deg)
        x = round(600 + r_outer * math.cos(rad))
        y = round(270 + r_outer * math.sin(rad))
        x_clamped = max(50, min(1150, x))
        y_clamped = max(40, min(590, y))
        outer_points.append((x_clamped, y_clamped, angle_deg))

    # 14 inner points
    inner_points = []
    num_inner = 14
    r_inner = 280
    for i in range(num_inner):
        angle_deg = i * (360 / num_inner) + 12
        rad = math.radians(angle_deg)
        x = round(600 + r_inner * math.cos(rad))
        y = round(270 + r_inner * math.sin(rad))
        inner_points.append((x, y, angle_deg))

    all_points = outer_points + inner_points

    # Mask circles SMIL
    mask_circles_xml = []
    for idx, (x, y, angle) in enumerate(all_points):
        dur = 6.0
        r_max = 300 if idx < num_outer else 220
        mask_circles_xml.append(f'''
      <!-- Mask particle {idx} -->
      <circle cx="600" cy="270" r="0" fill="#ffffff">
        <animate attributeName="cx" values="600; {x}; {x}; 600" keyTimes="0; 0.25; 0.8; 1" dur="{dur}s" repeatCount="indefinite" />
        <animate attributeName="cy" values="270; {y}; {y}; 270" keyTimes="0; 0.25; 0.8; 1" dur="{dur}s" repeatCount="indefinite" />
        <animate attributeName="r" values="0; {r_max}; {r_max+30}; 0" keyTimes="0; 0.25; 0.8; 1" dur="{dur}s" repeatCount="indefinite" />
      </circle>''')

    # Animated Birds (Light layer & Dark layer)
    birds_xml_light = []
    birds_xml_dark = []
    for idx, (x, y, angle) in enumerate(all_points):
        dur = 6.0
        rot = round(angle + 90, 1)
        scale = round(0.48 + (idx % 6) * 0.1, 2)
        color = "#2563eb" if idx % 3 == 0 else ("#4f46e5" if idx % 3 == 1 else "#7c3aed")
        flap_dur = round(0.3 + (idx % 4) * 0.05, 2)

        birds_xml_light.append(f'''
      <g transform="translate(600,270) rotate({rot}) scale({scale})">
        <animateTransform attributeName="transform" type="translate" values="600,270; {x},{y}; {x},{y}; 600,270" keyTimes="0; 0.25; 0.8; 1" dur="{dur}s" repeatCount="indefinite" />
        <path d="M 0,-14 C 8,-10 16,-2 22,6 C 12,4 3,0 0,9 C -3,0 -12,4 -22,6 C -16,-2 -8,-10 0,-14 Z" fill="{color}">
          <animateTransform attributeName="transform" type="scale" values="1,1; 1,0.25; 1,1" dur="{flap_dur}s" repeatCount="indefinite" />
        </path>
        <circle cx="0" cy="0" r="3.5" fill="#38bdf8" opacity="0.9"/>
      </g>''')

        birds_xml_dark.append(f'''
      <g transform="translate(600,270) rotate({rot}) scale({scale})">
        <animateTransform attributeName="transform" type="translate" values="600,270; {x},{y}; {x},{y}; 600,270" keyTimes="0; 0.25; 0.8; 1" dur="{dur}s" repeatCount="indefinite" />
        <path d="M 0,-14 C 8,-10 16,-2 22,6 C 12,4 3,0 0,9 C -3,0 -12,4 -22,6 C -16,-2 -8,-10 0,-14 Z" fill="#38bdf8" opacity="0.8">
          <animateTransform attributeName="transform" type="scale" values="1,1; 1,0.25; 1,1" dur="{flap_dur}s" repeatCount="indefinite" />
        </path>
      </g>''')

    # Static Bird Flock Silhouettes in background
    flock_silhouettes = []
    flock_coords = [
        (180, 140, 0.4, -20), (220, 110, 0.5, -15), (270, 130, 0.6, -10),
        (310, 90, 0.45, -5), (360, 120, 0.55, 0), (900, 120, 0.5, 10),
        (940, 90, 0.6, 15), (990, 130, 0.45, 20), (1030, 100, 0.55, 25),
        (140, 360, 0.4, -25), (180, 400, 0.5, -20), (1020, 380, 0.5, 20)
    ]
    for (fx, fy, fsc, frot) in flock_coords:
        flock_silhouettes.append(f'''
      <g transform="translate({fx},{fy}) rotate({frot}) scale({fsc})" opacity="0.25">
        <path d="M 0,-14 C 8,-10 16,-2 22,6 C 12,4 3,0 0,9 C -3,0 -12,4 -22,6 C -16,-2 -8,-10 0,-14 Z" />
      </g>''')

    svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630">
  <defs>
    <style>
      .title {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-weight: 900; font-size: 68px; letter-spacing: -2px; }}
      .subtitle {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-weight: 600; font-size: 24px; letter-spacing: -0.5px; }}
      .badge-text {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-weight: 700; font-size: 12px; letter-spacing: 2px; text-transform: uppercase; }}
      .card-title {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-weight: 700; font-size: 15px; }}
      .card-sub {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-weight: 500; font-size: 12px; }}
      .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; font-weight: 600; }}
      
      @keyframes floatSlow {{ 0%, 100% {{ transform: translateY(0px); }} 50% {{ transform: translateY(-8px); }} }}
      @keyframes pulseGlow {{ 0%, 100% {{ opacity: 0.3; }} 50% {{ opacity: 0.8; }} }}

      .floating {{ animation: floatSlow 4s ease-in-out infinite; }}
      .glowing {{ animation: pulseGlow 3s ease-in-out infinite; }}
    </style>

    <linearGradient id="bg-dark" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#070a12"/>
      <stop offset="50%" stop-color="#0f172a"/>
      <stop offset="100%" stop-color="#1e1b4b"/>
    </linearGradient>

    <linearGradient id="bg-light" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="60%" stop-color="#f8fafc"/>
      <stop offset="100%" stop-color="#f1f5f9"/>
    </linearGradient>

    <linearGradient id="brand-grad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#2563eb"/>
      <stop offset="50%" stop-color="#4f46e5"/>
      <stop offset="100%" stop-color="#7c3aed"/>
    </linearGradient>

    <!-- Mask that reveals top white layer as points fan out in 360 degrees -->
    <mask id="reveal-mask" maskUnits="userSpaceOnUse" x="0" y="0" width="1200" height="630">
      <rect x="0" y="0" width="1200" height="630" fill="#000000" />
      
      <!-- Central expanding core -->
      <circle cx="600" cy="270" r="0" fill="#ffffff">
        <animate attributeName="r" values="0; 100; 800; 900; 900; 0" keyTimes="0; 0.08; 0.25; 0.8; 0.9; 1" dur="6.0s" repeatCount="indefinite" />
      </circle>
      {"".join(mask_circles_xml)}
    </mask>

    <pattern id="grid-pattern-dark" width="40" height="40" patternUnits="userSpaceOnUse">
      <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#334155" stroke-width="1" stroke-opacity="0.25"/>
    </pattern>

    <pattern id="grid-pattern-light" width="40" height="40" patternUnits="userSpaceOnUse">
      <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#cbd5e1" stroke-width="1" stroke-opacity="0.4"/>
    </pattern>
  </defs>

  <!-- ==================== BASE LAYER: DARK BACKGROUND ==================== -->
  <g id="dark-base-layer">
    <rect width="1200" height="630" fill="url(#bg-dark)"/>
    <rect width="1200" height="630" fill="url(#grid-pattern-dark)"/>

    <!-- Bird Flock Background Motif (Dark) -->
    <g fill="#38bdf8">
      {"".join(flock_silhouettes)}
    </g>

    <!-- Swarm Radial Vector Rays (Dark) -->
    <g stroke="#38bdf8" stroke-width="1.5" fill="none" opacity="0.25">
      <path d="M 600,270 L 100,60 M 600,270 L 1100,60 M 600,270 L 1100,480 M 600,270 L 100,480" stroke-dasharray="4 4" />
    </g>

    <!-- Central Point Origin (Dark) -->
    <circle cx="600" cy="270" r="14" fill="#38bdf8" opacity="0.3" class="glowing"/>
    <circle cx="600" cy="270" r="6" fill="#38bdf8"/>

    <!-- Header Badge Dark -->
    <g transform="translate(600, 62)">
      <rect x="-140" y="-16" width="280" height="32" rx="16" fill="#1e293b" stroke="#334155" stroke-width="1"/>
      <text x="0" y="5" text-anchor="middle" fill="#38bdf8" class="badge-text">LLM Swarm Intelligence</text>
    </g>

    <!-- Title & Subtitle Dark -->
    <text x="600" y="142" text-anchor="middle" fill="#f8fafc" class="title">swarm-ai</text>
    <text x="600" y="182" text-anchor="middle" fill="#94a3b8" class="subtitle">many points, more ground, same time</text>

    <!-- Dark Flying Swarm Birds -->
    {"".join(birds_xml_dark)}

    <!-- Bottom Comparison Section (Dark Mode) -->
    <g transform="translate(180, 480)">
      <rect x="0" y="0" width="380" height="110" rx="14" fill="#0f172a" stroke="#1e293b" stroke-width="1.5"/>
      <text x="20" y="32" fill="#f8fafc" class="card-title">1 Agent (Single Point)</text>
      <text x="20" y="52" fill="#64748b" class="card-sub">Serial execution • 1x Area covered</text>
      <rect x="20" y="66" width="340" height="28" rx="6" fill="#1e293b"/>
      <circle cx="35" cy="80" r="6" fill="#ef4444"/>
      <text x="360" y="84" text-anchor="end" fill="#ef4444" class="mono">5% / T</text>

      <g transform="translate(460, 0)">
        <rect x="0" y="0" width="380" height="110" rx="14" fill="#0f172a" stroke="#312e81" stroke-width="1.5"/>
        <text x="20" y="32" fill="#f8fafc" class="card-title">Swarm AI (Many Points)</text>
        <text x="20" y="52" fill="#818cf8" class="card-sub">Parallel execution • 20x Area covered</text>
        <rect x="20" y="66" width="340" height="28" rx="6" fill="#1e1b4b"/>
        <text x="360" y="84" text-anchor="end" fill="#34d399" class="mono">100% / T</text>
      </g>
    </g>
  </g>

  <!-- ==================== TOP LAYER: REVEALED WHITE CANVAS ==================== -->
  <g id="light-revealed-layer" mask="url(#reveal-mask)">
    <rect width="1200" height="630" fill="url(#bg-light)"/>
    <rect width="1200" height="630" fill="url(#grid-pattern-light)"/>

    <!-- Bird Flock Background Motif (Light) -->
    <g fill="#2563eb">
      {"".join(flock_silhouettes)}
    </g>

    <!-- Swarm Radial Vector Rays (Light) -->
    <g stroke="url(#brand-grad)" stroke-width="2" fill="none" opacity="0.4">
      <path d="M 600,270 L 100,60 M 600,270 L 1100,60 M 600,270 L 1100,480 M 600,270 L 100,480" stroke-dasharray="6 6" opacity="0.6"/>
    </g>

    <!-- Header Badge Light -->
    <g transform="translate(600, 62)">
      <rect x="-150" y="-16" width="300" height="32" rx="16" fill="#eff6ff" stroke="#bfdbfe" stroke-width="1.5"/>
      <text x="0" y="5" text-anchor="middle" fill="#2563eb" class="badge-text">Parallel Agent Orchestration</text>
    </g>

    <!-- Title & Subtitle Light -->
    <text x="600" y="142" text-anchor="middle" fill="url(#brand-grad)" class="title">swarm-ai</text>
    <text x="600" y="182" text-anchor="middle" fill="#334155" class="subtitle">many points, more ground, same time</text>

    <!-- Central point light mode burst origin -->
    <circle cx="600" cy="270" r="16" fill="url(#brand-grad)" opacity="0.2" class="glowing"/>
    <circle cx="600" cy="270" r="7" fill="#2563eb"/>

    <!-- Light Flying Swarm Birds -->
    {"".join(birds_xml_light)}

    <!-- Bottom Comparison Section (Light Mode - Premium Crisp Cards) -->
    <g transform="translate(180, 480)">
      <!-- Left Card: Single Point -->
      <rect x="0" y="0" width="380" height="110" rx="14" fill="#ffffff" stroke="#e2e8f0" stroke-width="2"/>
      <text x="20" y="32" fill="#0f172a" class="card-title">1 Agent (Single Point)</text>
      <text x="20" y="52" fill="#64748b" class="card-sub">Serial execution • Limited area</text>
      <rect x="20" y="66" width="340" height="28" rx="6" fill="#f8fafc" stroke="#e2e8f0" stroke-width="1"/>
      <circle cx="40" cy="80" r="6" fill="#ef4444">
        <animate attributeName="cx" values="40; 140; 40" dur="3.5s" repeatCount="indefinite"/>
      </circle>
      <text x="345" y="85" text-anchor="end" fill="#dc2626" class="mono">5% / T</text>

      <!-- Right Card: Swarm AI -->
      <g transform="translate(460, 0)">
        <rect x="0" y="0" width="380" height="110" rx="14" fill="#ffffff" stroke="#6366f1" stroke-width="2"/>
        <text x="20" y="32" fill="#0f172a" class="card-title">Swarm AI (Many Points)</text>
        <text x="20" y="52" fill="#4f46e5" class="card-sub">Parallel execution • Maximum ground</text>
        <rect x="20" y="66" width="340" height="28" rx="6" fill="#f5f3ff" stroke="#ddd6fe" stroke-width="1"/>
        <g fill="#10b981">
          <circle cx="40" cy="80" r="5"/>
          <circle cx="75" cy="80" r="5"/>
          <circle cx="110" cy="80" r="5"/>
          <circle cx="145" cy="80" r="5"/>
          <circle cx="180" cy="80" r="5"/>
          <circle cx="215" cy="80" r="5"/>
          <circle cx="250" cy="80" r="5"/>
          <circle cx="285" cy="80" r="5"/>
        </g>
        <text x="345" y="85" text-anchor="end" fill="#059669" class="mono">100% / T</text>
      </g>
    </g>
  </g>
</svg>'''
    return svg_content


def create_goldfish_svg():
    # 24 goldfish target positions swimming outward from (600, 270)
    fish_targets = []
    num_fish = 24
    for i in range(num_fish):
        angle_deg = i * (360 / num_fish)
        rad = math.radians(angle_deg)
        r = 500 if i % 2 == 0 else 300
        x = round(600 + r * math.cos(rad))
        y = round(270 + r * math.sin(rad))
        x_clamped = max(60, min(1140, x))
        y_clamped = max(50, min(580, y))
        fish_targets.append((x_clamped, y_clamped, angle_deg))

    # Mask circles
    mask_circles_xml = []
    for idx, (x, y, angle) in enumerate(fish_targets):
        dur = 6.0
        r_max = 300 if idx % 2 == 0 else 220
        mask_circles_xml.append(f'''
      <!-- Goldfish mask particle {idx} -->
      <circle cx="600" cy="270" r="0" fill="#ffffff">
        <animate attributeName="cx" values="600; {x}; {x}; 600" keyTimes="0; 0.25; 0.8; 1" dur="{dur}s" repeatCount="indefinite" />
        <animate attributeName="cy" values="270; {y}; {y}; 270" keyTimes="0; 0.25; 0.8; 1" dur="{dur}s" repeatCount="indefinite" />
        <animate attributeName="r" values="0; {r_max}; {r_max+30}; 0" keyTimes="0; 0.25; 0.8; 1" dur="{dur}s" repeatCount="indefinite" />
      </circle>''')

    # Goldfish SVG graphics (Light & Dark)
    fish_light_xml = []
    fish_dark_xml = []
    for idx, (x, y, angle) in enumerate(fish_targets):
        dur = 6.0
        rot = round(angle + 90, 1)
        scale = round(0.55 + (idx % 4) * 0.1, 2)
        body_color = "#f97316" if idx % 2 == 0 else "#ea580c"
        fin_color = "#fb923c" if idx % 2 == 0 else "#f97316"

        fish_light_xml.append(f'''
      <g transform="translate(600,270) rotate({rot}) scale({scale})">
        <animateTransform attributeName="transform" type="translate" values="600,270; {x},{y}; {x},{y}; 600,270" keyTimes="0; 0.25; 0.8; 1" dur="{dur}s" repeatCount="indefinite" />
        <path d="M 0,-18 C 10,-8 12,6 0,16 C -12,6 -10,-8 0,-18 Z" fill="{body_color}" />
        <path d="M 0,14 Q 10,26 14,32 Q 0,24 -14,32 Q -10,26 0,14 Z" fill="{fin_color}" opacity="0.9">
          <animateTransform attributeName="transform" type="rotate" values="-15 0 14; 15 0 14; -15 0 14" dur="0.35s" repeatCount="indefinite"/>
        </path>
        <path d="M 6,-2 Q 16,-6 14,4 Z" fill="{fin_color}" opacity="0.8" />
        <path d="M -6,-2 Q -16,-6 -14,4 Z" fill="{fin_color}" opacity="0.8" />
        <circle cx="3" cy="-10" r="2" fill="#0f172a" />
        <circle cx="3.5" cy="-10.5" r="0.7" fill="#ffffff" />
      </g>''')

        fish_dark_xml.append(f'''
      <g transform="translate(600,270) rotate({rot}) scale({scale})">
        <animateTransform attributeName="transform" type="translate" values="600,270; {x},{y}; {x},{y}; 600,270" keyTimes="0; 0.25; 0.8; 1" dur="{dur}s" repeatCount="indefinite" />
        <path d="M 0,-18 C 10,-8 12,6 0,16 C -12,6 -10,-8 0,-18 Z" fill="#38bdf8" opacity="0.8" />
        <path d="M 0,14 Q 10,26 14,32 Q 0,24 -14,32 Q -10,26 0,14 Z" fill="#0ea5e9" opacity="0.7">
          <animateTransform attributeName="transform" type="rotate" values="-15 0 14; 15 0 14; -15 0 14" dur="0.35s" repeatCount="indefinite"/>
        </path>
      </g>''')

    svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630">
  <defs>
    <style>
      .title {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-weight: 900; font-size: 68px; letter-spacing: -2px; }}
      .subtitle {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-weight: 600; font-size: 24px; letter-spacing: -0.5px; }}
      .badge-text {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-weight: 700; font-size: 12px; letter-spacing: 2px; text-transform: uppercase; }}
      .card-title {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-weight: 700; font-size: 15px; }}
      .card-sub {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-weight: 500; font-size: 12px; }}
      .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; font-weight: 600; }}
    </style>

    <linearGradient id="bg-ocean-dark" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#031327"/>
      <stop offset="50%" stop-color="#072545"/>
      <stop offset="100%" stop-color="#0f172a"/>
    </linearGradient>

    <linearGradient id="bg-ocean-light" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="60%" stop-color="#f0f9ff"/>
      <stop offset="100%" stop-color="#e0f2fe"/>
    </linearGradient>

    <linearGradient id="goldfish-grad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#ea580c"/>
      <stop offset="50%" stop-color="#f97316"/>
      <stop offset="100%" stop-color="#eab308"/>
    </linearGradient>

    <!-- Mask that brightens underwater view into clear white light as goldfish swim out -->
    <mask id="reveal-mask-fish" maskUnits="userSpaceOnUse" x="0" y="0" width="1200" height="630">
      <rect x="0" y="0" width="1200" height="630" fill="#000000" />
      <circle cx="600" cy="270" r="0" fill="#ffffff">
        <animate attributeName="r" values="0; 100; 800; 900; 900; 0" keyTimes="0; 0.08; 0.25; 0.8; 0.9; 1" dur="6.0s" repeatCount="indefinite" />
      </circle>
      {"".join(mask_circles_xml)}
    </mask>

    <pattern id="wave-grid-dark" width="60" height="60" patternUnits="userSpaceOnUse">
      <path d="M 0 30 Q 15 15 30 30 T 60 30" fill="none" stroke="#1e293b" stroke-width="1.5" opacity="0.3"/>
    </pattern>

    <pattern id="wave-grid-light" width="60" height="60" patternUnits="userSpaceOnUse">
      <path d="M 0 30 Q 15 15 30 30 T 60 30" fill="none" stroke="#bae6fd" stroke-width="1.5" opacity="0.5"/>
    </pattern>
  </defs>

  <!-- ==================== BASE LAYER: DARK DEEP WATER ==================== -->
  <g id="dark-water-layer">
    <rect width="1200" height="630" fill="url(#bg-ocean-dark)"/>
    <rect width="1200" height="630" fill="url(#wave-grid-dark)"/>

    <g stroke="#0284c7" stroke-width="1.5" fill="none" opacity="0.25">
      <ellipse cx="600" cy="270" rx="300" ry="120"/>
      <ellipse cx="600" cy="270" rx="500" ry="200"/>
    </g>

    <!-- Header Badge Dark -->
    <g transform="translate(600, 62)">
      <rect x="-160" y="-16" width="320" height="32" rx="16" fill="#0f172a" stroke="#0284c7" stroke-width="1"/>
      <text x="0" y="5" text-anchor="middle" fill="#38bdf8" class="badge-text">Variant: Goldfish Swarm</text>
    </g>

    <!-- Title & Subtitle Dark -->
    <text x="600" y="142" text-anchor="middle" fill="#f8fafc" class="title">swarm-ai</text>
    <text x="600" y="182" text-anchor="middle" fill="#7dd3fc" class="subtitle">many points, more ground, same time</text>

    <!-- Dark Swimming Goldfish -->
    {"".join(fish_dark_xml)}

    <!-- Bottom Comparison Section (Dark Mode) -->
    <g transform="translate(180, 480)">
      <rect x="0" y="0" width="380" height="110" rx="14" fill="#091e3a" stroke="#1e293b" stroke-width="1.5"/>
      <text x="20" y="32" fill="#f8fafc" class="card-title">1 Goldfish (Single Point)</text>
      <text x="20" y="52" fill="#64748b" class="card-sub">Single fish • Slow water clearance</text>
      <rect x="20" y="66" width="340" height="28" rx="6" fill="#0f172a"/>
      <circle cx="35" cy="80" r="6" fill="#f97316"/>
      <text x="360" y="84" text-anchor="end" fill="#f97316" class="mono">5% / T</text>

      <g transform="translate(460, 0)">
        <rect x="0" y="0" width="380" height="110" rx="14" fill="#091e3a" stroke="#0369a1" stroke-width="1.5"/>
        <text x="20" y="32" fill="#f8fafc" class="card-title">Goldfish Swarm (Many Points)</text>
        <text x="20" y="52" fill="#38bdf8" class="card-sub">Entire school • Crystal clear water</text>
        <rect x="20" y="66" width="340" height="28" rx="6" fill="#0284c7" opacity="0.2"/>
        <text x="360" y="84" text-anchor="end" fill="#38bdf8" class="mono">100% / T</text>
      </g>
    </g>
  </g>

  <!-- ==================== TOP LAYER: REVEALED CLEAR WATER ==================== -->
  <g id="light-water-layer" mask="url(#reveal-mask-fish)">
    <rect width="1200" height="630" fill="url(#bg-ocean-light)"/>
    <rect width="1200" height="630" fill="url(#wave-grid-light)"/>

    <g stroke="#38bdf8" stroke-width="2" stroke-dasharray="10 10" opacity="0.3">
      <line x1="600" y1="0" x2="300" y2="630" />
      <line x1="600" y1="0" x2="900" y2="630" />
      <line x1="600" y1="0" x2="600" y2="630" />
    </g>

    <!-- Header Badge Light -->
    <g transform="translate(600, 62)">
      <rect x="-160" y="-16" width="320" height="32" rx="16" fill="#f0f9ff" stroke="#7dd3fc" stroke-width="1.5"/>
      <text x="0" y="5" text-anchor="middle" fill="#0284c7" class="badge-text">Variant: Goldfish Swarm</text>
    </g>

    <!-- Title & Subtitle Light -->
    <text x="600" y="142" text-anchor="middle" fill="url(#goldfish-grad)" class="title">swarm-ai</text>
    <text x="600" y="182" text-anchor="middle" fill="#0369a1" class="subtitle">many points, more ground, same time</text>

    <!-- Central point light mode burst origin -->
    <circle cx="600" cy="270" r="16" fill="#f97316" opacity="0.3"/>
    <circle cx="600" cy="270" r="7" fill="#ea580c"/>

    <!-- Light Swimming Goldfish -->
    {"".join(fish_light_xml)}

    <!-- Bottom Comparison Section (Light Mode) -->
    <g transform="translate(180, 480)">
      <!-- Left Card: Single Goldfish -->
      <rect x="0" y="0" width="380" height="110" rx="14" fill="#ffffff" stroke="#e0f2fe" stroke-width="2"/>
      <text x="20" y="32" fill="#0f172a" class="card-title">1 Goldfish (Single Point)</text>
      <text x="20" y="52" fill="#0369a1" class="card-sub">Single swimmer • 1x Water area</text>
      <rect x="20" y="66" width="340" height="28" rx="6" fill="#f0f9ff" stroke="#bae6fd" stroke-width="1"/>
      <circle cx="40" cy="80" r="6" fill="#ea580c">
        <animate attributeName="cx" values="40; 140; 40" dur="3.5s" repeatCount="indefinite"/>
      </circle>
      <text x="345" y="85" text-anchor="end" fill="#ea580c" class="mono">5% / T</text>

      <!-- Right Card: Goldfish Swarm -->
      <g transform="translate(460, 0)">
        <rect x="0" y="0" width="380" height="110" rx="14" fill="#ffffff" stroke="#0284c7" stroke-width="2"/>
        <text x="20" y="32" fill="#0f172a" class="card-title">Goldfish Swarm (Many Points)</text>
        <text x="20" y="52" fill="#0284c7" class="card-sub">Full school • 20x Clear water</text>
        <rect x="20" y="66" width="340" height="28" rx="6" fill="#e0f2fe" stroke="#7dd3fc" stroke-width="1"/>
        <g fill="#ea580c">
          <circle cx="40" cy="80" r="5"/>
          <circle cx="75" cy="80" r="5"/>
          <circle cx="110" cy="80" r="5"/>
          <circle cx="145" cy="80" r="5"/>
          <circle cx="180" cy="80" r="5"/>
          <circle cx="215" cy="80" r="5"/>
          <circle cx="250" cy="80" r="5"/>
          <circle cx="285" cy="80" r="5"/>
        </g>
        <text x="345" y="85" text-anchor="end" fill="#0284c7" class="mono">100% / T</text>
      </g>
    </g>
  </g>
</svg>'''
    return svg_content


def main():
    os.makedirs("assets", exist_ok=True)
    
    swarm_svg = create_swarm_svg()
    with open("assets/banner-swarm.svg", "w", encoding="utf-8") as f:
        f.write(swarm_svg)

    goldfish_svg = create_goldfish_svg()
    with open("assets/banner-goldfish.svg", "w", encoding="utf-8") as f:
        f.write(goldfish_svg)

    ET.fromstring(swarm_svg)
    ET.fromstring(goldfish_svg)
    print("Banners regenerated and validated successfully.")

if __name__ == "__main__":
    main()
