<template>
  <section class="page" data-module="site">
    <header class="page-head">
      <div>
        <h2>基站台账管理</h2>
        <p class="page-desc">维护基站，围绕基站编号、基站名称、基站类型、所属区县做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记基站</button>
        <button class="btn" type="button" @click="exportRows">导出基站台账清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>基站编号</span>
        <input v-model.trim="keyword" placeholder="按基站编号检索" />
      </label>
      <label class="filter-item">
        <span>基站状态</span>
        <select v-model="status">
          <option value="">全部状态</option>
          <option v-for="item in statuses" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            <button v-if="column === '基站编号'" class="link" type="button" @click="openDetail(row)">
              {{ row[column] ?? '—' }}
            </button>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
          <td class="row-actions">
            <button
              v-for="action in availableActions(row)"
              :key="action.key"
              class="link"
              type="button"
              @click="runAction(action.key, row)"
            >
              {{ action.label }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无符合条件的基站台账数据</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条基站台账记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="showCreateModal" class="modal-mask" @click.self="closeCreate">
      <section class="modal-card" role="dialog" aria-modal="true" aria-labelledby="create-title">
        <header class="modal-head">
          <h3 id="create-title">登记基站</h3>
          <button class="modal-close" type="button" @click="closeCreate">×</button>
        </header>
        <form @submit.prevent="submitCreate">
          <div class="form-grid">
            <label v-for="field in formFields" :key="field.name" class="form-item">
              <span>{{ field.label }}<em v-if="field.required">*</em></span>
              <input
                v-if="field.type !== 'date'"
                v-model.trim="createForm[field.name]"
                :type="field.type"
                :required="field.required"
              />
              <input v-else v-model="createForm[field.name]" type="date" required />
            </label>
          </div>
          <p v-if="formError" class="error-text">{{ formError }}</p>
          <footer class="modal-foot">
            <button class="btn ghost" type="button" @click="closeCreate">取消</button>
            <button class="btn primary" type="submit" :disabled="submitting">保存</button>
          </footer>
        </form>
      </section>
    </div>

    <div v-if="detail" class="modal-mask" @click.self="closeDetail">
      <section class="modal-card detail-card" role="dialog" aria-modal="true" aria-labelledby="detail-title">
        <header class="modal-head">
          <h3 id="detail-title">基站详情</h3>
          <button class="modal-close" type="button" @click="closeDetail">×</button>
        </header>
        <div class="detail-grid">
          <div v-for="column in columns" :key="column">
            <span>{{ column }}</span>
            <strong>{{ detail[column] ?? '—' }}</strong>
          </div>
        </div>
        <section class="history-panel">
          <h4>操作轨迹</h4>
          <ul v-if="history(detail).length">
            <li v-for="(item, index) in history(detail)" :key="index">
              <span>{{ formatTime(item.time) }}</span>
              <strong>{{ item.action }}</strong>
              <em>{{ item.from ?? '—' }} → {{ item.to }}</em>
            </li>
          </ul>
          <p v-else class="empty-state">暂无操作轨迹</p>
        </section>
        <footer class="modal-foot">
          <button class="btn" type="button" @click="closeDetail">关闭</button>
        </footer>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue }
type Row = Record<string, JsonValue>
type ActionRecord = {
  action: string
  from: string | null
  to: string
  time: string
  [key: string]: JsonValue
}
type FormField = {
  name: string
  label: string
  required: boolean
  type?: string
}

const ENDPOINT = '/api/site'
const columns = ['基站编号', '基站名称', '基站类型', '所属区县', '经纬度坐标', '铁塔高度', '入网日期', '基站状态']
const statuses = ['运行中', '退服中', '已退网', '已拆除']
const stats = [
  { label: '运行基站', value: 0 },
  { label: '退服基站', value: 0 },
  { label: '退网站点', value: 0 },
]
const formFields: FormField[] = [
  { name: '基站编号', label: '基站编号', required: true },
  { name: '基站名称', label: '基站名称', required: true },
  { name: '基站类型', label: '基站类型', required: true },
  { name: '所属区县', label: '所属区县', required: true },
  { name: '经纬度坐标', label: '经纬度坐标', required: true },
  { name: '铁塔高度', label: '铁塔高度', required: false },
  { name: '入网日期', label: '入网日期', required: true, type: 'date' },
]
const today = () => {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

const emptyForm = (): Record<string, string> => ({
  基站编号: '',
  基站名称: '',
  基站类型: '',
  所属区县: '',
  经纬度坐标: '',
  铁塔高度: '',
  入网日期: today(),
})

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const keyword = ref('')
const status = ref('')
const showCreateModal = ref(false)
const submitting = ref(false)
const formError = ref('')
const createForm = ref(emptyForm())
const detail = ref<Row | null>(null)

function availableActions(row: Row): { key: string; label: string }[] {
  switch (row.基站状态) {
    case '运行中':
      return [{ key: '登记退服', label: '登记退服' }]
    case '退服中':
      return [
        { key: '申请退网', label: '申请退网' },
        { key: '恢复', label: '恢复' },
      ]
    case '已退网':
      return [
        { key: '拆站完成', label: '拆站完成' },
        { key: '恢复', label: '恢复' },
      ]
    default:
      return []
  }
}

function history(row: Row): ActionRecord[] {
  return Array.isArray(row.操作轨迹) ? (row.操作轨迹 as ActionRecord[]) : []
}

function formatTime(value: JsonValue): string {
  return typeof value === 'string' ? value.replace('T', ' ') : '—'
}

function resetFilters() {
  keyword.value = ''
  status.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createForm.value = emptyForm()
  formError.value = ''
  showCreateModal.value = true
}

function closeCreate() {
  showCreateModal.value = false
}

function closeDetail() {
  detail.value = null
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('基站详情读取失败')
    }
    detail.value = await response.json()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '基站详情读取失败'
  }
}

async function submitCreate() {
  formError.value = ''
  submitting.value = true
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: createForm.value }),
    })
    const payload = await response.json().catch(() => null) as { ok?: boolean; message?: string } | null
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message || '基站登记未生效，请稍后重试')
    }
    showCreateModal.value = false
    await reload()
  } catch (error) {
    formError.value = error instanceof Error ? error.message : '基站登记失败'
  } finally {
    submitting.value = false
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json().catch(() => null) as { ok?: boolean; message?: string; entry?: Row } | null
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message || '基站台账动作未生效，请稍后重试')
    }
    if (detail.value?.id === row.id && payload.entry) {
      detail.value = payload.entry
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '基站台账操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  if (keyword.value) {
    params.set('keyword', keyword.value)
  }
  if (status.value) {
    params.set('status', status.value)
  }
  const query = params.toString()
  try {
    const response = await request(`${ENDPOINT}${query ? `?${query}` : ''}`)
    if (!response.ok) {
      throw new Error('基站列表读取失败')
    }
    const payload = await response.json() as { items?: Row[]; total?: number }
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '基站台账列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgb(15 23 42 / 45%);
}

.modal-card {
  width: min(760px, calc(100vw - 32px));
  max-height: calc(100vh - 48px);
  overflow: auto;
  border-radius: 10px;
  background: #fff;
  padding: 18px 20px;
  box-shadow: 0 20px 50px rgb(15 23 42 / 25%);
}

.detail-card {
  width: min(860px, calc(100vw - 32px));
}

.modal-head,
.modal-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.modal-head h3 {
  margin: 0;
}

.modal-head h4 {
  margin: 0 0 8px;
}

.modal-close {
  border: none;
  background: none;
  color: var(--muted);
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
}

.modal-foot {
  justify-content: flex-end;
  margin-top: 16px;
}

.form-grid,
.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.form-item span,
.detail-grid span {
  display: block;
  margin-bottom: 4px;
  color: var(--muted);
  font-size: 12px;
}

.form-item em {
  margin-left: 2px;
  color: #b42318;
  font-style: normal;
}

.form-item input,
.filter-item input,
.filter-item select {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 7px 9px;
}

.detail-grid strong {
  display: block;
  min-height: 20px;
}

.history-panel {
  margin-top: 18px;
  border-top: 1px solid var(--border);
  padding-top: 14px;
}

.history-panel ul {
  margin: 0;
  padding: 0;
  list-style: none;
}

.history-panel li {
  display: grid;
  grid-template-columns: 170px 100px 1fr;
  gap: 10px;
  border-bottom: 1px solid #edf1f5;
  padding: 7px 0;
  font-size: 13px;
}

.history-panel em {
  color: var(--muted);
  font-style: normal;
}

@media (max-width: 720px) {
  .form-grid,
  .detail-grid {
    grid-template-columns: 1fr;
  }

  .history-panel li {
    grid-template-columns: 1fr;
    gap: 2px;
  }
}
</style>
