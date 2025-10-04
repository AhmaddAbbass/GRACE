export type Chunk = {
  tokens: number
  content: string
  chunk_order_index: number
  full_doc_id: string
}

export type NodeRec = {
  id: string
  label: string
  kind: string
  level: number
  degree: number
  betweenness: number
  cluster: number
  cluster_size: number
  tags: string[]
  saved_pos: [number, number] | null
  source_ids: string[]
  entity_type: string
  description: string
  source_id: string
  clusters: string
}

export type EdgeRec = {
  source: string
  target: string
  weight: number
  edge_type: string
  tags: string[]
  description: string
  source_id?: string
  order?: number
}

export type IndexJson = {
  kg_id?: string
  nodes: NodeRec[]
  edges: EdgeRec[]
  chunks: Record<string, Chunk>
  metadata: {
    run_id: string
    ts: string
  }
}

/** Retrieval payload (works for both retrieve and answer responses) */
export type RetrieveResponse = {
  kg_id?: string
  run_id?: string
  qid: string
  context: string
  node_hits: {
    use_communities: { id: number; report_string: string }[]
    use_reasoning_path: {
      src_tgt: [string, string]
      description: string
      weight: number
    }[]
    node_datas: {
      entity_name: string
      entity_type: string
      description: string
      rank: number
    }[]
    use_text_units: { id: number; content: string | null }[]
  }
}

export type RetrieveRequest = {
  query: string
  top_k?: number
}

export type AnswerRequest = {
  query: string
  top_k?: number
}

export type AnswerResponse = RetrieveResponse & { answer: string }

/* ---------------- Chat types ---------------- */

export type ChatMessage = {
  id: string
  type: 'user' | 'assistant'
  content: string
  timestamp: string
  qid?: string
  retrieval?: RetrieveResponse | AnswerResponse
}

export type ChatHistory = ChatMessage[]

export type ChatPanelState = {
  isLoading: boolean
  inputValue: string
  activeQid: string | null
}

export type KgSummary = {
  kg_id: string
  name: string
  summary_status?: string
  updated_at?: string
}
