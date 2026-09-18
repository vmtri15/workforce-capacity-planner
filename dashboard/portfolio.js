let portfolioData;
let networkCapacityData;
let decisionAnswerData;

const portfolioNumber = (value, digits = 0) => Number(value).toLocaleString('en-US', {
  maximumFractionDigits: digits,
});

const portfolioMoney = value => '$' + portfolioNumber(value, 0);
const portfolioEscape = value => String(value ?? '').replace(/[&<>"']/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[character]));

const policyLabel = policy => {
  const labels = {
    extra0_ot0_temps0: '6 workers, no added coverage',
    extra0_ot2_temps0: '6 workers, up to 2h overtime',
    extra3_ot2_temps0: '9 workers, up to 2h overtime',
    extra4_ot2_temps0: '10 workers, up to 2h overtime',
  };
  if (labels[policy]) return labels[policy];
  const match = policy.match(/^extra(\d+)_ot(\d+)_temps(\d+)$/);
  if (!match) return policy;
  const workers = 6 + Number(match[1]);
  return `${workers} workers, ${match[2]}h overtime, ${match[3]} temporary`;
};

function retainedDemand() {
  return portfolioData.demand_daily.filter(row => row.basis === 'retained');
}

function demandSummary() {
  const rows = retainedDemand();
  const daily = new Map();
  const mix = new Map();
  let orders = 0;
  let units = 0;
  rows.forEach(row => {
    const rowOrders = Number(row.orders);
    const rowUnits = Number(row.units);
    orders += rowOrders;
    units += rowUnits;
    if (!daily.has(row.date)) daily.set(row.date, { date: row.date, large: 0, small: 0, zero: 0 });
    const day = daily.get(row.date);
    const key = row.segment === 'large_over_5' ? 'large' : row.segment === 'small_1_5' ? 'small' : 'zero';
    day[key] += rowUnits;
    if (!mix.has(row.segment)) mix.set(row.segment, { orders: 0, units: 0 });
    mix.get(row.segment).orders += rowOrders;
    mix.get(row.segment).units += rowUnits;
  });
  const days = [...daily.values()].sort((a, b) => a.date.localeCompare(b.date));
  const peak = Math.max(...days.map(day => day.large + day.small + day.zero));
  return { rows, days, mix, orders, units, peak, average: units / days.length };
}

function renderDemandOverview() {
  const summary = demandSummary();
  const large = summary.mix.get('large_over_5') || { orders: 0, units: 0 };
  const orderShare = 100 * large.orders / summary.orders;
  const unitShare = 100 * large.units / summary.units;
  document.getElementById('portfolio-metrics').innerHTML = [
    ['Observed units', portfolioNumber(summary.units), 'Across retained source records'],
    ['Recorded dates', portfolioNumber(summary.days.length), 'Missing dates are not zero demand'],
    ['Average units / date', portfolioNumber(summary.average), 'Average across recorded dates'],
    ['Peak recorded date', portfolioNumber(summary.peak), 'Highest observed daily units'],
  ].map(item => `<div class="metric"><small>${item[0]}</small><strong>${item[1]}</strong><p>${item[2]}</p></div>`).join('');
  document.getElementById('mix-bars').innerHTML = [
    ['Share of orders', orderShare],
    ['Share of units', unitShare],
  ].map(([label, value]) => `<div class="mix-row"><span>${label}</span><div class="mix-track"><div class="mix-fill" style="width:${value.toFixed(2)}%"></div></div><strong>${value.toFixed(1)}%</strong></div>`).join('');
  window.drawPortfolioDemand();
}

window.drawPortfolioDemand = function drawPortfolioDemand() {
  if (!portfolioData) return;
  const canvas = document.getElementById('demand-chart');
  if (!canvas || canvas.hidden || !canvas.clientWidth) return;
  const days = demandSummary().days;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  const ratio = window.devicePixelRatio || 1;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  const context = canvas.getContext('2d');
  context.scale(ratio, ratio);
  const left = 48;
  const right = width - 12;
  const top = 12;
  const bottom = height - 30;
  const maximum = Math.max(...days.map(day => day.large + day.small + day.zero)) * 1.08;
  context.font = '10px Arial';
  context.fillStyle = '#7c8980';
  context.strokeStyle = '#e2e8e4';
  for (let index = 0; index <= 4; index += 1) {
    const y = bottom - (bottom - top) * index / 4;
    context.beginPath();
    context.moveTo(left, y);
    context.lineTo(right, y);
    context.stroke();
    context.fillText(portfolioNumber(maximum * index / 4), 0, y + 3);
  }
  const slot = (right - left) / days.length;
  const barWidth = Math.max(1, slot * .76);
  days.forEach((day, index) => {
    const x = left + index * slot;
    const smallHeight = day.small / maximum * (bottom - top);
    const largeHeight = day.large / maximum * (bottom - top);
    context.fillStyle = '#6b89b6';
    context.fillRect(x, bottom - smallHeight, barWidth, smallHeight);
    context.fillStyle = '#25816b';
    context.fillRect(x, bottom - smallHeight - largeHeight, barWidth, largeHeight);
  });
  const tickStep = Math.max(1, Math.ceil(days.length / (width < 600 ? 4 : 8)));
  context.fillStyle = '#7c8980';
  days.forEach((day, index) => {
    if (index % tickStep === 0) context.fillText(day.date.slice(5), left + index * slot - 10, height - 8);
  });
};

function scenarioRows() {
  return portfolioData.scenario_results.filter(row => row.basis === 'retained');
}

function optionValues(key) {
  return [...new Set(scenarioRows().map(row => row[key]))].sort((a, b) => Number(a) - Number(b));
}

function setOptions(id, values, formatter = value => value) {
  document.getElementById(id).innerHTML = values.map(value => `<option value="${value}">${formatter(value)}</option>`).join('');
}

function selectedScenario(policyId) {
  const selected = {
    period: document.getElementById('sb-period').value,
    policy: document.getElementById(policyId).value,
    rate: document.getElementById('sb-rate').value,
    absent: document.getElementById('sb-absent').value,
    lead_days: document.getElementById('sb-lead').value,
  };
  return scenarioRows().find(candidate => Object.entries(selected).every(([key, value]) => candidate[key] === value));
}

function scenarioCard(row, label) {
  if (!row) return `<article class="analysis-panel scenario-card unavailable"><p class="comparison-label">${label}</p><span class="status-pill fail">CASE UNAVAILABLE</span><h2>Combination not precomputed</h2><p>Choose another policy or assumption set. The browser does not interpolate missing results.</p></article>`;
  const service = 100 * Number(row.on_time_unit_share);
  const met = row.target_met === 'True';
  return `<article class="analysis-panel scenario-card">
    <div class="scenario-card-heading"><div><p class="comparison-label">${label}</p><h2>${portfolioEscape(policyLabel(row.policy))}</h2></div><span class="status-pill ${met ? '' : 'fail'}">${met ? 'TARGET MET' : 'TARGET MISSED'}</span></div>
    <div class="scenario-score"><strong>${service.toFixed(1)}%</strong><span>on-time units</span></div>
    <div class="scenario-card-metrics"><div><small>Modeled cost</small><strong>${portfolioMoney(row.total_cost)}</strong></div><div><small>Peak backlog</small><strong>${portfolioNumber(row.peak_backlog)}</strong></div><div><small>Present workers</small><strong>${portfolioNumber(row.present_workers)}</strong></div><div><small>Completed late</small><strong>${portfolioNumber(row.completed_late)}</strong></div></div>
    <p class="footnote">${portfolioNumber(row.rate)} units per productive hour · ${row.absent} absent · ${row.lead_days}-day lead time</p>
  </article>`;
}

function renderScenario() {
  if (!portfolioData) return;
  const first = selectedScenario('sb-policy');
  const second = selectedScenario('sb-policy-b');
  document.getElementById('scenario-cards').innerHTML = scenarioCard(first, 'POLICY A') + scenarioCard(second, 'POLICY B');
  if (!first || !second) {
    document.getElementById('scenario-comparison-summary').innerHTML = '<strong>Comparison unavailable</strong><span>Select two precomputed policies under the same assumptions.</span>';
    return;
  }
  const costDifference = Number(second.total_cost) - Number(first.total_cost);
  const serviceDifference = 100 * (Number(second.on_time_unit_share) - Number(first.on_time_unit_share));
  const backlogDifference = Number(second.peak_backlog) - Number(first.peak_backlog);
  document.getElementById('scenario-comparison-summary').innerHTML = `<div><small>Policy B cost difference</small><strong>${costDifference >= 0 ? '+' : '-'}${portfolioMoney(Math.abs(costDifference))}</strong></div><div><small>Service difference</small><strong>${serviceDifference >= 0 ? '+' : ''}${serviceDifference.toFixed(1)} pts</strong></div><div><small>Peak backlog difference</small><strong>${backlogDifference >= 0 ? '+' : ''}${portfolioNumber(backlogDifference)}</strong></div>`;
}

function setupScenarioBuilder() {
  const policies = [...new Set(scenarioRows().map(row => row.policy))];
  setOptions('sb-policy', policies, policyLabel);
  setOptions('sb-policy-b', policies, policyLabel);
  setOptions('sb-rate', optionValues('rate'), value => `${portfolioNumber(value)} units / productive hour`);
  setOptions('sb-absent', optionValues('absent'), value => `${value} worker${value === '1' ? '' : 's'}`);
  setOptions('sb-lead', optionValues('lead_days'), value => `${value} day${value === '1' ? '' : 's'}`);
  document.getElementById('sb-policy').value = 'extra0_ot2_temps0';
  document.getElementById('sb-policy-b').value = 'extra4_ot2_temps0';
  document.getElementById('sb-rate').value = '40.0';
  document.getElementById('sb-absent').value = '0';
  document.getElementById('sb-lead').value = '1';
  document.querySelectorAll('#scenario-form select').forEach(select => select.addEventListener('change', renderScenario));
  document.getElementById('scenario-export').addEventListener('click', exportScenarioComparison);
  document.getElementById('decision-report').addEventListener('click', exportDecisionReport);
  renderScenario();
}

function exportScenarioComparison() {
  const rows = [selectedScenario('sb-policy'), selectedScenario('sb-policy-b')].filter(Boolean);
  if (!rows.length) return;
  const keys = ['policy', 'period', 'rate', 'workers', 'present_workers', 'absent', 'lead_days', 'on_time_unit_share', 'target_met', 'total_cost', 'peak_backlog', 'completed_on_time', 'completed_late', 'backlog_unit_days', 'evidence'];
  const csv = [keys.join(','), ...rows.map(row => keys.map(key => `"${String(row[key] ?? '').replaceAll('"', '""')}"`).join(','))].join('\r\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `workforce-scenario-comparison-${document.getElementById('sb-period').value}.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function exportDecisionReport() {
  const first = selectedScenario('sb-policy');
  const second = selectedScenario('sb-policy-b');
  if (!first || !second) return;
  const serviceA = 100 * Number(first.on_time_unit_share);
  const serviceB = 100 * Number(second.on_time_unit_share);
  const costDifference = Number(second.total_cost) - Number(first.total_cost);
  const preferred = serviceB >= 95 && serviceA < 95 ? 'Policy B is the stronger candidate under this case.' :
    serviceA >= 95 && serviceB < 95 ? 'Policy A is the stronger candidate under this case.' :
    'Both policies require comparison against cost, backlog, and additional stress cases.';
  const report = [
    'WORKFORCE CAPACITY PLANNER - DECISION REPORT',
    '',
    `Evaluation period: ${first.period}`,
    `Productivity: ${first.rate} units per productive hour`,
    `Workers absent: ${first.absent}`,
    `Action lead time: ${first.lead_days} day(s)`,
    '',
    `Policy A: ${policyLabel(first.policy)}`,
    `On-time units: ${serviceA.toFixed(1)}% | Target met: ${first.target_met} | Modeled cost: ${portfolioMoney(first.total_cost)} | Peak backlog: ${portfolioNumber(first.peak_backlog)}`,
    '',
    `Policy B: ${policyLabel(second.policy)}`,
    `On-time units: ${serviceB.toFixed(1)}% | Target met: ${second.target_met} | Modeled cost: ${portfolioMoney(second.total_cost)} | Peak backlog: ${portfolioNumber(second.peak_backlog)}`,
    '',
    `Difference (B - A): ${serviceB - serviceA >= 0 ? '+' : ''}${(serviceB - serviceA).toFixed(1)} service points; ${costDifference >= 0 ? '+' : '-'}${portfolioMoney(Math.abs(costDifference))}.`,
    `Decision signal: ${preferred}`,
    '',
    'Evidence boundary:',
    'Observed 2023 demand is separated from hypothetical staffing, productivity, absence, lead-time, and cost assumptions. This report is for scenario comparison and does not prescribe actual headcount.',
  ].join('\n');
  const url = URL.createObjectURL(new Blob([report], { type: 'text/plain' }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `workforce-decision-report-${first.period}.txt`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function selectedNetworkCase() {
  return networkCapacityData?.cases.find(item => item.productivity_case === document.getElementById('network-case').value);
}

function selectedNetworkSite() {
  return document.getElementById('network-site').value;
}

function networkDailyRows(selected) {
  const site = selectedNetworkSite();
  return site === 'all' ? selected.daily : selected.site_daily.filter(row => row.site_id === site);
}

function renderNetworkCapacity() {
  const selected = selectedNetworkCase();
  if (!selected) return;
  const site = selectedNetworkSite();
  const siteSummary = selected.site_summary.find(row => row.site_id === site);
  const summary = site === 'all' ? selected.network_summary : {
    required_hours: siteSummary.required_hours,
    gap_hours: siteSummary.gap_hours,
    scheduled_headcount: siteSummary.scheduled_headcount,
    recorded_period_wage_cost: siteSummary.recorded_period_wage_cost,
  };
  document.getElementById('network-metrics').innerHTML = [
    ['Required productive hours', portfolioNumber(summary.required_hours, 1), 'Picking and packing on recorded dates'],
    ['Capacity gap', `${portfolioNumber(summary.gap_hours, 1)} h`, 'Sum of modeled role-level shortfalls'],
    ['Fixed positions', portfolioNumber(summary.scheduled_headcount), 'All four modeled roles'],
    ['Recorded-period wages', portfolioMoney(summary.recorded_period_wage_cost), 'Modeled direct scheduled wages'],
  ].map(item => `<div class="metric"><small>${item[0]}</small><strong>${item[1]}</strong><p>${item[2]}</p></div>`).join('');
  document.getElementById('network-period').textContent = `${networkCapacityData.metadata.source_window_start} to ${networkCapacityData.metadata.source_window_end} · ${networkCapacityData.metadata.recorded_dates} recorded dates`;
  document.getElementById('network-sites').innerHTML = selected.site_summary.filter(row => site === 'all' || row.site_id === site).map(row => `<tr><td>${portfolioEscape(row.site_name)}<p>${portfolioEscape(networkCapacityData.sites.find(item => item.site_id === row.site_id).allocation_basis)}</p></td><td>${portfolioNumber(row.scheduled_headcount)}</td><td>${portfolioNumber(row.required_hours, 1)}</td><td>${portfolioNumber(row.gap_hours, 1)}</td><td>${(100 * row.target_met_share).toFixed(1)}%</td><td>${portfolioMoney(row.recorded_period_wage_cost)}</td></tr>`).join('');
  window.drawNetworkCapacity();
}

window.drawNetworkCapacity = function drawNetworkCapacity() {
  const selected = selectedNetworkCase();
  const canvas = document.getElementById('network-chart');
  if (!selected || !canvas || canvas.hidden || !canvas.clientWidth) return;
  const days = networkDailyRows(selected);
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  const ratio = window.devicePixelRatio || 1;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  const context = canvas.getContext('2d');
  context.scale(ratio, ratio);
  const left = 48;
  const right = width - 12;
  const top = 12;
  const bottom = height - 30;
  const maximum = Math.max(...days.flatMap(day => [day.required_hours, day.available_hours])) * 1.12;
  const x = index => left + (right - left) * index / Math.max(1, days.length - 1);
  const y = value => bottom - value / maximum * (bottom - top);
  context.font = '10px Arial';
  context.fillStyle = '#7c8980';
  context.strokeStyle = '#e2e8e4';
  for (let index = 0; index <= 4; index += 1) {
    const lineY = bottom - (bottom - top) * index / 4;
    context.beginPath();
    context.moveTo(left, lineY);
    context.lineTo(right, lineY);
    context.stroke();
    context.fillText(portfolioNumber(maximum * index / 4), 0, lineY + 3);
  }
  [['required_hours', '#25816b'], ['available_hours', '#6b89b6']].forEach(([key, color]) => {
    context.beginPath();
    days.forEach((day, index) => index ? context.lineTo(x(index), y(day[key])) : context.moveTo(x(index), y(day[key])));
    context.strokeStyle = color;
    context.lineWidth = 2;
    context.setLineDash(key === 'available_hours' ? [6, 4] : []);
    context.stroke();
  });
  context.fillStyle = '#c95b521f';
  days.forEach((day, index) => {
    if (day.required_hours > day.available_hours) {
      const nextX = index === days.length - 1 ? right : x(index + 1);
      context.fillRect(x(index), top, Math.max(2, nextX - x(index)), bottom - top);
    }
  });
  context.setLineDash([]);
  const step = Math.max(1, Math.ceil(days.length / (width < 600 ? 4 : 8)));
  days.forEach((day, index) => {
    if (index % step === 0) context.fillText(day.date.slice(5), x(index) - 10, height - 8);
  });
};

function setupNetworkCapacity() {
  document.getElementById('network-case').addEventListener('change', renderNetworkCapacity);
  document.getElementById('network-site').insertAdjacentHTML('beforeend', networkCapacityData.sites.map(site => `<option value="${portfolioEscape(site.site_id)}">${portfolioEscape(site.site_name)}</option>`).join(''));
  document.getElementById('network-site').addEventListener('change', renderNetworkCapacity);
  const canvas = document.getElementById('network-chart');
  canvas.addEventListener('mousemove', event => {
    const selected = selectedNetworkCase();
    if (!selected) return;
    const days = networkDailyRows(selected);
    const index = Math.max(0, Math.min(days.length - 1, Math.round((event.offsetX - 48) / Math.max(1, canvas.clientWidth - 60) * (days.length - 1))));
    const day = days[index];
    const gap = Math.max(day.required_hours - day.available_hours, 0);
    document.getElementById('network-chart-detail').textContent = `${day.date} | Required: ${portfolioNumber(day.required_hours, 1)} h | Available: ${portfolioNumber(day.available_hours, 1)} h | Gap: ${portfolioNumber(gap, 1)} h`;
  });
  renderNetworkCapacity();
}

function renderDecisionAnswer() {
  if (!decisionAnswerData) return;
  document.getElementById('decision-answer').textContent = decisionAnswerData.answer;
  document.getElementById('decision-sites').innerHTML = decisionAnswerData.site_results.map(site => `<tr><td>${portfolioEscape(site.site_name)}</td><td><strong>${portfolioEscape(site.answer)}</strong></td><td>${portfolioNumber(site.modeled_positions)}</td><td>${portfolioNumber(site.base_gap_hours, 1)} h</td><td>${(100 * site.base_target_met_role_day_share).toFixed(1)}%</td></tr>`).join('');
  const affordable = decisionAnswerData.actions.affordable_base_case;
  const resilient = decisionAnswerData.actions.lowest_risk_tested;
  document.getElementById('decision-affordable').textContent = `${affordable.scheduled_workers} workers with up to ${affordable.overtime_limit_hours} overtime hours reaches ${(100 * affordable.base_on_time_share).toFixed(1)}% in the later-period base case at ${portfolioMoney(affordable.base_modeled_cost)}, but passes only ${affordable.stress_cases_passed}/${affordable.stress_cases_tested} listed stresses.`;
  document.getElementById('decision-resilient').textContent = `${resilient.scheduled_workers} workers with up to ${resilient.overtime_limit_hours} overtime hours passes ${resilient.stress_cases_passed}/${resilient.stress_cases_tested} listed later-period stresses; worst service is ${(100 * resilient.worst_on_time_share).toFixed(1)}%.`;
  document.getElementById('decision-rule').textContent = decisionAnswerData.actions.decision_rule;
}

async function loadDecisionAnswer() {
  let response = await fetch('./api/decision-answer');
  if (!response.ok) response = await fetch('./data/decision_answer.json');
  if (!response.ok) throw new Error('The reconciled decision answer could not be loaded.');
  decisionAnswerData = await response.json();
  renderDecisionAnswer();
}

async function loadNetworkCapacity() {
  let response = await fetch('./api/network-capacity');
  if (!response.ok) response = await fetch('./data/network_capacity_2023.json');
  if (!response.ok) throw new Error('The 2023 network capacity replay could not be loaded.');
  networkCapacityData = await response.json();
  setupNetworkCapacity();
}

async function loadPortfolio() {
  try {
    let response = await fetch('./api/portfolio');
    if (!response.ok) response = await fetch('./data/portfolio.json');
    if (!response.ok) throw new Error('Portfolio data could not be loaded. Use the local server or rebuild the static data bundle.');
    portfolioData = await response.json();
    window.portfolioReady = true;
    renderDemandOverview();
    setupScenarioBuilder();
    await loadNetworkCapacity();
    await loadDecisionAnswer();
    document.querySelectorAll('[data-go]').forEach(button => button.addEventListener('click', () => showView(button.dataset.go)));
  } catch (error) {
    const alert = document.getElementById('error');
    alert.hidden = false;
    alert.textContent = error.message;
  }
}

window.addEventListener('resize', window.drawPortfolioDemand);
window.addEventListener('resize', window.drawNetworkCapacity);
loadPortfolio();
