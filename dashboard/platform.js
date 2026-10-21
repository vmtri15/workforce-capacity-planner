// Home, demand forecast and middle mile views, plus routing, the mobile menu and the public Ask page.
// Reads dashboard/data/story.json (built by scripts/build_static_dashboard.py) and the decision answer.
(() => {
  const $ = id => document.getElementById(id);
  const esc = portfolioEscape;
  const num = portfolioNumber;
  const money = portfolioMoney;
  const pct = (value, digits = 1) => `${(100 * Number(value)).toFixed(digits)}%`;
  const GROUPS = {home: 'OVERVIEW', recommendations: 'OVERVIEW', portfolio: '1 · FORECAST DEMAND', forecast: '1 · FORECAST DEMAND',
    network: '2 · PLAN CAPACITY', builder: '2 · PLAN CAPACITY', middlemile: '3 · SHIP PARCELS', ask: 'TOOLS', tableau: 'TOOLS',
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

  function setupShell() {
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
    $('home-plan').addEventListener('planchange', event => renderPlan(event.detail));
    countUp($('home-kpis'));
    renderPlan('six');
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
    ctx.font = '11px Inter, Arial'; ctx.fillStyle = '#6b7a73'; ctx.strokeStyle = '#e6ece9';
    for (let i = 0; i <= 4; i++) { const ly = bottom - (bottom - top) * i / 4; ctx.beginPath(); ctx.moveTo(left, ly); ctx.lineTo(right, ly); ctx.stroke(); ctx.fillText(num(max * i / 4), 0, ly + 4); }
    const first = forecastPoints.findIndex(d => d.forecast != null);
    ctx.fillStyle = '#f3f6f5'; ctx.fillRect(x(first) - 4, top, right - x(first) + 4, bottom - top);
    ctx.beginPath();
    forecastPoints.forEach((d, i) => { if (i >= first) (i === first ? ctx.moveTo : ctx.lineTo).call(ctx, x(i), y(d.high)); });
    for (let i = forecastPoints.length - 1; i >= first; i--) ctx.lineTo(x(i), y(forecastPoints[i].low));
    ctx.closePath(); ctx.fillStyle = 'rgba(15,107,87,.14)'; ctx.fill();
    const line = (key, color, dash, from = 0, to = forecastPoints.length) => {
      ctx.beginPath(); ctx.setLineDash(dash); ctx.strokeStyle = color; ctx.lineWidth = 2;
      for (let i = from; i < to; i++) (i === from ? ctx.moveTo : ctx.lineTo).call(ctx, x(i), y(forecastPoints[i][key]));
      ctx.stroke(); ctx.setLineDash([]);
    };
    line('actual', '#24312e', [], 0, first);
    line('forecast', '#0f6b57', [], first);
    line('p90', '#c7841f', [5, 4], first);
    ctx.fillStyle = '#6b7a73';
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
    const lane = value => value.replace('>', ' → ').replaceAll('_sc', ' sort center').replace(/(^|→ )(\w)/g, (m, a, b) => a + b.toUpperCase());
    $('mm-trucks').innerHTML = trucks.slice(0, 12).map(row => `<tr><td>${esc(lane(row.lane))}</td><td>${esc(row.departure.slice(0, 16))}</td><td>${Number(row.delay_hours).toFixed(1)} h</td><td>${num(row.parcels_on_board)}</td><td><strong>${num(row.late_parcels_caused)}</strong></td><td><i class="pill">${esc(row.best_option)}</i></td><td>${money(row.cost)}</td></tr>`).join('');
    renderMap(plan);
    const six = plans.affordable_6_workers, ten = plans.safe_10_workers;
    $('mm-takeaway').textContent = `Most late parcels with 6 workers (${num(six.late_without_truck_delays)} of ${num(six.late_with_truck_delays)}) leave the warehouse late, so no truck fix can save them. Trucks add ${num(six.late_caused_by_trucks)} more, and recovering them costs ${money(six.truck_recovery_cost)}, a small fraction of the ${money(ten.labor_cost - six.labor_cost)} labor gap between the plans. With 10 workers only ${num(ten.late_with_truck_delays)} parcels are late, all from trucks.`;
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
    const columns = {site: 190, sort: 450, station: 700};
    Object.keys(columns).forEach(kind => {
      const group = all.filter(n => n.kind === kind).sort((a, b) => b.lat - a.lat);
      group.forEach((n, i) => { n.x = columns[kind]; n.y = H * (i + 1) / (group.length + 1); });
    });
    const X = n => n.x, Y = n => n.y;
    const maxOrders = Math.max(...[...lanes.values()].map(l => l.orders)), maxLate = Math.max(1, ...[...lanes.values()].map(l => l.late));
    const color = late => late === 0 ? '#b8c6c0' : late / maxLate > .5 ? '#c0472f' : '#d99a2b';
    const name = id => nodes[id].name;
    const lines = [...lanes.values()].sort((a, b) => a.late - b.late).map(l => {
      const a = nodes[l.from], b = nodes[l.to];
      const mid = (X(a) + X(b)) / 2;
      return `<path class="lane" data-key="${esc(l.key)}" d="M${X(a)},${Y(a).toFixed(1)} C${mid},${Y(a).toFixed(1)} ${mid},${Y(b).toFixed(1)} ${X(b)},${Y(b).toFixed(1)}" fill="none" stroke="${color(l.late)}" stroke-width="${(2 + 14 * l.orders / maxOrders).toFixed(1)}" tabindex="0"><title>${esc(name(l.from))} to ${esc(name(l.to))}</title></path>`;
    }).join('');
    const marker = n => n.kind === 'site' ? `<rect x="${X(n) - 8}" y="${Y(n) - 8}" width="16" height="16" rx="4" class="node site"/>`
      : n.kind === 'sort' ? `<circle cx="${X(n)}" cy="${Y(n)}" r="9" class="node sort"/>` : `<circle cx="${X(n)}" cy="${Y(n)}" r="7" class="node station"/>`;
    const label = n => n.kind === 'sort' ? `<text x="${X(n)}" y="${Y(n) - 16}" text-anchor="middle" class="node-label sort">${esc(n.name.replace(/ \(.*\)/, ''))}</text>`
      : `<text x="${X(n) + (n.kind === 'site' ? -16 : 16)}" y="${Y(n) + 5}" text-anchor="${n.kind === 'site' ? 'end' : 'start'}" class="node-label ${n.kind}">${esc(n.name)}</text>`;
    const heads = [['WAREHOUSES', 190], ['SORT CENTERS', 450], ['DELIVERY STATIONS', 700]].map(([t, x]) => `<text x="${x}" y="28" text-anchor="middle" class="map-head">${t}</text>`).join('');
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

  // ---- Ask the planner on the public site ----
  function renderAskSaved() {
    const ask = story.ask;
    const acc = ask.accuracy;
    const line = name => acc[name] ? `${acc[name].correct} of ${acc[name].of}` : null;
    $('ask-accuracy').innerHTML = `<strong>Tested accuracy:</strong> ${acc.guided ? `${line('guided')} test questions answered correctly with base case guidance (${pct(acc.guided.share, 0)}), up from ${line('glossary')} with the glossary alone and ${line('schema_only')} with the schema only.` : `${line('glossary')} test questions answered correctly with the business glossary (${pct(acc.glossary.share, 0)}).`}`;
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
