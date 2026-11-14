import { useCallback, useEffect, useState } from 'react'
import { apiGet, ApiError } from '../services/api'

interface ApiState<T> {
  data: T | null
  loading: boolean
  error: string | null
  refetch: () => void
}

export function useApi<T>(path: string | null): ApiState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState<boolean>(Boolean(path))
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)

  const refetch = useCallback(() => setNonce((value) => value + 1), [])

  useEffect(() => {
    if (!path) {
      setData(null)
      setLoading(false)
      setError(null)
      return
    }
    const controller = new AbortController()
    setLoading(true)
    setError(null)

    apiGet<T>(path, controller.signal)
      .then((payload) => {
        setData(payload)
        setLoading(false)
      })
      .catch((failure: unknown) => {
        if ((failure as Error)?.name === 'AbortError') return
        const message = failure instanceof ApiError ? failure.message : 'Error inesperado al consultar la API.'
        setError(message)
        setLoading(false)
      })

    return () => controller.abort()
  }, [path, nonce])

  return { data, loading, error, refetch }
}
