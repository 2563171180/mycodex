const form = document.getElementById('popsicleForm');
const resetBtn = document.getElementById('resetBtn');
const refreshBtn = document.getElementById('refreshBtn');
const searchBtn = document.getElementById('searchBtn');
const tableBody = document.getElementById('inventoryTableBody');
const metricsGrid = document.getElementById('metricsGrid');
const zoneCards = document.getElementById('zoneCards');
const formModeBadge = document.getElementById('formModeBadge');
const recordIdInput = document.getElementById('recordId');

const fields = ['name', 'flavor', 'storage_zone', 'quantity', 'unit_price', 'min_stock', 'supplier', 'production_date', 'expiry_date', 'notes'];

const metricConfig = [
  { key: 'total_skus', label: 'SKU 数量', format: (value) => `${value}`, hint: '当前冰棒品项数' },
  { key: 'total_quantity', label: '库存总支数', format: (value) => `${value}`, hint: '冷库内所有冰棒库存' },
  { key: 'inventory_value', label: '库存货值', format: (value) => `¥${Number(value).toFixed(2)}`, hint: '按单价估算库存总额' },
  { key: 'low_stock_count', label: '低库存预警', format: (value) => `${value}`, hint: '需要尽快补货的品项' },
  { key: 'expiring_soon_count', label: '30 天临期', format: (value) => `${value}`, hint: '建议优先销售或处理' },
];

function getStatus(item) {
  const today = new Date();
  const expiryDate = new Date(item.expiry_date);
  const daysUntilExpiry = Math.ceil((expiryDate - today) / (1000 * 60 * 60 * 24));

  if (item.quantity <= item.min_stock) {
    return { text: '低库存', className: 'danger' };
  }
  if (daysUntilExpiry <= 30) {
    return { text: '临近到期', className: 'warning' };
  }
  return { text: '正常', className: 'good' };
}

function showMessage(message) {
  window.alert(message);
}

function serializeForm() {
  const payload = {};
  fields.forEach((field) => {
    payload[field] = document.getElementById(field).value;
  });
  return payload;
}

function resetForm() {
  form.reset();
  recordIdInput.value = '';
  formModeBadge.textContent = '新增模式';
}

function fillForm(item) {
  recordIdInput.value = item.id;
  fields.forEach((field) => {
    document.getElementById(field).value = item[field] ?? '';
  });
  formModeBadge.textContent = `编辑模式：#${item.id}`;
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function renderMetrics(summary) {
  metricsGrid.innerHTML = '';
  const template = document.getElementById('metricCardTemplate');
  metricConfig.forEach((metric) => {
    const node = template.content.cloneNode(true);
    node.querySelector('.metric-label').textContent = metric.label;
    node.querySelector('.metric-value').textContent = metric.format(summary[metric.key] || 0);
    node.querySelector('.metric-hint').textContent = metric.hint;
    metricsGrid.appendChild(node);
  });
}

function renderZones(zones) {
  zoneCards.innerHTML = '';
  if (!zones.length) {
    zoneCards.innerHTML = '<div class="empty-state">暂无库区数据，添加冰棒后会自动生成。</div>';
    return;
  }

  zones.forEach((zone) => {
    const card = document.createElement('article');
    card.className = 'zone-card';
    card.innerHTML = `
      <p>${zone.storage_zone}</p>
      <strong>${zone.quantity || 0} 支</strong>
      <p>${zone.sku_count} 个品项</p>
    `;
    zoneCards.appendChild(card);
  });
}

function renderTable(items) {
  tableBody.innerHTML = '';
  if (!items.length) {
    tableBody.innerHTML = '<tr><td colspan="9" class="empty-state">暂无冰棒记录，请先新增库存信息。</td></tr>';
    return;
  }

  items.forEach((item) => {
    const row = document.createElement('tr');
    const status = getStatus(item);
    row.innerHTML = `
      <td>${item.name}</td>
      <td>${item.flavor}</td>
      <td>${item.storage_zone}</td>
      <td>${item.quantity}</td>
      <td>¥${Number(item.unit_price).toFixed(2)}</td>
      <td>${item.supplier}</td>
      <td>${item.expiry_date}</td>
      <td><span class="status-pill ${status.className}">${status.text}</span></td>
      <td class="actions-cell">
        <button class="small-btn" data-action="edit" data-id="${item.id}">编辑</button>
        <button class="danger-btn" data-action="delete" data-id="${item.id}">删除</button>
      </td>
    `;
    tableBody.appendChild(row);
  });
}

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || '请求失败');
  }
  return data;
}

async function loadSummary() {
  const data = await fetchJSON('/api/summary');
  renderMetrics(data.summary);
  renderZones(data.zones);
}

async function loadInventory() {
  const keyword = document.getElementById('keywordFilter').value.trim();
  const zone = document.getElementById('zoneFilter').value.trim();
  const params = new URLSearchParams();
  if (keyword) params.append('keyword', keyword);
  if (zone) params.append('zone', zone);
  const data = await fetchJSON(`/api/popsicles?${params.toString()}`);
  renderTable(data.items);
}

async function refreshAll() {
  await Promise.all([loadSummary(), loadInventory()]);
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    const recordId = recordIdInput.value;
    const payload = serializeForm();
    const method = recordId ? 'PUT' : 'POST';
    const url = recordId ? `/api/popsicles/${recordId}` : '/api/popsicles';
    await fetchJSON(url, { method, body: JSON.stringify(payload) });
    showMessage(recordId ? '冰棒记录已更新。' : '冰棒记录已新增。');
    resetForm();
    await refreshAll();
  } catch (error) {
    showMessage(error.message);
  }
});

resetBtn.addEventListener('click', resetForm);
refreshBtn.addEventListener('click', async () => {
  try {
    await refreshAll();
  } catch (error) {
    showMessage(error.message);
  }
});
searchBtn.addEventListener('click', async () => {
  try {
    await loadInventory();
  } catch (error) {
    showMessage(error.message);
  }
});

tableBody.addEventListener('click', async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLButtonElement)) {
    return;
  }

  const id = target.dataset.id;
  const action = target.dataset.action;
  if (!id || !action) {
    return;
  }

  if (action === 'edit') {
    const data = await fetchJSON('/api/popsicles');
    const item = data.items.find((entry) => String(entry.id) === id);
    if (item) fillForm(item);
    return;
  }

  if (action === 'delete') {
    const confirmed = window.confirm('确定删除这条冰棒记录吗？');
    if (!confirmed) return;
    try {
      await fetchJSON(`/api/popsicles/${id}`, { method: 'DELETE' });
      showMessage('冰棒记录已删除。');
      await refreshAll();
    } catch (error) {
      showMessage(error.message);
    }
  }
});

window.addEventListener('load', async () => {
  try {
    await refreshAll();
  } catch (error) {
    showMessage(`初始化失败：${error.message}`);
  }
});
