# Рефакторинг схемы БД

Причина: связь «файл ↔ заказ» существовала только после оплаты, в `DownloadLink`. До оплаты
`RESERVED`-файл был ничей, и его мог забрать другой заказ. Отсюда инцидент
[`2026-07-28-order-652`](../incidents/2026-07-28-order-652-stuck-paid-order.md), фильтр
«ошибка при продаже» в админке и костыль, вслепую цеплявший чужие проданные файлы.

Заодно решается вторая задача: модели перестают называться предметно (`Passport`,
`PassportFile`), чтобы линейку товаров можно было расширить или сменить тематику проекта
без переписывания схемы.

## Документы

| Файл | О чём |
|---|---|
| [`current-schema.dbml`](./current-schema.dbml) | как было до рефакторинга (таблиц больше нет, см. `r5.md`) |
| [`target-schema.md`](./target-schema.md) | целевая схема, инварианты, потоки |
| [`data-migration-plan.md`](./data-migration-plan.md) | перелив данных и SQL-сверки |
| [`r1.md`](./r1.md) | релиз 1 — схема, перелив, бэкенд |
| [`r2.md`](./r2.md) | релиз 2 — страница покупок |
| [`r3.md`](./r3.md) | релиз 3 — язык писем и рассылки |
| [`r4.md`](./r4.md) | релиз 4 — статистика |
| [`r5.md`](./r5.md) | релиз 5 — дроп legacy и чистка техдолга |

Решения и отвергнутые альтернативы — в [`docs/adr/`](../adr/).
Термины домена — в [`CONTEXT.md`](../../CONTEXT.md).

## Коротко, что меняется

```
Passport      -> Product        (catalog)
PassportFile  -> StockItem      (catalog)
Country          без изменений  (catalog)
Order         -> Order          (sales)
OrderItem     -> OrderItem      (sales) + снапшот имени и цены
DownloadLink  -> исчезает, поля переезжают на Allocation
Unsubscribe   -> исчезает, становится Customer.is_subscribed
Transaction   -> FK вместо OneToOne + PaymentCallbackLog
              +  Allocation     (sales)    состояние выдачи
              +  Customer       (customer) покупатель и доступ
              +  BroadcastDelivery (mailing)
```

Три ранние заметки с вариантами схемы (`option-1-atomic-link`, `option-2-auditable-fulfillment`,
`option-3-license-based`) удалены — принятые решения и причины отказа от альтернатив записаны
в ADR. Сами заметки остались в истории git.
