import React, { useEffect, useState } from 'react'

type KgOption = { value: string; label: string }

type TopBarProps = {
  useAnswer: boolean
  setUseAnswer: (b: boolean) => void
  retrieving?: boolean
  topK: number
  setTopK: (n: number) => void
  onResetZoom?: () => void
  onClearHighlights?: () => void
  hasActiveHighlights?: boolean
  kgOptions?: KgOption[]
  selectedKg?: string | null
  onKgChange?: (kg: string) => void
}

const TopBar: React.FC<TopBarProps> = ({
  useAnswer,
  setUseAnswer,
  retrieving = false,
  topK,
  setTopK,
  onResetZoom,
  onClearHighlights,
  hasActiveHighlights = false,
  kgOptions = [],
  selectedKg = null,
  onKgChange,
}) => {
  const [topKText, setTopKText] = useState(String(topK))
  useEffect(() => setTopKText(String(topK)), [topK])

  const commitTopK = () => {
    let v = parseInt(topKText, 10)
    if (isNaN(v) || v < 1) v = 1
    if (v !== topK) setTopK(v)
    setTopKText(String(v))
  }

  return (
    <header className="topbar">
      <div className="topbar__left">
        <div className="brand">
          <span className="brand__logo">KG</span>
          <div className="brand__text">
            <div className="brand__title">KG Explorer</div>
            <div className="brand__sub">Chat · Retrieve · Visualize</div>
          </div>
        </div>
      </div>

      <div className="topbar__center">
        <div className="chip">
          <label htmlFor="tb-kg">KG</label>
          <select
            id="tb-kg"
            value={selectedKg ?? ''}
            onChange={(e) => onKgChange?.(e.target.value)}
            className="chip__input"
          >
            {kgOptions.length === 0 && <option value="" disabled>Loading…</option>}
            {kgOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <label className="chip">
          <input
            type="checkbox"
            checked={useAnswer}
            onChange={(e) => setUseAnswer(e.target.checked)}
          />
          <span>Full Answer</span>
        </label>

        <div className="chip">
          <label htmlFor="tb-topk">top_k</label>
          <input
            id="tb-topk"
            type="number"
            min={1}
            value={topKText}
            onChange={(e) => setTopKText(e.target.value)}
            onBlur={commitTopK}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                commitTopK()
                ;(e.target as HTMLInputElement).blur()
              }
            }}
            className="chip__input"
          />
        </div>

        {retrieving && (
          <div className="status-dot">
            <span className="dot" />
            <span>Processing…</span>
          </div>
        )}
      </div>

      <div className="topbar__right">
        <button className="btn" title="Zoom to fit" onClick={onResetZoom}>
          Zoom
        </button>
        <button
          className="btn"
          title="Clear graph highlights"
          onClick={onClearHighlights}
          disabled={!hasActiveHighlights}
        >
          Clear
        </button>
      </div>
    </header>
  )
}

export default TopBar
