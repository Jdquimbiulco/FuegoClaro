const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000/api/v1'

export class ApiError extends Error {
  status: number
  code: string

  constructor(message: string, status = 0, code = 'NETWORK_ERROR') {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

export function apiBase(): string {
  return API_BASE
}

export function withQuery(path: string, params: Record<string, string | number | boolean | null | undefined> = {}): string {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value === null || value === undefined || value === '') return
    search.set(key, String(value))
  })
  const query = search.toString()
  return query ? `${path}${path.includes('?') ? '&' : '?'}${query}` : path
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, { signal, headers: { Accept: 'application/json' } })
  } catch (error) {
    if ((error as Error).name === 'AbortError') throw error
    throw new ApiError('No se pudo conectar con el backend. Verifica que FastAPI esté corriendo y que la URL de la API sea correcta.')
  }

  if (!response.ok) {
    let message = `Error ${response.status}`
    let code = 'HTTP_ERROR'
    try {
      const payload = await response.json()
      if (payload?.error) {
        message = payload.error.message ?? message
        code = payload.error.code ?? code
      } else if (payload?.detail) {
        message = typeof payload.detail === 'string' ? payload.detail : payload.detail.message ?? message
      }
    } catch {
      // respuesta no JSON
    }
    throw new ApiError(message, response.status, code)
  }

  return (await response.json()) as T
}

export function exportUrl(path: string): string {
  return `${API_BASE}${path}`
}
