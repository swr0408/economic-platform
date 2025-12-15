import { Button, Space } from 'antd'

export type PeriodValue = number | 'all' | 'default'

interface PeriodOption {
  label: string
  value: PeriodValue
}

interface PeriodSelectorProps {
  onPeriodChange: (period: PeriodValue) => void
  selectedPeriod?: PeriodValue
  options?: PeriodOption[]
  size?: 'small' | 'middle' | 'large'
  showReset?: boolean
}

const defaultOptions: PeriodOption[] = [
  { label: '1Y', value: 1 },
  { label: '2Y', value: 2 },
  { label: '3Y', value: 3 },
  { label: '5Y', value: 5 },
  { label: '10Y', value: 10 },
  { label: 'All', value: 'all' },
]

export default function PeriodSelector({
  onPeriodChange,
  selectedPeriod,
  options = defaultOptions,
  size = 'small',
  showReset = true,
}: PeriodSelectorProps) {
  const resetOption: PeriodOption = { label: 'Reset', value: 'default' }
  const allOptions: PeriodOption[] = showReset ? [...options, resetOption] : options

  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
      <Space size={8}>
        {allOptions.map(({ label, value }) => (
          <Button
            key={label}
            size={size}
            type={selectedPeriod === value ? 'primary' : 'default'}
            onClick={() => onPeriodChange(value)}
          >
            {label}
          </Button>
        ))}
      </Space>
    </div>
  )
}
