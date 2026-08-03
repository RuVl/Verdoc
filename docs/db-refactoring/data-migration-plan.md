# План перелива данных

Целевая схема — [`target-schema.md`](./target-schema.md). Обоснование способа —
[ADR-0003](../adr/0003-new-apps-instead-of-rename.md) и
[ADR-0007](../adr/0007-cutover-with-fungible-file-assignment.md).

Старые приложения `passport` и `order` остаются в кодовой базе read-only до сверки на проде
и дропаются следующим релизом. Ничего не удаляется в том же окне, в котором переливается.

## Ключевая идея

Единицы одного товара взаимозаменяемы. Значит связь «файл ↔ заказ», которой в старой схеме
не существовало до оплаты, при переливе **восстанавливается назначением, а не поиском**:
любой `RESERVED`-файл товара подходит любой позиции `PENDING`-заказа того же товара.

Порядок перелива важен — сначала точные связи, потом раздача остатка:

1. `SOLD` + есть `DownloadLink` → точная связь, переносим 1:1 вместе с `uuid`.
2. `SOLD` без `DownloadLink` → раздаём позициям, у которых не хватает аллокаций
   (это и есть починка `HasSoldErrorFilter`).
3. `RESERVED` → раздаём позициям `PENDING`-заказов того же товара.
4. `IN_STOCK` → аллокаций нет, единица свободна.

## Порядок миграций

```
catalog  0001_initial                Country, Product, StockItem
customer 0001_initial                Customer
sales    0001_initial                Order, OrderItem, Allocation, Transaction, PaymentCallbackLog
mailing  0001_initial                Broadcast, BroadcastDelivery
sales    0002_transfer_from_legacy   RunPython - весь перелив, одной транзакцией
```

Перелив — одна миграция, а не пять: он обязан быть атомарным. Половина перелитых данных хуже,
чем ноль.

## Скелет перелива

```python
def transfer(apps, schema_editor):
    # legacy
    OldCountry = apps.get_model("passport", "Country")
    OldPassport = apps.get_model("passport", "Passport")
    OldFile = apps.get_model("passport", "PassportFile")
    OldOrder = apps.get_model("order", "Order")
    OldItem = apps.get_model("order", "OrderItem")
    OldLink = apps.get_model("order", "DownloadLink")
    OldTxn = apps.get_model("order", "Transaction")

    # target
    Country = apps.get_model("catalog", "Country")
    Product = apps.get_model("catalog", "Product")
    StockItem = apps.get_model("catalog", "StockItem")
    Customer = apps.get_model("customer", "Customer")
    Order = apps.get_model("sales", "Order")
    OrderItem = apps.get_model("sales", "OrderItem")
    Allocation = apps.get_model("sales", "Allocation")
    Transaction = apps.get_model("sales", "Transaction")
```

### 1. Каталог

`Country` и `Product` переносятся один-в-один, вместе со **всеми** языковыми колонками
`modeltranslation` (`name_en`, `name_ru`) — их нельзя пропустить, иначе витрина потеряет переводы.
`Passport.quantity` не переносится: колонки в целевой схеме нет.

`PassportFile.file_path` → `StockItem.file`. Физические файлы на диске не двигаем — меняется
только имя колонки, значения путей те же.

### 2. Покупатели

```python
emails = OldOrder.objects.values_list("user_email", flat=True).distinct()
Customer.objects.bulk_create([
    Customer(email=e, access_token=uuid4(), access_token_expires_at=now, is_subscribed=True)
    for e in emails
])
```

Если ветка `feature/add-broadcasting` уже была на проде — `Unsubscribe` схлопывается сюда:
`is_subscribed=False`, `unsubscribed_at` из `Unsubscribe.created_at`. Терять отписки нельзя,
это репутация домена у почтовых провайдеров.

### 3. Заказы и позиции

`Order` переносится с подстановкой `customer_id` вместо `user_email`.

`paid_at` для уже оплаченных заказов восстанавливаем из `Transaction.updated_at` — это
единственное приближение, которое у нас есть. Помечаем допущение в логе миграции: цифры
статистики за период до рефакторинга приблизительны.

`OrderItem` получает снапшоты. Здесь честное ограничение: **исторической цены нет**, есть только
текущая. Заполняем из живого каталога:

```python
product_name = old_item.passport.name        # текущее имя, не историческое
unit_price = old_item.passport.price         # текущая цена, не уплаченная
unit_price_usd = convert(unit_price)         # по сегодняшнему курсу
```

Инвариант `sum(unit_price_usd × qty) == order.total_price` для **старых** заказов не выполнится.
Это не ошибка перелива, а следствие того, что данных не существует. Проверку инварианта включаем
только для заказов, созданных после миграции (`created_at >= CUTOVER_AT`).

### 4. Аллокации

```python
def transfer_allocations():
    # 1. SOLD с точной связью
    for link in OldLink.objects.select_related("passport_file", "order_item"):
        Allocation.objects.create(
            order_item_id=link.order_item_id,
            stock_item_id=link.passport_file_id,
            state="DELIVERED",
            reserved_at=link.order_item.order.created_at,
            delivered_at=link.updated_at,
            token=link.uuid,                    # старые письма продолжают работать
            token_expires_at=link.updated_at + DOWNLOAD_TTL,
        )

    # 2-3. остальное - раздача взаимозаменяемых единиц по товарам
    for product_id in Product.objects.values_list("id", flat=True):
        assign_fungible(product_id, "SOLD", "DELIVERED")     # позициям оплаченных заказов
        assign_fungible(product_id, "RESERVED", "RESERVED")  # позициям PENDING-заказов
```

`assign_fungible` берёт незанятые единицы товара в нужном статусе и раздаёт их позициям того же
товара, которым не хватает аллокаций, по возрастанию `order_id` (детерминированно — чтобы прогон
на копии дампа и прогон на проде дали одно и то же).

Единицам, которым не хватило позиций, аллокация не создаётся — они станут свободными. Это
корректно: лишний `RESERVED`-файл без живого заказа и есть протёкший резерв.

### 5. Платежи

`Transaction` переносится один-в-один, `order` из `OneToOne` становится FK. `txn_id` был
`null=True` — строки без него получают синтетический `legacy-{order_id}`, иначе уникальный
индекс не встанет. `pending_amount` и `tx_urls` остаются пустыми: в старых данных их нет.

`PaymentCallbackLog` начинает заполняться с момента выкатки, историю восстановить неоткуда.

## Сверки после перелива

Гонять до снятия заглушки. Любое расхождение — откат на дамп.

```sql
-- каталог перенесён целиком
SELECT (SELECT count(*) FROM passport_country)      = (SELECT count(*) FROM catalog_country)
   AND (SELECT count(*) FROM passport_passport)     = (SELECT count(*) FROM catalog_product)
   AND (SELECT count(*) FROM passport_passportfile) = (SELECT count(*) FROM catalog_stockitem)
   AND (SELECT count(*) FROM order_order)           = (SELECT count(*) FROM sales_order)
   AND (SELECT count(*) FROM order_orderitem)       = (SELECT count(*) FROM sales_orderitem)
   AS catalog_ok;

-- ни одна ранее выданная ссылка не потеряна
SELECT count(*) AS lost_links
FROM order_downloadlink dl
LEFT JOIN sales_allocation a ON a.token = dl.uuid
WHERE a.id IS NULL;                                  -- ожидается 0

-- инвариант "один файл - один покупатель" не нарушен
SELECT stock_item_id, count(*)
FROM sales_allocation
WHERE state <> 'RELEASED'
GROUP BY stock_item_id HAVING count(*) > 1;          -- ожидается пусто

-- у каждой выданной аллокации есть токен
SELECT count(*) AS delivered_without_token
FROM sales_allocation
WHERE state = 'DELIVERED' AND token IS NULL;         -- ожидается 0

-- оплаченным заказам хватает выданных единиц
SELECT oi.id, oi.quantity, count(a.id) AS delivered
FROM sales_orderitem oi
JOIN sales_order o ON o.id = oi.order_id
LEFT JOIN sales_allocation a ON a.order_item_id = oi.id AND a.state = 'DELIVERED'
WHERE o.status IN ('PAID', 'OVERPAID')
GROUP BY oi.id, oi.quantity HAVING count(a.id) < oi.quantity;   -- ожидается пусто

-- остаток сходится со старым счётчиком (до 3-4 строк расхождения - это протёкшие резервы)
SELECT p.id, pp.quantity AS old_quantity, count(s.id) AS new_available
FROM catalog_product p
JOIN passport_passport pp ON pp.id = p.id
LEFT JOIN catalog_stockitem s ON s.product_id = p.id
 AND NOT EXISTS (SELECT 1 FROM sales_allocation a
                 WHERE a.stock_item_id = s.id AND a.state <> 'RELEASED')
GROUP BY p.id, pp.quantity
HAVING pp.quantity <> count(s.id);

-- покупатели не потеряны, отписки сохранены
SELECT (SELECT count(DISTINCT user_email) FROM order_order) = (SELECT count(*) FROM customer_customer)
   AND (SELECT count(*) FROM mailing_unsubscribe)
     = (SELECT count(*) FROM customer_customer WHERE is_subscribed = false)
   AS customers_ok;
```

Последняя сверка по остаткам — единственная, где расхождение допустимо и ожидаемо: старый
счётчик и был ненадёжен ([ADR-0002](../adr/0002-derived-stock-count.md)). Расхождение надо
глазами прочитать, а не автоматически принять.

## Что не переносится и почему

| Данные | Судьба |
|---|---|
| `Passport.quantity` | колонки нет, остаток выводится запросом |
| `OrderItem.is_reserved` | состояние переехало в `Allocation.state` |
| `PassportFile.status` | то же |
| историческая цена позиции | не существовала - заполняется текущей, инвариант включается с даты выкатки |
| история инвойсов до выкатки | затиралась `update_or_create`, восстановить неоткуда |
