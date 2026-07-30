# План выкатки

Три релиза. Схема обязана быть первой: статистика зависит от `paid_at` и снапшотов, рассылки —
от `Customer`, страница покупок — от `Allocation.token`.

---

## R1 — схема, перелив, бэкенд

UX покупателя не меняется вообще: письмо прежнего вида, фронт не трогаем. Смысл в том, чтобы
ошибки миграции ловились без шума от нового интерфейса.

### Backend

- Приложения `catalog`, `customer`, `sales`, `mailing` по [`target-schema.md`](./target-schema.md).
- Логика состояний переезжает на `Allocation`: `reserve` / `deliver` / `release` вместо
  `reserve` / `sell` / `return2stock` на `Passport`.
- `OrderSerializer` пишет снапшоты `product_name`, `unit_price`, `unit_price_usd`.
- `PlisioCallbackView`: `update_or_create` по `txn_id`, запись в `PaymentCallbackLog`,
  установка `paid_at` один раз.
- `expire_transactions` переводит `RESERVED` → `RELEASED` вместо возврата в сток.
- Старый роут `/api/order/file/<email>/<uuid>/` остаётся рабочим — ищет `Allocation` по `token`.
- Письмо пока прежнее: N ссылок на файлы, собранных из `Allocation.token`.
- Удаляются: `passport/signals.py`, `resync_quantity`, `HasSoldErrorFilter`,
  `get_order_item_links()`.
- `admin.py` переписывается под новые модели, остатки — через `annotate` + `Exists`.

### Frontend

Не трогаем. Проверить только, что ответ `/api/countries/` и `/api/exchange-rates/` не изменился
по форме — иначе витрина упадёт.

### Выкатка

Ночью, окно простоя. Порядок ([ADR-0007](../adr/0007-cutover-with-fungible-file-assignment.md)):

1. Проверить, что Plisio ретраит callback при 5xx. Без этого окно рискует потерять оплату.
2. Прогнать всё на копии прод-дампа: `make db-dump` → `make dev-infra` → `make db-restore` →
   `make dev-migrate` → сверки из [`data-migration-plan.md`](./data-migration-plan.md).
3. `make db-dump DUMP=backups/pre-refactor.sql` на проде.
4. Заглушка в nginx.
5. `make migrate`.
6. Сверки. Любое расхождение, кроме остатков, — стоп и откат.
7. Снять заглушку.
8. Дымовой тест: заказ на живом товаре, оплата тестовым инвойсом, письмо, скачивание,
   старая ссылка из письма недельной давности.

Откат: восстановление `backups/pre-refactor.sql` + предыдущий образ.

### Следующий релиз после R1

Дроп `passport` и `order` — отдельным PR, после того как схема отработала хотя бы один полный
цикл заказа на проде.

---

## R2 — страница покупок

- Модель уже готова, добавляется только выдача и ротация токенов.
- `POST /api/send-links/` переименовывается по смыслу: ротирует `Customer.access_token`,
  сбрасывает TTL, шлёт одну ссылку.
- Оплата шлёт то же письмо, но **не** ротирует токены
  ([ADR-0004](../adr/0004-customer-and-purchases-page.md)).
- Письмо: одна ссылка, предупреждение про TTL 24ч и про то, что ссылка открывает все покупки.
- Фронт: роут `/purchases/:token`, компонент в стилистике сайта. У каждого товара — кнопка
  скачивания, кнопка копирования ссылки, кнопка обновления ссылки. Просроченный токен →
  скачивание заблокировано с подсказкой. Отдельная кнопка «обновить все ссылки».
- Дизайн-макеты: десктоп и `_mob` по правилам из `CLAUDE.md`.

---

## R3 — рассылки и статистика

### Рассылки

Мёрж `feature/add-broadcasting` на новую схему:

- `Unsubscribe` выкидывается, отписка идёт через `Customer.is_subscribed`.
- `get_broadcast_recipients()` — queryset по `Customer` с оплаченными заказами и `is_subscribed`.
- Добавляется `BroadcastDelivery`: строка на пару (broadcast, customer). Даёт повтор только
  упавшим и идемпотентность, если крон упал посередине.
- Счётчики на `Broadcast` становятся производными от `BroadcastDelivery`.

### Статистика

Предагрегатов нет — при текущем объёме `TruncDay` + `Sum` по `OrderItem` считается мгновенно.
Материализованные таблицы имеет смысл заводить где-то от сотен тысяч позиций, до этого они
только источник рассинхрона.

Данные, которые теперь для этого есть:

| Метрика | Источник |
|---|---|
| выручка по дням | `Order.paid_at` + `OrderItem.unit_price_usd` |
| продажи по товарам и странам | `OrderItem.product_name` / `product_id` → `country` |
| конверсия | `Order.status` по когортам `created_at` |
| реальная комиссия Plisio | `Transaction.commission` по всем инвойсам заказа |
| недоплаты | `Transaction.pending_amount` |
| повторные покупатели, LTV | `Order.customer_id` |
| скорость оборачиваемости стока | `Allocation.reserved_at` → `delivered_at` |

Рендер — отдельная страница в админке с вендоренным JS-графиком. Решение обратимое, ADR не нужен.
