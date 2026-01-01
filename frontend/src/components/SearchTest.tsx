/**
 * 検索テストコンポーネント
 * - Everything互換APIの動作確認
 * - 検索結果の表示
 */
import { useState, useCallback } from 'react'
import { Search, File, Folder, Clock } from 'lucide-react'

interface SearchResult {
  name: string
  path: string
  type: string
  size: number
  date_modified: number
}

interface SearchResponse {
  totalResults: number
  results: SearchResult[]
}

interface Props {
  apiBase: string
}

function SearchTest({ apiBase }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchTime, setSearchTime] = useState<number | null>(null)
  const [fileType, setFileType] = useState<'all' | 'file' | 'directory'>('all')
  const [count, setCount] = useState(100)

  const handleSearch = useCallback(async () => {
    if (!query.trim()) {
      setResults(null)
      return
    }

    setLoading(true)
    setError(null)
    const startTime = performance.now()

    try {
      const params = new URLSearchParams({
        search: query,
        json: '1',
        count: count.toString(),
        file_type: fileType,
      })

      const response = await fetch(`${apiBase}/?${params}`)
      if (!response.ok) throw new Error('検索に失敗しました')

      const data = await response.json()
      setResults(data)
      setSearchTime(performance.now() - startTime)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [apiBase, query, count, fileType])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch()
    }
  }

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
  }

  const formatDate = (timestamp: number) => {
    if (!timestamp) return '-'
    return new Date(timestamp * 1000).toLocaleString('ja-JP')
  }

  return (
    <div className="card">
      <h2>
        <Search size={20} />
        検索テスト
      </h2>

      <div className="flex mb-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="検索クエリを入力..."
          style={{ flex: 1 }}
        />
        <select
          value={fileType}
          onChange={(e) => setFileType(e.target.value as 'all' | 'file' | 'directory')}
          style={{ padding: '8px', borderRadius: '4px', border: '1px solid var(--border-color)' }}
        >
          <option value="all">全て</option>
          <option value="file">ファイル</option>
          <option value="directory">フォルダ</option>
        </select>
        <select
          value={count}
          onChange={(e) => setCount(parseInt(e.target.value))}
          style={{ padding: '8px', borderRadius: '4px', border: '1px solid var(--border-color)' }}
        >
          <option value="50">50件</option>
          <option value="100">100件</option>
          <option value="500">500件</option>
          <option value="1000">1000件</option>
        </select>
        <button className="primary" onClick={handleSearch} disabled={loading}>
          <Search size={16} />
          検索
        </button>
      </div>

      {error && (
        <p style={{ color: 'var(--error-color)', marginBottom: '16px' }}>{error}</p>
      )}

      {results && (
        <>
          <div className="flex-between mb-2">
            <p>
              検索結果: <strong>{results.totalResults.toLocaleString()}</strong> 件
            </p>
            {searchTime && (
              <p className="text-secondary">
                <Clock size={14} style={{ verticalAlign: 'middle', marginRight: '4px' }} />
                {searchTime.toFixed(1)} ms
              </p>
            )}
          </div>

          {results.results.length > 0 ? (
            <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
              <table>
                <thead>
                  <tr>
                    <th style={{ width: '40px' }}></th>
                    <th>名前</th>
                    <th>パス</th>
                    <th style={{ width: '100px' }}>サイズ</th>
                    <th style={{ width: '160px' }}>更新日時</th>
                  </tr>
                </thead>
                <tbody>
                  {results.results.map((item, i) => (
                    <tr key={i}>
                      <td>
                        {item.type === 'directory' ? (
                          <Folder size={16} style={{ color: '#f9a825' }} />
                        ) : (
                          <File size={16} style={{ color: '#42a5f5' }} />
                        )}
                      </td>
                      <td>{item.name}</td>
                      <td style={{ fontFamily: 'monospace', fontSize: '12px', color: 'var(--text-secondary)' }}>
                        {item.path}
                      </td>
                      <td>{item.type === 'file' ? formatSize(item.size) : '-'}</td>
                      <td style={{ fontSize: '12px' }}>{formatDate(item.date_modified)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-secondary">結果がありません</p>
          )}
        </>
      )}

      {!results && !loading && (
        <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
          <Search size={48} style={{ opacity: 0.3 }} />
          <p style={{ marginTop: '16px' }}>検索クエリを入力して検索ボタンを押してください</p>
          <p style={{ fontSize: '12px', marginTop: '8px' }}>
            Everything互換API: <code>/?search=クエリ&json=1</code>
          </p>
        </div>
      )}
    </div>
  )
}

export default SearchTest
