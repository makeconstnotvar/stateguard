# Security notes

StateGuard обрабатывает корпоративный source context и security/correctness findings. Разворачивайте
его только в утверждённой внутренней инфраструктуре.

- Не отправляйте `.stateguard` reports/ledger в публичные issue trackers.
- Не храните tokens в repository или `.env` внутри VCS.
- Запускайте scanners без egress и с read-only checkout.
- Проверяйте и фиксируйте digest analyzer images.
- Считайте repository content недоверенным input для parser и ИИ.
- Raw CPG и prompts храните минимальный срок.

Этот starter kit не является hardened appliance. Перед production deployment выполните внутренний
threat model, supply-chain review и penetration/operations review.
