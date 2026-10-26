// Home, demand forecast and middle mile views, plus routing, the mobile menu and the public Ask page.
// Reads dashboard/data/story.json (built by scripts/build_static_dashboard.py) and the decision answer.
(() => {
  const $ = id => document.getElementById(id);
  const esc = portfolioEscape;
  const num = portfolioNumber;
  const money = portfolioMoney;
  const pct = (value, digits = 1) => `${(100 * Number(value)).toFixed(digits)}%`;
  const GROUPS = {home: 'OVERVIEW', recommendations: 'OVERVIEW', processcontrol: 'OVERVIEW', portfolio: '1 · FORECAST DEMAND', forecast: '1 · FORECAST DEMAND',
    inventory: '2 · PLAN CAPACITY', lastmile: '3 · SHIP PARCELS', network: '2 · PLAN CAPACITY', builder: '2 · PLAN CAPACITY', middlemile: '3 · SHIP PARCELS', ask: 'TOOLS', tableau: 'TOOLS',
    methodology: 'TOOLS', about: 'ABOUT', overview: 'ARCHIVE', scenarios: 'ARCHIVE', evidence: 'ARCHIVE'};
  const MODEL_NAMES = {SameWeekdayLastWeek: 'Same day last week', Mean20Days: '20 day average', QuantileP90: 'P90 high case'};
  const SOURCE_NAMES = {oracle: 'Hindsight (a perfect forecast)', fixed_6_workers_ot2: '6 workers + overtime, fixed',
    fixed_6_workers_ot2_temps4: '6 workers + overtime + temps on call', fixed_10_workers_ot2: '10 workers + overtime, fixed',
    'QuantileP90 x1.0': 'P90 high case forecast'};
  const RECOMMENDED_SOURCE = 'fixed_6_workers_ot2_temps4';
  let story, decision, forecastPoints = [];

  const sourceName = source => SOURCE_NAMES[source] || source.replace(/ x1\.0$/, ' forecast').replace(/ x1\.5$/, ' forecast + 50% buffer')
    .replace('Mean20Days', '20 day average');
  const metric = (label, value, note, tip) => `<div class="metric"><small>${label}${tip ? ` <span class="tip" tabindex="0" data-tip="${esc(tip)}">?</span>` : ''}</small><strong>${value}</strong><p>${note}</p></div>`;

  async function loadJson(apiPath, filePath) {
    let response = apiPath ? await fetch(apiPath).catch(() => null) : null;
    if (!response || !response.ok) response = await fetch(filePath);
    if (!response.ok) throw new Error(`${filePath} could not be loaded.`);
    return response.json();
  }

  // ---- routing and the mobile menu ----
  const baseShowView = showView;
  showView = function routedShowView(view) {  // app.js and portfolio.js call showView by name
    if (!$(view)) view = 'home';
    baseShowView(view);
    $('crumb').textContent = GROUPS[view] || 'OVERVIEW';
    if (location.hash !== `#${view}`) history.replaceState(null, '', `#${view}`);
    document.body.classList.remove('menu-open');
    $('scrim').hidden = true;
    $('menu-toggle').setAttribute('aria-expanded', 'false');
    window.scrollTo({top: 0});
    if (view === 'forecast') drawForecast();
  };

  function isDark() {
    const set = document.documentElement.dataset.theme;
    return set ? set === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
  }

  function redrawCharts() {  // canvases read the theme tokens only when they draw
    [window.drawPortfolioDemand, window.drawNetworkCapacity, drawForecast, typeof drawChart === 'function' ? drawChart : null]
      .forEach(draw => { try { if (draw) draw(); } catch (_) { /* a chart whose data has not loaded yet */ } });
  }

  function setupTheme() {
    const button = $('theme-toggle');
    const label = () => button.setAttribute('aria-label', isDark() ? 'Switch to light mode' : 'Switch to dark mode');
    label();
    button.addEventListener('click', () => {
      const next = isDark() ? 'light' : 'dark';
      document.documentElement.dataset.theme = next;
      try { localStorage.setItem('theme', next); } catch (_) { /* private mode: the choice lasts for this visit */ }
      label();
      redrawCharts();
    });
    matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { label(); redrawCharts(); });
  }

  function setupShell() {
    setupTheme();
    $('menu-toggle').addEventListener('click', () => {
      const open = !document.body.classList.contains('menu-open');
      document.body.classList.toggle('menu-open', open);
      $('scrim').hidden = !open;
      $('menu-toggle').setAttribute('aria-expanded', String(open));
    });
    $('scrim').addEventListener('click', () => $('menu-toggle').click());
    document.querySelectorAll('nav button').forEach(button => { button.onclick = () => showView(button.dataset.view); });
    document.querySelectorAll('[data-go]').forEach(element => element.addEventListener('click', event => {
      event.preventDefault();
      showView(element.dataset.go);
    }));
    window.addEventListener('hashchange', () => showView(location.hash.slice(1)));
    document.querySelectorAll('.segmented').forEach(group => group.addEventListener('click', event => {
      const button = event.target.closest('[data-plan]');
      if (!button) return;
      group.querySelectorAll('[data-plan]').forEach(b => b.setAttribute('aria-checked', String(b === button)));
      group.dispatchEvent(new CustomEvent('planchange', {detail: button.dataset.plan}));
    }));
  }

  // ---- home ----
  function linkRow(source) {
    return story.forecast.staffing_link.find(row => row.source === source);
  }

  function renderHome() {
    const affordable = decision.actions.affordable_base_case;
    const resilient = decision.actions.lowest_risk_tested;
    const mm = decision.middle_mile_check;
    const scores = story.forecast.model_scores.filter(row => row.model !== 'QuantileP90');
    const best = scores.reduce((a, b) => Number(a.WAPE) < Number(b.WAPE) ? a : b);
    const average = scores.find(row => row.model === 'Mean20Days');
    const flexible = linkRow(RECOMMENDED_SOURCE);
    $('home-answer').textContent = decision.answer;
    $('home-kpis').innerHTML = [
      [num(mm.affordable_6_workers.orders), 'real 2023 orders replayed'],
      ['3', 'modeled Midwest sites'],
      [`${affordable.stress_cases_passed} vs ${resilient.stress_cases_passed}`, `stress tests passed of ${resilient.stress_cases_tested} (6 vs 10 workers)`],
      [num(mm.affordable_6_workers.late_caused_by_trucks), 'parcels made late by trucks with 6 workers'],
    ].map(([value, label]) => `<div><strong>${value}</strong><span>${label}</span></div>`).join('');
    const steps = [
      ['1', 'Forecast demand', 'forecast', `Seven models tested on 2023 orders. The best, ${MODEL_NAMES[best.model] || best.model}, misses by ${pct(best.WAPE, 0)} a day; a plain 20 day average misses by ${pct(average.WAPE, 0)}. Daily demand is hard to predict.`],
      ['2', 'Plan capacity', 'builder', `6 workers with overtime reach ${pct(affordable.base_on_time_share)} on time for ${money(affordable.base_modeled_cost)} but pass only ${affordable.stress_cases_passed} of ${affordable.stress_cases_tested} stress tests. Keeping temps on call gets ${pct(flexible.mean_on_time_share)} without hiring.`],
      ['3', 'Ship parcels', 'middlemile', `With 6 workers, trucks add ${num(mm.affordable_6_workers.late_caused_by_trucks)} late parcels on top of ${num(mm.affordable_6_workers.late_without_truck_delays)} from the warehouse. Fixing the ${mm.affordable_6_workers.at_risk_trucks} riskiest trucks costs ${money(mm.affordable_6_workers.truck_recovery_cost)}.`],
    ];
    $('home-journey').innerHTML = steps.map(([n, title, view, text]) => `<button type="button" class="journey-step" data-go="${view}"><span class="step-number">${n}</span><h3>${title}</h3><p>${esc(text)}</p><span class="step-link">Explore →</span></button>`).join('<span class="journey-arrow" aria-hidden="true">→</span>');
    $('home-journey').querySelectorAll('[data-go]').forEach(b => b.addEventListener('click', () => showView(b.dataset.go)));
    renderImpact();
    $('home-plan').addEventListener('planchange', event => renderPlan(event.detail));
    countUp($('home-kpis'));
    renderPlan('six');
  }

  function renderImpact() {
    const safe = linkRow('fixed_10_workers_ot2'), flexible = linkRow(RECOMMENDED_SOURCE), perfect = linkRow('oracle');
    const six = decision.middle_mile_check.affordable_6_workers, ten = decision.middle_mile_check.safe_10_workers;
    const affordable = decision.actions.affordable_base_case;
    const saved = safe.mean_total_cost - flexible.mean_total_cost;
    const perfectGain = flexible.mean_total_cost - perfect.mean_total_cost;
    const truckFixed = six.late_with_truck_delays - six.late_after_truck_recovery;
    const perTruckParcel = six.truck_recovery_cost / truckFixed;
    const perHireParcel = (ten.labor_cost - six.labor_cost) / (six.late_with_truck_delays - ten.late_with_truck_delays);
    const warehouseShare = six.late_without_truck_delays / six.late_with_truck_delays;
    const round = (value, step) => Math.round(value / step) * step;
    const real = Object.fromEntries(story.checks.real_cost.map(r => [r.plan, +r.mean_cost_real]));
    const realSaved = real.fixed_10_workers_ot2 - real.fixed_6_workers_ot2_temps4;
    const invBy = Object.fromEntries(story.inventory.policies.map(r => [r.policy, r]));
    const invBase = invBy.flat_95, invHigh = invBy.flat_99;
    const lmPlan = story.last_mile.summary.plans.find(p => p.plan === 'affordable_6_workers');
    const cards = [
      ['save', money(round(saved, 100)), 'saved every 4 weeks',
       `Keep 6 workers and have temps on call for busy days, instead of hiring 4 more permanent workers. On real 2023 demand the lean plan still shipped ${pct(flexible.mean_on_time_share)} of orders on time, against ${pct(safe.mean_on_time_share)} for the bigger team.`,
       `That is ${pct(saved / safe.mean_total_cost, 0)} cheaper, roughly ${money(round(saved * 13, 10000))} a year. At real 2023 labor costs (BLS) the gap grows to about ${money(round(realSaved, 100))} every 4 weeks.`],
      ['forecast', money(round(Math.max(perfectGain, 0), 10)), 'extra saving from a perfect forecast, per 4 weeks',
       `Even knowing next month's orders in advance would barely change the bill. Daily orders swing too much to predict well, so money spent on better forecasting tools would not pay back.`,
       'Spend on flexibility (temps, overtime) instead.'],
      ['truck', `${Math.round(perHireParcel / perTruckParcel)}x`, 'cheaper to fix a late truck than to hire',
       `Fixing a risky truck costs about ${money(perTruckParcel)} per parcel saved; hiring more workers costs about ${money(perHireParcel)}. But ${pct(warehouseShare, 0)} of late parcels already leave the warehouse late, and no truck fix can save those.`,
       'Fix staffing first, then the riskiest trucks.'],
      ['watch', `${affordable.stress_cases_passed} of ${affordable.stress_cases_tested}`, 'tough weeks the lean plan survives',
       'The lean plan works in a normal week but fails when workers are slower than usual or two people are out. Those are the two warning signs to watch.',
       'When you see them, call in temps right away.'],
      ['stock', pct(story.inventory.why_lines_ran_short_flat_95.share_bigger_than_cover, 0), 'of stockouts start with one unusually big order',
       `Holding more of everything barely helps: going from a 95% to a 99% stock target adds ${money(invHigh.average_stock_value - invBase.average_stock_value)} of stock and still leaves ${pct(invHigh.share_orders_delayed, 0)} of orders waiting. Most waits come from one big order for a slow size, or a brand-new item.`,
       'Quote longer lead times for big orders; stock new items at launch.'],
      ['carrier', `$${lmPlan.carrier_cost_per_parcel.toFixed(0)} vs $${lmPlan.cost_per_parcel.toFixed(0)}`, 'per order: parcel carrier vs own vans',
       `Each station sees too few orders to fill a van: about ${lmPlan.orders_per_van_day} a day, when a van needs about ${Math.round(lmPlan.break_even_orders_per_van_day)} to pay off.`,
       'Use a parcel carrier until a station fills a van.'],
    ];
    const icons = {save: '<path d="M12 3v18M17 7.5c0-1.9-2.2-3-5-3s-5 1.1-5 3 2.2 2.8 5 3.4 5 1.5 5 3.6-2.2 3-5 3-5-1.1-5-3"/>',
      forecast: '<path d="M3 17l6-6 4 4 8-8"/><path d="M14 7h7v7"/>', truck: '<path d="M1 6h13v10H1zM14 10h4l3 3v3h-7"/><circle cx="5" cy="18" r="2"/><circle cx="17" cy="18" r="2"/>',
      watch: '<path d="M12 3l9 16H3z"/><path d="M12 10v4M12 17h0"/>',
      stock: '<path d="M3 7l9-4 9 4v10l-9 4-9-4z"/><path d="M3 7l9 4 9-4M12 11v10"/>',
      carrier: '<path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>'};
    $('home-impact').innerHTML = cards.map(([kind, value, label, text, action]) => `<article class="impact-card ${kind}"><span class="impact-icon"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${icons[kind]}</svg></span><strong>${value}</strong><small>${label}</small><p>${esc(text)}</p><p class="impact-action">${esc(action)}</p></article>`).join('');
  }

  function renderPlan(plan) {
    const six = plan === 'six';
    const action = decision.actions[six ? 'affordable_base_case' : 'lowest_risk_tested'];
    const replay = linkRow(six ? 'fixed_6_workers_ot2' : 'fixed_10_workers_ot2');
    const truck = decision.middle_mile_check[six ? 'affordable_6_workers' : 'safe_10_workers'];
    const passAll = action.stress_cases_passed === action.stress_cases_tested;
    const rows = [
      ['Warehouse, base case', pct(action.base_on_time_share), 'units shipped on time', money(action.base_modeled_cost) + ' modeled cost, later 2023 period', action.base_on_time_share >= 0.95],
      ['Stress tests', `${action.stress_cases_passed} / ${action.stress_cases_tested}`, 'low productivity and absence cases passed', passAll ? 'Holds up in every listed case' : 'Fails when productivity drops or two workers are out', passAll],
      ['Real demand swings', pct(replay.mean_on_time_share), 'on time across 25 four week windows', `Missed the 95% target in ${pct(replay.share_missing_target, 0)} of windows · ${money(replay.mean_total_cost)} per window`, Number(replay.share_missing_target) === 0],
      ['On the trucks', num(truck.late_with_truck_delays), 'late parcels in 2023', `${num(truck.late_caused_by_trucks)} caused by trucks · ${money(truck.labor_cost)} labor for the year`, truck.late_with_truck_delays < 100],
    ];
    $('home-plan-results').innerHTML = rows.map(([label, value, unit, note, good]) => `<div class="plan-row"><small>${label}</small><strong>${value}</strong><span>${unit}</span><p><i class="pill ${good ? 'good' : 'warn'}">${good ? 'OK' : 'Risk'}</i>${esc(note)}</p></div>`).join('');
  }

  // ---- demand forecast ----
  function recentActuals(count) {
    const daily = new Map();
    portfolioData.demand_daily.filter(row => row.basis === 'retained').forEach(row => daily.set(row.date, (daily.get(row.date) || 0) + Number(row.units)));
    return [...daily].filter(([date]) => ![0, 6].includes(new Date(`${date}T12:00:00`).getDay()))
      .sort((a, b) => a[0].localeCompare(b[0])).slice(-count).map(([date, units]) => ({date, actual: units}));
  }

  function renderForecast() {
    const f = story.forecast;
    const scores = f.model_scores.filter(row => row.model !== 'QuantileP90').sort((a, b) => a.WAPE - b.WAPE);
    const best = scores[0];
    const p90 = f.summary.p90;
    $('forecast-metrics').innerHTML = [
      metric('Best model', MODEL_NAMES[best.model] || best.model, `${f.summary.backtest.origins} past forecast dates, ${f.summary.backtest.horizon_weekdays} working days each`),
      metric('Daily error (WAPE)', pct(best.WAPE), 'Typical miss on a single day', 'Weighted absolute percentage error: total absolute error over total actual units.'),
      metric('4 week total error', pct(best.Total_4w_abs_pct_error), 'Totals are far easier to predict than days'),
      metric('P90 high case', pct(p90.share_of_days_at_or_below), `of days stayed at or under it (target ${pct(p90.target, 0)})`, 'A forecast set so that 9 days in 10 should come in below it.'),
    ].join('');
    const worst = Math.max(...scores.map(row => Number(row.WAPE)));
    $('forecast-leaderboard').innerHTML = scores.map((row, index) => `<div class="leader-row${index === 0 ? ' best' : ''}"><span>${esc(MODEL_NAMES[row.model] || row.model)}</span><div class="mix-track"><div class="mix-fill" style="width:${(100 * row.WAPE / worst).toFixed(1)}%"></div></div><strong>${pct(row.WAPE)}</strong></div>`).join('') +
      `<p class="footnote">Bias of the best model: ${Number(best.Bias) >= 0 ? '+' : ''}${pct(best.Bias)} (positive means it forecasts too high).</p>`;
    const link = f.staffing_link.slice().sort((a, b) => a.mean_total_cost - b.mean_total_cost);
    $('forecast-link').innerHTML = link.map(row => `<tr class="${row.source === RECOMMENDED_SOURCE ? 'highlight' : ''}"><td>${esc(sourceName(row.source))}${row.source === RECOMMENDED_SOURCE ? ' <i class="pill good">Best balance</i>' : ''}</td><td>${pct(row.mean_on_time_share)}</td><td>${pct(row.share_missing_target, 0)}</td><td>${money(row.mean_total_cost)}</td></tr>`).join('');
    const flexible = linkRow(RECOMMENDED_SOURCE);
    const high = linkRow('QuantileP90 x1.0');
    $('forecast-takeaway').textContent = `Staffing to the P90 high case costs ${money(high.mean_total_cost)} per four weeks and still misses the target in ${pct(high.share_missing_target, 0)} of windows. Keeping 6 workers with overtime and temps on call costs ${money(flexible.mean_total_cost)}, reaches ${pct(flexible.mean_on_time_share)} on time and never misses. When days are this hard to predict, buy flexibility, not forecast accuracy.`;
    const actual = recentActuals(40);
    forecastPoints = [...actual, ...f.latest.map(row => ({date: row.date, forecast: +row.forecast, low: +row.low, high: +row.high, p90: +row.p90}))];
    $('forecast-chart').addEventListener('mousemove', event => {
      const canvas = $('forecast-chart');
      const i = Math.max(0, Math.min(forecastPoints.length - 1, Math.round((event.offsetX - 48) / Math.max(1, canvas.clientWidth - 60) * (forecastPoints.length - 1))));
      const d = forecastPoints[i];
      $('forecast-chart-detail').textContent = d.actual != null ? `${d.date} | Actual: ${num(d.actual)} units`
        : `${d.date} | Forecast: ${num(d.forecast)} units | 80% range: ${num(d.low)} to ${num(d.high)} | P90: ${num(d.p90)}`;
    });
    window.addEventListener('resize', drawForecast);
  }

  function drawForecast() {
    const canvas = $('forecast-chart');
    if (!forecastPoints.length || !canvas.clientWidth) return;
    const width = canvas.clientWidth, height = canvas.clientHeight, ratio = window.devicePixelRatio || 1;
    canvas.width = width * ratio; canvas.height = height * ratio;
    const ctx = canvas.getContext('2d');
    ctx.scale(ratio, ratio);
    const left = 48, right = width - 12, top = 12, bottom = height - 30;
    const max = Math.max(...forecastPoints.map(d => Math.max(d.actual || 0, d.high || 0, d.p90 || 0))) * 1.08;
    const x = i => left + (right - left) * i / (forecastPoints.length - 1);
    const y = v => bottom - v / max * (bottom - top);
    ctx.font = '11px Inter, Arial'; ctx.fillStyle = themeColor('--chart-text'); ctx.strokeStyle = themeColor('--chart-grid');
    for (let i = 0; i <= 4; i++) { const ly = bottom - (bottom - top) * i / 4; ctx.beginPath(); ctx.moveTo(left, ly); ctx.lineTo(right, ly); ctx.stroke(); ctx.fillText(num(max * i / 4), 0, ly + 4); }
    const first = forecastPoints.findIndex(d => d.forecast != null);
    ctx.fillStyle = themeColor('--chart-shade'); ctx.fillRect(x(first) - 4, top, right - x(first) + 4, bottom - top);
    ctx.beginPath();
    forecastPoints.forEach((d, i) => { if (i >= first) (i === first ? ctx.moveTo : ctx.lineTo).call(ctx, x(i), y(d.high)); });
    for (let i = forecastPoints.length - 1; i >= first; i--) ctx.lineTo(x(i), y(forecastPoints[i].low));
    ctx.closePath(); ctx.fillStyle = themeColor('--chart-band'); ctx.fill();
    const line = (key, color, dash, from = 0, to = forecastPoints.length) => {
      ctx.beginPath(); ctx.setLineDash(dash); ctx.strokeStyle = color; ctx.lineWidth = 2;
      for (let i = from; i < to; i++) (i === from ? ctx.moveTo : ctx.lineTo).call(ctx, x(i), y(forecastPoints[i][key]));
      ctx.stroke(); ctx.setLineDash([]);
    };
    line('actual', themeColor('--chart-ink'), [], 0, first);
    line('forecast', themeColor('--chart-a'), [], first);
    line('p90', themeColor('--amber'), [5, 4], first);
    ctx.fillStyle = themeColor('--chart-text');
    ctx.fillText('Forecast →', x(first) + 6, top + 14);
    const step = Math.max(1, Math.ceil(forecastPoints.length / (width < 600 ? 4 : 8)));
    forecastPoints.forEach((d, i) => { if (i % step === 0) ctx.fillText(d.date.slice(5), x(i) - 12, height - 8); });
  }

  // ---- middle mile ----
  function renderMiddleMile(plan) {
    const mm = story.middle_mile;
    const plans = Object.fromEntries(mm.summary.plans.map(row => [row.plan, row]));
    const selected = plans[plan];
    $('mm-metrics').innerHTML = [
      metric('Late parcels', num(selected.late_with_truck_delays), `of ${num(selected.orders)} orders in 2023`),
      metric('Caused by trucks', num(selected.late_caused_by_trucks), 'On time leaving the site, late because of a truck', 'Parcels that would have arrived on time if every truck ran on schedule.'),
      metric('At-risk trucks', num(selected.at_risk_trucks), 'Departures that made a parcel late'),
      metric('Cost to fix them', money(selected.truck_recovery_cost), selected.late_after_truck_recovery ? `Still leaves ${num(selected.late_after_truck_recovery)} late parcels, ${num(selected.late_without_truck_delays)} of them from the warehouse` : 'Every truck-caused late parcel is recovered', 'Cheapest recovery per truck: a second truck or moving parcels. Hypothetical cost units.'),
    ].join('');
    const most = Math.max(...mm.summary.plans.map(row => row.late_with_truck_delays));
    const label = {affordable_6_workers: '6 workers + overtime', safe_10_workers: '10 workers + overtime'};
    $('mm-bars').innerHTML = mm.summary.plans.map(row => `<div class="compare-row${row.plan === plan ? ' selected' : ''}"><span>${label[row.plan]}</span><div class="stack"><i class="teal" style="width:${(100 * row.late_without_truck_delays / most).toFixed(1)}%" title="Warehouse: ${num(row.late_without_truck_delays)}"></i><i class="amber" style="width:${(100 * row.late_caused_by_trucks / most).toFixed(1)}%" title="Trucks: ${num(row.late_caused_by_trucks)}"></i></div><strong>${num(row.late_with_truck_delays)}</strong></div>`).join('');
    const trucks = mm.at_risk_trucks.filter(row => row.plan === plan);
    $('mm-truck-count').textContent = `${trucks.length} trucks`;
    const net = mm.network, place = id => { const n = net.sites[id] || net.sort_centers[id] || net.stations[id]; return placeName(id, n.name.replace(/ \(.*\)/, '')); };
    const lane = value => value.split('>').map(place).join(' → ');
    $('mm-trucks').innerHTML = trucks.slice(0, 12).map(row => `<tr><td>${esc(lane(row.lane))}</td><td>${esc(row.departure.slice(0, 16))}</td><td>${Number(row.delay_hours).toFixed(1)} h</td><td>${num(row.parcels_on_board)}</td><td><strong>${num(row.late_parcels_caused)}</strong></td><td><i class="pill">${esc(row.best_option)}</i></td><td>${money(row.cost)}</td></tr>`).join('');
    renderMap(plan);
    const six = plans.affordable_6_workers, ten = plans.safe_10_workers;
    $('mm-takeaway').textContent = `Most late parcels with 6 workers (${num(six.late_without_truck_delays)} of ${num(six.late_with_truck_delays)}) leave the warehouse late, so no truck fix can save them. Trucks add ${num(six.late_caused_by_trucks)} more, and recovering them costs ${money(six.truck_recovery_cost)}, a small fraction of the ${money(ten.labor_cost - six.labor_cost)} labor gap between the plans. With 10 workers only ${num(ten.late_with_truck_delays)} parcels are late, all from trucks, and real 2023 snow and heavy rain cause ${num(ten.late_caused_by_weather)} of them (${num(six.late_caused_by_weather)} with 6 workers).`;
  }

  function renderMap(plan) {
    const mm = story.middle_mile, net = mm.network;
    const nodes = {};
    [['site', net.sites], ['sort', net.sort_centers], ['station', net.stations]].forEach(([kind, group]) =>
      Object.entries(group).forEach(([id, n]) => { nodes[id] = {...n, id, kind}; }));
    const lanes = new Map();
    const lane = (from, to) => { const key = `${from}>${to}`; if (!lanes.has(key)) lanes.set(key, {key, from, to, orders: 0, late: 0}); return lanes.get(key); };
    mm.routes.forEach(route => {
      const sort = net.stations[route.station].sort_center;
      lane(route.site, sort).orders += Number(route.orders);
      lane(sort, route.station).orders += Number(route.orders);
    });
    mm.at_risk_trucks.filter(row => row.plan === plan).forEach(row => { if (lanes.has(row.lane)) lanes.get(row.lane).late += Number(row.late_parcels_caused); });
    const all = Object.values(nodes), H = 520;
    // a schematic, not a to-scale map: the Chicago area sites sit too close together to read at true scale
    const columns = {site: 240, sort: 470, station: 700};
    Object.keys(columns).forEach(kind => {
      const group = all.filter(n => n.kind === kind).sort((a, b) => b.lat - a.lat);
      group.forEach((n, i) => { n.x = columns[kind]; n.y = H * (i + 1) / (group.length + 1); });
    });
    const X = n => n.x, Y = n => n.y;
    const maxOrders = Math.max(...[...lanes.values()].map(l => l.orders)), maxLate = Math.max(1, ...[...lanes.values()].map(l => l.late));
    const color = late => late === 0 ? 'var(--lane-idle)' : late / maxLate > .5 ? 'var(--red)' : 'var(--amber)';
    const name = id => placeName(id, nodes[id].name.replace(/ \(.*\)/, ''));
    const lines = [...lanes.values()].sort((a, b) => a.late - b.late).map(l => {
      const a = nodes[l.from], b = nodes[l.to];
      const mid = (X(a) + X(b)) / 2;
      return `<path class="lane" data-key="${esc(l.key)}" d="M${X(a)},${Y(a).toFixed(1)} C${mid},${Y(a).toFixed(1)} ${mid},${Y(b).toFixed(1)} ${X(b)},${Y(b).toFixed(1)}" fill="none" style="stroke:${color(l.late)}" stroke-width="${(2 + 14 * l.orders / maxOrders).toFixed(1)}" tabindex="0"><title>${esc(name(l.from))} to ${esc(name(l.to))}</title></path>`;
    }).join('');
    const marker = n => n.kind === 'site' ? `<rect x="${X(n) - 8}" y="${Y(n) - 8}" width="16" height="16" rx="4" class="node site"/>`
      : n.kind === 'sort' ? `<circle cx="${X(n)}" cy="${Y(n)}" r="9" class="node sort"/>` : `<circle cx="${X(n)}" cy="${Y(n)}" r="7" class="node station"/>`;
    const label = n => n.kind === 'sort' ? `<text x="${X(n)}" y="${Y(n) - 16}" text-anchor="middle" class="node-label sort">${esc(name(n.id))}</text>`
      : `<text x="${X(n) + (n.kind === 'site' ? -16 : 16)}" y="${Y(n) + 5}" text-anchor="${n.kind === 'site' ? 'end' : 'start'}" class="node-label ${n.kind}">${esc(name(n.id))}</text>`;
    const heads = [['WAREHOUSES', 170], ['SORT CENTERS', 470], ['DELIVERY STATIONS', 760]].map(([t, x]) => `<text x="${x}" y="28" text-anchor="middle" class="map-head">${t}</text>`).join('');
    const labels = heads + all.map(n => `<g>${marker(n)}${label(n)}</g>`).join('');
    $('mm-map').innerHTML = `<g>${lines}</g><g>${labels}</g>`;
    const show = key => {
      const l = lanes.get(key);
      $('mm-map').querySelectorAll('.lane').forEach(el => el.classList.toggle('dim', el.dataset.key !== key));
      $('mm-map-detail').textContent = `${name(l.from)} → ${name(l.to)}: ${num(l.orders)} orders in 2023 · ${num(l.late)} parcels made late by its trucks with this plan`;
    };
    $('mm-map').querySelectorAll('.lane').forEach(el => {
      ['mouseenter', 'focus', 'click'].forEach(type => el.addEventListener(type, () => show(el.dataset.key)));
      el.addEventListener('mouseleave', () => $('mm-map').querySelectorAll('.lane').forEach(x => x.classList.remove('dim')));
    });
    const worst = [...lanes.values()].sort((a, b) => b.late - a.late)[0];
    $('mm-map-detail').textContent = worst.late ? `Worst lane with this plan: ${name(worst.from)} → ${name(worst.to)}, ${num(worst.late)} parcels made late. Hover or tap any lane.` : 'No lane makes parcels late with this plan. Hover or tap any lane.';
  }

  function countUp(container) {
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    container.querySelectorAll('strong').forEach(el => {
      const text = el.textContent, match = text.match(/^[\d,]+$/);
      if (!match) return;
      const target = Number(text.replaceAll(',', '')), start = performance.now();
      const step = now => {
        const t = Math.min(1, (now - start) / 900);
        el.textContent = num(Math.round(target * (1 - Math.pow(1 - t, 3))));
        if (t < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    });
  }


  // ---- process control ----
  function controlChart(points, value, opts) {  // points with value(), limits {center, ucl, lcl} or per point ucl, an optional spec line
    const {W, top, height, ymax, fmt, ucl, lcl, center, usl, label, tag = ''} = opts, L = 56, R = 16;
    const X = i => L + i / Math.max(1, points.length - 1) * (W - L - R), Y = v => top + height - Math.min(v, ymax) / ymax * height;
    const grid = [0, ymax / 2, ymax].map(t => `<line class="inv-axis" x1="${L}" x2="${W - R}" y1="${Y(t)}" y2="${Y(t)}"/><text class="inv-text" x="${L - 8}" y="${Y(t) + 4}" text-anchor="end">${fmt(t)}</text>`).join('');
    const limit = (v, cls) => typeof v === 'number' ? `<line class="${cls}" x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}"/>` : '';
    const stepUcl = Array.isArray(ucl) ? `<polyline class="pc-limit" fill="none" points="${ucl.map((u, i) => `${X(i)},${Y(u)}`).join(' ')}"/>` : limit(ucl, 'pc-limit');
    const line = `<polyline class="pc-line" points="${points.map((p, i) => `${X(i)},${Y(value(p))}`).join(' ')}"/>`;
    const dots = points.map((p, i) => `<circle class="pc-dot${p.out ? ' out' : ''}" data-c="${tag}" data-i="${i}" cx="${X(i)}" cy="${Y(value(p))}" r="${p.out ? 4 : 3}" tabindex="0"/>`).join('');
    return `${grid}<text class="inv-text" x="${L}" y="${top - 8}">${label}</text>${line}${limit(center, 'pc-center')}${stepUcl}${limit(lcl, 'pc-limit')}${limit(usl, 'pc-usl')}${dots}`;
  }

  function hover(svg, detail, text) {
    svg.querySelectorAll('.pc-dot').forEach(dot => ['mouseenter', 'focus', 'click'].forEach(type => dot.addEventListener(type, () => { detail.textContent = text(+dot.dataset.i, dot); })));
  }

  function renderProcessControl(plan) {
    const pc = story.process_control, pk = pc.packing, lp = pc.late_parcels[plan], six = pc.late_parcels.affordable_6_workers;
    const means = Object.values(pk.person_means);
    $('pc-metrics').innerHTML = [
      metric('Packing capability (Ppk)', pk.ppk.toFixed(2), `Against the ${pk.usl_seconds} s per unit the base case allows; 1.33 is the usual target`, 'Ppk: distance from the average to the limit, in units of 3 standard deviations of all boxes. Cpk uses the short-term spread instead and comes out at ' + pk.cpk.toFixed(2) + '.'),
      metric('Boxes over the limit', pct(pk.share_over_usl, 0), `${num(pk.boxes)} one-item boxes, ${pk.people} packers`),
      metric('Out-of-control days', `${lp.days_above_limit} of ${lp.days}`, 'Days with a late share above the p-chart limit'),
      metric('Late parcels on those days', pct(lp.late ? lp.late_on_those_days / lp.late : 0, 0), `${num(lp.late_on_those_days)} of ${num(lp.late)} late parcels`),
    ].join('');
    $('pc-imr-sub').textContent = `Packing-station seconds for each one-item box, in recording order (${num(pk.boxes)} boxes, ${pk.people} people); limits from the average moving range`;
    const box = pk.points.map(p => ({...p, out: p.seconds > pk.ucl || p.seconds < pk.lcl}));
    const mr = box.slice(1).map((p, i) => ({seconds: Math.abs(p.seconds - box[i].seconds), person: p.person})).map(p => ({...p, out: p.seconds > pk.mr_ucl}));
    const ymax = Math.ceil(Math.max(...box.map(p => p.seconds)) / 20) * 20, secs = v => `${Math.round(v)} s`;
    $('pc-imr').innerHTML = controlChart(box, p => p.seconds, {W: 900, top: 26, height: 250, ymax, fmt: secs, ucl: pk.ucl, lcl: pk.lcl, center: pk.mean_seconds, usl: pk.usl_seconds, label: 'Individuals (seconds per box)'})
      + controlChart(mr, p => p.seconds, {W: 900, top: 330, height: 80, ymax: Math.ceil(Math.max(...mr.map(p => p.seconds)) / 20) * 20, fmt: secs, ucl: pk.mr_ucl, center: pk.mr_bar, label: 'Moving range', tag: 'mr'});
    hover($('pc-imr'), $('pc-imr-detail'), (i, dot) => {
      const inMr = dot.dataset.c === 'mr', p = inMr ? mr[i] : box[i];
      return inMr ? `Change from the box before: ${p.seconds.toFixed(1)} s (packer ${p.person})${p.out ? ', above the limit' : ''}`
        : `Box ${i + 1}, packer ${p.person}: ${p.seconds.toFixed(1)} s${p.out ? ', beyond the control limits' : ''}${p.seconds > pk.usl_seconds ? `, over the ${pk.usl_seconds} s the planner allows` : ''}`;
    });
    const days = lp.points.map(d => ({...d, p: d.late / d.parcels, out: d.above}));
    const pmax = Math.max(.1, Math.ceil(Math.max(...six.points.map(d => d.late / d.parcels).filter(v => v < 1)) * 10) / 10);
    $('pc-p').innerHTML = controlChart(days, d => d.p, {W: 900, top: 26, height: 240, ymax: pmax, fmt: v => pct(v, 0), ucl: days.map(d => d.ucl), center: lp.p_bar, label: 'Late share of the day\'s parcels'});
    hover($('pc-p'), $('pc-p-detail'), i => { const d = days[i]; return `Promised ${d.date}: ${num(d.late)} of ${num(d.parcels)} parcels late (${pct(d.p, 1)}), limit ${pct(d.ucl, 1)}${d.out ? ', a special-cause day' : ''}`; });
    const rates = pk.ppk_at_stress_rates;
    $('pc-takeaway').textContent = `Packing time is not in statistical control: ${pk.points_beyond_limits} of ${num(pk.boxes)} boxes fall outside the limits, and packer averages range from ${Math.min(...means).toFixed(0)} to ${Math.max(...means).toFixed(0)} seconds, so who packs is the biggest special cause. Against the ${pk.usl_seconds} s per unit of the 40 units/hour base case, ${pct(pk.share_over_usl, 0)} of boxes run over (Ppk ${pk.ppk.toFixed(2)}); even the 30 units/hour stress case only reaches Ppk ${rates['30'].toFixed(2)}. That is why the plan keeps temps on call, and why standard work and coaching for the slowest packers come before any headcount change. Late parcels are not noise either: with 6 workers, ${six.days_above_limit} of ${six.days} days hold ${pct(six.late_on_those_days / six.late, 0)} of all late parcels, ${pct(six.late_on_those_days_that_were_peaks / six.late_on_those_days, 0)} of them on peak days (at least half again the usual volume) and only ${num(six.weather_late_on_those_days)} from weather. Call in temps when the forecast shows a peak day, and investigate any day above the limit.`;
  }


  // ---- who packs: block ANOVA, Tukey and the coaching simulator ----
  const pval = p => p < 0.001 ? '< 0.001' : p.toFixed(3);
  const signedMoney = v => `${v < 0 ? '−' : ''}${money(Math.abs(v))}`;
  function residualPlots(res) {
    const n = res.length, W = 440, L = 40, R = 12;
    const q = i => normalQuantile((i + 1 - 0.3) / (n + 0.4));
    const lim = Math.ceil(Math.max(...res.map(Math.abs), 3));
    const X = v => L + (v + lim) / (2 * lim) * (W - L - R), Y = z => 30 + (3.2 - z) / 6.4 * 190;
    const grid = [-3, -2, -1, 0, 1, 2, 3].map(z => `<line class="inv-axis" x1="${L}" x2="${W - R}" y1="${Y(z)}" y2="${Y(z)}"/><text class="inv-text" x="${L - 6}" y="${Y(z) + 4}" text-anchor="end">${z}</text>`).join('');
    const xt = [-lim, 0, lim].map(v => `<text class="inv-text" x="${X(v)}" y="240" text-anchor="middle">${v}</text>`).join('');
    $('pc-npp').innerHTML = `<text class="inv-label" x="${L}" y="16">Normal probability plot (standardized residuals)</text>${grid}${xt}<line class="pc-usl" x1="${X(-3.2)}" y1="${Y(-3.2)}" x2="${X(3.2)}" y2="${Y(3.2)}"/>${res.map((v, i) => `<circle class="pc-dot" r="2" cx="${X(v)}" cy="${Y(q(i))}"/>`).join('')}`;
    const bins = []; for (let a = -lim; a < lim; a += 0.5) bins.push({a, c: res.filter(v => v >= a && v < a + 0.5).length});
    const most = Math.max(...bins.map(b => b.c)), HX = v => L + (v + lim) / (2 * lim) * (W - L - R), HY = c => 180 - c / most * 150;
    $('pc-hist').innerHTML = `<text class="inv-label" x="${L}" y="16">Histogram</text><line class="inv-axis" x1="${L}" x2="${W - R}" y1="180" y2="180"/>${bins.map(b => b.c ? `<rect class="pc-bar" x="${HX(b.a) + 1}" y="${HY(b.c)}" width="${HX(b.a + 0.5) - HX(b.a) - 2}" height="${180 - HY(b.c)}"/>` : '').join('')}${[-lim, 0, lim].map(v => `<text class="inv-text" x="${HX(v)}" y="200" text-anchor="middle">${v}</text>`).join('')}`;
  }

  function normalQuantile(p) {  // Acklam's approximation, good to about 1e-9
    const a = [-39.69683028665376, 220.9460984245205, -275.9285104469687, 138.357751867269, -30.66479806614716, 2.506628277459239],
      b = [-54.47609879822406, 161.5858368580409, -155.6989798598866, 66.80131188771972, -13.28068155288572],
      c = [-0.007784894002430293, -0.3223964580411365, -2.400758277161838, -2.549732539343734, 4.374664141464968, 2.938163982698783],
      d = [0.007784695709041462, 0.3224671290700398, 2.445134137142996, 3.754408661907416];
    const tail = q => (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
    if (p < 0.02425) return tail(Math.sqrt(-2 * Math.log(p)));
    if (p > 1 - 0.02425) return -tail(Math.sqrt(-2 * Math.log(1 - p)));
    const q = p - 0.5, r = q * q;
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
  }

  function renderPackerStudy() {
    const ps = story.process_control.packer_study, A = ps.anova;
    $('pc-anova-sub').textContent = `${num(ps.boxes)} real boxes with 1 to 5 items from ${ps.packers} packers. Packer is the factor; box size is the block, because bigger boxes take longer for everyone.`;
    const row = (name, r, cls = '') => `<tr class="${cls}"><td>${name}</td><td>${r.df}</td><td>${num(r.adj_ss)}</td><td>${r.adj_ms !== undefined ? num(r.adj_ms) : ''}</td><td>${r.f !== undefined ? r.f.toFixed(2) : ''}</td><td>${r.p !== undefined ? pval(r.p) : ''}</td></tr>`;
    $('pc-anova').innerHTML = row('Packer', A.packer) + row('Box size (block)', A.box_size) + row('Error', A.error) + row('Lack-of-fit', A.lack_of_fit, 'indent') + row('Pure error', A.pure_error, 'indent') + row('Total', A.total);
    $('pc-model').innerHTML = `<tr><td>${ps.s.toFixed(2)}</td><td>${pct(ps.r_sq, 1)}</td><td>${pct(ps.r_sq_adj, 1)}</td></tr>`;
    residualPlots(ps.residuals);
    $('pc-anova-note').innerHTML = `<b>Reject H<sub>0</sub>.</b> Packer: F = ${A.packer.f.toFixed(1)}, P ${pval(A.packer.p)} &lt; 0.05, so who packs changes packing time even after removing the effect of box size (F = ${A.box_size.f.toFixed(1)}). Two honest checks: lack-of-fit is significant (P ${pval(A.lack_of_fit.p)}), so the gap between packers is not the same for every box size, and the residuals are right-skewed (skew ${ps.residual_skew}). Refitting on log seconds gives the same answer (F = ${ps.log_check.packer_f.toFixed(1)}, P ${pval(ps.log_check.packer_p)}).`;
    const median = ps.coaching.median_packer, means = ps.means;
    $('pc-tukey').innerHTML = means.map(m => `<tr class="${m.packer === median ? 'highlight' : ''}"><td>${m.packer}${m.packer === median ? ' <i class="pill">median</i>' : ''}</td><td>${m.boxes}</td><td>${m.adjusted_mean.toFixed(1)} s</td><td><b style="letter-spacing:4px">${m.group}</b></td></tr>`).join('');
    const W = 440, L = 58, R = 40, rowH = 26, top = 20, hi = Math.ceil(Math.max(...means.map(m => m.adjusted_mean)) / 20) * 20, lo = Math.floor(Math.min(...means.map(m => m.adjusted_mean)) / 20) * 20 - 20;
    const X = v => L + (v - lo) / (hi - lo) * (W - L - R), medianMean = means.find(m => m.packer === median).adjusted_mean;
    const ticks = []; for (let v = lo; v <= hi; v += 20) ticks.push(`<line class="inv-axis" x1="${X(v)}" x2="${X(v)}" y1="${top}" y2="${top + means.length * rowH}"/><text class="inv-text" x="${X(v)}" y="${top + means.length * rowH + 18}" text-anchor="middle">${v} s</text>`);
    $('pc-means').innerHTML = ticks.join('') + `<line class="pc-center" x1="${X(medianMean)}" x2="${X(medianMean)}" y1="${top - 6}" y2="${top + means.length * rowH}"/>` + means.map((m, i) => {
      const y = top + i * rowH + rowH / 2;
      return `<text class="inv-text" x="${L - 8}" y="${y + 4}" text-anchor="end">${m.packer}</text><line class="pc-line" x1="${X(lo)}" x2="${X(m.adjusted_mean)}" y1="${y}" y2="${y}"/><circle class="pc-dot" cx="${X(m.adjusted_mean)}" cy="${y}" r="5"/><text class="inv-label" x="${X(m.adjusted_mean) + 10}" y="${y + 4}">${m.group}</text>`;
    }).join('');
    renderCoaching(true);
  }

  let coached = new Set();
  function coachingRows() {
    const ps = story.process_control.packer_study, c = ps.coaching, close = +$('pc-close').value / 100, cost = Math.max(0, +$('pc-cost').value || 0);
    const median = ps.means.find(m => m.packer === c.median_packer);
    const pairP = (a, b) => (ps.pairs.find(p => (p.a === a && p.b === b) || (p.a === b && p.b === a)) || {p_adj: 1}).p_adj;
    return ps.means.filter(m => m.packer !== c.median_packer).map(m => {
      const gap = m.adjusted_mean - median.adjusted_mean, proven = gap > 0 && pairP(m.packer, c.median_packer) < 0.05;
      const seconds = proven ? gap * close : 0, hours = seconds * c.boxes_per_packer / 3600, saved = hours * c.hourly_cost;
      return {packer: m.packer, gap, proven, seconds, hours, saved, net: saved - cost, cost, p: pairP(m.packer, c.median_packer)};
    });
  }

  function renderCoaching(first) {
    const ps = story.process_control.packer_study, pk = story.process_control.packing, c = ps.coaching, rows = coachingRows();
    $('pc-close-out').textContent = `${$('pc-close').value}%`;
    if (first) {
      $('pc-picks').innerHTML = rows.map(r => `<button type="button" aria-pressed="false" data-packer="${r.packer}">${r.packer}<small>${r.gap >= 0 ? '+' : '−'}${Math.abs(r.gap).toFixed(1)} s vs median</small></button>`).join('');
      $('pc-picks').querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
        coached.has(b.dataset.packer) ? coached.delete(b.dataset.packer) : coached.add(b.dataset.packer);
        renderCoaching();
      }));
      ['input', 'change'].forEach(type => { $('pc-close').addEventListener(type, () => renderCoaching()); $('pc-cost').addEventListener(type, () => renderCoaching()); });
      $('pc-reset').addEventListener('click', () => { coached = new Set(); $('pc-close').value = 50; $('pc-cost').value = 400; renderCoaching(); });
    }
    $('pc-picks').querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(coached.has(b.dataset.packer))));
    const picked = rows.filter(r => coached.has(r.packer)), sum = k => picked.reduce((t, r) => t + r[k], 0);
    // capability after coaching: shift each coached packer's one-item boxes by the seconds that coaching saves
    const cut = Object.fromEntries(picked.map(r => [r.packer, r.seconds]));
    const after = pk.points.map(p => p.seconds - (cut[p.person] || 0)), mean = after.reduce((t, v) => t + v, 0) / after.length;
    const sd = Math.sqrt(after.reduce((t, v) => t + (v - mean) ** 2, 0) / (after.length - 1)), ppk = (pk.usl_seconds - mean) / (3 * sd);
    const over = after.filter(v => v > pk.usl_seconds).length / after.length;
    $('pc-sim').innerHTML = [
      metric('Packers coached', `${picked.length}`, `${picked.filter(r => r.proven).length} proven slower than the median packer`),
      metric('Labor saved', money(sum('saved')), `${num(Math.round(sum('hours')))} packing hours on ${num(c.boxes_per_packer)} boxes each`, `Each packer is assumed to pack one worker's share of the 2023 orders (${num(c.orders_2023)} ÷ ${c.base_workers} workers), at the planner's $${c.hourly_cost} an hour.`),
      metric('Net after coaching cost', `<span class="${sum('net') < 0 ? 'pc-bad' : sum('net') > 0 ? 'pc-good' : ''}">${signedMoney(sum('net'))}</span>`, `${money(sum('cost'))} to coach`),
      metric('Packing Ppk after', ppk.toFixed(2), `Was ${pk.ppk.toFixed(2)}; boxes over ${pk.usl_seconds} s: ${pct(pk.share_over_usl, 0)} → ${pct(over, 0)}`, 'Recomputed on the one-item boxes, with each coached packer\'s times lowered by the seconds coaching saves.'),
    ].join('');
    const unproven = picked.filter(r => !r.proven), msg = $('pc-sim-msg');
    if (!picked.length) { msg.className = 'pc-note'; msg.textContent = 'Pick one or more packers to run a coaching plan. The ranking below shows what each one is worth on its own.'; }
    else if (sum('net') > 0) { msg.className = 'pc-note good'; msg.innerHTML = `<b>Value created:</b> this plan nets ${money(sum('net'))} on the 2023 volume.${unproven.length ? ` ${unproven.map(r => r.packer).join(', ')} ${unproven.length > 1 ? 'are' : 'is'} not proven slower than the median packer, so ${unproven.length > 1 ? 'they add' : 'it adds'} cost but no counted saving.` : ''}`; }
    else { msg.className = 'pc-note bad'; msg.innerHTML = `<b>Value destroyed:</b> this plan loses ${money(-sum('net'))}.${unproven.length ? ` ${unproven.map(r => r.packer).join(', ')}: Tukey did not prove ${unproven.length > 1 ? 'them' : 'this packer'} slower than the median, so you pay for coaching without a reliable saving.` : ' The proven gap is too small to pay back the coaching cost at this share of the gap closed.'}`; }
    const ranked = rows.slice().sort((a, b) => b.net - a.net);
    $('pc-rank').innerHTML = ranked.map((r, i) => `<tr class="${coached.has(r.packer) ? 'pc-picked' : ''}"><td>${i + 1}</td><td>${r.packer}</td><td>${r.gap >= 0 ? '+' : '−'}${Math.abs(r.gap).toFixed(1)} s</td><td>${r.proven ? `<span class="pc-good">Yes</span> (P ${pval(r.p)})` : `<span class="pc-bad">No</span> (P ${pval(r.p)})`}</td><td>${r.hours.toFixed(1)}</td><td>${money(r.saved)}</td><td class="${r.net < 0 ? 'pc-bad' : 'pc-good'}">${signedMoney(r.net)}</td></tr>`).join('');
    const close = +$('pc-close').value / 100, cost = Math.max(0, +$('pc-cost').value || 0);
    const pays = rows.filter(r => r.net > 0).map(r => r.packer), top = rows.filter(r => r.proven).sort((a, b) => b.gap - a.gap)[0];
    const breakEven = top ? cost / (top.gap * c.boxes_per_packer / 3600 * c.hourly_cost) : null;
    $('pc-sim-foot').textContent = `Real: packing times, Tukey results and the 2023 order count. Assumed: coaching closes ${pct(close, 0)} of the gap, costs ${money(cost)} per packer, and each packer packs one worker's share of the orders. ${pays.length ? `At these settings coaching pays for ${pays.join(', ')}.` : 'At these settings coaching pays for no one in labor alone; its value is the capability gain, fewer boxes over the planner\'s time.'}${top ? ` Coaching ${top.packer}, the slowest proven packer, pays back once it closes ${breakEven <= 1 ? pct(breakEven, 0) : 'more than 100%'} of the gap.` : ''}`;
  }

  // ---- inventory ----
  const POLICY_NAMES = {by_class: 'By class (A 99%, B 95%, C 90%)', by_class_lean: 'By class, lean (A 95%, B 90%, C 80%)',
    flat_95_reliable_supplier: '95%, supplier always on time', flat_95_monthly_replan: '95%, re-planned every month'};
  const policyName = p => POLICY_NAMES[p] || p.replace(/^flat_(\d+)$/, '$1% target for every item');

  function renderInventory() {
    const inv = story.inventory, rows = inv.policies, why = inv.why_lines_ran_short_flat_95;
    const by = Object.fromEntries(rows.map(r => [r.policy, r]));
    const base = by.flat_95, high = by.flat_99;
    $('inv-metrics').innerHTML = [
      metric('Orders waiting for stock', pct(base.share_orders_delayed, 0), 'With a 95% target, July to October', 'Orders where at least one item was out of stock at the site, so the order waited for the next delivery from the supplier.'),
      metric('Stock held', money(base.average_stock_value), `${base.months_of_supply.toFixed(1)} months of sales; US retailers held ${story.checks.fred.series.RETAILIRSA.average_2023.toFixed(1)} in 2023`, 'Months of stock: average stock divided by a month of sales. The US figure is the FRED retail inventories to sales ratio.'),
      metric('Cost to hold it', money(base.holding_cost_per_year), 'A year, at an assumed 25% of value'),
      metric('Orders with a brand-new item', pct(inv.test_orders_with_a_new_item, 1), 'No history to stock from, so they always wait'),
    ].join('');
    const W = 900, H = 380, L = 70, R = 30, T = 24, B = 50;
    const xs = rows.map(r => r.average_stock_value), ys = rows.map(r => r.share_orders_delayed);
    const x0 = Math.min(...xs) * 0.9, x1 = Math.max(...xs) * 1.05, y1 = Math.max(...ys) * 1.1;
    const X = v => L + (v - x0) / (x1 - x0) * (W - L - R), Y = v => H - B - v / y1 * (H - T - B);
    const flat = rows.filter(r => /^flat_\d+$/.test(r.policy)).sort((a, b) => a.average_stock_value - b.average_stock_value);
    const ticks = [0, .1, .2, .3, .4].filter(t => t <= y1);
    const grid = ticks.map(t => `<line class="inv-axis" x1="${L}" x2="${W - R}" y1="${Y(t)}" y2="${Y(t)}"/><text class="inv-text" x="${L - 10}" y="${Y(t) + 4}" text-anchor="end">${pct(t, 0)}</text>`).join('');
    const xt = [0.5e6, 1e6, 1.5e6, 2e6].filter(v => v > x0 && v < x1).map(v => `<text class="inv-text" x="${X(v)}" y="${H - B + 22}" text-anchor="middle">$${(v / 1e6).toFixed(1)}M</text>`).join('');
    const line = `<polyline class="inv-line" points="${flat.map(r => `${X(r.average_stock_value)},${Y(r.share_orders_delayed)}`).join(' ')}"/>`;
    const dots = rows.map((r, i) => `<circle class="inv-dot ${/^flat_\d+$/.test(r.policy) ? 'flat' : 'other'}" data-i="${i}" cx="${X(r.average_stock_value)}" cy="${Y(r.share_orders_delayed)}" r="8" tabindex="0"><title>${esc(policyName(r.policy))}</title></circle>`).join('');
    const labels = flat.map(r => `<text class="inv-label" x="${X(r.average_stock_value) + 12}" y="${Y(r.share_orders_delayed) - 10}">${r.policy.replace('flat_', '')}%</text>`).join('');
    $('inv-chart').innerHTML = `${grid}${xt}<text class="inv-text" x="${(L + W - R) / 2}" y="${H - 8}" text-anchor="middle">Average stock value</text><text class="inv-text" x="16" y="${T}" >Orders waiting</text>${line}${dots}${labels}`;
    const show = i => { const r = rows[i]; $('inv-chart-detail').textContent = `${policyName(r.policy)}: ${pct(r.share_orders_delayed, 1)} of orders wait, ${money(r.average_stock_value)} of stock, ${money(r.holding_cost_per_year)} a year to hold`; };
    $('inv-chart').querySelectorAll('.inv-dot').forEach(dot => ['mouseenter', 'focus', 'click'].forEach(type => dot.addEventListener(type, () => show(+dot.dataset.i))));
    const reasons = [['One big order for a slow item', why.share_bigger_than_cover, 'A single order line larger than two weeks of that item\'s normal demand'],
      ['Item had no safety stock', why.share_no_safety_stock, 'Sold so rarely before that history said hold none'],
      ['Item never sold before July', why.share_never_sold_before, 'New products and sizes']];
    $('inv-reasons').innerHTML = reasons.map(([label, share, note], i) => `<div class="leader-row${i === 0 ? ' best' : ''}" title="${esc(note)}"><span>${esc(label)}</span><div class="mix-track"><div class="mix-fill" style="width:${(100 * share).toFixed(1)}%"></div></div><strong>${pct(share, 0)}</strong></div>`).join('') +
      `<p class="footnote">${num(why.short_lines)} lines ran short out of the July to October orders.</p>`;
    $('inv-takeaway').textContent = `Raising the target from 95% to 99% cuts waiting orders from ${pct(base.share_orders_delayed, 0)} to ${pct(high.share_orders_delayed, 0)}, but adds ${money(high.average_stock_value - base.average_stock_value)} of stock (${money(high.holding_cost_per_year - base.holding_cost_per_year)} a year to hold). A perfectly reliable supplier (${pct(by.flat_95_reliable_supplier.share_orders_delayed, 0)}) and monthly re-planning (${pct(by.flat_95_monthly_replan.share_orders_delayed, 0)}) changed almost nothing. Most stockouts come from one big order for a slow size or a brand-new item, so quote a longer lead time for unusually large orders and stock new items at launch, instead of holding more of everything.`;
    $('inv-table').innerHTML = rows.slice().sort((a, b) => a.average_stock_value - b.average_stock_value).map(r => `<tr class="${r.policy === 'flat_95' ? 'highlight' : ''}"><td>${esc(policyName(r.policy))}</td><td>${pct(r.share_orders_delayed, 1)}</td><td>${pct(r.line_fill_rate, 1)}</td><td>${r.months_of_supply.toFixed(2)}</td><td>${money(r.average_stock_value)}</td><td>${money(r.holding_cost_per_year)}</td></tr>`).join('');
  }

  // ---- last mile ----
  function renderLastMile(plan) {
    const lm = story.last_mile, s = lm.summary.plans.find(p => p.plan === plan);
    const other = lm.summary.plans.find(p => p.plan !== plan);
    const stations = lm.by_station.filter(r => r.plan === plan);
    const net = story.middle_mile.network;
    $('lm-metrics').innerHTML = [
      metric('Parcel carrier', `$${s.carrier_cost_per_parcel.toFixed(2)}`, 'Average cost per order, assumed price'),
      metric('Running vans', `$${s.cost_per_parcel.toFixed(2)}`, 'Cheapest mix of owned and contracted vans', 'Owned vans are paid every day; contracted vans only on days they are called. The model picks the cheapest mix for each station.'),
      metric('Orders per van a day', `${s.orders_per_van_day}`, `A van needs about ${Math.round(s.break_even_orders_per_van_day)} to beat the carrier`),
      metric('Vans needed at peak', num(s.peak_vans), "Each station's busiest day, added up"),
    ].join('');
    const most = Math.max(...stations.flatMap(r => [+r.cost_per_parcel, r.carrier_cost / r.parcels]));
    $('lm-bars').innerHTML = stations.sort((a, b) => b.parcels - a.parcels).map(r => {
      const carrier = r.carrier_cost / r.parcels;
      return `<div class="compare-row"><span>${esc(placeName(r.station, net.stations[r.station].name))}</span><div class="pair-bars"><i class="amber" style="width:${(100 * r.cost_per_parcel / most).toFixed(1)}%" title="Vans: $${(+r.cost_per_parcel).toFixed(2)}"></i><i class="teal" style="width:${(100 * carrier / most).toFixed(1)}%" title="Carrier: $${carrier.toFixed(2)}"></i></div><strong>$${(+r.cost_per_parcel).toFixed(0)} / $${carrier.toFixed(0)}</strong></div>`;
    }).join('');
    $('lm-table').innerHTML = stations.map(r => `<tr><td>${esc(placeName(r.station, net.stations[r.station].name))}</td><td>${num(r.parcels)}</td><td>${num(r.median_vans)}</td><td>${num(r.peak_vans)}</td><td>$${(+r.cost_per_parcel).toFixed(2)}</td><td>$${(r.carrier_cost / r.parcels).toFixed(2)}</td><td><i class="pill ${r.cheaper_option === 'carrier' ? 'good' : ''}">${esc(r.cheaper_option)}</i></td></tr>`).join('');
    const six = lm.summary.plans.find(p => p.plan === 'affordable_6_workers'), ten = lm.summary.plans.find(p => p.plan === 'safe_10_workers');
    $('lm-takeaway').textContent = `A parcel carrier costs about $${s.carrier_cost_per_parcel.toFixed(0)} an order; running vans costs about $${s.cost_per_parcel.toFixed(0)}, because each van carries only ${s.orders_per_van_day} orders a day and needs about ${Math.round(s.break_even_orders_per_van_day)} to break even. The carrier wins at all 6 stations, saving about ${money(s.cost - s.carrier_cost)} over the 10 months of 2023 data. Revisit vans when a station's volume grows about ${(s.break_even_orders_per_van_day / s.orders_per_van_day).toFixed(1)} times. If vans were used, the lean 6 worker plan would cost about ${money(six.cost - ten.cost)} more in vans than the 10 worker plan, because late parcels arrive in bunches; that is small next to the labor saving.`;
  }

  function renderChecks() {
    const bls = story.checks.bls, lanes = story.checks.road_check, roads = story.last_mile.summary.roads;
    const rc = Object.fromEntries(story.checks.real_cost.map(r => [r.plan, r]));
    const realGap = rc.fixed_10_workers_ot2.mean_cost_real - rc.fixed_6_workers_ot2_temps4.mean_cost_real;
    const assumedGap = rc.fixed_10_workers_ot2.mean_cost_assumed - rc.fixed_6_workers_ot2_temps4.mean_cost_assumed;
    const plans = Object.fromEntries(story.middle_mile.summary.plans.map(p => [p.plan, p]));
    const six = plans.affordable_6_workers, ten = plans.safe_10_workers;
    const indy = lanes.find(l => l.lane === 'chicago_sc>indianapolis');
    const rows = [
      ['U.S. Census (Gazetteer and ACS)', 'Where last-mile customers are', 'Customers now sit at real census tract centers inside each station\'s 45 minute drive area (OpenRouteService), picked with odds matching each tract\'s population, instead of random points (some of which landed in Lake Michigan). A parcel carrier still beats vans at every station.'],
      ['Bureau of Labor Statistics (CES, JOLTS, ECEC)', 'Pay, employer costs, temp rates and turnover', `Warehouse workers earned $${bls.real_production_worker_hourly_earnings.toFixed(2)} an hour in 2023; with benefits and payroll taxes (x${bls.employer_cost_multiplier.toFixed(2)}) they cost employers about $${bls.real_regular_employer_cost.toFixed(2)}, not the $${bls.assumed_regular_hourly_cost} assumed. Temps earned $${bls.real_temp_pay.toFixed(2)}, about $${bls.real_temp_bill_rate.toFixed(2)} billed with an assumed ${bls.assumed_agency_markup}x agency markup. Rerun at those costs, temps on call beat 10 workers by ${money(realGap)} every 4 weeks, up from ${money(assumedGap)}. A 2.6% monthly quit rate means a team of ${bls.expected_quits_per_year_in_a_team_of} loses about ${Math.round(bls.expected_quits_per_year)} people a year.`],
      ['NOAA Climate Data Online', 'Truck delays', `Trucks are now slowed by real 2023 snow and heavy rain at both ends of each lane. Weather causes ${num(six.late_caused_by_weather)} of ${num(six.late_caused_by_trucks)} truck-caused late parcels with 6 workers, and ${num(ten.late_caused_by_weather)} of ${num(ten.late_caused_by_trucks)} with 10.`],
      ['OpenRouteService', 'Road distances and drive times', `Van roads run ${roads.median_road_to_straight} times the straight line, close to the 1.3 assumed, and vans now route on real roads. Trucks now drive real truck routes too: Chicago to Indianapolis takes ${(+indy.road_truck_hours).toFixed(1)} hours, not the ${(+indy.straight_line_drive_hours).toFixed(1)} a straight line suggests, leaving minutes before the station cutoff; that one lane causes most truck lateness.`],
    ];
    const f = story.checks.fred.series, lead = story.checks.fred.demand_vs_shoe_stores, fuel = story.last_mile.summary.fuel;
    const inv95 = story.inventory.policies.find(p => p.policy === 'flat_95'), inv99 = story.inventory.policies.find(p => p.policy === 'flat_99');
    const change = id => `${f[id].change_2023_vs_2022 >= 0 ? '+' : ''}${pct(f[id].change_2023_vs_2022, 1)}`;
    rows.push(
      ['FRED: diesel price', 'Van fuel cost', `US diesel averaged $${f.GASDESW.average_2023.toFixed(2)} a gallon in 2023 (${change('GASDESW')} vs 2022). Vans now pay that week's real price: about $${fuel.average_cost_per_km_2023.toFixed(2)} a km with wear, not the $${fuel.assumed_cost_per_km_before.toFixed(2)} assumed. Vans get cheaper, but a carrier still wins.`],
      ['FRED: retail inventories to sales', 'How much stock is sensible', `US retailers held ${f.RETAILIRSA.average_2023.toFixed(2)} months of sales in stock in 2023. A 95% target holds ${inv95.months_of_supply.toFixed(2)} months, about the same; a 99% target holds ${inv99.months_of_supply.toFixed(2)}, nearly double.`],
      ['FRED: labor market', 'Hiring conditions', `US warehouse jobs fell ${pct(-f.CES4349300001.change_2023_vs_2022, 1)} in 2023 and Chicago metro unemployment averaged ${f.CHIC917URN.average_2023.toFixed(1)}%, so hiring got easier, while warehousing prices rose ${change('PCU493110493110')}.`],
      ['FRED: demand and freight', 'The 2023 backdrop', `A soft freight year: Cass shipments ${change('FRGSHPUSM649NCIS')}, truck tonnage ${change('TRUCKD11')}, retail sales ${change('RSXFS')}, online share ${f.ECOMPCTSA.average_2023.toFixed(1)}%. Warehouse orders line up best with US shoe store sales 3 months later (correlation ${lead['3_months_later']}), fitting a supplier that stocks stores ahead of their season, but with only ${lead.months} months that is a hint, not proof.`],
    );
    $('real-checks').innerHTML = rows.map(r => `<tr><td><strong>${esc(r[0])}</strong></td><td>${esc(r[1])}</td><td>${esc(r[2])}</td></tr>`).join('');
  }

  // ---- Ask the planner on the public site ----
  function renderAskSaved() {
    const ask = story.ask;
    const acc = ask.accuracy;
    const line = name => acc[name] ? `${acc[name].correct} of ${acc[name].of}` : null;
    $('ask-accuracy').innerHTML = `<strong>Tested accuracy:</strong> ${acc.guided ? `${line('guided')} test questions answered correctly with base case guidance (${pct(acc.guided.share, 0)}), up from ${line('glossary')} with the glossary alone and ${line('schema_only')} with the schema only, on ${esc(ask.model)}.` : `${line('glossary')} test questions answered correctly with the business glossary (${pct(acc.glossary.share, 0)}).`}`;
    if (window.askLive) return;
    $('ask-question').disabled = true;
    $('ask-submit').disabled = true;
    $('ask-question').placeholder = 'Live questions run on the local server. Saved answers are below.';
    document.querySelector('.ask-examples').hidden = true;
    $('ask-source').textContent = `Live questions need the local server and a Gemini key (see the README). Below are saved answers from the ${ask.model} evaluation run.`;
    $('ask-saved').hidden = false;
    $('ask-saved').innerHTML = ask.examples.map(e => `<article class="saved-answer"><p class="saved-q">${esc(e.question)}</p><p class="ask-answer">${esc(e.answer)}</p>${e.sql ? `<details><summary>SQL it ran</summary><pre>${esc(e.sql)}</pre></details>` : ''}</article>`).join('');
  }

  async function init() {
    setupShell();
    try {
      [story, decision] = await Promise.all([loadJson(null, './data/story.json'), loadJson('./api/decision-answer', './data/decision_answer.json')]);
      while (!window.portfolioDone) await new Promise(resolve => setTimeout(resolve, 50));  // demand data and the Ask status come from portfolio.js
      renderHome();
      renderForecast();
      renderMiddleMile('affordable_6_workers');
      renderInventory();
      renderProcessControl('affordable_6_workers');
      renderPackerStudy();
      $('pc-plan').addEventListener('planchange', event => renderProcessControl(event.detail));
      renderChecks();
      renderLastMile('affordable_6_workers');
      $('lm-plan').addEventListener('planchange', event => renderLastMile(event.detail));
      $('mm-plan').addEventListener('planchange', event => renderMiddleMile(event.detail));
      renderAskSaved();
    } catch (error) {
      const alert = $('error');
      alert.hidden = false;
      alert.textContent = error.message;
    }
    showView(location.hash.slice(1) || 'home');
  }

  init();
})();
