#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

# Ergebnisse laden
with open('pilot_probe_results.json', 'r', encoding='utf-8') as f:
    results = json.load(f)

# Kompakte Zusammenfassung erstellen
summary = {
    'experiment': 'LLM Navigation Pilot Probes',
    'total_probes': len(results),
    'probes': []
}

for task_id, data in sorted(results.items()):
    probe_summary = {
        'task_id': task_id,
        'model': data['model'],
        'task': data['task'],
        'stats': {
            'visited_paths': data['summary']['visited_paths_count'],
            'tool_calls': data['summary']['tool_calls_count'],
            'errors': data['summary']['error_count'],
            'conversation_turns': data['summary']['conversation_turns']
        },
        'success': data['success'],
        'visited_paths': data['visited_paths'][:10] + (['...'] if len(data['visited_paths']) > 10 else []),
        'key_files_read': [p for p in data['visited_paths'] if not p.startswith('Bash:') and not p.startswith('Glob:') and not p.startswith('Grep:')][:5],
        'final_output_preview': data['final_output'][:300] if data['final_output'] else 'N/A'
    }
    summary['probes'].append(probe_summary)

# Gesamtstatistik
summary['statistics'] = {
    'total_tool_calls': sum(p['stats']['tool_calls'] for p in summary['probes']),
    'total_paths_visited': sum(p['stats']['visited_paths'] for p in summary['probes']),
    'successful_probes': sum(1 for p in summary['probes'] if p['success']),
    'failed_probes': sum(1 for p in summary['probes'] if not p['success']),
    'inconclusive_probes': sum(1 for p in summary['probes'] if p['success'] is None),
    'haiku_probes': sum(1 for p in summary['probes'] if p['model'] == 'Haiku'),
    'sonnet_probes': sum(1 for p in summary['probes'] if p['model'] == 'Sonnet')
}

print(json.dumps(summary, indent=2, ensure_ascii=False))
