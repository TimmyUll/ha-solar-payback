// Solar Payback card: how much solar panels and a battery have earned back.
// Reads the "Saved so far" sensor of the Solar Payback integration.
const C = { home: '#ff7a59', sold: '#7b2cbf', reward: '#1fae7a', line: '#ef4444' };
const T = {
  en: {
    title: 'Solar and battery', paid: 'paid back', of: 'saved of', paidOff: 'Paid off!',
    payback: 'Paid back about', years: 'years', early: 'Too early for a forecast',
    soFar: 'So far', whole: 'All the way', home: 'Solar and battery in the house', sold: 'Sold electricity',
    perMonth: 'Saved per month', all: n => `Show all ${n} months`, fewer: 'Show fewer', price: 'Purchase price', loading: 'Waiting for data…',
    missing: 'Entity not found', pick: 'Pick the "Saved so far" sensor of Solar Payback.',
    add: l => `Add ${l}`, lacks: (l, m) => `${l} for ${m} is missing`, addNow: 'Add',
    month: 'Month', amount: 'Amount', exVat: 'excluding VAT', inclVat: 'including VAT',
    save: 'Save', cancel: 'Cancel', saved: 'Saved', failed: 'Could not save', current: v => `Now: ${v}`,
    note: (s) => `So far: solar and battery in the house ${s.home}, sold electricity ${s.sold}, ${s.label} ${s.reward}. `
      + `Compared with what the electricity would have cost without the system: the hourly price plus the grid fee (${s.fee} per kWh). `
      + `The forecast follows the pace of the last ${s.days} days (${s.rate} per day) and does not account for seasons.`
      + (s.est ? ` * partly estimated (house consumption before ${s.est}, ${s.label} for months without a value).` : ` * partly estimated (${s.label} for months without a value).`),
    months: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
  },
  sv: {
    title: 'Solceller och batteri', paid: 'betalt', of: 'sparat av', paidOff: 'Betalt!',
    payback: 'Betalt ca', years: 'år', early: 'För tidigt för prognos',
    soFar: 'Hittills', whole: 'Hela vägen', home: 'Sol och batteri i huset', sold: 'Såld el',
    perMonth: 'Sparat per månad', all: n => `Visa alla ${n} månader`, fewer: 'Visa färre', price: 'Inköpspris', loading: 'Väntar på data…',
    missing: 'Hittar inte entiteten', pick: 'Välj sensorn "Sparat hittills" från Solar Payback.',
    add: l => `Lägg till ${l}`, lacks: (l, m) => `${l} för ${m} saknas`, addNow: 'Lägg till',
    month: 'Månad', amount: 'Belopp', exVat: 'exklusive moms', inclVat: 'inklusive moms',
    save: 'Spara', cancel: 'Avbryt', saved: 'Sparat', failed: 'Kunde inte spara', current: v => `Nu: ${v}`,
    note: (s) => `Hittills: sol och batteri i huset ${s.home}, såld el ${s.sold}, ${s.label} ${s.reward}. `
      + `Jämfört med vad elen hade kostat utan anläggningen: timpriset plus nätavgiften (${s.fee} per kWh). `
      + `Prognosen följer takten de senaste ${s.days} dagarna (${s.rate} per dag) och tar inte hänsyn till årstider.`
      + (s.est ? ` * delvis uppskattat (husets förbrukning före ${s.est}, ${s.label} för månader utan värde).` : ` * delvis uppskattat (${s.label} för månader utan värde).`),
    months: ['jan', 'feb', 'mar', 'apr', 'maj', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec'],
  },
};
const DAY = 864e5;
const esc = s => String(s).replace(/[&<>"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]));
const parseDay = s => { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d).getTime(); };

class SolarPaybackCard extends HTMLElement {
  static getStubConfig(hass) {
    const id = Object.keys(hass.states).find(e => e.startsWith('sensor.') && hass.states[e].attributes.purchase_price != null
      && Array.isArray(hass.states[e].attributes.days));
    return { entity: id || '' };
  }

  setConfig(config) {
    this._c = Object.assign({ collapsed: true }, config || {});
    this._view = 'sofar';
    if (!this.shadowRoot) this._build();
    if (!this._c.collapsed) this._card.setAttribute('data-open', '');
    this._key = null;
  }

  set hass(hass) {
    this._hass = hass;
    const s = hass.states[this._c.entity];
    const key = s ? s.last_updated + s.state + hass.language : 'none';
    if (key === this._key) return;
    this._key = key;
    this._render();
  }

  connectedCallback() { if (this._ro && this._vp) this._ro.observe(this._vp); }
  disconnectedCallback() { if (this._ro) this._ro.disconnect(); }
  getCardSize() { return 8; }
  getGridOptions() { return { columns: 12, rows: 'auto', min_columns: 6 }; }

  get _t() {
    const lang = (this._hass && (this._hass.locale?.language || this._hass.language)) || 'en';
    return T[lang.slice(0, 2)] || T.en;
  }

  _money(v, digits = 0) {
    const s = this._hass.states[this._c.entity];
    const cur = (s && s.attributes.unit_of_measurement) || '';
    const lang = this._hass.locale?.language || this._hass.language || 'en';
    // ISO currency codes (SEK, EUR) are shown the local way, e.g. "7 281 kr" or "€7,281".
    if (/^[A-Z]{3}$/.test(cur)) {
      try {
        return Number(v).toLocaleString(lang, {
          style: 'currency', currency: cur, minimumFractionDigits: 0, maximumFractionDigits: digits,
        });
      } catch (e) { /* unknown code, fall through */ }
    }
    return `${Number(v).toLocaleString(lang, { maximumFractionDigits: digits })} ${cur}`.trim();
  }

  _build() {
    const root = this.attachShadow({ mode: 'open' });
    root.innerHTML = `
      <style>
        :host { display:block; }
        ha-card { display:block; padding:20px 0 18px 0; overflow:hidden; }
        .top { display:flex; align-items:center; gap:16px; padding:0 20px; cursor:pointer;
          -webkit-tap-highlight-color:transparent; }
        .chev { margin-left:auto; flex:0 0 auto; align-self:flex-start; --mdc-icon-size:22px;
          color:var(--secondary-text-color); transition:transform 0.2s ease; }
        ha-card[data-open] .chev { transform:rotate(180deg); }
        ha-card:not([data-open]) .more { display:none; }
        ha-card:not([data-open]) { padding-bottom:20px; }
        .ring { position:relative; width:92px; height:92px; flex:0 0 92px; }
        .ring svg { transform:rotate(-90deg); }
        .ring .val { position:absolute; inset:0; display:flex; flex-direction:column;
          align-items:center; justify-content:center; line-height:1; }
        .ring .num { font-size:24px; font-weight:400; }
        .ring .unit { font-size:11px; color:var(--secondary-text-color); margin-top:3px; }
        .info { min-width:0; }
        .title { font-size:13px; font-weight:600; }
        .big { font-size:28px; font-weight:300; margin-top:4px; }
        .of { font-size:13px; color:var(--secondary-text-color); margin-top:2px; }
        .pill { display:inline-block; margin-top:8px; padding:4px 10px; border-radius:999px;
          font-size:12px; font-weight:600; color:#fff; background:${C.sold}; }
        .seg { display:flex; padding:14px 20px 0 20px; }
        .grp { display:flex; background:var(--secondary-background-color); border-radius:999px; padding:3px; }
        .grp button { font:inherit; border:none; background:none; color:var(--secondary-text-color);
          font-size:12px; font-weight:600; padding:6px 12px; border-radius:999px; cursor:pointer; }
        .grp button.on { background:var(--card-background-color); color:var(--primary-text-color);
          box-shadow:0 2px 8px rgba(0,0,0,0.10); }
        .vp { position:relative; height:200px; margin:8px 12px 0 12px; }
        .vp svg { display:block; overflow:visible; }
        .leg { display:flex; flex-wrap:wrap; gap:6px 14px; padding:8px 20px 0 20px; font-size:12px;
          color:var(--secondary-text-color); }
        .leg span { display:inline-flex; align-items:center; gap:6px; }
        .leg i { width:8px; height:8px; border-radius:50%; display:inline-block; }
        .h { font-size:11px; letter-spacing:1.5px; text-transform:uppercase; color:var(--secondary-text-color);
          padding:18px 20px 6px 20px; }
        .rows { padding:0 20px; }
        .row { display:grid; grid-template-columns:52px 1fr 84px; align-items:center; gap:10px;
          padding:5px 0; font-size:13px; }
        .row .m { color:var(--secondary-text-color); }
        .row .s { text-align:right; font-weight:600; }
        .bar { display:flex; height:10px; border-radius:5px; overflow:hidden; background:var(--secondary-background-color); }
        .bar div { height:100%; }
        .toggle { font:inherit; font-size:12px; font-weight:600; color:var(--primary-color); background:none;
          border:none; padding:6px 0 0 0; cursor:pointer; }
        .note { font-size:11px; line-height:1.5; color:var(--secondary-text-color); padding:12px 20px 0 20px; }
        .msg { padding:20px; font-size:13px; color:var(--secondary-text-color); }
        .miss { display:none; margin-top:8px; font-size:12px; font-weight:600; color:${C.reward}; cursor:pointer; }
        .miss.on { display:block; }
        .rw { padding:14px 20px 0 20px; }
        .rw-btn { font:inherit; font-size:13px; font-weight:600; color:#fff; background:${C.reward}; border:none;
          border-radius:999px; padding:8px 14px; cursor:pointer; }
        .rw-form { display:none; background:var(--secondary-background-color); border-radius:16px; padding:14px; }
        .rw.open .rw-form { display:block; }
        .rw.open .rw-btn { display:none; }
        .rw-row { display:flex; gap:10px; flex-wrap:wrap; }
        .rw-row label { display:flex; flex-direction:column; gap:4px; font-size:11px; color:var(--secondary-text-color); flex:1 1 120px; }
        .rw-row select, .rw-row input { font:inherit; font-size:14px; color:var(--primary-text-color);
          background:var(--card-background-color); border:1px solid var(--divider-color, rgba(0,0,0,0.12));
          border-radius:10px; padding:8px 10px; min-width:0; }
        .rw-hint { font-size:11px; color:var(--secondary-text-color); margin-top:6px; min-height:14px; }
        .rw-act { display:flex; gap:8px; margin-top:10px; align-items:center; }
        .rw-act button { font:inherit; font-size:13px; font-weight:600; border:none; border-radius:999px; padding:8px 14px; cursor:pointer; }
        .rw-save { color:#fff; background:${C.reward}; }
        .rw-cancel { color:var(--primary-text-color); background:none; }
        .rw-msg { font-size:12px; color:var(--secondary-text-color); }
      </style>
      <ha-card>
        <div class="top">
          <div class="ring">
            <svg width="92" height="92" viewBox="0 0 92 92">
              <circle cx="46" cy="46" r="40" fill="none" stroke="var(--secondary-background-color)" stroke-width="8"/>
              <circle class="arc" cx="46" cy="46" r="40" fill="none" stroke="${C.reward}" stroke-width="8"
                stroke-linecap="round" stroke-dasharray="0 999"/>
            </svg>
            <div class="val"><span class="num">–</span><span class="unit"></span></div>
          </div>
          <div class="info">
            <div class="title"></div>
            <div class="big">–</div>
            <div class="of">&nbsp;</div>
            <div class="pill"></div>
            <div class="miss"></div>
          </div>
          <ha-icon class="chev" icon="mdi:chevron-down"></ha-icon>
        </div>
        <div class="more">
          <div class="seg"><div class="grp"><button data-v="sofar"></button><button data-v="whole"></button></div></div>
          <div class="vp"></div>
          <div class="leg"></div>
          <div class="h"></div>
          <div class="rows"></div>
          <div style="padding:0 20px"><button class="toggle"></button></div>
          <div class="rw">
            <button class="rw-btn"></button>
            <div class="rw-form">
              <div class="rw-row">
                <label><span class="rw-l-m"></span><select class="rw-m"></select></label>
                <label><span class="rw-l-a"></span><input class="rw-a" type="number" inputmode="decimal" step="0.01" min="0"></label>
              </div>
              <div class="rw-hint"></div>
              <div class="rw-act"><button class="rw-save"></button><button class="rw-cancel"></button><span class="rw-msg"></span></div>
            </div>
          </div>
          <div class="note"></div>
        </div>
      </ha-card>`;
    const $ = s => root.querySelector(s);
    this._card = $('ha-card'); this._vp = $('.vp'); this._rows = $('.rows'); this._note = $('.note');
    this._arc = $('.arc'); this._num = $('.num'); this._unit = $('.unit'); this._title = $('.title');
    this._big = $('.big'); this._of = $('.of'); this._pill = $('.pill'); this._leg = $('.leg'); this._h = $('.h'); this._toggle = $('.toggle');
    this._miss = $('.miss'); this._rw = $('.rw'); this._rwM = $('.rw-m'); this._rwA = $('.rw-a');
    this._rwHint = $('.rw-hint'); this._rwMsg = $('.rw-msg');
    $('.rw-btn').addEventListener('click', () => this._openReward());
    $('.rw-cancel').addEventListener('click', () => { this._rw.classList.remove('open'); this._rwMsg.textContent = ''; });
    $('.rw-save').addEventListener('click', () => this._saveReward());
    this._rwM.addEventListener('change', () => this._fillReward());
    this._miss.addEventListener('click', ev => {
      ev.stopPropagation();
      this._card.setAttribute('data-open', '');
      this._openReward(this._missing);
      requestAnimationFrame(() => { this._render(); this._rw.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); });
    });
    this._toggle.addEventListener('click', () => { this._allMonths = !this._allMonths; this._render(); });
    $('.top').addEventListener('click', () => {
      if (this._card.hasAttribute('data-open')) this._card.removeAttribute('data-open');
      else this._card.setAttribute('data-open', '');
      requestAnimationFrame(() => this._render());
    });
    root.querySelectorAll('.grp button').forEach(b => b.addEventListener('click', () => {
      this._view = b.dataset.v; this._render();
    }));
    this._ro = new ResizeObserver(() => {
      const w = this._vp.clientWidth;
      if (w && w !== this._lastW) { this._lastW = w; this._render(); }
    });
    this._ro.observe(this._vp);
  }

  _monthName(m) {
    return `${this._t.months[Number(m.slice(5, 7)) - 1]} ${m.slice(0, 4)}`;
  }

  // Months from the start date to this month, newest first.
  _rewardMonths() {
    const a = this._attrs || {};
    const out = [];
    if (!a.start_date) return out;
    const [sy, sm] = a.start_date.split('-').map(Number);
    const now = new Date();
    for (let y = now.getFullYear(), m = now.getMonth() + 1; y > sy || (y === sy && m >= sm); m--) {
      if (m === 0) { m = 12; y--; if (y < sy) break; }
      out.push(`${y}-${String(m).padStart(2, '0')}`);
      if (out.length > 240) break;
    }
    return out;
  }

  _openReward(month) {
    const months = this._rewardMonths();
    const rewards = (this._attrs && this._attrs.rewards) || {};
    const pick = month || months.find((m, i) => i > 0 && rewards[m] == null) || months[1] || months[0];
    this._rwM.innerHTML = months.map(m => `<option value="${m}">${esc(this._monthName(m))}</option>`).join('');
    if (pick) this._rwM.value = pick;
    this._rwMsg.textContent = '';
    this._rw.classList.add('open');
    this._fillReward();
    this._rwA.focus();
  }

  // Show the stored value for the chosen month, in the same VAT terms as it is entered.
  _fillReward() {
    const a = this._attrs || {};
    const v = (a.rewards || {})[this._rwM.value];
    const vat = Number(a.vat_factor) || 1;
    const shown = v == null ? null : Math.round((a.rewards_include_vat ? v : v / vat) * 100) / 100;
    this._rwA.value = shown == null ? '' : String(shown);
    this._rwHint.textContent = shown == null ? '' : this._t.current(this._money(shown, 2));
  }

  async _saveReward() {
    const amount = parseFloat(String(this._rwA.value).replace(',', '.'));
    if (!isFinite(amount) || amount < 0) { this._rwA.focus(); return; }
    const t = this._t;
    try {
      await this._hass.callService('solar_payback', 'set_monthly_reward', {
        config_entry_id: this._attrs.config_entry_id, month: this._rwM.value, amount,
      });
      this._rwMsg.textContent = t.saved;
      setTimeout(() => { this._rw.classList.remove('open'); this._rwMsg.textContent = ''; }, 1200);
    } catch (e) {
      this._rwMsg.textContent = `${t.failed}${e && e.message ? `: ${e.message}` : ''}`;
    }
  }

  _render() {
    if (!this._hass || !this._card) return;
    const t = this._t;
    const st = this._hass.states[this._c.entity];
    this._title.textContent = this._c.title || t.title;
    this._unit.textContent = t.paid;
    this.shadowRoot.querySelectorAll('.grp button').forEach(b => {
      b.textContent = b.dataset.v === 'sofar' ? t.soFar : t.whole;
      b.classList.toggle('on', b.dataset.v === this._view);
    });
    if (!st || !Array.isArray(st.attributes.days)) {
      this._pill.textContent = st ? t.loading : t.missing;
      this._of.textContent = st ? '' : t.pick;
      return;
    }
    const a = st.attributes;
    const label = a.reward_label || 'Grid Rewards';
    this._leg.innerHTML = `<span><i style="background:${C.home}"></i>${esc(t.home)}</span>`
      + `<span><i style="background:${C.sold}"></i>${esc(t.sold)}</span>`
      + `<span><i style="background:${C.reward}"></i>${esc(label)}</span>`;
    this._h.textContent = t.perMonth;
    this._attrs = a; this._label = label;
    this._missing = a.missing_reward_month || null;
    this._miss.classList.toggle('on', !!this._missing);
    if (this._missing) this._miss.textContent = `${t.lacks(label, this._monthName(this._missing))} · ${t.addNow} ›`;
    const sr = this.shadowRoot;
    sr.querySelector('.rw-btn').textContent = `+ ${t.add(label)}`;
    sr.querySelector('.rw-l-m').textContent = t.month;
    sr.querySelector('.rw-l-a').textContent = `${t.amount} (${a.rewards_include_vat ? t.inclVat : t.exVat})`;
    sr.querySelector('.rw-save').textContent = t.save;
    sr.querySelector('.rw-cancel').textContent = t.cancel;
    this._rw.style.display = a.config_entry_id ? '' : 'none';

    const inv = Number(a.purchase_price) || 0;
    const tot = Number(st.state) || 0;
    const rate = Number(a.daily_rate) || 0;
    const frac = inv > 0 ? Math.min(1, tot / inv) : 1;
    const payT = a.payback_date ? parseDay(a.payback_date) : null;
    const startT = parseDay(a.start_date);
    const yrs = payT ? (payT - startT) / (365.25 * DAY) : null;
    const lang = this._hass.locale?.language || this._hass.language || 'en';
    const CIRC = 2 * Math.PI * 40;
    this._arc.setAttribute('stroke-dasharray', `${Math.max(0.01, frac) * CIRC} ${CIRC}`);
    this._num.textContent = `${Math.round(frac * 100)} %`;
    this._big.textContent = this._money(tot);
    this._of.textContent = `${t.of} ${this._money(inv)}`;
    const payD = payT ? new Date(payT) : null;
    this._pill.textContent = frac >= 1 ? t.paidOff : payD
      ? `${t.payback} ${t.months[payD.getMonth()]} ${payD.getFullYear()} · ${yrs.toLocaleString(lang, { maximumFractionDigits: 1 })} ${t.years}`
      : t.early;

    const vw = this._vp.clientWidth;
    if (!vw) return;
    const days = a.days.map(d => ({ t: parseDay(d[0]), home: d[1], sold: d[2], reward: d[3] }));
    if (!days.length) return;

    // Chart
    const H = 200, top = 14, bot = 22, lpad = 44, rpad = 8;
    const t0 = days[0].t;
    const tNow = days[days.length - 1].t + DAY;
    const whole = this._view === 'whole' && payT && frac < 1;
    const t1 = whole ? Math.max(tNow + DAY, payT + 60 * DAY) : tNow;
    const yMax = whole ? inv * 1.08 : Math.max(tot * 1.15, 10);
    const raw = yMax / 4, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map(x => x * mag).find(s => s >= raw) || 10 * mag;
    const X = x => lpad + (x - t0) / (t1 - t0) * (vw - lpad - rpad);
    const Y = v => top + (H - top - bot) * (1 - v / yMax);
    const sub = 'var(--secondary-text-color)';
    let svg = `<svg width="${vw}" height="${H}" xmlns="http://www.w3.org/2000/svg">`;
    for (let v = 0; v <= yMax; v += step) {
      svg += `<line x1="${lpad}" x2="${vw - rpad}" y1="${Y(v)}" y2="${Y(v)}" stroke="${sub}" stroke-opacity="0.18"/>`;
      const lab = v >= 1000 ? `${Math.round(v / 100) / 10}k` : `${Math.round(v)}`;
      svg += `<text x="${lpad - 8}" y="${Y(v) + 3}" font-size="10" text-anchor="end" fill="${sub}">${lab}</text>`;
    }
    const span = (t1 - t0) / DAY;
    const d0 = new Date(t0);
    let lastX = -99;
    for (let d = new Date(d0.getFullYear(), d0.getMonth() + 1, 1); d.getTime() < t1; d = new Date(d.getFullYear(), d.getMonth() + 1, 1)) {
      const yearly = span > 500;
      if (yearly && d.getMonth() !== 0) continue;
      const x = X(d.getTime());
      if (x - lastX < 34) continue;
      lastX = x;
      svg += `<line x1="${x}" x2="${x}" y1="${top}" y2="${H - bot}" stroke="${sub}" stroke-opacity="0.12" stroke-dasharray="2 4"/>`;
      svg += `<text x="${x}" y="${H - 6}" font-size="10" text-anchor="middle" fill="${sub}">${yearly ? d.getFullYear() : t.months[d.getMonth()]}</text>`;
    }
    // Stacked cumulative areas
    const pts = [{ t: t0, a: 0, b: 0, c: 0 }];
    let h = 0, s = 0, r = 0;
    days.forEach(d => { h += d.home; s += d.sold; r += d.reward; pts.push({ t: d.t + DAY, a: h, b: s, c: r }); });
    const area = (lo, hi, col) => {
      let p = '';
      pts.forEach((q, i) => { p += `${i ? 'L' : 'M'}${X(q.t)},${Y(hi(q))}`; });
      for (let i = pts.length - 1; i >= 0; i--) p += `L${X(pts[i].t)},${Y(lo(pts[i]))}`;
      return `<path d="${p}Z" fill="${col}" fill-opacity="0.85" stroke="none"/>`;
    };
    svg += area(() => 0, q => Math.max(0, q.a), C.home);
    svg += area(q => Math.max(0, q.a), q => Math.max(0, q.a) + q.b, C.sold);
    svg += area(q => Math.max(0, q.a) + q.b, q => Math.max(0, q.a) + q.b + q.c, C.reward);
    if (whole) {
      const fg = 'var(--primary-text-color)';
      svg += `<line x1="${X(tNow)}" y1="${Y(tot)}" x2="${X(payT)}" y2="${Y(inv)}" stroke="${fg}" stroke-opacity="0.55" stroke-width="2" stroke-dasharray="4 5"/>`;
      svg += `<line x1="${lpad}" x2="${vw - rpad}" y1="${Y(inv)}" y2="${Y(inv)}" stroke="${C.line}" stroke-width="1.5" stroke-dasharray="6 4"/>`;
      svg += `<text x="${lpad + 4}" y="${Y(inv) - 6}" font-size="11" font-weight="600" fill="${C.line}">${esc(t.price)} ${esc(this._money(inv))}</text>`;
      svg += `<circle cx="${X(payT)}" cy="${Y(inv)}" r="5" fill="var(--card-background-color)" stroke="${C.reward}" stroke-width="3"/>`;
      svg += `<text x="${Math.min(X(payT), vw - rpad - 2)}" y="${Y(inv) + 18}" font-size="11" font-weight="600" text-anchor="end" fill="${C.reward}">${t.months[payD.getMonth()]} ${payD.getFullYear()}</text>`;
    }
    svg += `<circle cx="${X(tNow)}" cy="${Y(tot)}" r="4" fill="var(--primary-text-color)"/>`;
    svg += '</svg>';
    this._vp.innerHTML = svg;

    // Months
    const months = a.months || [];
    const maxM = Math.max(...months.map(m => Math.max(0, m.home) + m.sold + m.reward), 1);
    const multiYear = months.length && months[0].month.slice(0, 4) !== months[months.length - 1].month.slice(0, 4);
    const shown = this._allMonths ? months.slice().reverse() : months.slice(-12).reverse();
    this._toggle.style.display = months.length > 12 ? '' : 'none';
    this._toggle.textContent = this._allMonths ? t.fewer : t.all(months.length);
    this._rows.innerHTML = shown.map(m => {
      const w = v => `${Math.max(0, v) / maxM * 100}%`;
      const ml = t.months[Number(m.month.slice(5, 7)) - 1] + (multiYear ? ` ’${m.month.slice(2, 4)}` : '');
      return `<div class="row"><span class="m">${ml}${m.estimated ? '*' : ''}</span>
        <div class="bar"><div style="width:${w(m.home)};background:${C.home}"></div><div style="width:${w(m.sold)};background:${C.sold}"></div><div style="width:${w(m.reward)};background:${C.reward}"></div></div>
        <span class="s">${esc(this._money(m.home + m.sold + m.reward))}</span></div>`;
    }).join('');
    const sum = k => months.reduce((x, m) => x + m[k], 0);
    const estD = a.estimated_until ? new Date(parseDay(a.estimated_until) + DAY) : null;
    this._note.textContent = t.note({
      home: this._money(sum('home')), sold: this._money(sum('sold')), reward: this._money(sum('reward')),
      label, fee: this._money(Number(a.grid_fee_import) || 0, 4),
      days: a.forecast_days, rate: this._money(rate),
      est: estD ? estD.toLocaleDateString(lang, { day: 'numeric', month: 'long' }) : null,
    });
  }
}

if (!customElements.get('solar-payback-card')) customElements.define('solar-payback-card', SolarPaybackCard);
window.customCards = window.customCards || [];
if (!window.customCards.find(c => c.type === 'solar-payback-card')) {
  window.customCards.push({
    type: 'solar-payback-card', name: 'Solar Payback',
    description: 'When solar panels and a battery have paid for themselves', preview: false,
  });
}
