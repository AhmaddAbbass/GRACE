import type {
  IndexJson,
  RetrieveResponse,
  AnswerResponse,
  ChatMessage,
  ChatHistory,
  KgSummary,
} from './types'

function encodeKgPath(id: string): string {
  return id
    .split('/')
    .map(encodeURIComponent)
    .join('/')
}

const EMPTY_NODE_HITS = {
  use_communities: [] as { id: number; report_string: string }[],
  use_reasoning_path: [] as {
    src_tgt: [string, string]
    description: string
    weight: number
  }[],
  node_datas: [] as {
    entity_name: string
    entity_type: string
    description: string
    rank: number
  }[],
  use_text_units: [] as { id: number; content: string | null }[],
}

function normaliseIndex(raw: any): IndexJson {
  const nodes = raw.nodes ?? raw.entity_graph?.nodes ?? []
  const edges = raw.edges ?? raw.entity_graph?.edges ?? []
  const chunks = raw.chunks ?? raw.entity_graph?.chunks ?? raw.chunk_map ?? {}
  return {
    kg_id: raw.kg_id,
    nodes,
    edges,
    chunks,
    metadata:
      raw.metadata ?? {
        run_id: raw.run_id ?? 'unknown',
        ts: raw.ts ?? new Date().toISOString(),
      },
  }
}

function normaliseRetrievePayload(input: any, fallbackKg?: string): RetrieveResponse {
  const payload = input?.payload ?? input ?? {}
  const nodeHits = payload.node_hits ?? {}
  return {
    kg_id: payload.kg_id ?? input?.kg_id ?? fallbackKg,
    run_id: payload.run_id ?? input?.run_id,
    qid: payload.qid ?? input?.qid ?? '',
    context: payload.context ?? '',
    node_hits: {
      use_communities: nodeHits.use_communities ?? EMPTY_NODE_HITS.use_communities,
      use_reasoning_path:
        nodeHits.use_reasoning_path ?? EMPTY_NODE_HITS.use_reasoning_path,
      node_datas: nodeHits.node_datas ?? EMPTY_NODE_HITS.node_datas,
      use_text_units: nodeHits.use_text_units ?? EMPTY_NODE_HITS.use_text_units,
    },
  }
}

export class ChatAPIError extends Error {
  statusCode?: number
  endpoint?: string
  constructor(message: string, statusCode?: number, endpoint?: string) {
    super(message)
    this.statusCode = statusCode
    this.endpoint = endpoint
    this.name = 'ChatAPIError'
  }
}

async function ensureOk(res: Response, endpoint: string) {
  if (!res.ok) {
    const text = await res.text()
    let message = `Request failed (${res.status})`
    try {
      const json = JSON.parse(text)
      message = json?.error?.message ?? message
    } catch (err) {
      /* ignore */
    }
    throw new ChatAPIError(message, res.status, endpoint)
  }
}

export async function listKgs(): Promise<KgSummary[]> {
  const res = await fetch('/kgs')
  await ensureOk(res, '/kgs')
  const json = await res.json()
  const items: any[] = json?.items ?? []
  return items.map((item) => ({
    kg_id: item.kg_id,
    name: item.name ?? item.kg_id,
    summary_status: item.summary_status,
    updated_at: item.updated_at,
  }))
}

export async function getIndex(kg: string): Promise<IndexJson> {
  const path = `/data/${encodeKgPath(kg)}`
  const res = await fetch(path)
  await ensureOk(res, path)
  const raw = await res.json()
  const normalised = normaliseIndex(raw)
  normalised.kg_id = normalised.kg_id ?? kg
  return normalised
}

export async function retrieve(
  kg: string,
  query: string,
  top_k?: number
): Promise<RetrieveResponse> {
  const payload: any = { query, kg }
  if (top_k !== undefined) payload.top_k = top_k

  const endpoint = '/retrieve'
  const res = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  await ensureOk(res, endpoint)
  const json = await res.json()

  if (Array.isArray(json?.results) && json.results.length > 0) {
    return normaliseRetrievePayload(
      json.results[0],
      json.results[0]?.kg_id ?? kg
    )
  }
  return normaliseRetrievePayload(json, kg)
}

export async function answer(
  kg: string,
  query: string,
  top_k?: number
): Promise<AnswerResponse> {
  const payload: any = { query, kg }
  if (top_k !== undefined) payload.top_k = top_k

  const endpoint = '/answer'
  const res = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  await ensureOk(res, endpoint)
  const json = await res.json()

  let base: RetrieveResponse
  if (Array.isArray(json?.results) && json.results.length > 0) {
    base = normaliseRetrievePayload(
      json.results[0],
      json.results[0]?.kg_id ?? kg
    )
    const answerText =
      json.results[0]?.payload?.answer ?? json.results[0]?.answer ?? ''
    return { ...base, answer: answerText }
  }
  base = normaliseRetrievePayload(json, kg)
  return { ...base, answer: json.answer ?? '' }
}

type BackendHistoryItem = {
  kg_id?: string
  run_id?: string
  qid?: string
  ts?: string
  query?: string
  answer?: string | null
  payload?: BackendHistoryItem
}

export async function getChatHistory(kg: string): Promise<ChatHistory> {
  const endpoint = `/history?kg=${encodeKgPath(kg)}`
  const res = await fetch(endpoint)
  await ensureOk(res, endpoint)
  const raw = await res.json()
  let records: BackendHistoryItem[] = []

  if (Array.isArray(raw)) {
    records = raw
  } else if (Array.isArray(raw?.items)) {
    records = raw.items.map((item: any) => ({
      kg_id: item.kg_id,
      run_id: raw.run_id ?? item.run_id,
      ...(item.payload ?? item),
    }))
  }

  const chat: ChatHistory = []
  for (const entry of records) {
    const payload = entry.payload ?? entry
    const qid = payload.qid ?? ''
    const ts = payload.ts ?? new Date().toISOString()
    const query = payload.query ?? ''
    chat.push({
      id: `${qid || Math.random()}_user`,
      type: 'user',
      content: query,
      timestamp: ts,
      qid,
    })
    if (payload.answer) {
      chat.push({
        id: `${qid}_assistant`,
        type: 'assistant',
        content: payload.answer,
        timestamp: ts,
        qid,
      })
    }
  }
  chat.sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  )
  return chat
}

export async function getContextData(
  kg: string,
  qid: string,
  runId?: string
): Promise<AnswerResponse | null> {
  const params = runId ? `?run_id=${encodeURIComponent(runId)}` : ''
  const endpoint = `/data/${encodeKgPath(kg)}/${encodeURIComponent(qid)}/context.json${params}`
  const res = await fetch(endpoint)
  if (!res.ok) return null
  const ctx = await res.json()
  return {
    kg_id: ctx.kg_id ?? kg,
    run_id: ctx.run_id,
    qid: ctx.qid,
    context: ctx.context ?? '',
    node_hits: ctx.node_hits ?? EMPTY_NODE_HITS,
    answer: ctx.answer ?? '',
  }
}

export async function sendChatMessage(
  kg: string,
  query: string,
  useAnswer: boolean = true,
  top_k?: number
): Promise<{
  userMessage: ChatMessage
  assistantMessage?: ChatMessage
  retrievalData: RetrieveResponse | AnswerResponse
}> {
  const timestamp = new Date().toISOString()
  const userMessage: ChatMessage = {
    id: `temp_user_${Date.now()}`,
    type: 'user',
    content: query,
    timestamp,
  }

  let retrievalData: RetrieveResponse | AnswerResponse
  let assistantMessage: ChatMessage | undefined

  if (useAnswer) {
    retrievalData = await answer(kg, query, top_k)
    assistantMessage = {
      id: `temp_assistant_${Date.now()}`,
      type: 'assistant',
      content: ("answer" in retrievalData ? (retrievalData as AnswerResponse).answer : ""),
      timestamp,
      qid: retrievalData.qid,
      retrieval: retrievalData,
    }
  } else {
    retrievalData = await retrieve(kg, query, top_k)
  }

  userMessage.qid = retrievalData.qid
  userMessage.retrieval = retrievalData

  return { userMessage, assistantMessage, retrievalData }
}

export function formatChatTimestamp(ts: string): string {
  const d = new Date(ts)
  const now = new Date()
  const diffH = (now.getTime() - d.getTime()) / 36e5
  if (diffH < 1) {
    const m = Math.max(1, Math.floor(diffH * 60))
    return m <= 1 ? 'Just now' : `${m}m ago`
  } else if (diffH < 24) {
    return `${Math.floor(diffH)}h ago`
  }
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function generateTempId(): string {
  return `temp_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
}

export function hasRetrievalData(m: ChatMessage): boolean {
  return !!(m.qid && (m.retrieval as any)?.node_hits)
}

