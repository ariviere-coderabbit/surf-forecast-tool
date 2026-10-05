import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import SearchBar from '../components/SearchBar'

describe('SearchBar', () => {
  it('renders input and button', () => {
    render(<SearchBar onSearch={vi.fn()} loading={false} />)
    expect(screen.getByRole('textbox')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /search/i })).toBeInTheDocument()
  })

  it('calls onSearch with trimmed value on submit', async () => {
    const onSearch = vi.fn()
    render(<SearchBar onSearch={onSearch} loading={false} />)
    await userEvent.type(screen.getByRole('textbox'), '  Jacó  ')
    await userEvent.click(screen.getByRole('button', { name: /search/i }))
    expect(onSearch).toHaveBeenCalledWith('Jacó')
  })

  it('does not call onSearch for blank input', async () => {
    const onSearch = vi.fn()
    render(<SearchBar onSearch={onSearch} loading={false} />)
    await userEvent.click(screen.getByRole('button', { name: /search/i }))
    expect(onSearch).not.toHaveBeenCalled()
  })

  it('disables input and shows loading label while loading', () => {
    render(<SearchBar onSearch={vi.fn()} loading={true} />)
    expect(screen.getByRole('textbox')).toBeDisabled()
    expect(screen.getByRole('button', { name: /searching/i })).toBeDisabled()
  })
})
