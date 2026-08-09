---
status: accepted
---

# Transaction — это инвойс Plisio, у заказа их может быть несколько

`Transaction` была `OneToOneField` на заказ, и `update_or_create(order=order)` перезаписывал
единственную строку. Это неверно фактически, а не гипотетически.

Из документации Plisio: при смене криптовалюты покупателем **создаётся новый инвойс** с новым
`id`, а после его оплаты все связанные инвойсы переводятся в статус `cancelled duplicate`, чтобы
исключить двойную оплату. Наш `order_number` при этом не меняется — приходит новый `txn_id`,
и текущий код затирает предыдущий инвойс вместе с его `amount` и `invoice_commission`.
Комментарий в `status_map` (`"cancelled duplicate": PENDING  # A customer has switched to another
cryptocurrency`) фиксировал этот сценарий, но схема его не выдерживала.

Отдельно Plisio допускает несколько блокчейн-платежей по одному инвойсу: в callback есть
`pending_amount` (остаток к доплате) и `tx_urls` — массив ссылок на транзакции. Эти платежи
Plisio агрегирует сам, поэтому отдельной сущности под них не заводим — храним `tx_urls` как JSON.

Итого два уровня, ранее слитых в одну строку: **инвойс** (много на заказ) и **блокчейн-платёж**
(много на инвойс, приходит агрегатом).

## Решение

- `Transaction` становится FK на `Order`, уникальность по `txn_id`. Каждый callback обновляет
  свою строку, а не чужую. Добавляются `pending_amount` и `tx_urls`.
- Добавляется `PaymentCallbackLog`: сырой `jsonb` каждого входящего callback. Разбор инцидентов
  перестаёт зависеть от того, что мы догадались распарсить.

## Consequences

- Там, где код обращался к `order.transaction`, теперь нужен явный выбор актуального инвойса
  (последний, либо со статусом `completed`). Правится `PlisioCallbackView` и админка.
- Реальная комиссия Plisio за период становится считаемой — это было необходимо для статистики
  продаж и невозможно на старой схеме.

Источники: [Plisio FAQ — transaction statuses](https://plisio.net/faq/transaction-statuses-mass-payouts-and-notifications-letters),
[Plisio — create an invoice](https://plisio.net/documentation/endpoints/create-an-invoice).
