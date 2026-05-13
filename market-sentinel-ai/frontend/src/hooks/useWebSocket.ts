import { useEffect, useRef, useCallback } from 'react'

export type WsEventType = 'signal' | 'trade' | 'risk' | 'portfolio' | 'heartbeat'

export interface WsEvent<T = unknown> {
  type: WsEventType
  data: T
  ts: string
}

type Handler<T = unknown> = (event: WsEvent<T>) => void

/**
 * Connect to the backend WebSocket at /ws and call handlers for each event type.
 * Auto-reconnects with exponential backoff on disconnect.
 */
export function useWebSocket(handlers: Partial<Record<WsEventType | 'any', Handler>>) {
  const wsRef = useRef<WebSocket | null>(null)
  const handlersRef = useRef(handlers)
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const retryDelay = useRef(1000)
  const unmounted = useRef(false)

  handlersRef.current = handlers

  const connect = useCallback(() => {
    if (unmounted.current) return

    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const url = `${proto}://${window.location.host}/ws`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      retryDelay.current = 1000
    }

    ws.onmessage = (ev) => {
      try {
        const event: WsEvent = JSON.parse(ev.data)
        const h = handlersRef.current
        h[event.type]?.(event as WsEvent<never>)
        h['any']?.(event)
      } catch {
        // ignore malformed messages
      }
    }

    ws.onclose = () => {
      if (unmounted.current) return
      retryRef.current = setTimeout(() => {
        retryDelay.current = Math.min(retryDelay.current * 2, 30_000)
        connect()
      }, retryDelay.current)
    }

    ws.onerror = () => ws.close()
  }, [])

  useEffect(() => {
    unmounted.current = false
    connect()
    return () => {
      unmounted.current = true
      if (retryRef.current) clearTimeout(retryRef.current)
      wsRef.current?.close()
    }
  }, [connect])
}
