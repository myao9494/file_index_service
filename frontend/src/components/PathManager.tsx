/**
 * 監視パス管理コンポーネント
 * - パスの追加・削除
 * - 再構築トリガー
 */
import { useState } from 'react'
import { FolderPlus, Trash2, RefreshCw, Loader, CheckCircle, AlertCircle } from 'lucide-react'

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

interface Props {
  paths: WatchPath[]
  onAddPath: (path: string) => void
  onRemovePath: (path: string) => void
  onRebuild: (path?: string) => void
}

function PathManager({ paths, onAddPath, onRemovePath, onRebuild }: Props) {
  const [newPath, setNewPath] = useState('')

  const handleAdd = () => {
    if (!newPath.trim()) return
    onAddPath(newPath.trim())
    setNewPath('')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleAdd()
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'watching':
        return <CheckCircle size={14} style={{ color: 'var(--success-color)' }} />
      case 'scanning':
        return <Loader size={14} className="spin" style={{ color: 'var(--warning-color)' }} />
      case 'error':
        return <AlertCircle size={14} style={{ color: 'var(--error-color)' }} />
      default:
        return null
    }
  }

  return (
    <div className="card">
      <div className="flex-between mb-2">
        <h2>
          <FolderPlus size={20} />
          監視パス管理
        </h2>
        <button className="primary" onClick={() => onRebuild()} title="全て再構築">
          <RefreshCw size={14} style={{ marginRight: '4px' }} />
          再構築
        </button>
      </div>

      <div className="flex mb-2">
        <input
          type="text"
          value={newPath}
          onChange={(e) => setNewPath(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="監視パスを入力... (例: /Users/example/Documents)"
          style={{ flex: 1 }}
        />
        <button className="primary" onClick={handleAdd}>
          <FolderPlus size={16} />
        </button>
      </div>

      {paths.length === 0 ? (
        <p className="text-secondary">監視パスがありません</p>
      ) : (
        <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
          {paths.map((p) => (
            <div
              key={p.path}
              style={{
                display: 'flex',
                alignItems: 'center',
                padding: '8px',
                borderBottom: '1px solid var(--border-color)',
              }}
            >
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {getStatusIcon(p.status)}
                  <span style={{ fontFamily: 'monospace', fontSize: '13px' }}>{p.path}</span>
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  {p.indexed_files.toLocaleString()} ファイル
                  {p.error_message && (
                    <span style={{ color: 'var(--error-color)', marginLeft: '8px' }}>
                      {p.error_message}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex">
                <button
                  onClick={() => onRebuild(p.path)}
                  title="再構築"
                  style={{ padding: '4px 8px' }}
                >
                  <RefreshCw size={14} />
                </button>
                <button
                  className="danger"
                  onClick={() => onRemovePath(p.path)}
                  title="削除"
                  style={{ padding: '4px 8px' }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default PathManager
