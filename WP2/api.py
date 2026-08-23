import os, json
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(BASE_DIR, 'schema.json')

def load_schema():
    if os.path.exists(SCHEMA_PATH):
        with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

SCHEMA_DATA = load_schema()

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/<path:path>')
def static_files(path):
    return app.send_static_file(path)

@app.route('/api/schema/<ds_id>', methods=['GET'])
def get_schema(ds_id):
    try:
        entry = SCHEMA_DATA.get(ds_id)
        if entry:
            return jsonify(entry)
        return jsonify({'error': 'not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/dqd/result', methods=['GET'])
def get_dqd_result():
    ds_id = request.args.get('ds_id', '').strip()
    if not ds_id:
        return jsonify({'ok': False, 'error': 'Missing ds_id'}), 400

    result_path = os.path.join(BASE_DIR, 'dqd/raw', f'{ds_id}.json')
    if not os.path.exists(result_path):
        return jsonify({'ok': False, 'error': 'DQD not run yet for this dataset'}), 404

    with open(result_path, 'r', encoding='utf-8') as f:
        dqd_data = json.load(f)

    return jsonify({'ok': True, 'result': dqd_data})


@app.route('/api/phidu/data/<ds_id>', methods=['GET'])
def get_phidu_data(ds_id):
    try:
        entry = SCHEMA_DATA.get(ds_id)
        if not entry or entry.get('source') != 'PHIDU':
            return jsonify({'error': 'not a PHIDU dataset'}), 404
        
        import pandas as pd
        url = entry['url']
        sheet = entry['sheet']
        filename = url.split('/')[-1]
        local_path = os.path.join(BASE_DIR, 'phidu_data', filename)
        
        if not os.path.exists(local_path):
            import urllib.request, ssl
            os.makedirs(os.path.join(BASE_DIR, 'phidu_data'), exist_ok=True)
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
                with open(local_path, 'wb') as f:
                    f.write(r.read())
        
        # Read header rows to build column names
        df_h = pd.read_excel(local_path, sheet_name=sheet, header=None, nrows=5)
        
        # Row 0: age group names (e.g. Males, 0-4 years)
        # Row 3: sub-column names (Number, Total males, %)
        # Build combined column names
        col_names = []
        current_group = ''
        for i, (h0, h3) in enumerate(zip(df_h.iloc[0], df_h.iloc[3])):
            if pd.notna(h0) and not str(h0).startswith('Unnamed') and not str(h0).startswith('Link') and not str(h0).startswith('BACK') and not str(h0).startswith('©'):
                current_group = str(h0).strip()
            sub = str(h3).strip() if pd.notna(h3) else ''
            if i == 0:
                col_names.append('Code')
            elif i == 1:
                col_names.append('Name')
            elif sub and sub not in ['nan', '']:
                col_names.append(f'{current_group} — {sub}' if current_group else sub)
            else:
                col_names.append(f'col_{i}')
        
        # Read actual data
        df = pd.read_excel(local_path, sheet_name=sheet, header=None, skiprows=5)
        df.columns = col_names[:len(df.columns)]
        
        # Remove empty rows and header-like rows
        df = df[df['Code'].notna() & (df['Code'] != '') & (df['Code'] != 'Code')]
        df = df.head(100)
        
        # Convert to list of dicts
        records = df.fillna('').astype(str).to_dict(orient='records')
        columns = col_names[:len(df.columns)]
        
        return jsonify({'columns': columns, 'rows': records})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=8765)
