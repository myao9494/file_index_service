/**
 * ステータス表示コンポーネント
 * - サービスの準備状態
 * - インデックス統計
 */
import { RefreshCw, CheckCircle, AlertCircle, Loader, Database } from 'lucide-react'

interface ServiceStatus {
  ready: boolean
  version: string
  paths: WatchPath[]
  total_indexed: number
}

interface WatchPath {
  status: string
}

interface Props {
  status: ServiceStatus | null
  onRefresh: () => void
}

function StatusView({ status, onRefresh }: Props) {
  if (!status) {
    return (
      <div className="card">
        <h2>
          <Database size={20} />
          サービス状態
        </h2>
        <p className="text-secondary">接続できません</p>
      </div>
    )
  }

  const isScanning = status.paths.some(p => p.status === 'scanning')
  const hasError = status.paths.some(p => p.status === 'error')

  return (
    <div className="card">
      <div className="flex-between mb-2">
        <h2>
          <Database size={20} />
          サービス状態
        </h2>
        <button onClick={onRefresh} title="更新">
          <RefreshCw size={16} />
        </button>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
        {isScanning ? (
          <span className="status-badge scanning">
            <Loader size={14} className="spin" />
            スキャン中
          </span>
        ) : hasError ? (
          <span className="status-badge error">
            <AlertCircle size={14} />
            エラー
          </span>
        ) : status.ready ? (
          <span className="status-badge ready">
            <CheckCircle size={14} />
            準備完了
          </span>
        ) : (
          <span className="status-badge idle">
            待機中
          </span>
        )}
      </div>

      <table>
        <tbody>
          <tr>
            <td className="text-secondary">バージョン</td>
            <td>{status.version}</td>
          </tr>
          <tr>
            <td className="text-secondary">インデックス数</td>
            <td>{status.total_indexed.toLocaleString()} ファイル</td>
          </tr>
          <tr>
            <td className="text-secondary">監視パス数</td>
            <td>{status.paths.length}</td>
          </tr>
          <tr>
            <td className="text-secondary">API URL</td>
            <td>
              <code style={{ backgroundColor: '#f5f5f5', padding: '2px 6px', borderRadius: '4px' }}>
                http://localhost:8080
              </code>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}

export default StatusView
