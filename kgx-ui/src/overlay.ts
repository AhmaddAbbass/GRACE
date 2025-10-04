import type { RetrieveResponse, NodeRec } from './types'

/** strip wrapping quotes, whitespace, then uppercase */
const normalize = (s: string) =>
  s.replace(/^"+|"+$/g, '').trim().toUpperCase()

export type Overlay = {
  hitNodeIds: Set<string>
  pathNodeIds: Set<string>    // nodes that appear on reasoning-path edges
  pathEdgeKeys: Set<string>   // bidirectional keys "SRC||TGT"
}

/** Build overlay (hits + reasoning path) from a retrieval payload */
export function buildOverlay(res: RetrieveResponse, nodes: NodeRec[]): Overlay {
  // Map normalized id/label/description → node IDs (some KGs use label instead of id)
  const nameMap = new Map<string, string[]>()
  for (const n of nodes) {
    for (const key of [n.id, n.label, n.description]) {
      if (!key) continue
      const k = normalize(key)
      const arr = nameMap.get(k) || []
      arr.push(n.id)
      nameMap.set(k, arr)
    }
  }

  const hitNodeIds = new Set<string>()
  for (const nd of res.node_hits.node_datas) {
    const k = normalize(nd.entity_name)
    for (const id of nameMap.get(k) || []) hitNodeIds.add(id)
  }

  const reasoning = res.node_hits.use_reasoning_path ?? []
  const pathNodeIds = new Set<string>()
  const pathEdgeKeys = new Set<string>()
  for (const p of reasoning) {
    const [sNorm, tNorm] = p.src_tgt.map(normalize)
    for (const id of nameMap.get(sNorm) || []) pathNodeIds.add(id)
    for (const id of nameMap.get(tNorm) || []) pathNodeIds.add(id)
    pathEdgeKeys.add(`${sNorm}||${tNorm}`)
    pathEdgeKeys.add(`${tNorm}||${sNorm}`)
  }

  return { hitNodeIds, pathNodeIds, pathEdgeKeys }
}

/** Build the same key whether source/target are strings or node objects */
export function edgeKey(e: any): string {
  const g = (x: any) => (typeof x === 'string' ? normalize(x) : normalize(x?.id ?? ''))
  return `${g(e.source)}||${g(e.target)}`
}
