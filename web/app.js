const $ = (selector) => document.querySelector(selector);
let state = { phase: 'empty' };
let publicMode = false;
let authClient = null;
let authUserId = null;
let selectedReviewId = null;
let reviews = [];
let viewEpoch = 0;
let authEpoch = 0;
let activeView = 'welcome';
const arrowIcon = '<svg class="icon" aria-hidden="true"><use href="#icon-arrow"></use></svg>';

function derivedView(next) {
  if (!next?.case) return 'home';
  if (next.result) return 'findings';
  return next.checks?.length ? 'rerun' : 'prepare';
}

function showView(view, focus=false) {
  const loaded = !!state.case;
  if (view === 'findings' && !state.result) view = derivedView(state);
  if (view === 'export' && !state.result) view = derivedView(state);
  if (view === 'rerun' && state.result) view = 'findings';
  if (!loaded && !['welcome','home'].includes(view)) view = 'home';
  activeView = view;
  document.body.dataset.view = view;
  $('#welcome').classList.toggle('hidden', view !== 'welcome');
  $('#how-it-works').classList.toggle('hidden', view !== 'welcome');
  $('#start-stage').classList.toggle('hidden', view !== 'home');
  $('#workspace').classList.toggle('hidden', !loaded || !['prepare','rerun','findings','export'].includes(view));
  for (const [name,id] of [['prepare','#prepare-stage'],['rerun','#rerun-stage'],['findings','#results'],['export','#export-stage']]) {
    $(id).classList.toggle('hidden', view !== name);
  }
  for (const button of document.querySelectorAll('[data-flow]')) {
    const destination = button.dataset.flow;
    button.disabled = destination === 'findings' && !state.result || destination === 'export' && !state.result;
    button.setAttribute('aria-current', destination === view || view === 'rerun' && destination === 'prepare' ? 'step' : 'false');
  }
  if (focus) {
    const target = ({home:'#start-title',prepare:'#prepare-title',rerun:'#rerun-title',findings:'#results-title',export:'#export-title',welcome:'#page-title'})[view];
    const node = $(target);
    node?.focus({preventScroll:true});
    node?.scrollIntoView({block:'start',behavior:'auto'});
  }
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

async function request(path, body) {
  const headers = {};
  if (publicMode) {
    const {data, error} = await authClient.auth.getSession();
    if (error || !data.session?.access_token) throw new Error('Your session ended. Sign in again to continue.');
    headers.Authorization = `Bearer ${data.session.access_token}`;
  }
  const options = {headers};
  if (body !== undefined) {
    if (publicMode && path !== '/api/reviews') {
      if (!selectedReviewId) throw new Error('Choose or create a saved review first.');
      body = {...body, review_id: selectedReviewId};
    }
    options.method = 'POST';
    headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

function notice(message, error=false) {
  $('#notice').textContent = message;
  $('#notice').classList.toggle('error', error);
}

async function act(button, action, success) {
  const label = button.innerHTML;
  const epoch = viewEpoch;
  const explanationKey = button.closest('.explain-form')?.dataset.key;
  button.disabled = true;
  button.textContent = 'Working...';
  notice('Working on this review. Your current records are still here.');
  try {
    const next = await action();
    if (epoch !== viewEpoch) return;
    state = next;
    activeView = derivedView(next);
    if (button.id === 'check' || button.id === 'rerun-check') $('#finding-list').replaceChildren();
    render();
    notice(success);
    if (publicMode) {
      try { await refreshReviewList(); }
      catch (error) { notice(`Review saved, but the saved list could not refresh: ${error.message}`, true); }
    }
    if (explanationKey) {
      showView('findings');
      const finding = [...document.querySelectorAll('.finding')].find(item => item.dataset.key === explanationKey);
      const note = finding?.querySelector('.human-note');
      note?.focus({preventScroll:true});
      note?.scrollIntoView({block:'center',behavior:'auto'});
    } else if (activeView === 'rerun') showView('rerun', true);
    else if (activeView === 'prepare') showView('prepare', true);
    else if (activeView === 'findings' && state.result) showView('findings', true);
  }
  catch (error) { if (epoch === viewEpoch) notice(error.message, true); }
  finally {
    button.disabled = false;
    if (button.isConnected) button.innerHTML = button.id === 'check'
      ? (state.result ? 'Run check again' + arrowIcon : 'Check both reports' + arrowIcon)
      : label;
  }
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
  const sourceForms = unmapped.map(claim => {
      const sources = state.case.sources.filter(source => source.kind === claim.reported_kind);
      return `<form class="mapping-form source-map" data-claim="${escapeHtml(claim.id)}"><label>${escapeHtml(claim.grant)}: ${escapeHtml(claim.quantity)} ${escapeHtml(claim.unit)} has no confirmed source</label><div class="row"><select name="source_id" required><option value="">Choose a source row</option>${sources.map(source=>`<option value="${escapeHtml(source.id)}">${escapeHtml(source.id)} · ${escapeHtml(source.person || source.vendor)} · ${escapeHtml(source.quantity)} ${escapeHtml(source.unit)}</option>`).join('')}</select><button class="secondary" type="submit">Confirm source</button></div><p class="fine">Lens will not guess a match from a person's name.</p></form>`;
    }).join('');
  const activityForms = activities.map(claim => {
      const sources = state.case.sources.filter(source => source.kind === 'activity');
      return `<form class="mapping-form activity-map" data-claim="${escapeHtml(claim.id)}"><label>${escapeHtml(claim.grant)} · ${escapeHtml(claim.id)}: ${escapeHtml(claim.quantity)} sessions reported</label><p class="fine">Current links: ${escapeHtml(claim.evidence_ids.length)} · ${escapeHtml(claim.evidence_link_method)}</p><div class="activity-choices">${sources.map(source=>`<label><input type="checkbox" name="evidence" value="${escapeHtml(source.id)}" ${claim.evidence_ids.includes(source.id)?'checked':''}> ${escapeHtml(source.id)} · ${escapeHtml(source.date)}</label>`).join('')}</div><button class="secondary" type="submit">Save activity links</button></form>`;
    }).join('');
  $('#mapping').innerHTML = `<p class="muted">Confirmed source IDs support allocation arithmetic. Activity rows count only when linked to a claim.</p>${sourceForms || '<p class="good-note">All allocation claims have a source ID. You can still inspect activity links below.</p>'}${activityForms ? `<details class="activity-review"><summary>Inspect activity links<svg class="icon" aria-hidden="true"><use href="#icon-chevron"></use></svg></summary>${activityForms}</details>` : ''}`;
  $('#mapping-disclosure').open = unmapped.length > 0;
  $('#mapping-disclosure > summary').firstChild.textContent = unmapped.length
    ? `Review evidence links (${unmapped.length} to confirm)`
    : 'Review evidence links (optional)';
}

function title(finding) {
  if (finding.code === 'ACTIVITY_SUPPORT_GAP' && finding.arithmetic?.reported !== undefined)
    return `${finding.arithmetic.reported} sessions reported, ${finding.arithmetic.linked_distinct_records} records found`;
  return ({OVERALLOCATED_SOURCE:'Two reports claim more hours than the timesheet shows',
    ALLOCATION_WITHIN_SOURCE:'These claims fit the supporting record',
    ACTIVITY_SUPPORT_GAP:'The report lists more sessions than the records show',
    ACTIVITY_LINKS_UNVERIFIED:'Some activity links need review',
    TIMESHEET_PROJECT_DIFFERS:'Timesheet names another program',
    ALLOCATION_TOTAL_WITH_PROJECT_QUESTION:'Allocation total fits, project basis needs review',
    SOURCE_IDENTITY_UNCERTAIN:'Choose which timesheet supports this claim',
    SOURCE_MISMATCH:'Claim and source differ', SOURCE_OUTSIDE_PERIOD:'Source is outside the period',
    STAFF_IDENTITY_UNVERIFIED:'Staff identity needs review', EXPENSE_IDENTITY_UNVERIFIED:'Vendor identity needs review'})[finding.code] || finding.code;
}

function plainFinding(finding) {
  const a = finding.arithmetic || {};
  if (finding.code === 'OVERALLOCATED_SOURCE' && a.allocated_total !== undefined)
    return `Together, the reports claim ${a.allocated_total} ${a.unit}, but the linked timesheet records ${a.source_total} ${a.unit} in total.`;
  if (finding.code === 'ACTIVITY_SUPPORT_GAP' && a.reported !== undefined)
    return `The report says ${a.reported} sessions took place. The linked activity log contains ${a.linked_distinct_records}, leaving ${a.gap} without a supplied record.`;
  if (finding.code === 'SOURCE_IDENTITY_UNCERTAIN')
    return 'This claim has no confirmed supporting record. The possible matches need a person to check them.';
  if (finding.status === 'clear' && a.allocated_total !== undefined)
    return `The reports claim ${a.allocated_total} ${a.unit} together, matching the ${a.source_total} ${a.unit} in the linked record.`;
  return finding.message;
}

function reviewerStep(finding) {
  if (finding.status === 'clear') return 'No amount gap was found in these linked records. You can continue or inspect the original rows.';
  if (finding.code === 'OVERALLOCATED_SOURCE') return 'Check how the time should be split, then change the claim that needs correcting. Lens cannot tell which report is wrong.';
  if (finding.code === 'ACTIVITY_SUPPORT_GAP') return 'Look for the missing session records. If the reported count is wrong, update your draft report and import the revised files. You can save a note while you check.';
  if (finding.code === 'SOURCE_IDENTITY_UNCERTAIN') return 'Go to Prepare and confirm the matching timesheet. Do not choose based on a similar name alone.';
  return 'Check the original records, correct the draft if needed, or save a note for your team.';
}

function comparison(finding) {
  const claims = finding.claims.map(ref => state.case.claims.find(claim => claim.id === ref.id)).filter(Boolean);
  const a = finding.arithmetic || {};
  const cards = claims.map((claim, index) => `<div class="comparison-item"><span>Report ${index + 1}: ${escapeHtml(claim.grant)}</span><strong>${escapeHtml(claim.quantity)} ${escapeHtml(claim.unit)}</strong></div>`);
  if (finding.code === 'ACTIVITY_SUPPORT_GAP' && a.linked_distinct_records !== undefined)
    cards.push(`<div class="comparison-item source"><span>Sessions in the activity log</span><strong>${escapeHtml(a.linked_distinct_records)} sessions</strong></div>`);
  else if (a.source_total !== undefined)
    cards.push(`<div class="comparison-item source"><span>Amount in the linked record</span><strong>${escapeHtml(a.source_total)} ${escapeHtml(a.unit)}</strong></div>`);
  else if (finding.sources.length)
    cards.push(`<div class="comparison-item source"><span>Possible supporting records</span><strong>${escapeHtml(finding.sources.length)} to check</strong></div>`);
  return cards.length ? `<div class="comparison">${cards.join('')}</div>` : '';
}

function arithmetic(finding) {
  const a = finding.arithmetic;
  if (!a) return 'No conclusive arithmetic until the source identity is confirmed.';
  if (a.allocated_total !== undefined) return `Claims total ${escapeHtml(a.allocated_total)} ${escapeHtml(a.unit)}; the linked source records ${escapeHtml(a.source_total)} ${escapeHtml(a.unit)}.`;
  if (a.reported !== undefined) return `Report states ${escapeHtml(a.reported)} sessions; ${escapeHtml(a.linked_distinct_records)} distinct supplied activity rows are linked; ${escapeHtml(a.gap)} sessions lack supplied evidence.`;
  return Object.entries(a).map(([key,value]) => `${escapeHtml(key)}: ${escapeHtml(Array.isArray(value)?value.join(', '):value)}`).join(' · ');
}

function findingHtml(finding, open=false) {
  const currentClaims = finding.claims.map(ref => {
    const claim = state.case.claims.find(item => item.id === ref.id);
    return claim ? `<div class="evidence-entry"><strong>Current ${escapeHtml(claim.grant)} claim</strong>${escapeHtml(claim.id)}: ${escapeHtml(claim.quantity)} ${escapeHtml(claim.unit)}${claim.kind === 'activity_count' ? ` · linked using ${escapeHtml(claim.evidence_link_method || 'explicit evidence IDs')}` : ''}</div>` : '';
  }).join('');
  const claimOptions = finding.claims.map(ref => {
    const claim = state.case.claims.find(item => item.id === ref.id);
    return claim?.kind === 'allocation' ? `<option value="${escapeHtml(claim.id)}">${escapeHtml(claim.grant)} · ${escapeHtml(claim.id)} · ${escapeHtml(claim.quantity)} ${escapeHtml(claim.unit)}</option>` : '';
  }).join('');
  const note = finding.human_explanation;
  const status = ({needs_correction:'Needs correction',needs_evidence:'Needs evidence',needs_review:'Needs review',clear:'Totals fit'})[finding.status] || finding.status.replaceAll('_',' ');
  return `<details class="finding ${escapeHtml(finding.status)}" name="lens-finding" data-key="${escapeHtml(finding.key)}" ${open ? 'open' : ''}>
    <summary><div class="finding-head"><div><h3>${escapeHtml(title(finding))}</h3><p class="finding-summary">${escapeHtml(plainFinding(finding))}</p></div><span class="badge">${escapeHtml(status)}</span></div><svg class="icon" aria-hidden="true"><use href="#icon-chevron"></use></svg></summary>
    <div class="finding-body"><div class="finding-work"><div class="finding-story"><p class="eyebrow">What we found</p><p class="finding-lead">${escapeHtml(plainFinding(finding))}</p>${comparison(finding)}</div>
    <aside class="decision-panel"><p class="eyebrow">WHAT YOU CAN DO</p><p class="reviewer-step">${escapeHtml(reviewerStep(finding))}</p>
      ${note ? `<p class="human-note" tabindex="-1"><strong>Explanation saved</strong><br>${escapeHtml(note.text)}<br><small>Source revision ${escapeHtml(note.source_revision)}. This note does not clear the question.</small></p>` : ''}
      <div class="review-actions">${finding.code === 'SOURCE_IDENTITY_UNCERTAIN' ? '<button type="button" class="secondary review-links">Confirm supporting record</button>' : ''}${claimOptions && finding.status !== 'clear' ? `<form class="correct-form" data-key="${escapeHtml(finding.key)}"><label>Choose which report amount to change</label><select name="claim_id" aria-label="Report claim to correct">${claimOptions}</select><label for="qty-${escapeHtml(finding.key)}">New amount (${escapeHtml(state.case.claims.find(claim => claim.id === finding.claims[0]?.id)?.unit || 'same unit')})</label><input id="qty-${escapeHtml(finding.key)}" name="quantity" type="number" min="0" step="any" required aria-label="New report amount"><button type="submit" class="primary">Save correction</button></form>` : ''}
      ${finding.status !== 'clear' ? `<form class="explain-form" data-key="${escapeHtml(finding.key)}"><label>Or record an explanation</label><textarea name="explanation" maxlength="2000" required placeholder="What should your team know?"></textarea><button type="submit" class="secondary">Save explanation</button></form>` : '<p class="good-note">This check found no quantity gap for these linked rows. You can inspect the evidence or continue to export.</p>'}</div>
    </aside><details class="source-details"><summary>View original rows and references <svg class="icon" aria-hidden="true"><use href="#icon-chevron"></use></svg></summary><div class="evidence"><div><h4>Draft report rows</h4>${currentClaims}${finding.claims.map(record).join('')}</div><div><h4>${finding.code === 'SOURCE_IDENTITY_UNCERTAIN' ? 'Possible source rows' : 'Supporting source rows'}</h4>${finding.sources.length ? finding.sources.map(record).join('') : '<p class="muted">No confirmed source row. Choose a source before treating this claim as verified.</p>'}</div></div>
      ${finding.claims.some(ref => ['linked source','user-confirmed source link'].includes(state.case.claims.find(c=>c.id===ref.id)?.identity_origin)) ? '<p class="fine">At least one draft omitted person or vendor. Identity shown in analysis came from the linked source ID; the report did not independently state it.</p>' : ''}
    </details></div></div>
  </details>`;
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
  panel.innerHTML = `<summary><span class="eyebrow">SELECTED FOLLOW-UP · ${escapeHtml(probe.code)}</span><strong>${escapeHtml(label)}</strong></summary><div class="adaptive-body">
    <p><strong>Why this probe:</strong> ${escapeHtml(probe.reason)}</p>
    <p>${escapeHtml(probe.observation)}</p>
    <p><strong>Ask the reviewer:</strong> ${escapeHtml(probe.question)}</p>
    <p class="fine">Selected ${escapeHtml((probe.tables?.length ? probe.tables : probe.files || []).join(', '))} · ${escapeHtml((probe.request_ids || []).length)} follow-up request IDs.</p>
    <p class="fine">Referenced rows: ${escapeHtml(locations.join('; '))}</p></div>`;
  panel.open = window.matchMedia('(min-width: 801px)').matches;
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
  document.body.classList.toggle('has-case', loaded);
  const savedLabel = state.saved_at ? `Saved ${new Date(state.saved_at).toLocaleString()}` : '';
  $('#saved').textContent = savedLabel;
  $('#workspace-saved').textContent = savedLabel;
  if (!loaded) { showView(activeView === 'welcome' ? 'welcome' : 'home'); return; }
  $('#data-label').textContent = state.case.label;
  $('#import-summary').textContent = `${state.case.claims.length} report claims and ${state.case.sources.length} source records from ${Object.keys(state.files).length} ${state.zetaris ? 'Zetaris table snapshots' : 'CSV files'}. Period: ${state.case.reporting_period.start} to ${state.case.reporting_period.end}.`;
  renderZetarisEvidence();
  renderInvestigationTrace();
  inspectRecords();
  renderMapping();
  renderAdaptiveInvestigation();
  $('#check').innerHTML = state.result ? 'Run check again' + arrowIcon : 'Check both reports' + arrowIcon;
  $('#check-state').textContent = state.result ? `Checked revision ${state.revision}. Review remains saved after refresh.` : state.corrections?.length ? 'Correction saved. Rerun to see the updated result.' : 'Ready to check the imported records.';
  if (state.result) {
    const currentKeys = new Set(state.result.findings.map(item => item.key));
    const openKeys = new Set([...document.querySelectorAll('.finding[open]')].map(item => item.dataset.key).filter(key => currentKeys.has(key)));
    const firstQuestion = state.result.findings.findIndex(item => item.status !== 'clear');
    $('#finding-list').innerHTML = state.result.findings.map((finding,index) => findingHtml(finding, openKeys.has(finding.key) || (!openKeys.size && index === (firstQuestion < 0 ? 0 : firstQuestion)))).join('');
    const open = state.result.findings.filter(item => item.status !== 'clear').length;
    const clear = state.result.findings.length - open;
    $('#finding-summary').innerHTML = `<strong>${open} ${open === 1 ? 'question' : 'questions'} to review</strong><span>${clear} ${clear === 1 ? 'check' : 'checks'} fit the supplied evidence</span>`;
  }
  const m = state.meterless || {status:'unknown'};
  $('#integration-status').textContent = `Review history: Meterless ${m.status}${m.event_count === undefined ? '' : ` · ${m.event_count} events`}. Analysis: local deterministic reconciliation. Zetaris grant-data query: ${state.zetaris ? 'five tables captured for this review; snapshot hashes and request IDs saved. Tables were not transactionally frozen.' : 'not connected to this review.'}`;
  showView(activeView);
}

function reviewStatePath() {
  return publicMode ? `/api/state?review_id=${encodeURIComponent(selectedReviewId)}` : '/api/state';
}

function renderReviewPicker() {
  const picker = $('#review-picker');
  picker.classList.toggle('hidden', !publicMode || !authUserId);
  if (!publicMode || !authUserId) return;
  const select = $('#review-select');
  select.replaceChildren(new Option('Start a new review', ''));
  for (const review of reviews) select.add(new Option(review.title || 'Untitled review', review.id));
  select.value = selectedReviewId || '';
  $('#review-picker-help').textContent = reviews.length
    ? 'Your saved work is available on any device after sign-in.'
    : 'No saved reviews yet. Open the sample case or bring your own records below.';
}

async function refreshReviewList() {
  if (!publicMode || !authUserId) return;
  const data = await request('/api/reviews');
  reviews = data.reviews || [];
  renderReviewPicker();
}

async function createReview(title) {
  if (!publicMode) return null;
  const data = await request('/api/reviews', {title});
  selectedReviewId = data.review.id;
  await refreshReviewList();
  return data.review;
}

async function ensureReview(title) {
  if (publicMode && !selectedReviewId) await createReview(title);
}

async function selectReview(reviewId) {
  const epoch = ++viewEpoch;
  selectedReviewId = reviewId || null;
  state = {phase:'empty'};
  activeView = 'home';
  render();
  renderReviewPicker();
  notice('');
  if (!selectedReviewId) return;
  notice('Opening your saved review...');
  try {
    const next = await request(reviewStatePath());
    if (epoch !== viewEpoch) return;
    state = next;
    activeView = derivedView(next);
    render();
    notice('Saved review opened.');
    if (next.case) showView(activeView, true);
  } catch (error) {
    if (epoch === viewEpoch) notice(`Could not open this review: ${error.message}`, true);
  }
}

function setSignedOutView() {
  viewEpoch++;
  authUserId = null;
  selectedReviewId = null;
  reviews = [];
  state = {phase:'empty'};
  activeView = 'welcome';
  render();
  renderReviewPicker();
  $('#account-controls').classList.add('hidden');
  $('#account-email').textContent = '';
  $('#account-name').textContent = '';
  document.body.classList.remove('zetaris-allowed');
  $('#own-data-intro').textContent = 'Review two draft reports against the timesheets, receipts and activity log you upload.';
  $('#auth-gate').classList.remove('hidden');
  document.body.classList.add('auth-required');
  document.body.classList.remove('booting');
  $('#local-label').classList.add('hidden');
}

async function syncSession(session) {
  const epoch = ++authEpoch;
  if (!session?.access_token) {
    setSignedOutView();
    return;
  }
  try {
    const data = await request('/api/session');
    if (epoch !== authEpoch) return;
    const changedUser = authUserId !== data.user.id;
    authUserId = data.user.id;
    document.body.classList.toggle('zetaris-allowed', Boolean(data.can_import_zetaris));
    $('#own-data-intro').textContent = data.can_import_zetaris
      ? 'Review two draft reports against timesheets, receipts and activity records you upload, or query five registered Zetaris tables.'
      : 'Review two draft reports against the timesheets, receipts and activity log you upload.';
    $('#account-email').textContent = data.user.email || 'Signed in';
    const metadata = session.user?.user_metadata || {};
    const greeting = String(metadata.full_name || metadata.name || data.user.email?.split('@')[0] || 'Your account').trim().split(/\s+/)[0];
    $('#account-name').textContent = `Hello, ${greeting}`;
    $('#account-controls').classList.remove('hidden');
    $('#auth-gate').classList.add('hidden');
    document.body.classList.remove('auth-required', 'booting');
    if (changedUser) {
      selectedReviewId = null;
      state = {phase:'empty'};
      activeView = 'home';
      render();
      await refreshReviewList();
      if (epoch !== authEpoch) return;
      if (reviews.length) await selectReview(reviews[0].id);
    }
  } catch (error) {
    if (epoch !== authEpoch) return;
    setSignedOutView();
    notice(`Could not verify your sign-in: ${error.message}`, true);
  }
}

async function loadSupabaseClient() {
  if (window.supabase?.createClient) return;
  await new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = '/vendor/supabase.js';
    script.onload = () => window.supabase?.createClient ? resolve() : reject(new Error('Sign-in library did not load.'));
    script.onerror = () => reject(new Error('Sign-in library is unavailable. Check your connection and refresh.'));
    document.head.append(script);
  });
}

async function boot() {
  try {
    const response = await fetch('/api/config');
    const config = await response.json();
    if (!response.ok) throw new Error(config.error || 'Could not read service configuration.');
    publicMode = config.auth_mode === 'supabase';
    if (!publicMode) {
      document.body.classList.remove('booting');
      state = await request('/api/state');
      activeView = derivedView(state);
      render();
      return;
    }
    document.body.classList.add('public-mode');
    $('#own-data-intro').textContent = 'Review two draft reports against the timesheets, receipts and activity log you upload.';
    $('#local-label').classList.add('hidden');
    $('footer p').textContent = 'Reviews are saved to your account. Lens raises questions for human review and does not make a compliance determination.';
    await loadSupabaseClient();
    authClient = window.supabase.createClient(config.supabase_url, config.supabase_anon_key, {
      auth: {persistSession:true, autoRefreshToken:true, detectSessionInUrl:true}
    });
    authClient.auth.onAuthStateChange((_event, session) => {
      window.setTimeout(() => { syncSession(session); }, 0);
    });
    const {data, error} = await authClient.auth.getSession();
    if (error) throw error;
    await syncSession(data.session);
  } catch (error) {
    document.body.classList.add('auth-required');
    document.body.classList.remove('booting');
    notice(`Lens could not start: ${error.message}`, true);
  }
}

$('#google-sign-in').addEventListener('click', async event => {
  const button = event.currentTarget;
  button.disabled = true;
  try {
    if (!authClient) throw new Error('Sign-in is unavailable. Refresh and try again.');
    const {error} = await authClient.auth.signInWithOAuth({provider:'google', options:{redirectTo:window.location.origin + window.location.pathname}});
    if (error) throw error;
  } catch (error) {
    notice(`Google sign-in could not start: ${error.message}`, true);
  } finally { button.disabled = false; }
});
$('#sign-out').addEventListener('click', async () => {
  if (!authClient) return;
  try {
    const {error} = await authClient.auth.signOut();
    if (error) throw error;
    setSignedOutView();
    notice('Signed out. Your saved reviews will be here when you return.');
  } catch (error) { notice(`Could not sign out: ${error.message}`, true); }
});
$('#review-select').addEventListener('change', event => selectReview(event.currentTarget.value));
$('#back-to-reviews').addEventListener('click', () => showView('home', true));
document.querySelectorAll('[data-flow]').forEach(button => button.addEventListener('click', () => showView(button.dataset.flow, true)));
$('#go-export').addEventListener('click', () => showView('export', true));
$('#return-to-findings').addEventListener('click', () => showView('findings', true));
$('#rerun-check').addEventListener('click', event => act(event.currentTarget, () => request('/api/check', {}), 'Check complete. Review the updated questions below.'));
$('#new-review').addEventListener('click', async event => {
  const button = event.currentTarget;
  button.disabled = true;
  try {
    const review = await createReview(`Review ${new Date().toLocaleDateString()}`);
    await selectReview(review.id);
    notice('New review created. Open the sample case or import your own records.');
  } catch (error) { notice(`Could not create a review: ${error.message}`, true); }
  finally { button.disabled = false; }
});
$('#sample').addEventListener('click', event => {
  if (state.case && !window.confirm('Replace the current case in this review with the synthetic example? Export it first if you need a copy.')) return;
  act(event.currentTarget, async () => {
    await ensureReview('Sample review');
    return request('/api/sample', {});
  }, 'Synthetic case loaded. Check the imported records, then run a review.');
});
$('#import-zetaris').addEventListener('click', event => act(event.currentTarget, async () => {
  await ensureReview('Zetaris review');
  return request('/api/import-zetaris', {period: {start: $('#period-start').value, end: $('#period-end').value}});
}, 'Complete Zetaris query snapshot imported. Inspect source IDs and confirm activity links before checking.'));
$('#import-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (state.case && !window.confirm('Replace the current case in this review with these CSV files? Export it first if you need a copy.')) return;
  const files = {};
  for (const input of document.querySelectorAll('[data-file]')) {
    if (!input.files[0]) return notice(`Choose ${input.dataset.file}`, true);
    files[input.dataset.file] = await input.files[0].text();
  }
  const period = {start: $('#period-start').value, end: $('#period-end').value};
  act(event.submitter, async () => {
    await ensureReview('CSV review');
    return request('/api/import', {files, period});
  }, 'Five CSVs imported. Inspect rows, then run a check.');
});
$('#check').addEventListener('click', event => act(event.currentTarget, () => request('/api/check', {}), 'Check complete. Review the questions and source rows below.'));
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
$('#finding-list').addEventListener('click', event => {
  if (!event.target.closest('.review-links')) return;
  showView('prepare', true);
  $('#mapping-disclosure').open = true;
  $('#mapping-disclosure').scrollIntoView({block:'start', behavior:'smooth'});
});
$('#export').addEventListener('click', async event => {
  event.preventDefault();
  try {
    const path = publicMode ? `/api/export?review_id=${encodeURIComponent(selectedReviewId)}` : '/api/export';
    const data = await request(path);
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type:'application/json'}));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'lens-review.json';
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    notice('Current review exported as JSON.');
  } catch (error) { notice(`Could not export this review: ${error.message}`, true); }
});
boot();
