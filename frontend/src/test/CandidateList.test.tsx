import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import CandidateList from '../components/CandidateList'
import type { GeoCandidate } from '../api/types'

const makeCandidate = (id: number, name: string, country: string): GeoCandidate => ({
  id,
  name,
  country,
  country_code: country.slice(0, 2).toUpperCase(),
  latitude: 9.6 + id * 0.1,
  longitude: -84.6,
  timezone: 'America/Costa_Rica',
})

describe('CandidateList', () => {
  it('renders nothing when candidates is empty', () => {
    const { container } = render(<CandidateList candidates={[]} onSelect={vi.fn()} />)
    expect(container.firstChild).toBeNull()
  })

  it('shows all candidates as buttons', () => {
    const candidates = [
      makeCandidate(1, 'Jacó', 'Costa Rica'),
      makeCandidate(2, 'Jacó', 'Mexico'),
    ]
    render(<CandidateList candidates={candidates} onSelect={vi.fn()} />)
    expect(screen.getAllByRole('button')).toHaveLength(2)
    expect(screen.getByText(/Costa Rica/)).toBeInTheDocument()
    expect(screen.getByText(/Mexico/)).toBeInTheDocument()
  })

  it('calls onSelect with the clicked candidate', async () => {
    const onSelect = vi.fn()
    const candidate = makeCandidate(1, 'Jacó', 'Costa Rica')
    render(<CandidateList candidates={[candidate]} onSelect={onSelect} />)
    await userEvent.click(screen.getByRole('button'))
    expect(onSelect).toHaveBeenCalledWith(candidate)
  })
})
