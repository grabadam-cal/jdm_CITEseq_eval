"""jdm-fig7 — export every sheet of an .xlsx to CSV (Python stdlib only; values as stored).
Usage: python3 -I env/xlsx_to_csv.py JCI_data/<workbook>.xlsx  -> JCI_data/<stem>_<Sheet>.csv"""
import sys, os, re, csv, zipfile, xml.etree.ElementTree as ET
p = sys.argv[1]; out = os.path.dirname(p); stem = os.path.splitext(os.path.basename(p))[0]
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
z = zipfile.ZipFile(p)
ss = []
if 'xl/sharedStrings.xml' in z.namelist():
    for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si', NS):
        ss.append(''.join(t.text or '' for t in si.iter('{%s}t' % NS['m'])))
rels = {r.get('Id'): r.get('Target') for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
wb = ET.fromstring(z.read('xl/workbook.xml'))
def col(ref):
    n = 0
    for ch in re.match(r'[A-Z]+', ref).group():
        n = n * 26 + ord(ch) - 64
    return n - 1
for sh in wb.find('m:sheets', NS):
    name = sh.get('name'); tgt = rels[sh.get('{%s}id' % NS['r'])]
    path = tgt.lstrip('/') if tgt.startswith('/') else 'xl/' + tgt
    root = ET.fromstring(z.read(path))
    rows = {}
    for row in root.iter('{%s}row' % NS['m']):
        r = int(row.get('r')) - 1; cells = {}
        for c in row.findall('m:c', NS):
            t = c.get('t'); v = c.find('m:v', NS)
            if t == 's' and v is not None: val = ss[int(v.text)]
            elif t == 'inlineStr': val = ''.join(x.text or '' for x in c.iter('{%s}t' % NS['m']))
            elif t == 'b' and v is not None: val = 'TRUE' if v.text == '1' else 'FALSE'
            else: val = v.text if v is not None else ''
            if val != '': cells[col(c.get('r'))] = val
        if cells: rows[r] = cells
    nr = max(rows) + 1 if rows else 0
    nc = max((max(c) for c in rows.values()), default=-1) + 1
    safe = re.sub(r'[^A-Za-z0-9._-]+', '_', name).strip('_')
    f = os.path.join(out, f'{stem}_{safe}.csv')
    with open(f, 'w', newline='') as fh:
        w = csv.writer(fh)
        for i in range(nr):
            w.writerow([rows.get(i, {}).get(j, '') for j in range(nc)])
    print(repr(name), f'{nr}x{nc}', '->', os.path.basename(f))
