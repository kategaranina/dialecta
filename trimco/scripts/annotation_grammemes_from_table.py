import os
import json
from collections import defaultdict

import pandas as pd


table_path = '../data/auxiliary/dialecta_tags_20250323.xlsx'
tables = pd.read_excel(
    table_path,
    engine='openpyxl',
    sheet_name=[
        'compulsory',
        'compulsory_order',
        'facultative',
        'facultative_order'
    ]
)

compulsory = {}
for i, row in tables['compulsory'].iterrows():
    row = row.fillna('')
    if not row['auto_ann_tag']:
        continue

    compulsory[row['auto_ann_tag']] = {
        'pymorphy_tag': row['auto_ann_tag'],
        'surface_tag': str(row['tag']),
        'description': row['description'],
        'category': row['type'],
        'example': row['example'],
        'comment': row['comments']
    }

compulsory_order = defaultdict(dict)
for i, row in tables['compulsory_order'].iterrows():
    compulsory_order[row['part of speech']][row['restrictions'].lower()] = row['order'].split('-')

facultative_table = tables['facultative'].dropna(subset=['num in order (auto)']).sort_values('num in order (auto)')
facultative_table = facultative_table.fillna('')

facultative = {}
for i, row in facultative_table.iterrows():
    facultative[row['name']] = {
        'label': row['meaning'],
        'description': row['description'],
        'categories': row['in which categories shown'].split(', '),
        'examples': row['examples']
    }

annotation_info = {
    'grammemes': compulsory,
    'order': compulsory_order,
    'facultative': facultative
}

with open(os.path.join('..', 'data', 'static', 'annotation_grammemes.json'), 'w') as f:
    json.dump(annotation_info, f, indent=2, ensure_ascii=False)



