import { money } from '../../utils/auctionRules'
import type { PendingBidState } from '../../utils/interfaces/bidInterface'
import { Link } from '../common/Router'
import { Button, Icon } from '../common/Ui'

export function FormularioLance({
  loggedIn,
  disabled,
  pending,
  minNextBidCents,
  amount,
  onAmountChange,
  onQuickBid,
  onCustomBid,
  pendingBidState,
  onRetryPendingBid,
}: {
  loggedIn: boolean
  disabled: boolean
  pending: boolean
  minNextBidCents: number
  amount: string
  onAmountChange: (value: string) => void
  onQuickBid: () => void
  onCustomBid: () => void
  pendingBidState: PendingBidState | null
  onRetryPendingBid: () => void
}) {
  if (!loggedIn) {
    return (
      <Link to="/login" className="app-button button-primary w-full">
        Entrar para participar
        <Icon name="arrow" />
      </Link>
    )
  }

  return (
    <>
      <Button className="w-full" disabled={disabled} onClick={onQuickBid}>
        <Icon name="hammer" />
        {pending ? 'Enviando…' : `Dar lance de ${money(minNextBidCents)}`}
      </Button>
      <div className="mt-5">
        <label className="field-label" htmlFor="custom-bid">
          Seu lance (R$)
        </label>
        <div className="flex gap-2">
          <input
            id="custom-bid"
            className="field min-w-0"
            inputMode="decimal"
            value={amount}
            onChange={(e) => onAmountChange(e.target.value)}
            placeholder="0,00"
          />
          <Button
            variant="outline"
            disabled={disabled || !amount}
            onClick={onCustomBid}
            aria-label="Enviar lance personalizado"
          >
            <Icon name="arrow" />
          </Button>
        </div>
      </div>
      {pendingBidState && (
        <Button
          variant="outline"
          className="mt-3 w-full"
          disabled={disabled}
          onClick={onRetryPendingBid}
        >
          Reenviar lance pendente ({money(pendingBidState.amount_cents)})
        </Button>
      )}
    </>
  )
}
