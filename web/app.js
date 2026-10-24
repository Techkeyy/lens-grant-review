const $ = (selector) => document.querySelector(selector);
let state = { phase: 'empty' };

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

async function request(path, body) {
  const response = await fetch(path, body === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

function notice(message, error=false) {
  $('#notice').textContent = message;
  $('#notice').classList.toggle('error', error);
}

async function act(button, action, success) {
  button.disabled = true;
  notice('Working…');
  try { state = await action(); render(); notice(success); }
  catch (error) { notice(error.message, true); }
  finally { button.disabled = false; }
}

function sourceRow(ref) {
  const file = state.files?.[ref.file];
  return file?.find(entry => entry.line === ref.row)?.values;
}

function record(ref) {
  const row = sourceRow(ref);
  const location = ref.zetaris ? `${ref.zetaris.table} · ${ref.zetaris.key} · snapshot ${ref.zetaris.snapshot_sha256.slice(0,12)}` : `${ref.file} · row ${ref.row}`;
  return `<div class="evidence-entry"><strong>${escapeHtml(ref.id)}</strong><code>${escapeHtml(location)}</code><div>${row ? Object.entries(row).map(([key,value]) => `<b>${escapeHtml(key)}</b>: ${escapeHtml(value)}`).join(' · ') : 'Captured row unavailable'}</div></div>`;
}

function inspectRecords() {
  $('#record-list').innerHTML = Object.entries(state.files || {}).map(([filename, entries]) => `
    <div class="record-group"><h4>${escapeHtml(filename)} (${entries.length} rows)</h4>
    ${entries.map(entry => `<div class="record-row"><code>row ${entry.line}</code><div>${Object.entries(entry.values).map(([key,value])=>`<b>${escapeHtml(key)}</b>: ${escapeHtml(value)}`).join(' · ')}</div></div>`).join('')}</div>`).join('');
}

function renderMapping() {
  const unmapped = state.case.claims.filter(claim => claim.kind === 'allocation' && !claim.source_id);
  const activities = state.case.claims.filter(claim => claim.kind === 'activity_count');
  $('#mapping').innerHTML = `<div class="mapping-head"><h3>Confirm evidence links</h3><p class="muted">Only confirmed source IDs are used for allocation arithmetic. Activity records count only when linked to the claim.</p></div>` +
    unmapped.map(claim => {
      const sources = state.case.sources.filter(source => source.kind === claim.reported_kind);
      return `<form class="mapping-form source-map" data-claim="${escapeHtml(claim.id)}"><label>${escapeHtml(claim.grant)} · ${escapeHtml(claim.id)} (${escapeHtml(claim.quantity)} ${escapeHtml(claim.unit)})</label><div class="row"><select name="source_id" required><option value="">Choose confirmed source</option>${sources.map(source=>`<option value="${escapeHtml(source.id)}">${escapeHtml(source.id)} · ${escapeHtml(source.person || source.vendor)} · ${escapeHtml(source.quantity)} ${escapeHtml(source.unit)}</option>`).join('')}</select><button class="secondary" type="submit">Confirm source</button></div></form>`;
    }).join('') +
    activities.map(claim => {
      const sources = state.case.sources.filter(source => source.kind === 'activity');
      return `<form class="mapping-form activity-map" data-claim="${escapeHtml(claim.id)}"><label>${escapeHtml(claim.grant)} · ${escapeHtml(claim.id)}: ${escapeHtml(claim.quantity)} sessions reported</label><p class="fine">Current links: ${escapeHtml(claim.evidence_ids.length)} · ${escapeHtml(claim.evidence_link_method)}</p><div class="activity-choices">${sources.map(source=>`<label><input type="checkbox" name="evidence" value="${escapeHtml(source.id)}" ${claim.evidence_ids.includes(source.id)?'checked':''}> ${escapeHtml(source.id)} · ${escapeHtml(source.date)}</label>`).join('')}</div><button class="secondary" type="submit">Save activity links</button></form>`;
    }).join('');
}

function title(finding) {
  return ({OVERALLOCATED_SOURCE:'Shared source exceeds recorded total',
    ALLOCATION_WITHIN_SOURCE:'Allocation fits the supplied source',
    ACTIVITY_SUPPORT_GAP:'Activity claim needs more support',
    ACTIVITY_LINKS_UNVERIFIED:'Some activity links need review',
    TIMESHEET_PROJECT_DIFFERS:'Timesheet names another program',
    ALLOCATION_TOTAL_WITH_PROJECT_QUESTION:'Allocation total fits, project basis needs review',
    SOURCE_IDENTITY_UNCERTAIN:'Source identity needs confirmation',
    SOURCE_MISMATCH:'Claim and source differ', SOURCE_OUTSIDE_PERIOD:'Source is outside the period',
    STAFF_IDENTITY_UNVERIFIED:'Staff identity needs review', EXPENSE_IDENTITY_UNVERIFIED:'Vendor identity needs review'})[finding.code] || finding.code;
}

function arithmetic(finding) {
  const a = finding.arithmetic;
  if (!a) return 'No conclusive arithmetic until the source identity is confirmed.';
  if (a.allocated_total !== undefined) return `Claims total ${escapeHtml(a.allocated_total)} ${escapeHtml(a.unit)}; the linked source records ${escapeHtml(a.source_total)} ${escapeHtml(a.unit)}.`;
  if (a.reported !== undefined) return `Report states ${escapeHtml(a.reported)} sessions; ${escapeHtml(a.linked_distinct_records)} distinct supplied activity rows are linked; ${escapeHtml(a.gap)} sessions lack supplied evidence.`;
  return Object.entries(a).map(([key,value]) => `${escapeHtml(key)}: ${escapeHtml(Array.isArray(value)?value.join(', '):value)}`).join(' · ');
}

function findingHtml(finding) {
  const currentClaims = finding.claims.map(ref => {
    const claim = state.case.claims.find(item => item.id === ref.id);
    return claim ? `<div class="evidence-entry"><strong>Current ${escapeHtml(claim.grant)} claim</strong>${escapeHtml(claim.id)}: ${escapeHtml(claim.quantity)} ${escapeHtml(claim.unit)}${claim.kind === 'activity_count' ? ` · linked using ${escapeHtml(claim.evidence_link_method || 'explicit evidence IDs')}` : ''}</div>` : '';
  }).join('');
  const claimOptions = finding.claims.map(ref => {
    const claim = state.case.claims.find(item => item.id === ref.id);
    return claim?.kind === 'allocation' ? `<option value="${escapeHtml(claim.id)}">${escapeHtml(claim.grant)} · ${escapeHtml(claim.id)} · ${escapeHtml(claim.quantity)} ${escapeHtml(claim.unit)}</option>` : '';
  }).join('');
  const note = finding.human_explanation;
  return `<article class="finding ${escapeHtml(finding.status)}">
    <div class="finding-head"><h3>${escapeHtml(title(finding))}</h3><span class="badge">${escapeHtml(finding.status.replaceAll('_',' '))}</span></div>
    <p>${escapeHtml(finding.message)}</p><div class="math">${arithmetic(finding)}</div>
    <div class="evidence"><div><h4>Report claims</h4>${currentClaims}${finding.claims.map(record).join('')}</div><div><h4>Captured source rows</h4>${finding.sources.length ? finding.sources.map(record).join('') : '<p class="muted">No confirmed source row. Choose a source before treating this claim as verified.</p>'}</div></div>
    ${finding.claims.some(ref => ['linked source','user-confirmed source link'].includes(state.case.claims.find(c=>c.id===ref.id)?.identity_origin)) ? '<p class="fine">At least one draft omitted person or vendor. Identity shown in analysis came from the linked source ID; the report did not independently state it.</p>' : ''}
    ${note ? `<p class="human-note"><strong>Human explanation</strong> · ${escapeHtml(note.text)}<br><small>Saved against source revision ${escapeHtml(note.source_revision)}. The finding still requires human judgment.</small></p>` : ''}
    <div class="review-actions">
      ${claimOptions ? `<form class="correct-form" data-key="${escapeHtml(finding.key)}"><label>Correct a report allocation</label><div class="row"><select name="claim_id" aria-label="Claim to correct">${claimOptions}</select><input name="quantity" type="number" min="0" step="any" placeholder="New amount" required aria-label="New quantity"><button type="submit" class="secondary">Save correction</button></div></form>` : ''}
      ${finding.status !== 'clear' ? `<form class="explain-form" data-key="${escapeHtml(finding.key)}"><label>Record an explanation for your team</label><textarea name="explanation" maxlength="2000" required placeholder="What should a reviewer know?"></textarea><button type="submit" class="secondary">Save explanation</button></form>` : ''}
    </div>
  </article>`;
}

function requestIdCount(requestIds) {
  return Object.values(requestIds || {}).reduce((total, value) => total + (Array.isArray(value) ? value.length : 1), 0);
}

function renderAdaptiveInvestigation() {
  const panel = $('#adaptive-investigation');
  const probe = state.investigation;
  if (!state.result || !probe) {
    panel.classList.add('hidden');
    panel.innerHTML = '';
    return;
  }
  const label = {
    confirmed_against_snapshot: 'Live reread matched the imported snapshot',
    snapshot_only: 'Checked uploaded rows only',
    stale: 'Source changed since import',
    unavailable: 'Live follow-up unavailable'
  }[probe.status] || 'Follow-up status unknown';
  const locations = (probe.refs || []).map(ref => ref.zetaris
    ? `${ref.id} · ${ref.zetaris.table} / ${ref.zetaris.key}`
    : `${ref.id} · ${ref.file} row ${ref.row}`);
  panel.innerHTML = `<p class="eyebrow">SELECTED FOLLOW-UP · ${escapeHtml(probe.code)}</p>
    <h3>${escapeHtml(label)}</h3>
    <p><strong>Why this probe:</strong> ${escapeHtml(probe.reason)}</p>
    <p>${escapeHtml(probe.observation)}</p>
    <p><strong>Ask the reviewer:</strong> ${escapeHtml(probe.question)}</p>
    <p class="fine">Selected ${escapeHtml((probe.tables?.length ? probe.tables : probe.files || []).join(', '))} · ${escapeHtml((probe.request_ids || []).length)} follow-up request IDs.</p>
    <p class="fine">Referenced rows: ${escapeHtml(locations.join('; '))}</p>`;
  panel.classList.remove('hidden');
}

function renderZetarisEvidence() {
  const panel = $('#zetaris-evidence');
  const z = state.zetaris;
  if (!z) {
    panel.classList.add('hidden');
    panel.innerHTML = '';
    return;
  }
  const rows = Object.values(z.manifest || {}).map(entry => `
    <li><span class="zetaris-table">${escapeHtml(entry.table)}</span><span class="zetaris-meta">${escapeHtml(entry.row_count)} rows · sha ${escapeHtml(String(entry.snapshot_sha256 || '').slice(0, 12))}</span></li>`).join('');
  panel.innerHTML = `
    <p class="eyebrow">ZETARIS EVIDENCE SNAPSHOT</p>
    <ul class="zetaris-manifest">${rows}</ul>
    <p class="zetaris-requests">${escapeHtml(requestIdCount(z.request_ids))} request IDs captured for this review.</p>
    <p class="fine">${escapeHtml(z.caveat)}</p>`;
  panel.classList.remove('hidden');
}

function renderInvestigationTrace() {
  const panel = $('#investigation-trace');
  const steps = state.trace || [];
  panel.classList.toggle('hidden', !steps.length);
  const labels = {zetaris_query:'Zetaris query', local_import:'Local import', meterless_ingest:'Meterless ingest', source_link:'Source link', reconciliation:'Rule check', adaptive_probe:'Selected follow-up', finding_recorded:'Meterless finding'};
  $('#trace-list').innerHTML = steps.map(step => {
    const refs = (step.refs || []).map(ref => {
      const location = ref.zetaris
        ? `${ref.zetaris.table} / ${ref.zetaris.key} / snapshot ${ref.zetaris.snapshot_sha256}`
        : `${ref.file} / row ${ref.row}`;
      return `<li><strong>${escapeHtml(ref.id)}</strong> · <code>${escapeHtml(location)}</code></li>`;
    }).join('');
    const context = step.stage === 'zetaris_query'
      ? `${step.table} · ${step.row_count} rows · sha ${step.snapshot_sha256} · request IDs: ${(step.request_ids || []).join(', ')}`
      : step.stage === 'source_link'
        ? `${step.claim_id}: ${step.basis}; linked IDs: ${(step.source_ids || []).join(', ') || 'none'}; unconfirmed candidates: ${(step.candidate_ids || []).join(', ') || 'none'}`
        : step.stage === 'reconciliation'
          ? `${step.finding_count} findings: ${(step.finding_codes || []).join(', ')}`
          : step.stage === 'finding_recorded'
            ? `${step.code} · ${step.status} · arithmetic ${JSON.stringify(step.arithmetic)} · Meterless ID ${step.meterless_id}`
            : step.stage === 'adaptive_probe'
              ? `${step.code} · ${step.status} · ${step.reason} · ${step.observation} · tables: ${(step.tables || []).join(', ') || 'none'} · request IDs: ${(step.request_ids || []).join(', ') || 'none'}`
            : step.stage === 'meterless_ingest'
              ? `${step.source_count} source rows; ${step.claim_count} report claims`
              : `${Object.entries(step.files || {}).map(([name,count]) => `${name}: ${count} rows`).join('; ')}`;
    return `<li><strong>${escapeHtml(labels[step.stage] || step.stage)}</strong><p>${escapeHtml(step.summary)}</p><p class="fine">${escapeHtml(context)}</p>${refs ? `<ul class="trace-refs">${refs}</ul>` : ''}</li>`;
  }).join('');
}

function render() {
  const loaded = !!state.case;
  $('#workspace').classList.toggle('hidden', !loaded);
  $('#saved').textContent = state.saved_at ? `Saved ${new Date(state.saved_at).toLocaleString()}` : '';
  if (!loaded) return;
  $('#data-label').textContent = state.case.label;
  $('#import-summary').textContent = `${state.case.claims.length} report claims and ${state.case.sources.length} source records from ${Object.keys(state.files).length} ${state.zetaris ? 'Zetaris table snapshots' : 'CSV files'}. Period: ${state.case.reporting_period.start} to ${state.case.reporting_period.end}.`;
  renderZetarisEvidence();
  renderInvestigationTrace();
  inspectRecords();
  renderMapping();
  $('#results').classList.toggle('hidden', !state.result);
  renderAdaptiveInvestigation();
  $('#check').textContent = state.result ? 'Rerun check' : 'Check both reports';
  $('#check-state').textContent = state.result ? `Checked revision ${state.revision}. Review remains saved after refresh.` : state.corrections?.length ? 'Correction saved. Rerun to see the updated result.' : 'Ready to check the imported records.';
  if (state.result) $('#finding-list').innerHTML = state.result.findings.map(findingHtml).join('');
  const m = state.meterless || {status:'unknown'};
  $('#integration-status').textContent = `Review history: Meterless ${m.status}${m.event_count === undefined ? '' : ` · ${m.event_count} events`}. Analysis: local deterministic reconciliation. Zetaris grant-data query: ${state.zetaris ? 'five tables captured for this review; snapshot hashes and request IDs saved. Tables were not transactionally frozen.' : 'not connected to this review.'}`;
}

$('#sample').addEventListener('click', event => act(event.currentTarget, () => request('/api/sample', {}), 'Synthetic case loaded. Inspect its rows, then run a check.'));
$('#import-zetaris').addEventListener('click', event => act(event.currentTarget, () => request('/api/import-zetaris', {period: {start: $('#period-start').value, end: $('#period-end').value}}), 'Complete Zetaris query snapshot imported. Inspect source IDs and confirm activity links before checking.'));
$('#import-form').addEventListener('submit', async event => {
  event.preventDefault();
  const files = {};
  for (const input of document.querySelectorAll('[data-file]')) {
    if (!input.files[0]) return notice(`Choose ${input.dataset.file}`, true);
    files[input.dataset.file] = await input.files[0].text();
  }
  const period = {start: $('#period-start').value, end: $('#period-end').value};
  act(event.submitter, () => request('/api/import', {files, period}), 'Five CSVs imported. Inspect rows, then run a check.');
});
$('#check').addEventListener('click', event => act(event.currentTarget, () => request('/api/check', {}), 'Check complete. Open each finding to inspect the original rows and arithmetic.'));
$('#mapping').addEventListener('submit', event => {
  const form = event.target;
  if (form.matches('.source-map')) {
    event.preventDefault();
    act(event.submitter, () => request('/api/link-source', {claim_id: form.dataset.claim, source_id: form.elements.source_id.value}), 'Source linked. Rerun the check.');
  } else if (form.matches('.activity-map')) {
    event.preventDefault();
    const evidence_ids = [...form.querySelectorAll('input[name=evidence]:checked')].map(input => input.value);
    act(event.submitter, () => request('/api/link-activities', {claim_id: form.dataset.claim, evidence_ids}), 'Activity links saved. Rerun the check.');
  }
});
$('#finding-list').addEventListener('submit', event => {
  const form = event.target;
  if (form.matches('.correct-form')) {
    event.preventDefault();
    act(event.submitter, () => request('/api/correct', {claim_id: form.elements.claim_id.value, quantity: form.elements.quantity.value}), 'Correction saved. Rerun the check to see its effect.');
  } else if (form.matches('.explain-form')) {
    event.preventDefault();
    act(event.submitter, () => request('/api/explain', {key: form.dataset.key, explanation: form.elements.explanation.value}), 'Explanation saved with the current source revision.');
  }
});
request('/api/state').then(data => {state=data;render();}).catch(error=>notice(`Could not load the local review: ${error.message}`,true));
