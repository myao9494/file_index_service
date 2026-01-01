/**
 * File Index Service GUI - メインアプリケーション
 * - 検索テスト
 * - 監視パス管理
 * - インデックス状態表示
 */
import { useState, useEffect, useCallback } from 'react'
import { Database, Loader } from 'lucide-react'
import StatusView from './components/StatusView'
import PathManager from './components/PathManager'
import IgnoreManager from './components/IgnoreManager'
import SearchTest from './components/SearchTest'

const API_BASE = 'http://localhost:8080'

interface ServiceStatus {
  ready: boolean
  version: string
  paths: WatchPath[]
  total_indexed: number
}

interface WatchPath {
  id: number
  path: string
  enabled: number
  status: string
  total_files: number
  indexed_files: number
  last_full_scan: number | null
  last_updated: number | null
  error_message: string | null
}

function App() {
  const [status, setStatus] = useState<ServiceStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/status`)
      if (!response.ok) throw new Error('ステータス取得に失敗しました')
      const data = await response.json()
      setStatus(data)
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 5000) // 5秒ごとに更新
    return () => clearInterval(interval)
  }, [fetchStatus])

  const handleAddPath = async (path: string) => {
    try {
      const response = await fetch(`${API_BASE}/paths`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
      })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'パスの追加に失敗しました')
      }
      fetchStatus()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const handleRemovePath = async (path: string) => {
    if (!confirm(`監視パス「${path}」を削除しますか？`)) return

    try {
      const response = await fetch(`${API_BASE}/paths?path=${encodeURIComponent(path)}`, {
        method: 'DELETE',
      })
      if (!response.ok) throw new Error('パスの削除に失敗しました')
      fetchStatus()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const handleRebuild = async (path?: string) => {
    try {
      const url = path
        ? `${API_BASE}/rebuild?path=${encodeURIComponent(path)}`
        : `${API_BASE}/rebuild`
      const response = await fetch(url, { method: 'POST' })
      if (!response.ok) throw new Error('再構築の開始に失敗しました')
      fetchStatus()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  if (loading) {
    return (
      <div className="container" style={{ textAlign: 'center', padding: '100px 0' }}>
        <Loader size={48} className="spin" style={{ color: 'var(--primary-color)' }} />
        <p style={{ marginTop: '16px' }}>読み込み中...</p>
      </div>
    )
  }

  return (
    <>
      <header className="header">
        <h1>
          <Database size={24} style={{ verticalAlign: 'middle', marginRight: '8px' }} />
          File Index Service
        </h1>
        <p className="subtitle">Everything互換ファイルインデックス検索サービス</p>
      </header>

      <div className="container">
        {error && (
          <div className="card" style={{ backgroundColor: '#ffebee', borderColor: 'var(--error-color)' }}>
            <p style={{ color: 'var(--error-color)' }}>エラー: {error}</p>
            <button onClick={() => setError(null)} style={{ marginTop: '8px' }}>
              閉じる
            </button>
          </div>
        )}

        <div className="grid">
          <StatusView
            status={status}
            onRefresh={fetchStatus}
          />

          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <PathManager
              paths={status?.paths || []}
              onAddPath={handleAddPath}
              onRemovePath={handleRemovePath}
              onRebuild={handleRebuild}
            />
            <IgnoreManager
              apiBase={API_BASE}
              onError={setError}
            />
          </div>
        </div>

        <SearchTest apiBase={API_BASE} />
      </div>
    </>
  )
}

export default App
