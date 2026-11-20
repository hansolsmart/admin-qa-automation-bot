'use strict';

const select = (selector) => document.querySelector(selector);
const view = document.body.dataset.page;
let csrfToken = null;

function showStatus(message, kind = '') {
  const status = select('#status');
  status.textContent = message;
  status.dataset.kind = kind;
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers);
  if (options.body !== undefined) headers.set('Content-Type', 'application/json');
  if (csrfToken && options.method) headers.set('X-CSRF-Token', csrfToken);
  let response;
  try {
    response = await fetch(path, {...options, headers, body: options.body === undefined ? undefined : JSON.stringify(options.body)});
  } catch {
    throw new Error('서버 연결을 확인하고 다시 시도해 주세요.');
  }
  const data = response.status === 204 ? null : await response.json();
  if (!response.ok) {
    if (response.status === 401 && view !== 'login') window.location.assign('/');
    const error = new Error(data?.error?.message || '요청을 처리할 수 없습니다.');
    error.status = response.status;
    throw error;
  }
  return data;
}

function textElement(tag, text, className) {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
}

function busyForm(form, handler) {
  const submit = form.querySelector('button[type="submit"]');
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (submit.disabled) return;
    submit.disabled = true;
    try {
      await handler();
    } catch (error) {
      showStatus(error.message, 'error');
    } finally {
      submit.disabled = false;
    }
  });
  submit.disabled = false;
}

function setUpLogin() {
  busyForm(select('#login-form'), async () => {
    showStatus('로그인 중…');
    await api('/api/auth/login', {method: 'POST', body: {username: select('#username').value, password: select('#password').value}});
    window.location.assign('/items');
  });
}

function setUpItems() {
  const form = select('#item-form');
  const submit = select('#save-item');
  const cancel = select('#cancel-edit');
  const more = select('#more-items');
  let editing = null;
  let pending = null;
  let cursor = null;
  let refresh = 0;

  function resetForm() {
    form.reset();
    editing = null;
    pending = null;
    submit.textContent = '항목 등록';
    select('#item-form-title').textContent = '새 항목';
    cancel.hidden = true;
  }

  function rowFor(item) {
    const row = document.createElement('tr');
    const action = document.createElement('td');
    const edit = textElement('button', '수정', 'quiet');
    edit.type = 'button';
    edit.addEventListener('click', () => {
      if (submit.disabled) return;
      editing = item.id;
      pending = null;
      select('#name').value = item.name;
      select('#description').value = item.description;
      select('#item-form-title').textContent = '항목 수정';
      submit.textContent = '변경 저장';
      cancel.hidden = false;
      select('#name').focus();
      showStatus('');
    });
    action.append(edit);
    row.append(textElement('td', item.name), textElement('td', item.description), action);
    return row;
  }

  async function loadItems(append = false) {
    const requestNumber = ++refresh;
    const result = await api(append ? '/api/items?before=' + cursor : '/api/items');
    if (requestNumber !== refresh) return;
    const table = select('#item-table');
    if (!append) table.replaceChildren();
    table.append(...result.items.map(rowFor));
    cursor = result.next_before;
    more.hidden = cursor === null;
    select('#item-inventory').textContent = table.childElementCount ? '' : '등록된 항목이 없습니다.';
  }

  more.addEventListener('click', async () => {
    more.disabled = true;
    try { await loadItems(true); } catch (error) { showStatus(error.message, 'error'); }
    finally { more.disabled = false; }
  });
  cancel.addEventListener('click', () => {
    if (!submit.disabled) {
      resetForm();
      showStatus('');
    }
  });
  busyForm(form, async () => {
    const body = {name: select('#name').value, description: select('#description').value};
    if (!body.name.trim() || Array.from(body.name).length > 100 || Array.from(body.description).length > 500) {
      throw new Error('항목 이름은 1~100자, 설명은 500자 이내로 입력해 주세요.');
    }
    const updating = editing !== null;
    const signature = JSON.stringify(body);
    if (!updating && pending?.signature !== signature) pending = {signature, key: crypto.randomUUID()};
    showStatus('저장 중…');
    try {
      await api(updating ? '/api/items/' + editing : '/api/items', {
        method: updating ? 'PATCH' : 'POST', body,
        headers: updating ? undefined : {'Idempotency-Key': pending.key},
      });
    } catch (error) {
      if (!updating && (!error.status || error.status === 503)) {
        throw new Error('저장 응답을 확인하지 못했습니다. 같은 내용으로 다시 시도해 주세요.');
      }
      throw error;
    }
    resetForm();
    showStatus(updating ? '변경 내용을 저장했습니다.' : '항목을 등록했습니다.');
    await loadItems();
  });
  return loadItems();
}

function stateBadge(state) {
  const badge = textElement('span', state, 'state');
  badge.dataset.state = state;
  return badge;
}

function formatTime(seconds) {
  return new Date(seconds * 1000).toLocaleString('ko-KR');
}

function evidenceLink(path, label) {
  const link = textElement('a', label);
  link.href = path;
  link.target = '_blank';
  link.rel = 'noopener';
  return link;
}

function setUpDashboard() {
  const list = select('#run-list');
  const detail = select('#run-detail');
  const more = select('#more-runs');
  const history = new Map();
  let before = null;
  let selected = null;
  let listSignature = '';
  let detailSignature = '';
  let polling = false;

  function renderList() {
    const runs = [...history.values()].sort((left, right) => right.id - left.id);
    const signature = JSON.stringify([selected, runs]);
    if (signature === listSignature) return;
    listSignature = signature;
    list.replaceChildren();
    if (!runs.length) list.textContent = '아직 실행 이력이 없습니다.';
    for (const run of runs) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'quiet run-row';
      button.setAttribute('aria-current', run.id === selected ? 'true' : 'false');
      button.append(textElement('span', '실행 #' + run.id + ' · ' + formatTime(run.requested_at)), stateBadge(run.status));
      button.addEventListener('click', async () => {
        selected = run.id;
        renderList();
        try { await loadDetail(); } catch (error) { showStatus(error.message, 'error'); }
      });
      list.append(button);
    }
  }

  async function loadDetail() {
    if (selected === null) return;
    const id = selected;
    const run = await api('/api/qa/runs/' + id);
    if (selected !== id) return;
    const signature = JSON.stringify(run);
    if (signature === detailSignature) return;
    detailSignature = signature;
    detail.hidden = false;
    detail.replaceChildren(textElement('h3', '실행 #' + run.id), stateBadge(run.status));
    if (run.started_at !== null) detail.append(textElement('p', '시작 ' + formatTime(run.started_at), 'secondary'));
    if (run.finished_at !== null) detail.append(textElement('p', '종료 ' + formatTime(run.finished_at), 'secondary'));
    detail.append(textElement('p', run.scenarios.join(' · '), 'secondary'));
    if (run.error_code) detail.append(textElement('p', run.error_code));
    if (run.log_url) detail.append(evidenceLink(run.log_url, '실행 로그'));
    if (!run.results.length) return;
    const results = document.createElement('ul');
    for (const result of run.results) {
      const element = textElement('li', result.scenario_id + ' · ' + result.duration_ms + ' ms ');
      element.append(stateBadge(result.status));
      if (result.detail) element.append(textElement('p', result.detail, 'secondary'));
      if (result.screenshot_url) element.append(evidenceLink(result.screenshot_url, '스크린샷'));
      results.append(element);
    }
    detail.append(results);
  }

  async function loadRuns(append = false) {
    const result = await api(append ? '/api/qa/runs?before=' + before : '/api/qa/runs');
    if (append || history.size <= 25) before = result.next_before;
    for (const run of result.runs) history.set(run.id, run);
    more.hidden = before === null;
    const metrics = result.metrics;
    select('#pass-count').textContent = metrics.counts.PASS;
    select('#fail-count').textContent = metrics.counts.FAIL;
    select('#pass-rate').textContent = metrics.pass_rate === null ? '—' : Math.round(100 * metrics.pass_rate) + '%';
    select('#avg-time').textContent = metrics.mean_duration_ms === null ? '—' : Math.round(metrics.mean_duration_ms) + ' ms';
    renderList();
    await loadDetail();
  }

  more.addEventListener('click', async () => {
    more.disabled = true;
    try { await loadRuns(true); } catch (error) { showStatus(error.message, 'error'); }
    finally { more.disabled = false; }
  });
  const form = select('#run-form');
  busyForm(form, async () => {
    const scenarios = new FormData(form).getAll('scenario');
    if (!scenarios.length) throw new Error('시나리오를 하나 이상 선택해 주세요.');
    showStatus('실행 요청 중…');
    const run = await api('/api/qa/runs', {method: 'POST', body: {scenarios}});
    selected = run.id;
    showStatus('실행 #' + run.id + '을 대기열에 추가했습니다.');
    await loadRuns();
  });
  window.setInterval(async () => {
    if (polling || document.hidden) return;
    polling = true;
    try { await loadRuns(); } catch (error) { showStatus(error.message, 'error'); }
    finally { polling = false; }
  }, 1800);
  return loadRuns();
}

async function start() {
  if (view === 'login') {
    setUpLogin();
    return;
  }
  csrfToken = (await api('/api/auth/me')).csrf_token;
  const logout = select('#logout');
  logout.addEventListener('click', async () => {
    logout.disabled = true;
    try {
      await api('/api/auth/logout', {method: 'POST'});
      window.location.assign('/');
    } catch (error) {
      showStatus(error.message, 'error');
      logout.disabled = false;
    }
  });
  logout.disabled = false;
  await (view === 'items' ? setUpItems() : setUpDashboard());
}

start().catch((error) => showStatus(error.message, 'error'));
