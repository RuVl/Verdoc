# План миграции данных (без потери текущих Passport/PassportFile/Order/Customer)

Общий чеклист для любого из 3 вариантов:

1. `make db-dump` (или `make db-dump DUMP=backups/pre-refactor.sql`) прямо перед миграцией на проде.
2. Прогнать миграцию сперва локально на копии прод-дампа: `make dev-infra` → `make db-restore DUMP=backups/pre-refactor.sql` → `make dev-migrate`.
3. Миграция в 2 этапа релиза:
   - **Этап A (add-only):** новые поля/таблицы добавляются как `null=True`/отдельная таблица, старые остаются рабочими. Деплой безопасен, откатываем просто предыдущим образом без миграций назад.
   - **Верификация:** ручные SQL-проверки (см. ниже) на проде после этапа A.
   - **Этап B (cleanup):** отдельным PR/релизом убираем старые поля/таблицы, когда новые уже отработали хотя бы один полный цикл заказа.
4. Ни одна миграция не должна ставить `NOT NULL` на поле, где могут быть существующие NULL/несопоставленные строки, без предварительного `RunPython`-backfill в этой же миграции.

---

## Вариант 1 (Atomic Link) — самый безопасный

```python
# passport/migrations/000X_passportfile_reserved_for_item.py
class Migration(migrations.Migration):
    dependencies = [("passport", "000N_previous"), ("order", "000M_previous")]
    operations = [
        migrations.AddField(
            model_name="passportfile",
            name="reserved_for_item",
            field=models.ForeignKey(
                "order.OrderItem", null=True, blank=True,
                on_delete=models.SET_NULL, related_name="reserved_files",
            ),
        ),
    ]
```

- **Потери данных: нет.** Поле nullable, существующие строки (`IN_STOCK`/`RESERVED`/`SOLD`) просто получают `NULL`.
- Опциональный backfill для уже проданных файлов (восстанавливаем историческую связь из `DownloadLink`, которая её и так хранит):

```python
def backfill_reserved_for_item(apps, schema_editor):
    DownloadLink = apps.get_model("order", "DownloadLink")
    for link in DownloadLink.objects.select_related("passport_file"):
        pf = link.passport_file
        pf.reserved_for_item_id = link.order_item_id
        pf.save(update_fields=["reserved_for_item_id"])
```

- Для файлов, которые в момент миграции `RESERVED` по "живым" заказам — сопоставить некому (в этом и была исходная проблема), поэтому они остаются `NULL` до следующего цикла reserve/sell. Не блокирует деплой.
- Этап B не обязателен — старое поведение (`status`) остаётся, `reserved_for_item` просто дополняет его.

---

## Вариант 2 (Fulfillment) — требует переноса состояния

```python
# order/migrations/000X_create_fulfillment.py
operations = [
    migrations.CreateModel(
        name="Fulfillment",
        fields=[
            ("id", models.BigAutoField(primary_key=True)),
            ("status", models.CharField(max_length=20, choices=[...])),
            ("fulfilled_at", models.DateTimeField(null=True, blank=True)),
            ("order_item", models.ForeignKey("order.OrderItem", on_delete=models.CASCADE)),
            ("stock_file", models.ForeignKey("passport.PassportFile", on_delete=models.SET_NULL, null=True)),
        ],
    ),
]
```

```python
def backfill_fulfillment(apps, schema_editor):
    PassportFile = apps.get_model("passport", "PassportFile")
    DownloadLink = apps.get_model("order", "DownloadLink")
    Fulfillment = apps.get_model("order", "Fulfillment")

    # SOLD: связь есть через DownloadLink - переносим точно
    for link in DownloadLink.objects.select_related("passport_file", "order_item"):
        Fulfillment.objects.create(
            order_item_id=link.order_item_id,
            stock_file_id=link.passport_file_id,
            status="DELIVERED",
            fulfilled_at=link.updated_at,
        )

    # RESERVED без DownloadLink: заказ ещё не оплачен - привязки файл-заказ нет
    # (это и есть исходная проблема из заметки). Создаём Fulfillment без order_item
    # или оставляем как задокументированное ограничение - см. ниже.
```

- **Известное ограничение:** на момент миграции могут быть "живые" `PENDING`-заказы с `RESERVED`-файлами, для которых нет `DownloadLink`, а значит нет способа восстановить, какой файл зарезервирован каким заказом (это ровно то, что чинит Вариант 1). Практический выход: **выполнять эту миграцию только когда в системе нет активных `PENDING`-заказов** (проверить `Order.objects.filter(status="PENDING").count() == 0` перед стартом, либо подождать `make expire`, который очистит их), тогда backfill нужен только для `SOLD`.
- `PassportFile.status → current_status`: переименование в 2 шага внутри Этапа A, чтобы не потерять данные при рестарте на середине деплоя:
  1. `AddField(current_status)` + `RunPython` копирует `status → current_status` для всех строк.
  2. Код переключается на `current_status`, старое поле `status` остаётся (read-only) до Этапа B.
  3. Этап B (следующий релиз): `RemoveField(status)`.
- Сверка перед Этапом B: `assert Fulfillment.objects.count() >= DownloadLink.objects.count()`.

---

## Вариант 3 (License) — самый рискованный, план на 2 релиза с окном отката

```python
def backfill_licenses(apps, schema_editor):
    Order = apps.get_model("order", "Order")
    OrderItem = apps.get_model("order", "OrderItem")
    DownloadLink = apps.get_model("order", "DownloadLink")
    License = apps.get_model("order", "License")
    AssetDownload = apps.get_model("order", "AssetDownload")

    for item in OrderItem.objects.select_related("order", "passport"):
        status = "ACTIVE" if item.order.status in ("PAID", "OVERPAID") else "PENDING"
        for _ in range(item.quantity):
            License.objects.create(order=item.order, product_id=item.passport_id, status=status)

    # Для уже выданных файлов - восстановить ASSET_DOWNLOAD 1:1 из DownloadLink,
    # сопоставляя License по order_item (нужен promo-поле order_item_id на License
    # временно, на время миграции, потом удалить).
```

- **Риск потери контекста:** `License` в целевой модели не хранит `order_item_id` (только `order_id` + `product_id`), а значит при нескольких `OrderItem` одного `Passport` в одном заказе теряется однозначное сопоставление старых `DownloadLink` → новым `License`. Обход: держать `order_item_id` как временное служебное поле на `License` только на время миграции (`db_column`, не в основной модели), удалить в Этапе B после сверки.
- **Обязательная сверка перед Этапом B** (удаление `OrderItem`/`DownloadLink` как основных таблиц):
  ```
  assert License.objects.count() == sum(OrderItem.objects.values_list("quantity", flat=True))
  assert AssetDownload.objects.count() == DownloadLink.objects.count()
  ```
- **Держать старые таблицы `OrderItem`/`DownloadLink` минимум один релизный цикл** как read-only fallback — если после Этапа A на проде всплывёт расхождение, откат на них не требует новой миграции назад, только откат кода.
- Самый долгий Этап A из трёх вариантов, т.к. требует одновременно писать в старую и новую схему (dual-write) на переходный период, если нельзя остановить приём заказов на время миграции.

---

## Что не меняется ни в одном варианте

`Country`, `Passport` (кроме, возможно, добавления `current_status`-подобных полей в Варианте 2), `Transaction`, `Unsubscribe`, `Broadcast` — их миграция не касается. Клиентские данные (`Order.user_email`, история `Transaction`) не трогаются ни в одном из вариантов — риск только на стороне `PassportFile ↔ OrderItem` связи, которая и была изначальной проблемой.
