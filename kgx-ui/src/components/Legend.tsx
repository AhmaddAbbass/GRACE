import React, { useMemo, useState } from 'react'

type LegendProps = {
  /** All distinct node levels in current graph (sorted). */
  levels: number[]
  /** Show dashed swatch caption for bridge edges. */
  showBridgeDashed?: boolean
}

const PATH_FILL = '#3B82F6'

// same palette as GraphCanvas
const LEVEL_PALETTE = [
  '#4F46E5', '#10B981', '#F59E0B', '#06B6D4', '#8B5CF6',
  '#22C55E', '#F97316', '#14B8A6', '#A855F7', '#84CC16',
  '#0EA5E9', '#E11D48', '#7C3AED', '#059669', '#D97706',
  '#0D9488', '#DB2777', '#2563EB', '#16A34A', '#EA580C',
  '#1E293B', '#ef4444', '#0284C7', '#6D28D9', '#65A30D',
  '#DC2626', '#0891B2', '#9333EA', '#22D3EE', '#F43F5E'
]

const Legend: React.FC<LegendProps> = ({ levels, showBridgeDashed = true }) => {
  const [open, setOpen] = useState(true)

  const levelColorMap = useMemo(() => {
    const sorted = (levels ?? []).slice().sort((a, b) => a - b)
    const m = new Map<number, string>()
    sorted.forEach((lvl, i) => m.set(lvl, LEVEL_PALETTE[i % LEVEL_PALETTE.length]))
    return m
  }, [levels])

  const getLevelColor = (lvl: number) =>
    levelColorMap.get(lvl) ?? LEVEL_PALETTE[lvl % LEVEL_PALETTE.length]

  if (!open) {
    return (
      <button className="legend-toggle" onClick={() => setOpen(true)} aria-label="Show legend">
        ℹ️
      </button>
    )
  }

  return (
    <div className="legend">
      <button className="legend__close" onClick={() => setOpen(false)} aria-label="Close legend">✕</button>
      <div className="legend__title">Legend</div>

      <ul className="legend__list">
        <li>
          <span className="swatch swatch--hit" />
          Hit node
        </li>
        <li>
          <span
            className="swatch"
            style={{ ['--swatch-bg' as any]: PATH_FILL, border: '2px solid #3b5bdb55' }}
          />
          Path node
        </li>
        <li>
          <span className="swatch swatch--path-edge" />
          Path edge
        </li>
        {showBridgeDashed && (
          <li>
            <span className="swatch swatch--bridge" />
            Bridge edge
          </li>
        )}
      </ul>

      {!!levels?.length && (
        <>
          <div className="legend__section">Levels</div>
          <ul className="legend__list">
            {levels.slice().sort((a, b) => a - b).map(lvl => (
              <li key={lvl}>
                <span
                  className="swatch"
                  style={{ ['--swatch-bg' as any]: getLevelColor(lvl) }}
                />
                Level {lvl}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

export default Legend
