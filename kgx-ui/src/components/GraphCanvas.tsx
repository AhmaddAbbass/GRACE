import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import type { ForceGraphMethods } from 'react-force-graph-2d'
import * as d3 from 'd3-force'
import type { EdgeRec, IndexJson, NodeRec } from '../types'
import { edgeKey, type Overlay } from '../overlay'

type Props = {
  data: IndexJson
  overlay?: Overlay | null
  resetZoomTick?: number
  onNodeSelect?: (n: NodeRec) => void
  onLinkSelect?: (l: EdgeRec) => void
}

const PATH_FILL = '#3B82F6'
const HIT_FILL = '#dc143c'
const PATH_EDGE = '#FB8C00'
const OTHER_EDGE = 'rgba(0,0,0,0.1)'

const LEVEL_PALETTE = [
  '#4F46E5', '#10B981', '#F59E0B', '#06B6D4', '#8B5CF6',
  '#22C55E', '#F97316', '#14B8A6', '#A855F7', '#84CC16',
  '#0EA5E9', '#E11D48', '#7C3AED', '#059669', '#D97706',
  '#0D9488', '#DB2777', '#2563EB', '#16A34A', '#EA580C',
  '#1E293B', '#EF4444', '#0284C7', '#6D28D9', '#65A30D',
  '#DC2626', '#0891B2', '#9333EA', '#22D3EE', '#F43F5E',
]

const GraphCanvas: React.FC<Props> = memo(({ data, overlay, resetZoomTick, onNodeSelect, onLinkSelect }) => {
  const fgRef = useRef<ForceGraphMethods | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [dims, setDims] = useState({ w: 0, h: 0 })
  const zoomSigRef = useRef('')

const updateDims = useCallback(() => {
  if (!containerRef.current) return
  setDims({
    w: containerRef.current.clientWidth,
    h: containerRef.current.clientHeight,
  })
}, [])

useEffect(() => {
  if (!containerRef.current) return
  updateDims()
  const ro = new ResizeObserver(() => updateDims())
  ro.observe(containerRef.current)
  return () => ro.disconnect()
}, [updateDims])

  const levelColorMap = useMemo(() => {
    const levels = Array.from(new Set((data.nodes ?? []).map((n) => n.level))).sort((a, b) => a - b)
    const m = new Map<number, string>()
    levels.forEach((lvl, index) => m.set(lvl, LEVEL_PALETTE[index % LEVEL_PALETTE.length]))
    return m
  }, [data.nodes])

  const getLevelColor = (lvl: number) => levelColorMap.get(lvl) ?? LEVEL_PALETTE[lvl % LEVEL_PALETTE.length]

  const hasOverlay = !!(
    overlay && (overlay.hitNodeIds.size || overlay.pathNodeIds.size || overlay.pathEdgeKeys.size)
  )
  const isHitNode = (n: NodeRec) => overlay?.hitNodeIds.has(n.id) ?? false
  const isPathNode = (n: NodeRec) => overlay?.pathNodeIds.has(n.id) ?? false
  const isPathEdge = (l: any) => overlay?.pathEdgeKeys.has(edgeKey(l)) ?? false

  useEffect(() => {
    if (!fgRef.current) return
    const focusSet = new Set<string>([
      ...(overlay?.hitNodeIds ?? new Set<string>()),
      ...(overlay?.pathNodeIds ?? new Set<string>()),
    ])
    if (focusSet.size === 0) return

    const signature = Array.from(focusSet).sort().join('|')
    if (signature === zoomSigRef.current) return
    zoomSigRef.current = signature

    requestAnimationFrame(() => {
      ;(fgRef.current as any).zoomToFit(500, 40, (n: any) => focusSet.has((n as NodeRec).id))
      fgRef.current!.d3ReheatSimulation()
    })
  }, [overlay])

  useEffect(() => {
    if (!fgRef.current || resetZoomTick === undefined) return
    requestAnimationFrame(() => {
      ;(fgRef.current as any).zoomToFit(500, 40)
      fgRef.current!.d3ReheatSimulation()
      zoomSigRef.current = 'reset'
    })
  }, [resetZoomTick])

  const [minLevel, maxLevel] = useMemo(() => {
    if (!data.nodes?.length) return [0, 0]
    let min = Infinity
    let max = -Infinity
    for (const n of data.nodes) {
      if (n.level < min) min = n.level
      if (n.level > max) max = n.level
    }
    return [Number.isFinite(min) ? min : 0, Number.isFinite(max) ? max : 0]
  }, [data.nodes])

  useEffect(() => {
    if (!fgRef.current || dims.h === 0) return
    const levels = maxLevel - minLevel + 1 || 1
    const padding = 48
    const innerHeight = Math.max(1, dims.h - padding * 2)
    const spacing = innerHeight / levels
    const yFor = (lvl: number) => (dims.h - padding) - (lvl - minLevel) * spacing

    fgRef.current.d3Force('levelY', d3.forceY((d: any) => yFor((d as NodeRec).level)).strength(0.2))
    fgRef.current.d3Force('xCenter', d3.forceX(0).strength(0.002))
    fgRef.current.d3ReheatSimulation()
  }, [dims.h, minLevel, maxLevel])

  const graphData = useMemo(() => ({
    nodes: data.nodes,
    links: data.edges as EdgeRec[],
  }), [data.nodes, data.edges])

  const resolveNodeStyle = (n: NodeRec) => {
    const levelColor = getLevelColor(n.level)
    if (!hasOverlay) {
      return { fill: levelColor, stroke: 'transparent', lineWidth: 0, glow: false, r: 3 }
    }
    if (isHitNode(n)) {
      return { fill: HIT_FILL, stroke: levelColor, lineWidth: 2, glow: true, r: 5 }
    }
    if (isPathNode(n)) {
      return { fill: PATH_FILL, stroke: levelColor, lineWidth: 2, glow: false, r: 4 }
    }
    return { fill: levelColor, stroke: 'transparent', lineWidth: 0, glow: false, r: 3 }
  }

  return (
    <div ref={containerRef} className="graph-viewport">
      <ForceGraph2D
        ref={fgRef as any}
        graphData={graphData}
        width={dims.w}
        height={dims.h}
        backgroundColor="var(--panel)"
        nodeLabel={(n) => (n as NodeRec).label}
        linkWidth={(link) => (isPathEdge(link) ? 3 : 1)}
        linkColor={(link) => (isPathEdge(link) ? PATH_EDGE : OTHER_EDGE)}
        linkCanvasObjectMode={(link) =>
          (link as EdgeRec).edge_type === 'bridge' && isPathEdge(link) ? 'replace' : undefined
        }
        linkCanvasObject={(link, ctx) => {
          const l = link as EdgeRec
          if (!(l.edge_type === 'bridge' && isPathEdge(link))) return
          const { x: x1, y: y1 } = (link as any).source
          const { x: x2, y: y2 } = (link as any).target
          ctx.save()
          ctx.beginPath()
          ctx.setLineDash([6, 6])
          ctx.lineWidth = 3
          ctx.strokeStyle = PATH_EDGE
          ctx.moveTo(x1, y1)
          ctx.lineTo(x2, y2)
          ctx.stroke()
          ctx.restore()
        }}
        onNodeClick={(node) => onNodeSelect?.(node as NodeRec)}
        onLinkClick={(link) => onLinkSelect?.(link as EdgeRec)}
        cooldownTicks={300}
        nodeCanvasObject={(node, ctx, globalScale) => {
          const n = node as NodeRec
          const { fill, stroke, lineWidth, glow, r } = resolveNodeStyle(n)

          ctx.shadowBlur = glow ? 8 : 0
          ctx.shadowColor = HIT_FILL

          ctx.fillStyle = fill
          ctx.strokeStyle = stroke
          ctx.lineWidth = lineWidth

          ctx.beginPath()
          ctx.arc(node.x!, node.y!, r, 0, 2 * Math.PI, false)
          ctx.fill()
          if (lineWidth > 0) ctx.stroke()
          ctx.shadowBlur = 0

          const labelZoom = isHitNode(n) ? 1.5 : 4
          if (isHitNode(n) || globalScale > labelZoom) {
            const fontSize = 12 / globalScale
            ctx.font = `${fontSize}px sans-serif`
            ctx.fillStyle = isHitNode(n) || isPathNode(n) ? '#000' : '#1a1a1a'
            ctx.textAlign = 'center'
            ctx.textBaseline = 'top'
            ctx.fillText(n.label, node.x!, node.y! + r + 2)
          }
        }}
      />
    </div>
  )
})

export default GraphCanvas
