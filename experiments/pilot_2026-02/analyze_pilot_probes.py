#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import sys
import os
from datetime import datetime
from pathlib import Path

# Task-IDs und deren Aufträge
tasks_meta = {
    'af22b5f': {'model': 'Haiku', 'task': 'Task erstellen'},
    'a79cfdb': {'model': 'Sonnet', 'task': 'BACH starten'},
    'ae480d9': {'model': 'Haiku', 'task': 'Steuerbelege finden'},
    'a233c53': {'model': 'Sonnet', 'task': 'Offene Tasks'},
    'a76d7f1': {'model': 'Haiku', 'task': 'Python-Tools finden'},
    'ae2fe98': {'model': 'Sonnet', 'task': 'Wiki-Artikel schreiben'},
    'a877330': {'model': 'Haiku', 'task': 'Logs lesen'},
    'a1c18c2': {'model': 'Sonnet', 'task': 'Agenten auflisten'},
    'adff5c1': {'model': 'Haiku', 'task': 'DB exportieren'},
    'a743337': {'model': 'Sonnet', 'task': 'System-Status'}
}

# Subagents-Verzeichnis muss explizit angegeben werden; keine Benutzerpfade im Code.
subagents_arg = sys.argv[1] if len(sys.argv) > 1 else os.getenv("SWARM_SUBAGENTS_DIR")
if not subagents_arg:
    raise SystemExit(
        "Usage: analyze_pilot_probes.py SUBAGENTS_DIR "
        "(or set SWARM_SUBAGENTS_DIR)"
    )
subagents_dir = str(Path(subagents_arg).expanduser().resolve())
if not Path(subagents_dir).is_dir():
    raise SystemExit(f"Subagents directory not found: {subagents_dir}")

# Ergebnis-Struktur
results = {}

for task_id, meta in tasks_meta.items():
    filepath = os.path.join(subagents_dir, f'agent-{task_id}.jsonl')

    results[task_id] = {
        'model': meta['model'],
        'task': meta['task'],
        'visited_paths': [],
        'tool_calls': [],
        'success': None,
        'error_messages': [],
        'timeline': [],
        'final_output': ''
    }

    if not os.path.exists(filepath):
        results[task_id]['error_messages'].append(f'File not found: {filepath}')
        continue

    # JSONL-Datei parsen
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                try:
                    entry = json.loads(line.strip())

                    # Timestamp extrahieren
                    timestamp = entry.get('ts', '')

                    # Tool-Aufrufe extrahieren
                    if 'content' in entry:
                        for content_item in entry.get('content', []):
                            if content_item.get('type') == 'tool_use':
                                tool_name = content_item.get('name', '')
                                tool_input = content_item.get('input', {})
                                tool_id = content_item.get('id', '')

                                # Pfade extrahieren
                                path = None
                                if tool_name == 'Read':
                                    path = tool_input.get('file_path', '')
                                elif tool_name == 'Glob':
                                    pattern = tool_input.get('pattern', '')
                                    search_path = tool_input.get('path', '.')
                                    path = f"Glob: {search_path}/{pattern}"
                                elif tool_name == 'Grep':
                                    pattern = tool_input.get('pattern', '')
                                    search_path = tool_input.get('path', '.')
                                    path = f"Grep: {pattern} in {search_path}"
                                elif tool_name == 'Bash':
                                    cmd = tool_input.get('command', '')
                                    if any(keyword in cmd for keyword in ['ls', 'cd', 'find', 'tree', 'pwd']):
                                        path = f"Bash: {cmd[:80]}"
                                elif tool_name == 'Write':
                                    path = f"Write: {tool_input.get('file_path', '')}"
                                elif tool_name == 'Edit':
                                    path = f"Edit: {tool_input.get('file_path', '')}"
                                elif tool_name == 'TaskCreate':
                                    path = f"TaskCreate: {tool_input.get('subject', '')[:50]}"
                                elif tool_name == 'TaskList':
                                    path = "TaskList"
                                elif tool_name == 'Skill':
                                    path = f"Skill: {tool_input.get('skill', '')}"

                                # Tool-Aufruf speichern
                                call_info = {
                                    'timestamp': timestamp,
                                    'tool': tool_name,
                                    'id': tool_id,
                                    'path': path
                                }
                                results[task_id]['tool_calls'].append(call_info)
                                results[task_id]['timeline'].append({
                                    'time': timestamp,
                                    'action': f"{tool_name}: {path}" if path else tool_name
                                })

                                if path and path not in results[task_id]['visited_paths']:
                                    results[task_id]['visited_paths'].append(path)

                            # Tool-Ergebnisse für Erfolgsanalyse
                            elif content_item.get('type') == 'tool_result':
                                result_content = content_item.get('content', '')
                                if isinstance(result_content, str):
                                    # Fehler-Meldungen extrahieren
                                    if 'error' in result_content.lower() or 'failed' in result_content.lower():
                                        error_snippet = result_content[:150]
                                        results[task_id]['error_messages'].append(error_snippet)

                            # Text-Antworten für finale Ausgabe
                            elif content_item.get('type') == 'text':
                                text = content_item.get('text', '')
                                # Letzte Textausgabe merken
                                if len(text) > 50:  # Nur substantielle Texte
                                    results[task_id]['final_output'] = text[:500]

                    # Rolle assistant = finale Antwort des Agenten
                    if entry.get('role') == 'assistant':
                        # Erfolgsanalyse basierend auf letzter Nachricht
                        if 'content' in entry:
                            full_text = ''
                            for item in entry['content']:
                                if item.get('type') == 'text':
                                    full_text += item.get('text', '')

                            lower_text = full_text.lower()
                            # Erfolgs-Indikatoren
                            if any(word in lower_text for word in ['erfolgreich', 'completed', 'done', 'finished', 'erstellt', 'gefunden', 'geschrieben']):
                                results[task_id]['success'] = True
                            elif any(word in lower_text for word in ['fehler', 'error', 'failed', 'nicht gefunden', 'konnte nicht']):
                                results[task_id]['success'] = False

                except json.JSONDecodeError as e:
                    print(f"JSON-Fehler in {task_id}, Zeile {line_num}: {e}", file=sys.stderr)
                    continue

        # Zusammenfassung
        results[task_id]['summary'] = {
            'visited_paths_count': len(results[task_id]['visited_paths']),
            'tool_calls_count': len(results[task_id]['tool_calls']),
            'error_count': len(results[task_id]['error_messages'])
        }

    except Exception as e:
        results[task_id]['error_messages'].append(f"Datei-Lesefehler: {str(e)}")

# Ergebnis als JSON ausgeben
print(json.dumps(results, indent=2, ensure_ascii=False))
