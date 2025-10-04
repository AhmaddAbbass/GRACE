import { useEffect, useMemo, useState, useCallback } from 'react'
import TopBar from './components/TopBar'
import ChatDock from './components/ChatDock'
import GraphCanvas from './components/GraphCanvas'
import Legend from './components/Legend'
import SideInfo from './components/SideInfo'
import { getIndex, getContextData, listKgs } from './api'
import { buildOverlay, type Overlay } from './overlay'
import type { ChatMessage, EdgeRec, IndexJson, NodeRec, KgSummary } from './types'
import './theme.css'

function App() {
  const [kgList, setKgList] = useState<KgSummary[]>([])
  const [selectedKg, setSelectedKg] = useState<string | null>(null)

  const [indexData, setIndexData] = useState<IndexJson | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [useAnswer, setUseAnswer] = useState(true)
  const [topK, setTopK] = useState(8)
  const [chatLoading, setChatLoading] = useState(false)
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([])
  const [activeOverlay, setActiveOverlay] = useState<Overlay | null>(null)
  const [mergedOverlay, setMergedOverlay] = useState<Overlay | null>(null)
  const [resetZoomTick, setResetZoomTick] = useState(0)

  const [selectedNode, setSelectedNode] = useState<NodeRec | null>(null)
  const [selectedLink, setSelectedLink] = useState<EdgeRec | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const items = await listKgs()
        setKgList(items)
        if (items.length > 0) {
          setSelectedKg((prev) => prev ?? items[0].kg_id)
        }
      } catch (e: any) {
        setError(e?.message ?? 'Failed to load knowledge graphs')
      }
    }
    load()
  }, [])

  useEffect(() => {
    if (!selectedKg) {
      setIndexData(null)
      setChatHistory([])
      setLoading(false)
      return
    }

    setLoading(true)
    setError(null)
    setActiveOverlay(null)
    setMergedOverlay(null)
    setSelectedNode(null)
    setSelectedLink(null)
    setChatHistory([])

    const loadIndex = async () => {
      try {
        const data = await getIndex(selectedKg)
        setIndexData(data)
      } catch (e: any) {
        setError(e?.message ?? String(e))
        setIndexData(null)
      } finally {
        setLoading(false)
      }
    }
    loadIndex()
  }, [selectedKg])

  useEffect(() => {
    if (!indexData) return
    const hits = new Set<string>()
    const pathNodes = new Set<string>()
    const pathEdges = new Set<string>()

    for (const msg of chatHistory) {
      if (!msg.retrieval || !indexData.nodes) continue
      const ov = buildOverlay(msg.retrieval as any, indexData.nodes)
      ov.hitNodeIds.forEach((id) => hits.add(id))
      ov.pathNodeIds.forEach((id) => pathNodes.add(id))
      ov.pathEdgeKeys.forEach((key) => pathEdges.add(key))
    }
    setMergedOverlay({ hitNodeIds: hits, pathNodeIds: pathNodes, pathEdgeKeys: pathEdges })
  }, [chatHistory, indexData])

  const handleMessageSelect = useCallback(
    async (msg: ChatMessage) => {
      if (!msg.qid || !indexData || !selectedKg) return
      setChatLoading(true)
      setSelectedNode(null)
      setSelectedLink(null)
      try {
        const ctx = await getContextData(selectedKg, msg.qid, (msg.retrieval as any)?.run_id)
        if (ctx) {
          const ov = buildOverlay(ctx, indexData.nodes)
          setActiveOverlay(ov)
          setChatHistory((prev) =>
            prev.map((m) => (m.id === msg.id ? { ...m, retrieval: ctx } : m))
          )
          setResetZoomTick((z) => z + 1)
        }
      } finally {
        setChatLoading(false)
      }
    },
    [indexData, selectedKg]
  )

  const clearHighlights = () => {
    setActiveOverlay(null)
    setSelectedNode(null)
    setSelectedLink(null)
  }

  const levels = useMemo(() => {
    const set = new Set<number>()
    for (const n of indexData?.nodes ?? []) set.add(n.level)
    return Array.from(set).sort((a, b) => a - b)
  }, [indexData?.nodes])

  const kgOptions = useMemo(
    () => kgList.map((kg) => ({ value: kg.kg_id, label: kg.name ?? kg.kg_id })),
    [kgList]
  )

  if (!selectedKg && kgList.length === 0) {
    return (
      <div className="center">
        <div className="spinner" />
        <div>Discovering knowledge graphs…</div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="center">
        <div className="spinner" />
        <div>Loading knowledge graph…</div>
      </div>
    )
  }

  if (error || !indexData || !selectedKg) {
    return (
      <div className="center">
        <div style={{ fontSize: 28 }}>:(</div>
        <div>Failed to load index</div>
        <div className="muted">{error}</div>
      </div>
    )
  }

  return (
    <div className="app-shell">
      <TopBar
        useAnswer={useAnswer}
        setUseAnswer={setUseAnswer}
        retrieving={chatLoading}
        topK={topK}
        setTopK={setTopK}
        onResetZoom={() => setResetZoomTick((t) => t + 1)}
        onClearHighlights={clearHighlights}
        hasActiveHighlights={!!(activeOverlay || mergedOverlay)}
        kgOptions={kgOptions}
        selectedKg={selectedKg}
        onKgChange={(kg) => setSelectedKg(kg)}
      />

      <div className="shell-body">
        <div className="shell-left">
          <ChatDock
            kg={selectedKg}
            useAnswer={useAnswer}
            topK={topK}
            onMessageSelect={handleMessageSelect}
            onHistoryChange={setChatHistory}
            isBusyExternal={chatLoading}
          />
        </div>

        <div className="shell-right">
          <div className="panel graph-host">
            <Legend levels={levels} showBridgeDashed />
            <GraphCanvas
              data={indexData}
              overlay={activeOverlay || mergedOverlay}
              resetZoomTick={resetZoomTick}
              onNodeSelect={(node) => {
                setSelectedLink(null)
                setSelectedNode(node)
              }}
              onLinkSelect={(link) => {
                setSelectedNode(null)
                setSelectedLink(link)
              }}
            />
          </div>
        </div>
      </div>

      <SideInfo
        node={selectedNode}
        link={selectedLink}
        chunks={indexData.chunks}
        onClose={() => {
          setSelectedNode(null)
          setSelectedLink(null)
        }}
      />
    </div>
  )
}

export default App
