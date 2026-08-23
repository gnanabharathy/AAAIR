// ── Filter state ──
const state = {
  subtypes: new Set(),
  tasks: new Set()
};

// ── Accordion ──
document.querySelectorAll('.category-header').forEach(header => {
  header.addEventListener('click', () => {
    const item = header.parentElement;
    const arrow = header.querySelector('.category-arrow');
    const sublist = item.querySelector('.subcategory-list');

    const isOpen = sublist.classList.contains('open');
    sublist.classList.toggle('open', !isOpen);
    arrow.classList.toggle('open', !isOpen);
  });
});

// ── Subtype checkboxes ──
document.querySelectorAll('.sub-item').forEach(item => {
  item.addEventListener('click', () => {
    const value = item.dataset.value;
    const cb = item.querySelector('.sub-cb');
    const isChecked = cb.classList.contains('checked');

    if (isChecked) {
      cb.classList.remove('checked');
      state.subtypes.delete(value);
    } else {
      cb.classList.add('checked');
      state.subtypes.add(value);
    }
    updateSummary();
  });
});

// ── Task checkboxes ──
document.querySelectorAll('.task-item').forEach(item => {
  item.addEventListener('click', () => {
    const value = item.dataset.value;
    const isChecked = item.classList.contains('checked');

    if (isChecked) {
      item.classList.remove('checked');
      state.tasks.delete(value);
    } else {
      item.classList.add('checked');
      state.tasks.add(value);
    }
    updateSummary();
  });
});

// ── Summary text ──
function updateSummary() {
  const summary = document.getElementById('filter-summary');
  const s = state.subtypes.size;
  const t = state.tasks.size;
  if (s === 0 && t === 0) {
    summary.textContent = 'No filters selected';
  } else {
    const parts = [];
    if (s > 0) parts.push(`${s} data type${s > 1 ? 's' : ''}`);
    if (t > 0) parts.push(`${t} task${t > 1 ? 's' : ''}`);
    summary.textContent = parts.join(' · ') + ' selected';
  }
}

// ── Apply button ──
document.getElementById('apply-btn').addEventListener('click', () => {
  const results = filterDatasets();
  renderCards(results);
  document.getElementById('results-section').style.display = 'block';
  document.getElementById('results-count').textContent = `Showing ${results.length} dataset${results.length !== 1 ? 's' : ''}`;
});

// // ── Mock datasets ──
// const DATASETS = [
//   {
//     id: 'nhanes-demo-2015',
//     name: 'NHANES Demographics 2015–16',
//     desc: 'Age, gender, race, income and socioeconomic variables from US national survey.',
//     subtypes: ['demographics'],
//     tasks: ['classification', 'regression'],
//     source: 'NHANES',
//     rows: '10,000',
//     docUrl: 'https://wwwn.cdc.gov/Nchs/Nhanes/2015-2016/DEMO_I.htm'
//   },
//   {
//     id: 'nhanes-dietary-2015',
//     name: 'NHANES Dietary Interview 2015–16',
//     desc: 'Individual food intake, nutrient values and dietary recall interviews.',
//     subtypes: ['dietary'],
//     tasks: ['regression', 'clustering'],
//     source: 'NHANES',
//     rows: '8,700',
//     docUrl: 'https://wwwn.cdc.gov/Nchs/Nhanes/2015-2016/DR1TOT_I.htm'
//   },
//   {
//     id: 'nhanes-lab-2015',
//     name: 'NHANES Laboratory 2015–16',
//     desc: 'Blood and urine biochemistry, metabolic markers, glucose, lipids, HbA1c.',
//     subtypes: ['laboratory'],
//     tasks: ['regression', 'classification'],
//     source: 'NHANES',
//     rows: '8,300',
//     docUrl: 'https://wwwn.cdc.gov/Nchs/Nhanes/2015-2016/TCHOL_I.htm'
//   },
//   {
//     id: 'nhanes-exam-2015',
//     name: 'NHANES Examination 2015–16',
//     desc: 'Anthropometrics, vital signs, blood pressure, BMI and physical exam results.',
//     subtypes: ['examination'],
//     tasks: ['classification', 'regression'],
//     source: 'NHANES',
//     rows: '9,500',
//     docUrl: 'https://wwwn.cdc.gov/Nchs/Nhanes/2015-2016/BMX_I.htm'
//   },
//   {
//     id: 'nhanes-quest-2015',
//     name: 'NHANES Questionnaire 2015–16',
//     desc: 'Health history, lifestyle factors, smoking, alcohol and physical activity.',
//     subtypes: ['questionnaire'],
//     tasks: ['classification', 'clustering'],
//     source: 'NHANES',
//     rows: '9,971',
//     docUrl: 'https://wwwn.cdc.gov/Nchs/Nhanes/2015-2016/ALQ_I.htm'
//   },
//   {
//     id: 'mimic-ehr',
//     name: 'MIMIC-IV Clinical Records',
//     desc: 'ICU patient records including diagnoses, procedures, medications and lab results.',
//     subtypes: ['ehr'],
//     tasks: ['classification', 'prediction', 'survival'],
//     source: 'MIMIC-IV',
//     rows: '500,000+',
//     docUrl: 'https://mimic.mit.edu'
//   },
//   {
//     id: 'nih-chest-xray',
//     name: 'NIH Chest X-ray Dataset',
//     desc: '100,000+ frontal chest X-ray images with 14 disease labels.',
//     subtypes: ['chest-xray'],
//     tasks: ['classification', 'detection'],
//     source: 'NIH',
//     rows: '112,120',
//     docUrl: 'https://nihcc.app.box.com/v/ChestXray-NIHCC'
//   },
//   {
//     id: 'lidc-ct',
//     name: 'LIDC-IDRI Lung CT',
//     desc: 'Lung CT scans with radiologist annotations for nodule detection.',
//     subtypes: ['ct-scan'],
//     tasks: ['detection', 'segmentation'],
//     source: 'LIDC',
//     rows: '1,018 scans',
//     docUrl: 'https://wiki.cancerimagingarchive.net/display/Public/LIDC-IDRI'
//   },
//   {
//     id: 'brats-mri',
//     name: 'BraTS Brain MRI',
//     desc: 'Multi-modal brain tumor MRI scans with segmentation annotations.',
//     subtypes: ['mri'],
//     tasks: ['segmentation', 'classification'],
//     source: 'BraTS',
//     rows: '2,040 scans',
//     docUrl: 'https://www.med.upenn.edu/cbica/brats'
//   },
//   {
//     id: 'mimic-notes',
//     name: 'MIMIC-III Clinical Notes',
//     desc: 'De-identified clinical notes including discharge summaries and radiology reports.',
//     subtypes: ['clinical-notes'],
//     tasks: ['nlp', 'classification'],
//     source: 'MIMIC-III',
//     rows: '2M+ notes',
//     docUrl: 'https://mimic.mit.edu'
//   },
//   {
//     id: 'ptb-ecg',
//     name: 'PTB-XL ECG Database',
//     desc: '100,000+ 12-lead ECG recordings with diagnostic labels.',
//     subtypes: ['ecg'],
//     tasks: ['classification', 'detection'],
//     source: 'PTB-XL',
//     rows: '21,837',
//     docUrl: 'https://physionet.org/content/ptb-xl'
//   },
//   {
//     id: 'mimic-waveforms',
//     name: 'MIMIC-III ICU Waveforms',
//     desc: 'Multi-modal ICU physiological waveforms including ECG, arterial pressure and SpO2.',
//     subtypes: ['icu-waveforms'],
//     tasks: ['prediction', 'classification'],
//     source: 'MIMIC-III',
//     rows: '30,000+',
//     docUrl: 'https://physionet.org/content/mimic3wdb'
//   },
// ];

// const SUBTYPE_TAG = {
//   demographics:   { label: 'Demographics',   cls: 'tag-blue' },
//   dietary:        { label: 'Dietary',         cls: 'tag-amber' },
//   laboratory:     { label: 'Laboratory',      cls: 'tag-blue' },
//   examination:    { label: 'Examination',     cls: 'tag-blue' },
//   questionnaire:  { label: 'Questionnaire',   cls: 'tag-blue' },
//   ehr:            { label: 'EHR',             cls: 'tag-blue' },
//   genomics:       { label: 'Genomics',        cls: 'tag-purple' },
//   'chest-xray':   { label: 'Chest X-ray',     cls: 'tag-teal' },
//   'ct-scan':      { label: 'CT Scan',         cls: 'tag-teal' },
//   mri:            { label: 'MRI',             cls: 'tag-teal' },
//   pathology:      { label: 'Pathology',       cls: 'tag-teal' },
//   'skin-imaging': { label: 'Skin Imaging',    cls: 'tag-teal' },
//   'cardiac-imaging':{ label: 'Cardiac',       cls: 'tag-teal' },
//   'clinical-notes':{ label: 'Clinical Notes', cls: 'tag-purple' },
//   'radiology-reports':{ label: 'Radiology',   cls: 'tag-purple' },
//   'dietary-interview':{ label: 'Dietary Text',cls: 'tag-amber' },
//   ecg:            { label: 'ECG',             cls: 'tag-coral' },
//   eeg:            { label: 'EEG',             cls: 'tag-coral' },
//   'icu-waveforms':{ label: 'ICU Waveforms',   cls: 'tag-coral' },
//   vitals:         { label: 'Vitals',          cls: 'tag-coral' },
// };

// const TASK_TAG = {
//   classification: { label: 'Classification', cls: 'tag-teal' },
//   regression:     { label: 'Regression',     cls: 'tag-teal' },
//   clustering:     { label: 'Clustering',     cls: 'tag-teal' },
//   nlp:            { label: 'NLP',            cls: 'tag-teal' },
//   detection:      { label: 'Detection',      cls: 'tag-teal' },
//   segmentation:   { label: 'Segmentation',   cls: 'tag-teal' },
//   survival:       { label: 'Survival',       cls: 'tag-teal' },
//   prediction:     { label: 'Prediction',     cls: 'tag-teal' },
//   'multimodal-fusion': { label: 'Multi-modal', cls: 'tag-teal' },
// };

function filterDatasets() {
  return DATASETS.filter(ds => {
    const typeMatch = state.subtypes.size === 0 ||
      ds.subtypes.some(s => state.subtypes.has(s));
    const taskMatch = state.tasks.size === 0 ||
      ds.tasks.some(t => state.tasks.has(t));
    return typeMatch && taskMatch;
  });
}

function renderCards(datasets) {
  const grid = document.getElementById('card-grid');

  if (!datasets.length) {
    grid.innerHTML = '<div class="empty">No datasets match your filters</div>';
    return;
  }

  grid.innerHTML = datasets.map(ds => {
    const subtypeTags = ds.subtypes.map(s => {
      const t = SUBTYPE_TAG[s] || { label: s, cls: 'tag-blue' };
      return `<span class="ds-tag ${t.cls}">${t.label}</span>`;
    }).join('');

    const taskTags = ds.tasks.map(t => {
      const tag = TASK_TAG[t] || { label: t, cls: 'tag-teal' };
      return `<span class="ds-tag ${tag.cls}">${tag.label}</span>`;
    }).join('');

    return `
      <div class="ds-card" data-id="${ds.id}">
        <div class="ds-card-name">${ds.name}</div>
        <div class="ds-desc">${ds.desc}</div>
        <div class="ds-tags">${subtypeTags}${taskTags}</div>
        <div class="ds-footer" style="flex-direction:column;gap:4px">
          <div style="display:flex;justify-content:space-between;align-items:center;width:100%">
            <div class="ds-meta">Source: ${ds.source}</div>
            <div class="ds-arrow">View schema →</div>
          </div>
          <div class="ds-meta" style="text-align:left;width:100%">Last Updated: ${ds.last_updated || 'not available'}</div>
        </div>
      </div>
    `;
  }).join('');

  grid.querySelectorAll('.ds-card').forEach(card => {
    card.addEventListener('click', () => {
      const ds = datasets.find(d => d.id === card.dataset.id);
      openDrawer(ds);
    });
  });
}

// ── Drawer ──
function openDrawer(ds) {
  const params = new URLSearchParams({ id: ds.id });
  window.location.href = `schema.html?${params.toString()}`;
}

function closeDrawer() {
  document.getElementById('drawer').classList.remove('open');
  document.getElementById('drawer-overlay').classList.remove('open');
}

document.getElementById('drawer-close').addEventListener('click', closeDrawer);
document.getElementById('drawer-overlay').addEventListener('click', closeDrawer);


async function fetchSchema(ds) {
  try {
    const res = await fetch(PROXY + encodeURIComponent(ds.docUrl));
    const html = await res.text();
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');

    const rows = doc.querySelectorAll('table tr');
    const schema = [];

    rows.forEach(row => {
      const tds = row.querySelectorAll('td');
      if (tds.length < 2) return;
      const name = tds[0].textContent.trim();
      const label = tds[1].textContent.trim();
      if (!name || name === 'Variable Name') return;
      schema.push({ name, label });
    });

    if (schema.length > 0) {
      renderSchema(schema, ds.docUrl);
    } else {
      document.getElementById('drawer-body').innerHTML =
        `<div class="empty">Schema not available.<br><a href="${ds.docUrl}" target="_blank" style="color:#0C447C">View documentation ↗</a></div>`;
    }
  } catch (e) {
    document.getElementById('drawer-body').innerHTML =
      `<div class="empty">Could not load schema.<br><a href="${ds.docUrl}" target="_blank" style="color:#0C447C">View documentation ↗</a></div>`;
  }
}

function renderSchema(schema, docUrl) {
  document.getElementById('drawer-body').innerHTML = `
    <div style="margin-bottom:12px">
      <a href="${docUrl}" target="_blank" style="font-size:12px;color:#0C447C;text-decoration:none">
        View full documentation ↗
      </a>
    </div>
    <table class="sch-tbl">
      <colgroup>
        <col style="width:30%">
        <col style="width:70%">
      </colgroup>
      <thead>
        <tr><th>Variable</th><th>Label / Description</th></tr>
      </thead>
      <tbody>
        ${schema.map(v => `
          <tr>
            <td style="font-family:ui-monospace,monospace;font-size:11px">${v.name}</td>
            <td style="color:var(--text2);font-size:12px">${v.label}</td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}