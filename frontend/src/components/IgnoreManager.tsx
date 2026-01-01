/**
 * 除外パターン管理コンポーネント
 * - 除外パターンの追加・削除
 * - Pythonデフォルトパターンの追加
 */
import { useState, useEffect } from 'react'
import { EyeOff, Trash2, Plus, Code } from 'lucide-react'

interface Props {
    apiBase: string
    onError: (msg: string) => void
}

function IgnoreManager({ apiBase, onError }: Props) {
    const [patterns, setPatterns] = useState<string[]>([])
    const [newPattern, setNewPattern] = useState('')
    const [loading, setLoading] = useState(false)

    const fetchPatterns = async () => {
        try {
            const res = await fetch(`${apiBase}/ignores`)
            if (!res.ok) throw new Error('除外パターンの取得に失敗しました')
            const data = await res.json()
            setPatterns(data)
        } catch (e) {
            onError((e as Error).message)
        }
    }

    useEffect(() => {
        fetchPatterns()
    }, [])

    const handleAdd = async () => {
        if (!newPattern.trim()) return
        try {
            setLoading(true)
            const res = await fetch(`${apiBase}/ignores`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pattern: newPattern.trim() }),
            })
            if (!res.ok) {
                const data = await res.json().catch(() => ({}))
                throw new Error(data.detail || '除外パターンの追加に失敗しました')
            }
            await fetchPatterns()
            setNewPattern('')
        } catch (e) {
            onError((e as Error).message)
        } finally {
            setLoading(false)
        }
    }

    const handleRemove = async (pattern: string) => {
        if (!confirm(`除外パターン「${pattern}」を削除しますか？`)) return
        try {
            const res = await fetch(`${apiBase}/ignores?pattern=${encodeURIComponent(pattern)}`, {
                method: 'DELETE',
            })
            if (!res.ok) throw new Error('除外パターンの削除に失敗しました')
            fetchPatterns()
        } catch (e) {
            onError((e as Error).message)
        }
    }

    const handleAddDefaults = async () => {
        if (!confirm('Python開発で一般的な除外パターンを一括追加しますか？\n(例: node_modules, __pycache__, .git 等)')) return
        try {
            setLoading(true)
            const res = await fetch(`${apiBase}/ignores/defaults`, {
                method: 'POST',
            })
            if (!res.ok) throw new Error('デフォルトパターンの追加に失敗しました')
            await fetchPatterns()
            alert('追加しました')
        } catch (e) {
            onError((e as Error).message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="card">
            <div className="flex-between mb-2">
                <h2>
                    <EyeOff size={20} />
                    除外設定
                </h2>
                <button className="secondary" onClick={handleAddDefaults} disabled={loading} title="Pythonデフォルト設定を追加">
                    <Code size={14} style={{ marginRight: '4px' }} />
                    Pythonデフォルト
                </button>
            </div>

            <div className="flex mb-2">
                <input
                    type="text"
                    value={newPattern}
                    onChange={(e) => setNewPattern(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
                    placeholder="除外パターン (例: *.log, temp)"
                    style={{ flex: 1 }}
                />
                <button className="primary" onClick={handleAdd} disabled={loading || !newPattern.trim()}>
                    <Plus size={16} />
                </button>
            </div>

            <div style={{ maxHeight: '200px', overflowY: 'auto', display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {patterns.length === 0 ? (
                    <p className="text-secondary" style={{ width: '100%' }}>除外パターンはありません</p>
                ) : (
                    patterns.map((p) => (
                        <div
                            key={p}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                backgroundColor: 'var(--bg-secondary)',
                                padding: '4px 8px',
                                borderRadius: '4px',
                                fontSize: '13px',
                            }}
                        >
                            <span style={{ fontFamily: 'monospace', marginRight: '6px' }}>{p}</span>
                            <button
                                className="icon-btn danger"
                                onClick={() => handleRemove(p)}
                                style={{ padding: '0', border: 'none', background: 'none', cursor: 'pointer', display: 'flex' }}
                            >
                                <Trash2 size={12} />
                            </button>
                        </div>
                    ))
                )}
            </div>
        </div>
    )
}

export default IgnoreManager
