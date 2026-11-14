import { Button } from '../common/Ui'

export function ModalCancelar({
  open,
  pending,
  onClose,
  onConfirm,
}: {
  open: boolean
  pending: boolean
  onClose: () => void
  onConfirm: () => void
}) {
  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-header/60 p-5"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="cancel-title"
        className="w-full max-w-md rounded-lg bg-card p-7"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="cancel-title" className="text-xl font-extrabold">
          Cancelar este leilão?
        </h2>
        <p className="my-4 text-sm text-muted-foreground">
          Esta ação não pode ser desfeita.
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>
            Voltar
          </Button>
          <Button variant="danger" disabled={pending} onClick={onConfirm}>
            Confirmar cancelamento
          </Button>
        </div>
      </div>
    </div>
  )
}
