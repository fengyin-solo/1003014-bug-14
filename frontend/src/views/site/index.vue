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
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
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
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">详情</button>
            <button
              v-for="action in availableActions(row)"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无基站台账数据，可先登记基站</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条基站台账记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="showCreate" class="modal-mask" @click.self="showCreate = false">
      <form class="modal-card" @submit.prevent="submitCreate">
        <h3>登记基站</h3>
        <label v-for="field in editableFields" :key="field" class="modal-field">
          <span>{{ field }}<em v-if="requiredFields.includes(field)">*</em></span>
          <input v-model="createForm[field]" :placeholder="`请输入${field}`" />
        </label>
        <div class="modal-actions">
          <button class="btn primary" type="submit">提交登记</button>
          <button class="btn ghost" type="button" @click="showCreate = false">取消</button>
        </div>
      </form>
    </div>

    <div v-if="showDetail" class="modal-mask" @click.self="closeDetail">
      <div class="modal-card">
        <h3>基站详情</h3>
        <p v-if="detailLoading" class="empty-state">正在读取基站详情…</p>
        <template v-else-if="detail">
          <dl class="detail-grid">
            <template v-for="column in columns" :key="column">
              <dt>{{ column }}</dt>
              <dd>{{ cell(detail[column]) }}</dd>
            </template>
          </dl>
          <h4>状态流转记录</h4>
          <ul class="history-list">
            <li v-for="(log, index) in detailLogs" :key="index">
              {{ log.时间 }} · {{ log.动作 }}<template v-if="log.从">：{{ log.从 }} → {{ log.到 }}</template><template v-else>：{{ log.到 }}</template>
            </li>
            <li v-if="!detailLogs.length" class="empty-state">暂无流转记录</li>
          </ul>
        </template>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="closeDetail">关闭</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type EntryDetail = Record<string, unknown> & { 流转记录?: HistoryLog[] }
interface HistoryLog {
  动作?: string
  从?: string
  到?: string
  时间?: string
}
interface ActionReply {
  ok?: boolean
  message?: string
  detail?: string
}

const ENDPOINT = '/api/site'
const columns = ["基站编号", "基站名称", "基站类型", "所属区县", "经纬度坐标", "铁塔高度", "入网日期", "基站状态"]
const statuses = ["运行中", "退服中", "已退网", "已拆除"]
const stats = [{"label": "运行基站", "value": 0}, {"label": "退服基站", "value": 0}, {"label": "退网站点", "value": 0}]
const requiredFields = ["基站编号", "基站名称", "基站类型"]
const editableFields = columns.filter((column) => column !== '基站状态')
const FILTER_PARAMS: Record<string, string> = { 基站编号: 'keyword', 基站名称: 'name', 基站类型: 'station_type' }
const ACTIONS_BY_STATUS: Record<string, string[]> = {
  运行中: ['登记退服'],
  退服中: ['申请退网', '恢复'],
  已退网: ['拆站完成', '恢复'],
  已拆除: ['恢复'],
}
const ALL_ACTIONS = ['登记退服', '申请退网', '拆站完成', '恢复']

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)
const showCreate = ref(false)
const createForm = ref<Record<string, string>>({})
const showDetail = ref(false)
const detail = ref<EntryDetail | null>(null)
const detailLoading = ref(false)

const detailLogs = computed<HistoryLog[]>(() => {
  const logs = detail.value?.流转记录
  return Array.isArray(logs) ? logs : []
})

function cell(value: unknown): string {
  return value === null || value === undefined || value === '' ? '—' : String(value)
}

function availableActions(row: Row): string[] {
  const status = String(row.status ?? row['基站状态'] ?? '')
  return ACTIONS_BY_STATUS[status] ?? ALL_ACTIONS
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = ''
  noticeMessage.value = ''
  createForm.value = {}
  showCreate.value = true
}

async function readReply(response: Response): Promise<ActionReply> {
  return (await response.json().catch(() => ({}))) as ActionReply
}

async function submitCreate() {
  errorMessage.value = ''
  noticeMessage.value = ''
  const values = Object.fromEntries(
    Object.entries(createForm.value).filter(([, value]) => String(value ?? '').trim() !== ''),
  )
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = await readReply(response)
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.message ?? payload.detail ?? '基站登记未生效，请稍后重试')
    }
    showCreate.value = false
    noticeMessage.value = payload.message ?? '基站已登记'
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '基站登记失败'
  }
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  showDetail.value = true
  detailLoading.value = true
  detail.value = null
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    const payload = (await response.json().catch(() => null)) as (EntryDetail & ActionReply) | null
    if (!response.ok || !payload) {
      throw new Error(payload?.detail ?? '基站详情读取失败')
    }
    detail.value = payload
  } catch (error) {
    showDetail.value = false
    errorMessage.value = error instanceof Error ? error.message : '基站详情读取失败'
  } finally {
    detailLoading.value = false
  }
}

function closeDetail() {
  showDetail.value = false
  detail.value = null
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await readReply(response)
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.message ?? payload.detail ?? '基站台账动作未生效，请稍后重试')
    }
    noticeMessage.value = payload.message ?? '基站台账动作已生效'
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '基站台账操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  for (const [field, value] of Object.entries(filters.value)) {
    const key = FILTER_PARAMS[field]
    const text = String(value ?? '').trim()
    if (key && text) {
      params.set(key, text)
    }
  }
  const query = params.toString()
  try {
    const response = await request(query ? `${ENDPOINT}?${query}` : ENDPOINT)
    if (!response.ok) {
      throw new Error('基站列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '基站台账列表读取失败'
  }
}

onMounted(reload)
</script>
