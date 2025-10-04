import React from 'react'
import type { Chunk, EdgeRec, NodeRec } from '../types'

type Props = {
  node?: NodeRec | null
  link?: EdgeRec | null
  chunks: Record<string, Chunk>
  onClose: () => void
}

const SideInfo: React.FC<Props> = ({ node, link, chunks, onClose }) => {
  const open = !!(node || link)

  return (
    <>
      {open && <div className="drawer-backdrop" onClick={onClose} />}

      <aside className={`drawer ${open ? 'drawer--open' : ''}`}>
        <div className="drawer__header">
          <div className="drawer__title">{node ? 'Node Details' : 'Edge Details'}</div>
          <button className="drawer__close" onClick={onClose}>✕</button>
        </div>

        <div className="drawer__body">
          {!node && !link && <div>No selection.</div>}

          {node && (
            <>
              <section className="section">
                <div className="section__title">Metadata</div>
                <ul className="kv">
                  <li><b>ID:</b> {node.id}</li>
                  <li><b>Label:</b> {node.label}</li>
                  <li><b>Kind:</b> {node.kind}</li>
                  <li><b>Level:</b> {node.level}</li>
                  <li><b>Degree:</b> {node.degree}</li>
                  <li><b>Betweenness:</b> {node.betweenness}</li>
                  <li><b>Cluster:</b> {node.cluster} (size {node.cluster_size})</li>
                  <li><b>Entity Type:</b> {node.entity_type}</li>
                </ul>
              </section>

              <section className="section">
                <div className="section__title">Description</div>
                <p>{node.description}</p>
              </section>

              <section className="section">
                <div className="section__title">Source Chunks</div>
                {!node.source_ids?.length && <div className="muted">None</div>}
                {node.source_ids?.map(cid => (
                  <pre key={cid} className="chunk">{chunks[cid]?.content ?? '[missing]'}</pre>
                ))}
              </section>
            </>
          )}

          {link && (
            <>
              <section className="section">
                <div className="section__title">Edge Metadata</div>
                <ul className="kv">
                  <li><b>Source:</b> {typeof link.source === 'string' ? link.source : (link.source as NodeRec).id}</li>
                  <li><b>Target:</b> {typeof link.target === 'string' ? link.target : (link.target as NodeRec).id}</li>
                  <li><b>Weight:</b> {link.weight}</li>
                  <li><b>Type:</b> {link.edge_type}</li>
                  <li><b>Description:</b> {link.description}</li>
                </ul>
              </section>

              <section className="section">
                <div className="section__title">Source Chunk</div>
                <pre className="chunk">{chunks[link.source_id ?? '']?.content ?? '[missing]'}</pre>
              </section>
            </>
          )}
        </div>
      </aside>
    </>
  )
}

export default SideInfo
