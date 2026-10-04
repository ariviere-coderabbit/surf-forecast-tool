import { FormEvent, useState } from 'react'

interface Props {
  onSearch: (query: string) => void
  loading: boolean
}

export default function SearchBar({ onSearch, loading }: Props) {
  const [value, setValue] = useState('')

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const q = value.trim()
    if (q) onSearch(q)
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
      <input
        type="text"
        value={value}
        onChange={e => setValue(e.target.value)}
        placeholder="e.g. Jacó, Costa Rica"
        aria-label="Location search"
        disabled={loading}
        style={{ flex: 1, padding: '0.5rem', fontSize: '1rem', borderRadius: 4, border: '1px solid #ccc' }}
      />
      <button
        type="submit"
        disabled={loading || !value.trim()}
        style={{ padding: '0.5rem 1rem', fontSize: '1rem', borderRadius: 4, cursor: 'pointer' }}
      >
        {loading ? 'Searching…' : 'Search'}
      </button>
    </form>
  )
}
