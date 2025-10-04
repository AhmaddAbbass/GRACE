import React, { useEffect, useRef, useState, useCallback } from 'react'
import type { ChatHistory, ChatMessage, ChatPanelState } from '../types'
import {
  getChatHistory,
  sendChatMessage,
  formatChatTimestamp,
  hasRetrievalData,
  ChatAPIError,
} from '../api'

type ChatDockProps = {
  kg?: string
  useAnswer: boolean
  topK: number
  onMessageSelect?: (message: ChatMessage) => void
  onHistoryChange?: (history: ChatHistory) => void
  isBusyExternal?: boolean
}

const ChatDock: React.FC<ChatDockProps> = ({
  kg,
  useAnswer,
  topK,
  onMessageSelect,
  onHistoryChange,
  isBusyExternal = false,
}) => {
  const [chatHistory, setChatHistory] = useState<ChatHistory>([])
  const [panel, setPanel] = useState<ChatPanelState>({
    isLoading: false,
    inputValue: '',
    activeQid: null,
  })
  const [error, setError] = useState<string | null>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const scrollToBottom = useCallback(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    (async () => {
      if (!kg) {
        setChatHistory([])
        return
      }
      try {
        setError(null)
        setPanel((p) => ({ ...p, isLoading: true }))
        const hist = await getChatHistory(kg)
        setChatHistory(hist)
      } catch (e) {
        setError(e instanceof ChatAPIError ? e.message : 'Failed to load history')
      } finally {
        setPanel((p) => ({ ...p, isLoading: false }))
      }
    })()
  }, [kg])

  useEffect(() => {
    onHistoryChange?.(chatHistory)
  }, [chatHistory, onHistoryChange])

  useEffect(() => {
    scrollToBottom()
  }, [chatHistory, panel.isLoading, scrollToBottom])

  const send = async () => {
    if (!kg) return
    const text = panel.inputValue.trim()
    if (!text || panel.isLoading || isBusyExternal) return
    try {
      setError(null)
      setPanel((p) => ({ ...p, isLoading: true, inputValue: '' }))
      const result = await sendChatMessage(kg, text, useAnswer, topK)
      const msgs: ChatMessage[] = [result.userMessage]
      if (result.assistantMessage) msgs.push(result.assistantMessage)
      setChatHistory((prev) => [...prev, ...msgs])

      const target = result.assistantMessage || result.userMessage
      if (hasRetrievalData(target) && onMessageSelect) {
        setPanel((p) => ({ ...p, activeQid: target.qid ?? null }))
        onMessageSelect(target)
      }
    } catch (e) {
      setError(e instanceof ChatAPIError ? e.message : 'Failed to send message')
    } finally {
      setPanel((p) => ({ ...p, isLoading: false }))
    }
  }

  const canSend =
    panel.inputValue.trim().length > 0 &&
    !panel.isLoading &&
    !isBusyExternal &&
    !!kg

  const kgLabel = kg ?? 'Select a KG'

  return (
    <aside className="chatdock">
      <div className="chatdock__header">
        <div>
          <div className="chatdock__title">RAG Chat</div>
          <div className="chatdock__subtitle">
            KG: <code>{kgLabel}</code> · {useAnswer ? 'Answer' : 'Retrieve'}
          </div>
        </div>
        <button
          className="icon-btn"
          title="Clear chat (local view)"
          onClick={() => {
            setChatHistory([])
            setError(null)
          }}
        >
          Clear
        </button>
      </div>

      <div className="chatdock__messages">
        {error && (
          <div className="notice notice--error">
            {error}
            <button className="notice__close" onClick={() => setError(null)}>
              ×
            </button>
          </div>
        )}

        {panel.isLoading && chatHistory.length === 0 && (
          <div className="notice">Loading chat history…</div>
        )}

        {!panel.isLoading && chatHistory.length === 0 && !error && (
          <div className="empty">
            <div className="empty__icon">💬</div>
            <div>Start a conversation!</div>
            <div className="empty__hint">
              Your messages will appear here and can highlight the graph.
            </div>
          </div>
        )}

        {chatHistory.map((m) => (
          <div
            key={m.id}
            className={`bubble ${m.type} ${m.qid === panel.activeQid ? 'is-active' : ''}`}
            onClick={() => {
              if (!m.qid || !onMessageSelect) return
              setPanel((p) => ({ ...p, activeQid: m.qid ?? null }))
              onMessageSelect(m)
            }}
            style={{ cursor: m.qid ? 'pointer' : 'default' }}
          >
            <div className="bubble__body">
              {m.content}
              {hasRetrievalData(m) && (
                <div className="bubble__meta">
                  <span>Click to highlight graph</span>
                </div>
              )}
            </div>
            <div className="bubble__ts">{formatChatTimestamp(m.timestamp)}</div>
          </div>
        ))}

        {panel.isLoading && (
          <div className="bubble assistant">
            <div className="bubble__body">
              <span className="dots">
                <i></i>
                <i></i>
                <i></i>
              </span>
              <span className="dots__label">
                {useAnswer ? 'Generating answer…' : 'Retrieving context…'}
              </span>
            </div>
          </div>
        )}

        <div ref={endRef} />
      </div>

      <div className="chatdock__input">
        <textarea
          ref={inputRef}
          className="chat-input"
          placeholder="Ask about the knowledge graph…"
          value={panel.inputValue}
          onChange={(e) => setPanel((p) => ({ ...p, inputValue: e.target.value }))}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              send()
            }
          }}
          rows={1}
          disabled={panel.isLoading || isBusyExternal || !kg}
        />
        <button className="send-btn" onClick={send} disabled={!canSend}>
          {panel.isLoading || isBusyExternal ? '…' : 'Send'}
        </button>
      </div>

      <div className="chatdock__hint">Press Enter to send · Shift+Enter for new line</div>
    </aside>
  )
}

export default ChatDock
